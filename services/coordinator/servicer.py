"""RPC method implementations for the coordinator service."""

from __future__ import annotations

import logging
import threading
from typing import Optional

import grpc
from common.rpc_defaults import (
    FETCHWORK_RETRY_AFTER_DEFAULT_MS,
    FETCHWORK_RETRY_AFTER_MAX_MS,
    FETCHWORK_RETRY_AFTER_MIN_MS,
    INTERNAL_UNARY_RPC_TIMEOUT_MS,
)

try:
    # Preferred when PYTHONPATH includes ./generated
    import taskqueue_internal_pb2 as pb2
    import taskqueue_internal_pb2_grpc as pb2_grpc
except ModuleNotFoundError:  # pragma: no cover
    # Fallback if generated modules are imported as a package
    from generated import taskqueue_internal_pb2 as pb2
    from generated import taskqueue_internal_pb2_grpc as pb2_grpc
    from generated import taskqueue_public_pb2 as public_pb2
else:
    import taskqueue_public_pb2 as public_pb2

try:
    from common.time_utils import now_ms
except Exception:  # pragma: no cover
    import time

    def now_ms() -> int:
        return int(time.time() * 1000)


_OUTCOME_TO_TERMINAL_STATUS = {
    public_pb2.JOB_OUTCOME_SUCCEEDED: public_pb2.DONE,
    public_pb2.JOB_OUTCOME_FAILED: public_pb2.FAILED,
    public_pb2.JOB_OUTCOME_CANCELED: public_pb2.CANCELED,
}

_TERMINAL_STATUSES = {
    public_pb2.DONE,
    public_pb2.FAILED,
    public_pb2.CANCELED,
}


class _WorkerState:
    """ worker state state and behavior."""
    __slots__ = ("last_seen_at_ms", "last_heartbeat_at_ms", "capacity_hint")

    def __init__(self, last_seen_at_ms: int, last_heartbeat_at_ms: int, capacity_hint: int) -> None:
        """Initialize  worker state instance state."""
        self.last_seen_at_ms = last_seen_at_ms
        self.last_heartbeat_at_ms = last_heartbeat_at_ms
        self.capacity_hint = capacity_hint


