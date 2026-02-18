#!/usr/bin/env python3
"""
Smoke test for Gateway service behavior (in-process, no network bind).

This validates key v1 semantics directly against GatewayServicer RPC handlers:
- Submit create+enqueue acceptance and compensation on enqueue failure
- Canonical status reads and result canonical-first behavior
- Terminal status/result mismatch handling
- Queued/running cancel semantics and deterministic repeated-terminal behavior
- List pass-through behavior and error propagation
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

import grpc


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


class FakeContext(grpc.ServicerContext):
    def __init__(self) -> None:
        self._code = grpc.StatusCode.OK
        self._details = ""

    def set_code(self, code):
        self._code = code

    def set_details(self, details):
        self._details = details

    @property
    def code(self):
        return self._code

    @property
    def details(self):
        return self._details

    # Unused abstract methods for compatibility.
    def abort(self, code, details):
        raise NotImplementedError

    def abort_with_status(self, status):
        raise NotImplementedError

    def add_callback(self, callback):
        return False

    def auth_context(self):
        return {}

    def cancel(self):
        return False

    def invocation_metadata(self):
        return []

    def is_active(self):
        return True

    def peer(self):
        return ""

    def peer_identities(self):
        return None

    def peer_identity_key(self):
        return None

    def send_initial_metadata(self, initial_metadata):
        return None

    def set_compression(self, compression):
        return None

    def set_trailing_metadata(self, trailing_metadata):
        return None

    def time_remaining(self):
        return None


class FakeRpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode, details: str = "") -> None:
        super().__init__()
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


class FakeJobClient:
    def __init__(self, pb2, public_pb2):
        self.pb2 = pb2
        self.public_pb2 = public_pb2
        self.create_resp = pb2.CreateJobResponse(job_id="job-submit", status=public_pb2.QUEUED)
        self.create_error: FakeRpcError | None = None
        self.delete_called = False
        self.delete_resp = pb2.DeleteJobIfStatusResponse(deleted=True, current_status=public_pb2.QUEUED)
        self.records: dict[str, pb2.GetJobRecordResponse] = {}
        self.transitions: dict[str, pb2.TransitionJobStatusResponse] = {}
        self.cancel_resp = pb2.SetCancelRequestedResponse(applied=True, current_status=public_pb2.RUNNING)
        self.list_resp = pb2.ListJobRecordsResponse()

    def CreateJob(self, request, timeout=None):
        if self.create_error is not None:
            raise self.create_error
        return self.create_resp

    def DeleteJobIfStatus(self, request, timeout=None):
        self.delete_called = True
        return self.delete_resp

    def GetJobRecord(self, request, timeout=None):
        rec = self.records.get(request.job_id)
        if rec is None:
            raise FakeRpcError(grpc.StatusCode.NOT_FOUND, "unknown job_id")
        return rec

    def TransitionJobStatus(self, request, timeout=None):
        return self.transitions.get(
            request.job_id,
            self.pb2.TransitionJobStatusResponse(applied=True, current_status=request.to_status),
        )

    def SetCancelRequested(self, request, timeout=None):
        return self.cancel_resp

    def ListJobRecords(self, request, timeout=None):
        return self.list_resp


class FakeQueueClient:
    def __init__(self, pb2):
        self.pb2 = pb2
        self.enqueue_error: FakeRpcError | None = None
        self.enqueue_resp = pb2.EnqueueJobResponse(accepted=True)
        self.remove_resp = pb2.RemoveJobIfPresentResponse(removed=True)

    def EnqueueJob(self, request, timeout=None):
        if self.enqueue_error is not None:
            raise self.enqueue_error
        return self.enqueue_resp

    def RemoveJobIfPresent(self, request, timeout=None):
        return self.remove_resp


class FakeResultClient:
    def __init__(self, pb2, public_pb2):
        self.pb2 = pb2
        self.public_pb2 = public_pb2
        self.store_resp = pb2.StoreResultResponse(
            stored=True,
            already_exists=False,
            current_terminal_status=public_pb2.CANCELED,
        )
        self.get_resp = pb2.GetResultResponse(found=False, job_id="", terminal_status=public_pb2.JOB_STATUS_UNSPECIFIED)

    def StoreResult(self, request, timeout=None):
        return self.store_resp

    def GetResult(self, request, timeout=None):
        return self.get_resp


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _record(pb2, public_pb2, job_id: str, status: int, failure_reason: str = ""):
    return pb2.GetJobRecordResponse(
        summary=public_pb2.JobSummary(
            job_id=job_id,
            status=status,
            job_type="smoke",
            created_at_ms=1,
            started_at_ms=2 if status != public_pb2.QUEUED else 0,
            finished_at_ms=3 if status in {public_pb2.DONE, public_pb2.FAILED, public_pb2.CANCELED} else 0,
            cancel_requested=(status == public_pb2.CANCELED),
        ),
        failure_reason=failure_reason,
    )


def _print_summary_and_exit(checks: List[CheckResult]) -> int:
    print("\n=== Gateway Behavior Smoke Test Summary ===")
    max_name = max((len(c.name) for c in checks), default=10)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<{max_name}}  {c.detail}")
        if not c.passed:
            all_passed = False
    print("==========================================")
    if all_passed:
        print("RESULT: PASS")
        return 0
    print("RESULT: FAIL")
    return 1


def main() -> int:
    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import taskqueue_internal_pb2 as pb2
    import taskqueue_public_pb2 as public_pb2
    from services.gateway.servicer import GatewayServicer

    checks: List[CheckResult] = []

    # 1) Submit success path.
    job = FakeJobClient(pb2, public_pb2)
    queue = FakeQueueClient(pb2)
    result = FakeResultClient(pb2, public_pb2)
    svc = GatewayServicer(job_client=job, queue_client=queue, result_client=result)

    ctx = FakeContext()
    submit = svc.SubmitJob(
        public_pb2.SubmitJobRequest(
            spec=public_pb2.JobSpec(job_type="submit", work_duration_ms=1, payload_size_bytes=0),
            client_request_id="submit-1",
        ),
        ctx,
    )
    checks.append(
        CheckResult(
            "submit_accept",
            ctx.code == grpc.StatusCode.OK and bool(submit.job_id) and submit.initial_status == public_pb2.QUEUED,
            f"code={ctx.code.name}, job_id={submit.job_id}, status={submit.initial_status}",
        )
    )

    # 2) Submit enqueue failure triggers compensation + UNAVAILABLE.
    job = FakeJobClient(pb2, public_pb2)
    queue = FakeQueueClient(pb2)
    queue.enqueue_error = FakeRpcError(grpc.StatusCode.UNAVAILABLE, "queue down")
    svc = GatewayServicer(job_client=job, queue_client=queue, result_client=FakeResultClient(pb2, public_pb2))
    ctx = FakeContext()
    _ = svc.SubmitJob(
        public_pb2.SubmitJobRequest(spec=public_pb2.JobSpec(job_type="submit", work_duration_ms=1, payload_size_bytes=0)),
        ctx,
    )
    checks.append(
        CheckResult(
            "submit_compensate_on_enqueue_fail",
            ctx.code == grpc.StatusCode.UNAVAILABLE and job.delete_called,
            f"code={ctx.code.name}, compensation_called={job.delete_called}",
        )
    )

    # 3) Status read pass-through.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-status"] = _record(pb2, public_pb2, "job-status", public_pb2.FAILED, "boom")
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=FakeResultClient(pb2, public_pb2))
    ctx = FakeContext()
    st = svc.GetJobStatus(public_pb2.GetJobStatusRequest(job_id="job-status"), ctx)
    checks.append(
        CheckResult(
            "get_status",
            ctx.code == grpc.StatusCode.OK and st.status == public_pb2.FAILED and st.failure_reason == "boom",
            f"code={ctx.code.name}, status={st.status}, failure_reason={st.failure_reason}",
        )
    )

    # 4) Result not ready for non-terminal status.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-running"] = _record(pb2, public_pb2, "job-running", public_pb2.RUNNING)
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=FakeResultClient(pb2, public_pb2))
    ctx = FakeContext()
    not_ready = svc.GetJobResult(public_pb2.GetJobResultRequest(job_id="job-running"), ctx)
    checks.append(
        CheckResult(
            "get_result_not_ready",
            ctx.code == grpc.StatusCode.OK and (not not_ready.result_ready),
            f"code={ctx.code.name}, ready={not_ready.result_ready}",
        )
    )

    # 5) Terminal + missing envelope => UNAVAILABLE.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-done-missing"] = _record(pb2, public_pb2, "job-done-missing", public_pb2.DONE)
    result = FakeResultClient(pb2, public_pb2)
    result.get_resp = pb2.GetResultResponse(found=False, job_id="job-done-missing", terminal_status=public_pb2.JOB_STATUS_UNSPECIFIED)
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=result)
    ctx = FakeContext()
    _ = svc.GetJobResult(public_pb2.GetJobResultRequest(job_id="job-done-missing"), ctx)
    checks.append(
        CheckResult(
            "get_result_terminal_missing",
            ctx.code == grpc.StatusCode.UNAVAILABLE,
            f"code={ctx.code.name}",
        )
    )

    # 6) Terminal + mismatch envelope => UNAVAILABLE.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-done-mismatch"] = _record(pb2, public_pb2, "job-done-mismatch", public_pb2.DONE)
    result = FakeResultClient(pb2, public_pb2)
    result.get_resp = pb2.GetResultResponse(
        found=True,
        job_id="job-done-mismatch",
        terminal_status=public_pb2.FAILED,
        runtime_ms=1,
        output_summary="x",
        output_bytes=b"",
        checksum="",
    )
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=result)
    ctx = FakeContext()
    _ = svc.GetJobResult(public_pb2.GetJobResultRequest(job_id="job-done-mismatch"), ctx)
    checks.append(CheckResult("get_result_terminal_mismatch", ctx.code == grpc.StatusCode.UNAVAILABLE, f"code={ctx.code.name}"))

    # 7) Terminal result success path.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-done"] = _record(pb2, public_pb2, "job-done", public_pb2.DONE)
    result = FakeResultClient(pb2, public_pb2)
    result.get_resp = pb2.GetResultResponse(
        found=True,
        job_id="job-done",
        terminal_status=public_pb2.DONE,
        runtime_ms=42,
        output_summary="ok",
        output_bytes=b"abc",
        checksum="deadbeef",
    )
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=result)
    ctx = FakeContext()
    ready = svc.GetJobResult(public_pb2.GetJobResultRequest(job_id="job-done"), ctx)
    checks.append(
        CheckResult(
            "get_result_terminal_ready",
            ctx.code == grpc.StatusCode.OK and ready.result_ready and ready.terminal_status == public_pb2.DONE,
            f"code={ctx.code.name}, ready={ready.result_ready}, status={ready.terminal_status}",
        )
    )

    # 8) Cancel terminal is deterministic + already_terminal.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-canceled"] = _record(pb2, public_pb2, "job-canceled", public_pb2.CANCELED)
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=FakeResultClient(pb2, public_pb2))
    ctx = FakeContext()
    cancel_terminal = svc.CancelJob(public_pb2.CancelJobRequest(job_id="job-canceled", reason="again"), ctx)
    checks.append(
        CheckResult(
            "cancel_terminal_repeat",
            ctx.code == grpc.StatusCode.OK and cancel_terminal.accepted and cancel_terminal.already_terminal,
            f"code={ctx.code.name}, accepted={cancel_terminal.accepted}, already_terminal={cancel_terminal.already_terminal}",
        )
    )

    # 9) Queued cancel happy path.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-queued"] = _record(pb2, public_pb2, "job-queued", public_pb2.QUEUED)
    job.transitions["job-queued"] = pb2.TransitionJobStatusResponse(applied=True, current_status=public_pb2.CANCELED)
    queue = FakeQueueClient(pb2)
    queue.remove_resp = pb2.RemoveJobIfPresentResponse(removed=True)
    result = FakeResultClient(pb2, public_pb2)
    result.store_resp = pb2.StoreResultResponse(stored=True, already_exists=False, current_terminal_status=public_pb2.CANCELED)
    svc = GatewayServicer(job_client=job, queue_client=queue, result_client=result)
    ctx = FakeContext()
    cancel_queued = svc.CancelJob(public_pb2.CancelJobRequest(job_id="job-queued", reason="stop"), ctx)
    checks.append(
        CheckResult(
            "cancel_queued_path",
            ctx.code == grpc.StatusCode.OK and cancel_queued.accepted and cancel_queued.current_status == public_pb2.CANCELED,
            f"code={ctx.code.name}, accepted={cancel_queued.accepted}, current_status={cancel_queued.current_status}",
        )
    )

    # 10) Queued remove-miss fallback sets cancel_requested.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-race"] = _record(pb2, public_pb2, "job-race", public_pb2.QUEUED)
    job.cancel_resp = pb2.SetCancelRequestedResponse(applied=True, current_status=public_pb2.RUNNING)
    queue = FakeQueueClient(pb2)
    queue.remove_resp = pb2.RemoveJobIfPresentResponse(removed=False)
    svc = GatewayServicer(job_client=job, queue_client=queue, result_client=FakeResultClient(pb2, public_pb2))
    ctx = FakeContext()
    cancel_race = svc.CancelJob(public_pb2.CancelJobRequest(job_id="job-race", reason="stop"), ctx)
    checks.append(
        CheckResult(
            "cancel_queued_race_fallback",
            ctx.code == grpc.StatusCode.OK and cancel_race.accepted and cancel_race.current_status == public_pb2.RUNNING,
            f"code={ctx.code.name}, accepted={cancel_race.accepted}, current_status={cancel_race.current_status}",
        )
    )

    # 11) Running cancel sets advisory flag.
    job = FakeJobClient(pb2, public_pb2)
    job.records["job-running-cancel"] = _record(pb2, public_pb2, "job-running-cancel", public_pb2.RUNNING)
    job.cancel_resp = pb2.SetCancelRequestedResponse(applied=False, current_status=public_pb2.RUNNING)
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=FakeResultClient(pb2, public_pb2))
    ctx = FakeContext()
    cancel_running = svc.CancelJob(public_pb2.CancelJobRequest(job_id="job-running-cancel", reason="stop"), ctx)
    checks.append(
        CheckResult(
            "cancel_running_advisory",
            ctx.code == grpc.StatusCode.OK and cancel_running.accepted and cancel_running.current_status == public_pb2.RUNNING,
            f"code={ctx.code.name}, accepted={cancel_running.accepted}, current_status={cancel_running.current_status}",
        )
    )

    # 12) List pass-through and INVALID_ARGUMENT propagation.
    job = FakeJobClient(pb2, public_pb2)
    job.list_resp = pb2.ListJobRecordsResponse(
        jobs=[_record(pb2, public_pb2, "job-list-1", public_pb2.QUEUED).summary],
        page=public_pb2.PageResponse(next_page_token=""),
    )
    svc = GatewayServicer(job_client=job, queue_client=FakeQueueClient(pb2), result_client=FakeResultClient(pb2, public_pb2))
    ctx = FakeContext()
    listed = svc.ListJobs(
        public_pb2.ListJobsRequest(
            status_filter=[public_pb2.QUEUED],
            page=public_pb2.PageRequest(page_size=10, page_token="0"),
            sort=public_pb2.CREATED_AT_DESC,
        ),
        ctx,
    )
    list_ok = ctx.code == grpc.StatusCode.OK and len(listed.jobs) == 1 and listed.jobs[0].job_id == "job-list-1"

    def _list_raises_invalid(request, timeout=None):
        raise FakeRpcError(grpc.StatusCode.INVALID_ARGUMENT, "bad token")

    job.ListJobRecords = _list_raises_invalid  # type: ignore[method-assign]
    ctx_err = FakeContext()
    _ = svc.ListJobs(
        public_pb2.ListJobsRequest(page=public_pb2.PageRequest(page_size=10, page_token="NaN")),
        ctx_err,
    )
    checks.append(
        CheckResult(
            "list_passthrough_and_error",
            list_ok and ctx_err.code == grpc.StatusCode.INVALID_ARGUMENT,
            f"list_ok={list_ok}, error_code={ctx_err.code.name}",
        )
    )

    return _print_summary_and_exit(checks)


if __name__ == "__main__":
    raise SystemExit(main())
