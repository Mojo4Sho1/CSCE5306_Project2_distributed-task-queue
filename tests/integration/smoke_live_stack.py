#!/usr/bin/env python3
"""
Live smoke probes against an already-running Design A stack.

This script does not start/stop services. It validates:
- public Gateway flows (submit/status/result/cancel/list)
- core internal service reachability (Job/Queue/Coordinator/Result)
"""

from __future__ import annotations

import argparse
import time
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

import grpc

_TERMINAL_STATUSES = {3, 4, 5}


@dataclass
class CheckResult:
    """One smoke-check result record."""
    name: str
    passed: bool
    detail: str


def _repo_root() -> Path:
    """Return repository root for import bootstrapping."""
    return Path(__file__).resolve().parents[2]


def _expect_ok(name: str, rpc_call: Callable[[], object], validator: Callable[[object], bool], detail_fn: Callable[[object], str]) -> CheckResult:
    """Assert expected RPC outcome for this check."""
    try:
        response = rpc_call()
        passed = validator(response)
        return CheckResult(
            name=name,
            passed=passed,
            detail=detail_fn(response),
        )
    except grpc.RpcError as exc:
        return CheckResult(
            name=name,
            passed=False,
            detail=f"{exc.code().name}: {exc.details() or ''}".strip(),
        )


def _print_summary(checks: List[CheckResult]) -> int:
    """Print a concise pass/fail summary for smoke checks."""
    print("\n=== Live Stack Smoke Probe Summary ===")
    max_name = max((len(c.name) for c in checks), default=10)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<{max_name}}  {c.detail}")
        if not c.passed:
            all_passed = False
    print("======================================")
    if all_passed:
        print("RESULT: PASS")
        return 0
    print("RESULT: FAIL")
    return 1


def _status_name(pb2_module, status_value: int) -> str:
    """Return status name text for readable assertions."""
    try:
        return pb2_module.JobStatus.Name(int(status_value))
    except Exception:
        return str(int(status_value))


