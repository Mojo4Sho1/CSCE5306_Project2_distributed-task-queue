from __future__ import annotations

import logging
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import grpc

try:
    # Preferred when PYTHONPATH includes ./generated
    import taskqueue_internal_pb2 as pb2
    import taskqueue_internal_pb2_grpc as pb2_grpc
    import taskqueue_public_pb2 as public_pb2
except ModuleNotFoundError:  # pragma: no cover
    # Fallback if generated modules are imported as a package
    from generated import taskqueue_internal_pb2 as pb2
    from generated import taskqueue_internal_pb2_grpc as pb2_grpc
    from generated import taskqueue_public_pb2 as public_pb2

try:
    from common.time_utils import now_ms
except Exception:  # pragma: no cover
    import time

    def now_ms() -> int:
        return int(time.time() * 1000)


_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200
_DEFAULT_MAX_DEDUP_KEYS = 10000

_TERMINAL_STATUSES = {
    public_pb2.DONE,
    public_pb2.FAILED,
    public_pb2.CANCELED,
}

_ALLOWED_TRANSITIONS = {
    (public_pb2.QUEUED, public_pb2.RUNNING),
    (public_pb2.RUNNING, public_pb2.DONE),
    (public_pb2.RUNNING, public_pb2.FAILED),
    (public_pb2.RUNNING, public_pb2.CANCELED),
    (public_pb2.QUEUED, public_pb2.CANCELED),
}


@dataclass
class _JobRecord:
    job_id: str
    status: int
    job_type: str
    work_duration_ms: int
    payload_size_bytes: int
    labels: Dict[str, str]
    created_at_ms: int
    started_at_ms: int
    finished_at_ms: int
    cancel_requested: bool
    failure_reason: str


@dataclass
class _DedupEntry:
    fingerprint: Tuple[str, int, int, Tuple[Tuple[str, str], ...]]
    job_id: str


