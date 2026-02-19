from __future__ import annotations

import logging
from typing import Any, Optional

import grpc
from common.rpc_defaults import INTERNAL_UNARY_RPC_TIMEOUT_MS

try:
    # Preferred when PYTHONPATH includes ./generated
    import taskqueue_internal_pb2 as internal_pb2
    import taskqueue_internal_pb2_grpc as internal_pb2_grpc
    import taskqueue_public_pb2 as pb2
    import taskqueue_public_pb2_grpc as pb2_grpc
except ModuleNotFoundError:  # pragma: no cover
    # Fallback if generated modules are imported as a package
    from generated import taskqueue_internal_pb2 as internal_pb2
    from generated import taskqueue_internal_pb2_grpc as internal_pb2_grpc
    from generated import taskqueue_public_pb2 as pb2
    from generated import taskqueue_public_pb2_grpc as pb2_grpc

try:
    from common.time_utils import now_ms
except Exception:  # pragma: no cover
    import time

    def now_ms() -> int:
        return int(time.time() * 1000)


_TERMINAL_STATUSES = {
    pb2.DONE,
    pb2.FAILED,
    pb2.CANCELED,
}

_CANCEL_RESULT_SUMMARY_DEFAULT = "canceled_by_user"


class GatewayServicer(pb2_grpc.TaskQueuePublicServiceServicer):
    """Gateway TaskQueuePublicService v1 orchestration implementation."""

    def __init__(
        self,
        config: Optional[object] = None,
        logger: Optional[logging.Logger] = None,
        job_client: Optional[Any] = None,
        queue_client: Optional[Any] = None,
        result_client: Optional[Any] = None,
    ) -> None:
        self._config = config
        self._logger = logger or logging.getLogger("gateway.servicer")
        self._job_channel = None
        self._queue_channel = None
        self._result_channel = None
        self._job_client = job_client
        self._queue_client = queue_client
        self._result_client = result_client
        timeout_ms = int(getattr(config, "internal_rpc_timeout_ms", INTERNAL_UNARY_RPC_TIMEOUT_MS))
        self._downstream_rpc_timeout_s = max(timeout_ms, 1) / 1000.0
        self._init_clients()

    def _init_clients(self) -> None:
        if self._job_client is None:
            job_addr = str(getattr(self._config, "job_addr", "")).strip()
            if job_addr:
                self._job_channel = grpc.insecure_channel(job_addr)
                self._job_client = internal_pb2_grpc.JobInternalServiceStub(self._job_channel)

        if self._queue_client is None:
            queue_addr = str(getattr(self._config, "queue_addr", "")).strip()
            if queue_addr:
                self._queue_channel = grpc.insecure_channel(queue_addr)
                self._queue_client = internal_pb2_grpc.QueueInternalServiceStub(self._queue_channel)

        if self._result_client is None:
            result_addr = str(getattr(self._config, "result_addr", "")).strip()
            if result_addr:
                self._result_channel = grpc.insecure_channel(result_addr)
                self._result_client = internal_pb2_grpc.ResultInternalServiceStub(self._result_channel)

    def _set_error(
        self,
        context: grpc.ServicerContext,
        code: grpc.StatusCode,
        detail: str,
    ) -> None:
        context.set_code(code)
        context.set_details(detail)

    def _map_downstream_error(
        self,
        context: grpc.ServicerContext,
        *,
        operation: str,
        exc: grpc.RpcError,
        job_id: str = "",
    ) -> None:
        code = exc.code()
        detail = exc.details() or ""

        if code in {
            grpc.StatusCode.INVALID_ARGUMENT,
            grpc.StatusCode.NOT_FOUND,
            grpc.StatusCode.FAILED_PRECONDITION,
        }:
            mapped = code
        elif code in {
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.RESOURCE_EXHAUSTED,
        }:
            mapped = grpc.StatusCode.UNAVAILABLE
        else:
            mapped = grpc.StatusCode.INTERNAL

        msg = f"{operation} failed: {code.name}"
        if detail:
            msg = f"{msg} ({detail})"

        self._logger.warning(
            "gateway.downstream_error",
            extra={
                "method": operation,
                "job_id": job_id,
                "grpc_code": mapped.name,
                "downstream_code": code.name,
                "error_detail": detail,
            },
        )
        self._set_error(context, mapped, msg)

    def _require_upstreams(
        self,
        context: grpc.ServicerContext,
        *,
        need_job: bool = False,
        need_queue: bool = False,
        need_result: bool = False,
    ) -> bool:
        if need_job and self._job_client is None:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, "job service upstream not configured")
            return False
        if need_queue and self._queue_client is None:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, "queue service upstream not configured")
            return False
        if need_result and self._result_client is None:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, "result service upstream not configured")
            return False
        return True

    def _fetch_record(
        self,
        job_id: str,
        context: grpc.ServicerContext,
        *,
        operation: str,
    ) -> Optional[internal_pb2.GetJobRecordResponse]:
        try:
            return self._job_client.GetJobRecord(  # type: ignore[union-attr]
                internal_pb2.GetJobRecordRequest(job_id=job_id),
                timeout=self._downstream_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._map_downstream_error(context, operation=operation, exc=exc, job_id=job_id)
            return None

    def _store_cancel_result(
        self,
        job_id: str,
        reason: str,
        context: grpc.ServicerContext,
    ) -> bool:
        summary = reason.strip() or _CANCEL_RESULT_SUMMARY_DEFAULT
        try:
            resp = self._result_client.StoreResult(  # type: ignore[union-attr]
                internal_pb2.StoreResultRequest(
                    job_id=job_id,
                    terminal_status=pb2.CANCELED,
                    runtime_ms=0,
                    output_summary=summary,
                    output_bytes=b"",
                    checksum="",
                ),
                timeout=self._downstream_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._map_downstream_error(context, operation="Result.StoreResult", exc=exc, job_id=job_id)
            return False

        if resp.current_terminal_status not in _TERMINAL_STATUSES:
            self._set_error(context, grpc.StatusCode.INTERNAL, "Result.StoreResult returned non-terminal status")
            return False
        return True

    def _set_cancel_requested(
        self,
        job_id: str,
        reason: str,
        context: grpc.ServicerContext,
    ) -> Optional[internal_pb2.SetCancelRequestedResponse]:
        try:
            return self._job_client.SetCancelRequested(  # type: ignore[union-attr]
                internal_pb2.SetCancelRequestedRequest(
                    job_id=job_id,
                    cancel_requested=True,
                    reason=reason,
                ),
                timeout=self._downstream_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._map_downstream_error(context, operation="Job.SetCancelRequested", exc=exc, job_id=job_id)
            return None

    def _attempt_submit_compensation(self, job_id: str) -> None:
        if self._job_client is None:
            return
        try:
            resp = self._job_client.DeleteJobIfStatus(  # type: ignore[union-attr]
                internal_pb2.DeleteJobIfStatusRequest(
                    job_id=job_id,
                    expected_status=pb2.QUEUED,
                ),
                timeout=self._downstream_rpc_timeout_s,
            )
            if not resp.deleted:
                self._logger.error(
                    "gateway.submit.compensation_not_deleted",
                    extra={"job_id": job_id, "current_status": int(resp.current_status)},
                )
        except grpc.RpcError as exc:
            self._logger.error(
                "gateway.submit.compensation_failed",
                extra={"job_id": job_id, "downstream_code": exc.code().name},
            )

    def SubmitJob(
        self,
        request: pb2.SubmitJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.SubmitJobResponse:
        if not self._require_upstreams(context, need_job=True, need_queue=True):
            return pb2.SubmitJobResponse()

        if not request.spec.job_type.strip():
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "spec.job_type must be non-empty")
            return pb2.SubmitJobResponse()

        try:
            create_resp = self._job_client.CreateJob(  # type: ignore[union-attr]
                internal_pb2.CreateJobRequest(
                    spec=request.spec,
                    client_request_id=request.client_request_id,
                ),
                timeout=self._downstream_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._map_downstream_error(context, operation="Job.CreateJob", exc=exc)
            return pb2.SubmitJobResponse()

        job_id = create_resp.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INTERNAL, "Job.CreateJob returned empty job_id")
            return pb2.SubmitJobResponse()

        initial_status = int(create_resp.status)
        if initial_status == pb2.QUEUED:
            try:
                enqueue_resp = self._queue_client.EnqueueJob(  # type: ignore[union-attr]
                    internal_pb2.EnqueueJobRequest(
                        job_id=job_id,
                        enqueued_at_ms=now_ms(),
                    ),
                    timeout=self._downstream_rpc_timeout_s,
                )
            except grpc.RpcError:
                self._attempt_submit_compensation(job_id)
                self._set_error(context, grpc.StatusCode.UNAVAILABLE, "submit enqueue failed")
                return pb2.SubmitJobResponse()

            if not enqueue_resp.accepted:
                self._attempt_submit_compensation(job_id)
                self._set_error(context, grpc.StatusCode.UNAVAILABLE, "submit enqueue rejected")
                return pb2.SubmitJobResponse()

        return pb2.SubmitJobResponse(
            job_id=job_id,
            initial_status=initial_status,
            accepted_at_ms=now_ms(),
        )

    def GetJobStatus(
        self,
        request: pb2.GetJobStatusRequest,
        context: grpc.ServicerContext,
    ) -> pb2.GetJobStatusResponse:
        job_id = request.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.GetJobStatusResponse(job_id="")

        if not self._require_upstreams(context, need_job=True):
            return pb2.GetJobStatusResponse(job_id=job_id)

        rec = self._fetch_record(job_id, context, operation="Job.GetJobRecord")
        if rec is None:
            return pb2.GetJobStatusResponse(job_id=job_id)

        return pb2.GetJobStatusResponse(
            job_id=job_id,
            status=rec.summary.status,
            cancel_requested=rec.summary.cancel_requested,
            created_at_ms=rec.summary.created_at_ms,
            started_at_ms=rec.summary.started_at_ms,
            finished_at_ms=rec.summary.finished_at_ms,
            failure_reason=rec.failure_reason,
        )

    def GetJobResult(
        self,
        request: pb2.GetJobResultRequest,
        context: grpc.ServicerContext,
    ) -> pb2.GetJobResultResponse:
        job_id = request.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.GetJobResultResponse(job_id="")

        if not self._require_upstreams(context, need_job=True, need_result=True):
            return pb2.GetJobResultResponse(job_id=job_id)

        rec = self._fetch_record(job_id, context, operation="Job.GetJobRecord")
        if rec is None:
            return pb2.GetJobResultResponse(job_id=job_id)

        if rec.summary.status not in _TERMINAL_STATUSES:
            return pb2.GetJobResultResponse(
                job_id=job_id,
                result_ready=False,
                terminal_status=pb2.JOB_STATUS_UNSPECIFIED,
            )

        try:
            result = self._result_client.GetResult(  # type: ignore[union-attr]
                internal_pb2.GetResultRequest(job_id=job_id),
                timeout=self._downstream_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._map_downstream_error(context, operation="Result.GetResult", exc=exc, job_id=job_id)
            return pb2.GetJobResultResponse(job_id=job_id)

        if not result.found:
            self._logger.error(
                "gateway.result.terminal_missing_envelope",
                extra={"job_id": job_id, "status": int(rec.summary.status)},
            )
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, "terminal status present but result envelope missing")
            return pb2.GetJobResultResponse(job_id=job_id)

        if int(result.terminal_status) != int(rec.summary.status):
            self._logger.error(
                "gateway.result.terminal_mismatch",
                extra={
                    "job_id": job_id,
                    "canonical_status": int(rec.summary.status),
                    "result_status": int(result.terminal_status),
                },
            )
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, "terminal status/result mismatch")
            return pb2.GetJobResultResponse(job_id=job_id)

        return pb2.GetJobResultResponse(
            job_id=job_id,
            result_ready=True,
            terminal_status=rec.summary.status,
            output_bytes=result.output_bytes,
            output_summary=result.output_summary,
            runtime_ms=result.runtime_ms,
            checksum=result.checksum,
        )

    def CancelJob(
        self,
        request: pb2.CancelJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.CancelJobResponse:
        job_id = request.job_id.strip()
        reason = request.reason.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.CancelJobResponse(job_id="")

        if not self._require_upstreams(context, need_job=True, need_queue=True, need_result=True):
            return pb2.CancelJobResponse(job_id=job_id)

        rec = self._fetch_record(job_id, context, operation="Job.GetJobRecord")
        if rec is None:
            return pb2.CancelJobResponse(job_id=job_id)

        status = int(rec.summary.status)
        if status in _TERMINAL_STATUSES:
            return pb2.CancelJobResponse(
                job_id=job_id,
                accepted=True,
                current_status=status,
                already_terminal=True,
            )

        if status == pb2.QUEUED:
            try:
                rm = self._queue_client.RemoveJobIfPresent(  # type: ignore[union-attr]
                    internal_pb2.RemoveJobIfPresentRequest(job_id=job_id),
                    timeout=self._downstream_rpc_timeout_s,
                )
            except grpc.RpcError as exc:
                self._map_downstream_error(context, operation="Queue.RemoveJobIfPresent", exc=exc, job_id=job_id)
                return pb2.CancelJobResponse(job_id=job_id)

            if rm.removed:
                if not self._store_cancel_result(job_id, reason, context):
                    return pb2.CancelJobResponse(job_id=job_id)

                try:
                    transition = self._job_client.TransitionJobStatus(  # type: ignore[union-attr]
                        internal_pb2.TransitionJobStatusRequest(
                            job_id=job_id,
                            expected_from_status=pb2.QUEUED,
                            to_status=pb2.CANCELED,
                            actor="gateway",
                            reason=reason,
                        ),
                        timeout=self._downstream_rpc_timeout_s,
                    )
                except grpc.RpcError as exc:
                    self._map_downstream_error(context, operation="Job.TransitionJobStatus", exc=exc, job_id=job_id)
                    return pb2.CancelJobResponse(job_id=job_id)

                if transition.applied:
                    return pb2.CancelJobResponse(
                        job_id=job_id,
                        accepted=True,
                        current_status=pb2.CANCELED,
                        already_terminal=False,
                    )

                if int(transition.current_status) in _TERMINAL_STATUSES:
                    return pb2.CancelJobResponse(
                        job_id=job_id,
                        accepted=True,
                        current_status=int(transition.current_status),
                        already_terminal=True,
                    )

                set_resp = self._set_cancel_requested(job_id, reason, context)
                if set_resp is None:
                    return pb2.CancelJobResponse(job_id=job_id)
                return pb2.CancelJobResponse(
                    job_id=job_id,
                    accepted=True,
                    current_status=int(set_resp.current_status),
                    already_terminal=int(set_resp.current_status) in _TERMINAL_STATUSES,
                )

            set_resp = self._set_cancel_requested(job_id, reason, context)
            if set_resp is None:
                return pb2.CancelJobResponse(job_id=job_id)
            return pb2.CancelJobResponse(
                job_id=job_id,
                accepted=True,
                current_status=int(set_resp.current_status),
                already_terminal=int(set_resp.current_status) in _TERMINAL_STATUSES,
            )

        set_resp = self._set_cancel_requested(job_id, reason, context)
        if set_resp is None:
            return pb2.CancelJobResponse(job_id=job_id)
        return pb2.CancelJobResponse(
            job_id=job_id,
            accepted=True,
            current_status=int(set_resp.current_status),
            already_terminal=int(set_resp.current_status) in _TERMINAL_STATUSES,
        )

    def ListJobs(
        self,
        request: pb2.ListJobsRequest,
        context: grpc.ServicerContext,
    ) -> pb2.ListJobsResponse:
        if not self._require_upstreams(context, need_job=True):
            return pb2.ListJobsResponse()

        try:
            recs = self._job_client.ListJobRecords(  # type: ignore[union-attr]
                internal_pb2.ListJobRecordsRequest(
                    status_filter=request.status_filter,
                    page=request.page,
                    sort=request.sort,
                ),
                timeout=self._downstream_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._map_downstream_error(context, operation="Job.ListJobRecords", exc=exc)
            return pb2.ListJobsResponse()

        return pb2.ListJobsResponse(
            jobs=recs.jobs,
            page=recs.page,
        )
