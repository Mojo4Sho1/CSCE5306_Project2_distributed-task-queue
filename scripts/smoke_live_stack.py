#!/usr/bin/env python3
"""
Live smoke probes against an already-running Design A stack.

This script does not start/stop services; it validates that exposed gRPC
surfaces are reachable and return expected responses for current implementation
phase (mixed: implemented Job service + skeleton others).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Tuple

import grpc


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _expect_unimplemented(name: str, rpc_call: Callable[[], object]) -> CheckResult:
    try:
        _ = rpc_call()
        return CheckResult(
            name=name,
            passed=False,
            detail="returned OK; expected UNIMPLEMENTED during skeleton phase",
        )
    except grpc.RpcError as exc:
        code = exc.code()
        detail = exc.details() or ""
        if code == grpc.StatusCode.UNIMPLEMENTED:
            return CheckResult(
                name=name,
                passed=True,
                detail=f"UNIMPLEMENTED ({detail})" if detail else "UNIMPLEMENTED",
            )
        return CheckResult(
            name=name,
            passed=False,
            detail=f"{code.name}: {detail}" if detail else code.name,
        )


def _expect_ok(name: str, rpc_call: Callable[[], object], validator: Callable[[object], bool], detail_fn: Callable[[object], str]) -> CheckResult:
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


def main() -> int:
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
        checks.append(
            _expect_unimplemented(
                "gateway.SubmitJob",
                lambda: stub.SubmitJob(
                    public_pb2.SubmitJobRequest(
                        spec=public_pb2.JobSpec(job_type="smoke", work_duration_ms=1, payload_size_bytes=0),
                    ),
                    timeout=args.rpc_timeout,
                ),
            )
        )

    with grpc.insecure_channel(f"{args.host}:{args.job_port}") as channel:
        stub = internal_pb2_grpc.JobInternalServiceStub(channel)
        checks.append(
            _expect_ok(
                "job.CreateJob",
                lambda: stub.CreateJob(
                    internal_pb2.CreateJobRequest(
                        spec={
                            "job_type": "smoke",
                            "work_duration_ms": 1,
                            "payload_size_bytes": 0,
                        },
                        client_request_id="",
                    ),
                    timeout=args.rpc_timeout,
                ),
                lambda resp: bool(resp.job_id) and resp.status == public_pb2.QUEUED,
                lambda resp: f"job_id={resp.job_id}, status={resp.status}",
            )
        )

    with grpc.insecure_channel(f"{args.host}:{args.queue_port}") as channel:
        stub = internal_pb2_grpc.QueueInternalServiceStub(channel)
        checks.append(
            _expect_unimplemented(
                "queue.EnqueueJob",
                lambda: stub.EnqueueJob(
                    internal_pb2.EnqueueJobRequest(job_id="smoke-job", enqueued_at_ms=0),
                    timeout=args.rpc_timeout,
                ),
            )
        )

    with grpc.insecure_channel(f"{args.host}:{args.coordinator_port}") as channel:
        stub = internal_pb2_grpc.CoordinatorInternalServiceStub(channel)
        checks.append(
            _expect_unimplemented(
                "coordinator.WorkerHeartbeat",
                lambda: stub.WorkerHeartbeat(
                    internal_pb2.WorkerHeartbeatRequest(
                        worker_id="smoke-worker",
                        heartbeat_at_ms=0,
                        capacity_hint=1,
                    ),
                    timeout=args.rpc_timeout,
                ),
            )
        )

    with grpc.insecure_channel(f"{args.host}:{args.result_port}") as channel:
        stub = internal_pb2_grpc.ResultInternalServiceStub(channel)
        checks.append(
            _expect_unimplemented(
                "result.StoreResult",
                lambda: stub.StoreResult(
                    internal_pb2.StoreResultRequest(
                        job_id="smoke-job",
                        terminal_status=0,
                        runtime_ms=0,
                        output_summary="",
                        output_bytes=b"",
                        checksum="",
                    ),
                    timeout=args.rpc_timeout,
                ),
            )
        )

    return _print_summary(checks)


if __name__ == "__main__":
    raise SystemExit(main())