class JobServicer(pb2_grpc.JobInternalServiceServicer):
    """
    JobInternalService v1 implementation.

    Responsibilities:
    - canonical job record authority for status/timestamps
    - submit idempotency (bounded in-memory dedup)
    - conditional delete / CAS transition semantics
    - list/filter/sort/pagination semantics for internal readers
    """

    def __init__(self, config: Optional[object] = None, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("job.servicer")
        configured_cap = int(getattr(config, "max_dedup_keys", _DEFAULT_MAX_DEDUP_KEYS))
        self._max_dedup_keys = configured_cap if configured_cap > 0 else _DEFAULT_MAX_DEDUP_KEYS

        self._lock = threading.RLock()
        self._jobs: Dict[str, _JobRecord] = {}
        self._dedup: OrderedDict[str, _DedupEntry] = OrderedDict()

    def _fingerprint(self, spec: public_pb2.JobSpec) -> Tuple[str, int, int, Tuple[Tuple[str, str], ...]]:
        labels_tuple = tuple(sorted((str(k), str(v)) for k, v in spec.labels.items()))
        return (str(spec.job_type), int(spec.work_duration_ms), int(spec.payload_size_bytes), labels_tuple)

    def _summary_from_record(self, rec: _JobRecord) -> public_pb2.JobSummary:
        return public_pb2.JobSummary(
            job_id=rec.job_id,
            status=rec.status,
            job_type=rec.job_type,
            created_at_ms=rec.created_at_ms,
            started_at_ms=rec.started_at_ms,
            finished_at_ms=rec.finished_at_ms,
            cancel_requested=rec.cancel_requested,
        )

    def _set_error(self, context: grpc.ServicerContext, code: grpc.StatusCode, detail: str) -> None:
        context.set_code(code)
        context.set_details(detail)

    def _coerce_sort(self, sort: int) -> int:
        if sort == public_pb2.JOB_SORT_UNSPECIFIED:
            return public_pb2.CREATED_AT_DESC
        if sort in (public_pb2.CREATED_AT_DESC, public_pb2.CREATED_AT_ASC):
            return sort
        return public_pb2.CREATED_AT_DESC

    def _parse_offset(self, token: str) -> Optional[int]:
        value = (token or "").strip()
        if value == "":
            return 0
        if not value.isdigit():
            return None
        return int(value)

    def _validate_status_filter(self, statuses) -> bool:
        for status in statuses:
            if status == public_pb2.JOB_STATUS_UNSPECIFIED:
                return False
        return True

    def CreateJob(self, request: pb2.CreateJobRequest, context: grpc.ServicerContext) -> pb2.CreateJobResponse:
        if not request.spec.job_type.strip():
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "spec.job_type must be non-empty")
            return pb2.CreateJobResponse(job_id="", status=public_pb2.JOB_STATUS_UNSPECIFIED)

        fingerprint = self._fingerprint(request.spec)
        dedup_key = request.client_request_id.strip()

        with self._lock:
            if dedup_key:
                existing = self._dedup.get(dedup_key)
                if existing is not None:
                    if existing.fingerprint != fingerprint:
                        self._set_error(
                            context,
                            grpc.StatusCode.FAILED_PRECONDITION,
                            "client_request_id reused with different payload",
                        )
                        return pb2.CreateJobResponse(job_id="", status=public_pb2.JOB_STATUS_UNSPECIFIED)

                    rec = self._jobs.get(existing.job_id)
                    if rec is None:
                        self._set_error(context, grpc.StatusCode.INTERNAL, "dedup index points to missing job record")
                        return pb2.CreateJobResponse(job_id="", status=public_pb2.JOB_STATUS_UNSPECIFIED)

                    self._dedup.move_to_end(dedup_key)
                    return pb2.CreateJobResponse(job_id=rec.job_id, status=rec.status)

            job_id = str(uuid.uuid4())
            created_at = now_ms()
            rec = _JobRecord(
                job_id=job_id,
                status=public_pb2.QUEUED,
                job_type=request.spec.job_type,
                work_duration_ms=request.spec.work_duration_ms,
                payload_size_bytes=request.spec.payload_size_bytes,
                labels={k: v for k, v in request.spec.labels.items()},
                created_at_ms=created_at,
                started_at_ms=0,
                finished_at_ms=0,
                cancel_requested=False,
                failure_reason="",
            )
            self._jobs[job_id] = rec

            if dedup_key:
                self._dedup[dedup_key] = _DedupEntry(fingerprint=fingerprint, job_id=job_id)
                self._dedup.move_to_end(dedup_key)
                while len(self._dedup) > self._max_dedup_keys:
                    self._dedup.popitem(last=False)

            return pb2.CreateJobResponse(job_id=job_id, status=public_pb2.QUEUED)

    def DeleteJobIfStatus(
        self,
        request: pb2.DeleteJobIfStatusRequest,
        context: grpc.ServicerContext,
    ) -> pb2.DeleteJobIfStatusResponse:
        with self._lock:
            rec = self._jobs.get(request.job_id)
            if rec is None:
                return pb2.DeleteJobIfStatusResponse(
                    deleted=False,
                    current_status=public_pb2.JOB_STATUS_UNSPECIFIED,
                )

            if rec.status != request.expected_status:
                return pb2.DeleteJobIfStatusResponse(deleted=False, current_status=rec.status)

            del self._jobs[request.job_id]
            return pb2.DeleteJobIfStatusResponse(deleted=True, current_status=request.expected_status)

    def GetJobRecord(self, request: pb2.GetJobRecordRequest, context: grpc.ServicerContext) -> pb2.GetJobRecordResponse:
        with self._lock:
            rec = self._jobs.get(request.job_id)
            if rec is None:
                self._set_error(context, grpc.StatusCode.NOT_FOUND, "unknown job_id")
                return pb2.GetJobRecordResponse(summary=public_pb2.JobSummary(job_id=request.job_id), failure_reason="")

            return pb2.GetJobRecordResponse(
                summary=self._summary_from_record(rec),
                failure_reason=rec.failure_reason,
            )

    def ListJobRecords(
        self,
        request: pb2.ListJobRecordsRequest,
        context: grpc.ServicerContext,
    ) -> pb2.ListJobRecordsResponse:
        offset = self._parse_offset(request.page.page_token)
        if offset is None:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "page.page_token must be a non-negative integer string")
            return pb2.ListJobRecordsResponse()

        if not self._validate_status_filter(request.status_filter):
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "status_filter must not include JOB_STATUS_UNSPECIFIED")
            return pb2.ListJobRecordsResponse()

        page_size = int(request.page.page_size) if request.page.page_size else _DEFAULT_PAGE_SIZE
        page_size = max(1, min(page_size, _MAX_PAGE_SIZE))
        sort = self._coerce_sort(request.sort)

        with self._lock:
            records = list(self._jobs.values())

        if request.status_filter:
            wanted = set(request.status_filter)
            records = [rec for rec in records if rec.status in wanted]

        if sort == public_pb2.CREATED_AT_ASC:
            records.sort(key=lambda rec: (rec.created_at_ms, rec.job_id))
        else:
            records.sort(key=lambda rec: (-rec.created_at_ms, rec.job_id))

        if offset > len(records):
            offset = len(records)
        end = min(offset + page_size, len(records))
        window = records[offset:end]
        next_token = str(end) if end < len(records) else ""

        return pb2.ListJobRecordsResponse(
            jobs=[self._summary_from_record(rec) for rec in window],
            page=public_pb2.PageResponse(next_page_token=next_token),
        )

    def TransitionJobStatus(
        self,
        request: pb2.TransitionJobStatusRequest,
        context: grpc.ServicerContext,
    ) -> pb2.TransitionJobStatusResponse:
        if request.expected_from_status == public_pb2.JOB_STATUS_UNSPECIFIED:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "expected_from_status must be specified")
            return pb2.TransitionJobStatusResponse(applied=False, current_status=public_pb2.JOB_STATUS_UNSPECIFIED)

        if request.to_status == public_pb2.JOB_STATUS_UNSPECIFIED:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "to_status must be specified")
            return pb2.TransitionJobStatusResponse(applied=False, current_status=public_pb2.JOB_STATUS_UNSPECIFIED)

        with self._lock:
            rec = self._jobs.get(request.job_id)
            if rec is None:
                self._set_error(context, grpc.StatusCode.NOT_FOUND, "unknown job_id")
                return pb2.TransitionJobStatusResponse(applied=False, current_status=public_pb2.JOB_STATUS_UNSPECIFIED)

            if rec.status != request.expected_from_status:
                return pb2.TransitionJobStatusResponse(applied=False, current_status=rec.status)

            if (request.expected_from_status, request.to_status) not in _ALLOWED_TRANSITIONS:
                self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "invalid status transition")
                return pb2.TransitionJobStatusResponse(applied=False, current_status=rec.status)

            transition_time = now_ms()
            rec.status = request.to_status

            if request.to_status == public_pb2.RUNNING:
                if rec.started_at_ms == 0:
                    rec.started_at_ms = transition_time
            if request.to_status in _TERMINAL_STATUSES:
                rec.finished_at_ms = transition_time
                if request.to_status == public_pb2.FAILED:
                    rec.failure_reason = request.reason or ""
                if request.to_status == public_pb2.CANCELED:
                    rec.cancel_requested = True

            return pb2.TransitionJobStatusResponse(applied=True, current_status=rec.status)

    def SetCancelRequested(
        self,
        request: pb2.SetCancelRequestedRequest,
        context: grpc.ServicerContext,
    ) -> pb2.SetCancelRequestedResponse:
        with self._lock:
            rec = self._jobs.get(request.job_id)
            if rec is None:
                self._set_error(context, grpc.StatusCode.NOT_FOUND, "unknown job_id")
                return pb2.SetCancelRequestedResponse(applied=False, current_status=public_pb2.JOB_STATUS_UNSPECIFIED)

            if rec.status in _TERMINAL_STATUSES:
                return pb2.SetCancelRequestedResponse(applied=False, current_status=rec.status)

            changed = rec.cancel_requested != request.cancel_requested
            rec.cancel_requested = request.cancel_requested
            return pb2.SetCancelRequestedResponse(applied=changed, current_status=rec.status)
