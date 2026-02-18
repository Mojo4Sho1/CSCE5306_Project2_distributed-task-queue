#!/usr/bin/env python3
"""
Smoke test for Coordinator service behavior (in-process, no network bind).

This validates key v1 semantics directly against CoordinatorServicer RPC handlers:
- WorkerHeartbeat liveness acceptance + deterministic heartbeat hint
- FetchWork idle retry semantics
- FetchWork dequeue/CAS dispatch gating + QUEUED rescue re-enqueue on CAS mismatch
- ReportWorkOutcome terminalization + benign terminal-race acceptance
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
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


class FakeQueueClient:
    def __init__(self, pb2, items: List[str] | None = None) -> None:
        self._pb2 = pb2
        self._queue = list(items or [])
        self.reenqueue_calls: List[str] = []

    def DequeueJob(self, request):
        if self._queue:
            return self._pb2.DequeueJobResponse(found=True, job_id=self._queue.pop(0))
        return self._pb2.DequeueJobResponse(found=False, job_id="")

    def EnqueueJob(self, request):
        self._queue.append(request.job_id)
        self.reenqueue_calls.append(request.job_id)
        return self._pb2.EnqueueJobResponse(accepted=True)


class FakeJobClient:
    def __init__(self, pb2, public_pb2, records: dict, transitions: List[tuple[bool, int]]) -> None:
        self._pb2 = pb2
        self._public_pb2 = public_pb2
        self._records = records
        self._transitions = list(transitions)

    def TransitionJobStatus(self, request):
        if self._transitions:
            applied, current_status = self._transitions.pop(0)
        else:
            applied, current_status = True, request.to_status

        rec = self._records.get(request.job_id)
        if rec is not None and applied:
            rec["status"] = request.to_status

        return self._pb2.TransitionJobStatusResponse(applied=applied, current_status=current_status)

    def GetJobRecord(self, request):
        rec = self._records[request.job_id]
        return self._pb2.GetJobRecordResponse(
            summary=self._public_pb2.JobSummary(
                job_id=request.job_id,
                status=rec["status"],
                job_type=rec["job_type"],
                created_at_ms=1,
                started_at_ms=0,
                finished_at_ms=0,
                cancel_requested=False,
            ),
            failure_reason="",
        )


class FakeResultClient:
    def __init__(self, pb2, public_pb2, response_mode: str) -> None:
        self._pb2 = pb2
        self._public_pb2 = public_pb2
        self._response_mode = response_mode
        self.calls = []

    def StoreResult(self, request):
        self.calls.append(request)
        if self._response_mode == "already_exists":
            return self._pb2.StoreResultResponse(
                stored=False,
                already_exists=True,
                current_terminal_status=self._public_pb2.DONE,
            )
        return self._pb2.StoreResultResponse(
            stored=True,
            already_exists=False,
            current_terminal_status=request.terminal_status,
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _print_summary_and_exit(checks: List[CheckResult]) -> int:
    print("\n=== Coordinator Behavior Smoke Test Summary ===")
    max_name = max((len(c.name) for c in checks), default=10)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<{max_name}}  {c.detail}")
        if not c.passed:
            all_passed = False
    print("==============================================")
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
    from services.coordinator.servicer import CoordinatorServicer

    cfg = SimpleNamespace(heartbeat_interval_ms=1000, worker_timeout_ms=4000)
    checks: List[CheckResult] = []

    # 1) Heartbeat acceptance + deterministic hint.
    idle_queue = FakeQueueClient(pb2, items=[])
    idle_job = FakeJobClient(pb2, public_pb2, records={}, transitions=[])
    idle_result = FakeResultClient(pb2, public_pb2, response_mode="store")
    idle_svc = CoordinatorServicer(config=cfg, job_client=idle_job, queue_client=idle_queue, result_client=idle_result)

    ctx = FakeContext()
    hb = idle_svc.WorkerHeartbeat(
        pb2.WorkerHeartbeatRequest(worker_id="worker-1", heartbeat_at_ms=123, capacity_hint=1),
        ctx,
    )
    checks.append(
        CheckResult(
            "heartbeat_accept",
            ctx.code == grpc.StatusCode.OK and hb.accepted and hb.next_heartbeat_in_ms == 1000,
            f"code={ctx.code.name}, accepted={hb.accepted}, next={hb.next_heartbeat_in_ms}",
        )
    )

    # 2) Idle fetch with heartbeat-known worker.
    ctx = FakeContext()
    idle_fetch = idle_svc.FetchWork(pb2.FetchWorkRequest(worker_id="worker-1"), ctx)
    checks.append(
        CheckResult(
            "fetch_idle_retry_hint",
            ctx.code == grpc.StatusCode.OK
            and (not idle_fetch.assigned)
            and idle_fetch.job_id == ""
            and idle_fetch.retry_after_ms == 200,
            f"code={ctx.code.name}, assigned={idle_fetch.assigned}, retry={idle_fetch.retry_after_ms}",
        )
    )

    # 3) Dispatch success path with CAS gate.
    dispatch_records = {"job-1": {"status": public_pb2.QUEUED, "job_type": "dispatch-type"}}
    dispatch_svc = CoordinatorServicer(
        config=cfg,
        queue_client=FakeQueueClient(pb2, items=["job-1"]),
        job_client=FakeJobClient(pb2, public_pb2, records=dispatch_records, transitions=[(True, public_pb2.RUNNING)]),
        result_client=FakeResultClient(pb2, public_pb2, response_mode="store"),
    )
    _ = dispatch_svc.WorkerHeartbeat(pb2.WorkerHeartbeatRequest(worker_id="worker-2", heartbeat_at_ms=1, capacity_hint=1), FakeContext())
    ctx = FakeContext()
    dispatch = dispatch_svc.FetchWork(pb2.FetchWorkRequest(worker_id="worker-2"), ctx)
    checks.append(
        CheckResult(
            "fetch_dispatch_after_cas",
            ctx.code == grpc.StatusCode.OK
            and dispatch.assigned
            and dispatch.job_id == "job-1"
            and dispatch.spec.job_type == "dispatch-type",
            f"code={ctx.code.name}, assigned={dispatch.assigned}, job_id={dispatch.job_id}, job_type={dispatch.spec.job_type}",
        )
    )

    # 4) CAS mismatch rescue path (job still QUEUED -> re-enqueue once).
    rescue_queue = FakeQueueClient(pb2, items=["job-race"])
    rescue_records = {"job-race": {"status": public_pb2.QUEUED, "job_type": "rescue-type"}}
    rescue_svc = CoordinatorServicer(
        config=cfg,
        queue_client=rescue_queue,
        job_client=FakeJobClient(pb2, public_pb2, records=rescue_records, transitions=[(False, public_pb2.RUNNING)]),
        result_client=FakeResultClient(pb2, public_pb2, response_mode="store"),
    )
    _ = rescue_svc.WorkerHeartbeat(pb2.WorkerHeartbeatRequest(worker_id="worker-3", heartbeat_at_ms=1, capacity_hint=1), FakeContext())
    ctx = FakeContext()
    rescue = rescue_svc.FetchWork(pb2.FetchWorkRequest(worker_id="worker-3"), ctx)
    checks.append(
        CheckResult(
            "fetch_cas_rescue",
            ctx.code == grpc.StatusCode.OK
            and (not rescue.assigned)
            and rescue.retry_after_ms == 200
            and rescue_queue.reenqueue_calls == ["job-race"],
            f"code={ctx.code.name}, assigned={rescue.assigned}, reenqueue={rescue_queue.reenqueue_calls}",
        )
    )

    # 5) Outcome terminalization success path.
    outcome_records = {"job-outcome": {"status": public_pb2.RUNNING, "job_type": "ot"}}
    outcome_result = FakeResultClient(pb2, public_pb2, response_mode="store")
    outcome_svc = CoordinatorServicer(
        config=cfg,
        queue_client=FakeQueueClient(pb2),
        job_client=FakeJobClient(pb2, public_pb2, records=outcome_records, transitions=[(True, public_pb2.DONE)]),
        result_client=outcome_result,
    )
    ctx = FakeContext()
    outcome_ok = outcome_svc.ReportWorkOutcome(
        pb2.ReportWorkOutcomeRequest(
            worker_id="worker-4",
            job_id="job-outcome",
            outcome=public_pb2.JOB_OUTCOME_SUCCEEDED,
            runtime_ms=9,
            output_summary="ok",
            output_bytes=b"done",
            checksum="abc",
        ),
        ctx,
    )
    checks.append(
        CheckResult(
            "outcome_terminalize_success",
            ctx.code == grpc.StatusCode.OK and outcome_ok.accepted and len(outcome_result.calls) == 1,
            f"code={ctx.code.name}, accepted={outcome_ok.accepted}, result_calls={len(outcome_result.calls)}",
        )
    )

    # 6) Benign terminal race path: StoreResult already exists + terminal CAS mismatch.
    race_records = {"job-race-term": {"status": public_pb2.DONE, "job_type": "rt"}}
    race_svc = CoordinatorServicer(
        config=cfg,
        queue_client=FakeQueueClient(pb2),
        job_client=FakeJobClient(pb2, public_pb2, records=race_records, transitions=[(False, public_pb2.DONE)]),
        result_client=FakeResultClient(pb2, public_pb2, response_mode="already_exists"),
    )
    ctx = FakeContext()
    outcome_race = race_svc.ReportWorkOutcome(
        pb2.ReportWorkOutcomeRequest(
            worker_id="worker-5",
            job_id="job-race-term",
            outcome=public_pb2.JOB_OUTCOME_SUCCEEDED,
            runtime_ms=10,
            output_summary="dup",
            output_bytes=b"",
            checksum="",
        ),
        ctx,
    )
    checks.append(
        CheckResult(
            "outcome_terminal_race_benign",
            ctx.code == grpc.StatusCode.OK and outcome_race.accepted,
            f"code={ctx.code.name}, accepted={outcome_race.accepted}",
        )
    )

    # 7) Invalid outcome validation path.
    ctx = FakeContext()
    invalid_outcome = outcome_svc.ReportWorkOutcome(
        pb2.ReportWorkOutcomeRequest(
            worker_id="worker-4",
            job_id="job-outcome",
            outcome=public_pb2.JOB_OUTCOME_UNSPECIFIED,
        ),
        ctx,
    )
    checks.append(
        CheckResult(
            "outcome_invalid_argument",
            ctx.code == grpc.StatusCode.INVALID_ARGUMENT and (not invalid_outcome.accepted),
            f"code={ctx.code.name}, accepted={invalid_outcome.accepted}",
        )
    )

    return _print_summary_and_exit(checks)


if __name__ == "__main__":
    raise SystemExit(main())