class CoordinatorServicer(pb2_grpc.CoordinatorInternalServiceServicer):
    """CoordinatorInternalService v1 behavior implementation."""

    def __init__(
        self,
        config: Optional[object] = None,
        logger: Optional[logging.Logger] = None,
        job_client=None,
        queue_client=None,
        result_client=None,
    ) -> None:
        """Initialize coordinator servicer instance state."""
        self._config = config
        self._logger = logger or logging.getLogger("coordinator.servicer")
        self._heartbeat_interval_ms = int(getattr(config, "heartbeat_interval_ms", 1000))
        self._worker_timeout_ms = int(getattr(config, "worker_timeout_ms", 4000))
        self._retry_after_ms = self._clamp_retry_after(FETCHWORK_RETRY_AFTER_DEFAULT_MS)
        timeout_ms = int(getattr(config, "internal_rpc_timeout_ms", INTERNAL_UNARY_RPC_TIMEOUT_MS))
        self._internal_rpc_timeout_s = max(timeout_ms, 1) / 1000.0

        self._lock = threading.RLock()
        self._workers: dict[str, _WorkerState] = {}

        self._job_channel = None
        self._queue_channel = None
        self._result_channel = None

        self._job_client = job_client
        self._queue_client = queue_client
        self._result_client = result_client
        self._init_clients()

    def _init_clients(self) -> None:
        """Internal helper to  init clients."""
        if self._job_client is None:
            job_addr = str(getattr(self._config, "job_addr", "")).strip()
            if job_addr:
                self._job_channel = grpc.insecure_channel(job_addr)
                self._job_client = pb2_grpc.JobInternalServiceStub(self._job_channel)

        if self._queue_client is None:
            queue_addr = str(getattr(self._config, "queue_addr", "")).strip()
            if queue_addr:
                self._queue_channel = grpc.insecure_channel(queue_addr)
                self._queue_client = pb2_grpc.QueueInternalServiceStub(self._queue_channel)

        if self._result_client is None:
            result_addr = str(getattr(self._config, "result_addr", "")).strip()
            if result_addr:
                self._result_channel = grpc.insecure_channel(result_addr)
                self._result_client = pb2_grpc.ResultInternalServiceStub(self._result_channel)

    def _set_error(self, context: grpc.ServicerContext, code: grpc.StatusCode, detail: str) -> None:
        """Populate RPC error code and details on the context."""
        context.set_code(code)
        context.set_details(detail)

    def _clamp_retry_after(self, value: int) -> int:
        """Internal helper to  clamp retry after."""
        return max(FETCHWORK_RETRY_AFTER_MIN_MS, min(int(value), FETCHWORK_RETRY_AFTER_MAX_MS))

    def _prune_expired_workers_locked(self, now_ts_ms: int) -> None:
        """Internal helper to  prune expired workers locked."""
        expired = [
            worker_id
            for worker_id, state in self._workers.items()
            if now_ts_ms - state.last_seen_at_ms > self._worker_timeout_ms
        ]
        for worker_id in expired:
            self._workers.pop(worker_id, None)

    def _is_worker_live(self, worker_id: str, now_ts_ms: int) -> bool:
        """Internal helper to  is worker live."""
        with self._lock:
            self._prune_expired_workers_locked(now_ts_ms)
            state = self._workers.get(worker_id)
            if state is None:
                return False
            return now_ts_ms - state.last_seen_at_ms <= self._worker_timeout_ms

    def WorkerHeartbeat(
        self,
        request: pb2.WorkerHeartbeatRequest,
        context: grpc.ServicerContext,
    ) -> pb2.WorkerHeartbeatResponse:
        """Worker heartbeat."""
        worker_id = request.worker_id.strip()
        if not worker_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "worker_id must be non-empty")
            return pb2.WorkerHeartbeatResponse(accepted=False, next_heartbeat_in_ms=0)

        current_ts_ms = now_ms()
        reported_ts_ms = int(request.heartbeat_at_ms) if int(request.heartbeat_at_ms) > 0 else current_ts_ms
        capacity_hint = int(request.capacity_hint) if int(request.capacity_hint) > 0 else 1

        with self._lock:
            self._prune_expired_workers_locked(current_ts_ms)
            self._workers[worker_id] = _WorkerState(
                last_seen_at_ms=current_ts_ms,
                last_heartbeat_at_ms=reported_ts_ms,
                capacity_hint=capacity_hint,
            )

        return pb2.WorkerHeartbeatResponse(
            accepted=True,
            next_heartbeat_in_ms=max(1, self._heartbeat_interval_ms),
        )

    def FetchWork(
        self,
        request: pb2.FetchWorkRequest,
        context: grpc.ServicerContext,
    ) -> pb2.FetchWorkResponse:
        """Fetch work."""
        worker_id = request.worker_id.strip()
        if not worker_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "worker_id must be non-empty")
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        if self._queue_client is None or self._job_client is None:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, "coordinator upstream dependency not configured")
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        current_ts_ms = now_ms()
        if not self._is_worker_live(worker_id, current_ts_ms):
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        try:
            dequeued = self._queue_client.DequeueJob(
                pb2.DequeueJobRequest(worker_id=worker_id),
                timeout=self._internal_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, f"queue dequeue failed: {exc.code().name}")
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        if not dequeued.found or not dequeued.job_id:
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        job_id = dequeued.job_id
        try:
            transitioned = self._job_client.TransitionJobStatus(
                pb2.TransitionJobStatusRequest(
                    job_id=job_id,
                    expected_from_status=public_pb2.QUEUED,
                    to_status=public_pb2.RUNNING,
                    actor="coordinator",
                    reason="dispatch",
                ),
                timeout=self._internal_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, f"job transition failed: {exc.code().name}")
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        if not transitioned.applied:
            try:
                record = self._job_client.GetJobRecord(
                    pb2.GetJobRecordRequest(job_id=job_id),
                    timeout=self._internal_rpc_timeout_s,
                )
                if record.summary.status == public_pb2.QUEUED:
                    self._queue_client.EnqueueJob(
                        pb2.EnqueueJobRequest(job_id=job_id, enqueued_at_ms=now_ms()),
                        timeout=self._internal_rpc_timeout_s,
                    )
            except grpc.RpcError:
                # Rescue path is best effort; avoid surfacing additional hard error here.
                pass
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        try:
            record = self._job_client.GetJobRecord(
                pb2.GetJobRecordRequest(job_id=job_id),
                timeout=self._internal_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, f"job read failed: {exc.code().name}")
            return pb2.FetchWorkResponse(assigned=False, job_id="", retry_after_ms=self._retry_after_ms)

        return pb2.FetchWorkResponse(
            assigned=True,
            job_id=job_id,
            spec=public_pb2.JobSpec(
                job_type=record.summary.job_type,
                # v1 proto currently does not expose full JobSpec on GetJobRecord.
                work_duration_ms=0,
                payload_size_bytes=0,
                labels={},
            ),
            retry_after_ms=0,
        )

    def ReportWorkOutcome(
        self,
        request: pb2.ReportWorkOutcomeRequest,
        context: grpc.ServicerContext,
    ) -> pb2.ReportWorkOutcomeResponse:
        """Report work outcome."""
        worker_id = request.worker_id.strip()
        if not worker_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "worker_id must be non-empty")
            return pb2.ReportWorkOutcomeResponse(accepted=False)

        job_id = request.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.ReportWorkOutcomeResponse(accepted=False)

        terminal_status = _OUTCOME_TO_TERMINAL_STATUS.get(request.outcome)
        if terminal_status is None:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "outcome must be specified")
            return pb2.ReportWorkOutcomeResponse(accepted=False)

        if self._result_client is None or self._job_client is None:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, "coordinator upstream dependency not configured")
            return pb2.ReportWorkOutcomeResponse(accepted=False)

        try:
            self._result_client.StoreResult(
                pb2.StoreResultRequest(
                    job_id=job_id,
                    terminal_status=terminal_status,
                    runtime_ms=request.runtime_ms,
                    output_summary=request.output_summary,
                    output_bytes=request.output_bytes,
                    checksum=request.checksum,
                ),
                timeout=self._internal_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, f"result store failed: {exc.code().name}")
            return pb2.ReportWorkOutcomeResponse(accepted=False)

        transition_reason = request.failure_reason if terminal_status == public_pb2.FAILED else request.output_summary
        try:
            transition = self._job_client.TransitionJobStatus(
                pb2.TransitionJobStatusRequest(
                    job_id=job_id,
                    expected_from_status=public_pb2.RUNNING,
                    to_status=terminal_status,
                    actor="coordinator",
                    reason=transition_reason,
                ),
                timeout=self._internal_rpc_timeout_s,
            )
        except grpc.RpcError as exc:
            self._set_error(context, grpc.StatusCode.UNAVAILABLE, f"job transition failed: {exc.code().name}")
            return pb2.ReportWorkOutcomeResponse(accepted=False)

        if transition.applied:
            return pb2.ReportWorkOutcomeResponse(accepted=True)

        if transition.current_status in _TERMINAL_STATUSES:
            return pb2.ReportWorkOutcomeResponse(accepted=True)

        return pb2.ReportWorkOutcomeResponse(accepted=False)