def main() -> int:
    """Run the smoke test script and return an exit code."""
    parser = argparse.ArgumentParser(description="Live stack smoke probes")
    parser.add_argument("--host", default="127.0.0.1", help="Host for mapped service ports")
    parser.add_argument("--gateway-port", type=int, default=50051)
    parser.add_argument("--job-port", type=int, default=50052)
    parser.add_argument("--queue-port", type=int, default=50053)
    parser.add_argument("--coordinator-port", type=int, default=50054)
    parser.add_argument("--result-port", type=int, default=50055)
    parser.add_argument("--rpc-timeout", type=float, default=2.0)
    args = parser.parse_args()

    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import taskqueue_internal_pb2 as internal_pb2
    import taskqueue_internal_pb2_grpc as internal_pb2_grpc
    import taskqueue_public_pb2 as public_pb2
    import taskqueue_public_pb2_grpc as public_pb2_grpc

    checks: List[CheckResult] = []

    with grpc.insecure_channel(f"{args.host}:{args.gateway_port}") as channel:
        stub = public_pb2_grpc.TaskQueuePublicServiceStub(channel)
        submit_resp = None
        try:
            submit_spec = public_pb2.JobSpec(
                job_type=f"smoke-live-{int(time.time() * 1000)}",
                work_duration_ms=20,
                payload_size_bytes=8,
            )
            submit_resp = stub.SubmitJob(
                public_pb2.SubmitJobRequest(
                    spec=submit_spec,
                ),
                timeout=args.rpc_timeout,
            )
            submit = CheckResult(
                name="gateway.SubmitJob",
                passed=bool(submit_resp.job_id) and submit_resp.initial_status == public_pb2.QUEUED,
                detail=f"job_id={submit_resp.job_id}, status={_status_name(public_pb2, submit_resp.initial_status)}",
            )
        except grpc.RpcError as exc:
            submit = CheckResult(
                name="gateway.SubmitJob",
                passed=False,
                detail=f"{exc.code().name}: {exc.details() or ''}".strip(),
            )
        checks.append(submit)

        if submit.passed and submit_resp is not None:
            checks.append(
                _expect_ok(
                    "gateway.GetJobStatus",
                    lambda: stub.GetJobStatus(
                        public_pb2.GetJobStatusRequest(job_id=submit_resp.job_id),
                        timeout=args.rpc_timeout,
                    ),
                    lambda resp: resp.job_id == submit_resp.job_id and resp.status in {
                        public_pb2.QUEUED,
                        public_pb2.RUNNING,
                        public_pb2.CANCELED,
                    },
                    lambda resp: f"job_id={resp.job_id}, status={_status_name(public_pb2, resp.status)}",
                )
            )
            checks.append(
                _expect_ok(
                    "gateway.GetJobResult.not_ready_or_terminal",
                    lambda: stub.GetJobResult(
                        public_pb2.GetJobResultRequest(job_id=submit_resp.job_id),
                        timeout=args.rpc_timeout,
                    ),
                    lambda resp: resp.job_id == submit_resp.job_id and (
                        (not resp.result_ready and resp.terminal_status == public_pb2.JOB_STATUS_UNSPECIFIED)
                        or (resp.result_ready and resp.terminal_status in _TERMINAL_STATUSES)
                    ),
                    lambda resp: (
                        f"job_id={resp.job_id}, ready={resp.result_ready}, "
                        f"terminal={_status_name(public_pb2, resp.terminal_status)}"
                    ),
                )
            )
            checks.append(
                _expect_ok(
                    "gateway.CancelJob",
                    lambda: stub.CancelJob(
                        public_pb2.CancelJobRequest(
                            job_id=submit_resp.job_id,
                            reason="smoke_live_stack_cancel",
                        ),
                        timeout=args.rpc_timeout,
                    ),
                    lambda resp: (
                        resp.job_id == submit_resp.job_id
                        and resp.accepted
                        and resp.current_status in {
                            public_pb2.QUEUED,
                            public_pb2.RUNNING,
                            public_pb2.CANCELED,
                            public_pb2.DONE,
                            public_pb2.FAILED,
                        }
                    ),
                    lambda resp: (
                        f"job_id={resp.job_id}, accepted={resp.accepted}, "
                        f"current={_status_name(public_pb2, resp.current_status)}, "
                        f"already_terminal={resp.already_terminal}"
                    ),
                )
            )
            checks.append(
                _expect_ok(
                    "gateway.ListJobs",
                    lambda: stub.ListJobs(
                        public_pb2.ListJobsRequest(
                            page=public_pb2.PageRequest(page_size=25),
                            sort=public_pb2.CREATED_AT_DESC,
                        ),
                        timeout=args.rpc_timeout,
                    ),
                    lambda resp: any(item.job_id == submit_resp.job_id for item in resp.jobs),
                    lambda resp: f"jobs_returned={len(resp.jobs)}",
                )
            )

    with grpc.insecure_channel(f"{args.host}:{args.job_port}") as channel:
        stub = internal_pb2_grpc.JobInternalServiceStub(channel)
        checks.append(
            _expect_ok(
                "job.ListJobRecords",
                lambda: stub.ListJobRecords(
                    internal_pb2.ListJobRecordsRequest(
                        page=public_pb2.PageRequest(page_size=1),
                        sort=public_pb2.CREATED_AT_DESC,
                    ),
                    timeout=args.rpc_timeout,
                ),
                lambda resp: True,
                lambda resp: f"jobs_returned={len(resp.jobs)}",
            )
        )

    with grpc.insecure_channel(f"{args.host}:{args.queue_port}") as channel:
        stub = internal_pb2_grpc.QueueInternalServiceStub(channel)
        checks.append(
            _expect_ok(
                "queue.RemoveJobIfPresent",
                lambda: stub.RemoveJobIfPresent(
                    internal_pb2.RemoveJobIfPresentRequest(job_id="smoke-live-missing"),
                    timeout=args.rpc_timeout,
                ),
                lambda resp: isinstance(resp.removed, bool),
                lambda resp: f"removed={resp.removed}",
            )
        )

    with grpc.insecure_channel(f"{args.host}:{args.coordinator_port}") as channel:
        stub = internal_pb2_grpc.CoordinatorInternalServiceStub(channel)
        checks.append(
            _expect_ok(
                "coordinator.WorkerHeartbeat",
                lambda: stub.WorkerHeartbeat(
                    internal_pb2.WorkerHeartbeatRequest(
                        worker_id="smoke-worker",
                        heartbeat_at_ms=0,
                        capacity_hint=1,
                    ),
                    timeout=args.rpc_timeout,
                ),
                lambda resp: bool(resp.accepted) and int(resp.next_heartbeat_in_ms) > 0,
                lambda resp: f"accepted={resp.accepted}, next={resp.next_heartbeat_in_ms}",
            )
        )

    with grpc.insecure_channel(f"{args.host}:{args.result_port}") as channel:
        stub = internal_pb2_grpc.ResultInternalServiceStub(channel)
        checks.append(
            _expect_ok(
                "result.GetResult",
                lambda: stub.GetResult(
                    internal_pb2.GetResultRequest(job_id="smoke-live-missing"),
                    timeout=args.rpc_timeout,
                ),
                lambda resp: (not resp.found) and resp.job_id == "smoke-live-missing",
                lambda resp: f"found={resp.found}, job_id={resp.job_id}",
            )
        )

    return _print_summary(checks)


if __name__ == "__main__":
    raise SystemExit(main())
