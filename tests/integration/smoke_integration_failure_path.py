#!/usr/bin/env python3
"""
Live integration smoke for deterministic worker-driven FAILED terminalization.

Flow:
1) Submit a job whose job_type contains "force-fail".
2) Wait for RUNNING -> FAILED through Gateway.GetJobStatus.
3) Verify failure reason propagation and terminal result envelope consistency.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

import grpc


@dataclass
class CheckResult:
    """Check result state and behavior."""
    name: str
    passed: bool
    detail: str


def _repo_root() -> Path:
    """Internal helper to  repo root."""
    return Path(__file__).resolve().parents[2]


def _status_name(pb2_module, status_value: int) -> str:
    """Return a human-readable label for a status value."""
    try:
        return pb2_module.JobStatus.Name(int(status_value))
    except Exception:
        return str(int(status_value))


def _print_summary(checks: List[CheckResult]) -> int:
    """Print structured command output for operators."""
    print("\n=== Integration Failure Path Smoke Summary ===")
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


def _expect_ok(
    name: str,
    rpc_call: Callable[[], object],
    validator: Callable[[object], bool],
    detail_fn: Callable[[object], str],
) -> CheckResult:
    """Assert expected behavior for the smoke check."""
    try:
        response = rpc_call()
        return CheckResult(name=name, passed=validator(response), detail=detail_fn(response))
    except grpc.RpcError as exc:
        return CheckResult(
            name=name,
            passed=False,
            detail=f"{exc.code().name}: {exc.details() or ''}".strip(),
        )


def main() -> int:
    """Run the command-line entrypoint."""
    parser = argparse.ArgumentParser(description="Integration smoke for worker-driven FAILED terminalization path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--gateway-port", type=int, default=50051)
    parser.add_argument("--rpc-timeout", type=float, default=2.0)
    parser.add_argument("--status-poll-attempts", type=int, default=80)
    parser.add_argument("--result-poll-attempts", type=int, default=40)
    parser.add_argument("--poll-sleep-ms", type=int, default=100)
    parser.add_argument("--failure-marker", default="force-fail")
    args = parser.parse_args()

    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import taskqueue_public_pb2 as public_pb2
    import taskqueue_public_pb2_grpc as public_pb2_grpc

    checks: List[CheckResult] = []
    failure_reason = ""
    saw_running = False

    with grpc.insecure_channel(f"{args.host}:{args.gateway_port}") as gateway_channel:
        gateway = public_pb2_grpc.TaskQueuePublicServiceStub(gateway_channel)
        submit_resp = None
        try:
            submit_resp = gateway.SubmitJob(
                public_pb2.SubmitJobRequest(
                    spec=public_pb2.JobSpec(
                        job_type=f"integration-{args.failure_marker}-{int(time.time() * 1000)}",
                        work_duration_ms=120,
                        payload_size_bytes=16,
                        labels={"suite": "smoke_integration_failure_path"},
                    ),
                    client_request_id=f"smoke-integration-failure-{int(time.time() * 1000)}",
                ),
                timeout=args.rpc_timeout,
            )
        except grpc.RpcError as exc:
            checks.append(
                CheckResult(
                    "submit_failure_case",
                    False,
                    f"{exc.code().name}: {exc.details() or ''}".strip(),
                )
            )
            return _print_summary(checks)

        submit_ok = bool(submit_resp.job_id) and submit_resp.initial_status == public_pb2.QUEUED
        checks.append(
            CheckResult(
                "submit_failure_case",
                submit_ok,
                f"job_id={submit_resp.job_id}, status={_status_name(public_pb2, submit_resp.initial_status)}",
            )
        )
        if not submit_ok:
            return _print_summary(checks)

        job_id = submit_resp.job_id

        terminal_seen = False
        for _ in range(max(1, int(args.status_poll_attempts))):
            status_resp = gateway.GetJobStatus(
                public_pb2.GetJobStatusRequest(job_id=job_id),
                timeout=args.rpc_timeout,
            )
            if status_resp.status == public_pb2.RUNNING:
                saw_running = True
            if status_resp.status == public_pb2.FAILED:
                terminal_seen = True
                failure_reason = status_resp.failure_reason
                break
            if status_resp.status in {public_pb2.DONE, public_pb2.CANCELED}:
                break
            time.sleep(max(20, int(args.poll_sleep_ms)) / 1000.0)

        checks.append(
            CheckResult(
                "gateway.GetJobStatus.running_seen",
                saw_running,
                f"job_id={job_id}, running_seen={saw_running}",
            )
        )
        checks.append(
            CheckResult(
                "gateway.GetJobStatus.failed_terminal",
                terminal_seen,
                f"job_id={job_id}, failed_seen={terminal_seen}, failure_reason={failure_reason or '<empty>'}",
            )
        )
        checks.append(
            CheckResult(
                "gateway.GetJobStatus.failure_reason",
                bool(failure_reason) and "simulated_failure" in failure_reason and args.failure_marker in failure_reason,
                f"failure_reason={failure_reason or '<empty>'}",
            )
        )

        if not terminal_seen:
            return _print_summary(checks)

        result_resp = None
        for _ in range(max(1, int(args.result_poll_attempts))):
            result_resp = gateway.GetJobResult(
                public_pb2.GetJobResultRequest(job_id=job_id),
                timeout=args.rpc_timeout,
            )
            if result_resp.result_ready:
                break
            time.sleep(max(20, int(args.poll_sleep_ms)) / 1000.0)

        if result_resp is None:
            checks.append(CheckResult("gateway.GetJobResult.failed_ready", False, "no result response"))
            return _print_summary(checks)

        checksum_ok = result_resp.checksum == hashlib.sha256(bytes(result_resp.output_bytes)).hexdigest()
        checks.append(
            CheckResult(
                "gateway.GetJobResult.failed_ready",
                (
                    result_resp.job_id == job_id
                    and result_resp.result_ready
                    and result_resp.terminal_status == public_pb2.FAILED
                    and checksum_ok
                ),
                (
                    f"job_id={result_resp.job_id}, ready={result_resp.result_ready}, "
                    f"terminal={_status_name(public_pb2, result_resp.terminal_status)}, checksum_ok={checksum_ok}"
                ),
            )
        )
        checks.append(
            _expect_ok(
                "gateway.GetJobResult.failure_summary",
                lambda: gateway.GetJobResult(
                    public_pb2.GetJobResultRequest(job_id=job_id),
                    timeout=args.rpc_timeout,
                ),
                lambda resp: (
                    "simulated_failure" in resp.output_summary
                    and args.failure_marker in resp.output_summary
                    and failure_reason in resp.output_summary
                ),
                lambda resp: f"output_summary={resp.output_summary}",
            )
        )

    return _print_summary(checks)


if __name__ == "__main__":
    raise SystemExit(main())
