#!/usr/bin/env python3
"""
Live integration smoke for terminalization through the real worker process.

Flow:
1) Submit jobs through Gateway.
2) Wait for worker-driven RUNNING -> terminal progression.
3) Verify terminal status/result retrieval through public API.
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
    name: str
    passed: bool
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _status_name(pb2_module, status_value: int) -> str:
    try:
        return pb2_module.JobStatus.Name(int(status_value))
    except Exception:
        return str(int(status_value))


def _expect_ok(
    name: str,
    rpc_call: Callable[[], object],
    validator: Callable[[object], bool],
    detail_fn: Callable[[object], str],
) -> CheckResult:
    try:
        response = rpc_call()
        return CheckResult(name=name, passed=validator(response), detail=detail_fn(response))
    except grpc.RpcError as exc:
        return CheckResult(
            name=name,
            passed=False,
            detail=f"{exc.code().name}: {exc.details() or ''}".strip(),
        )


def _print_summary(checks: List[CheckResult]) -> int:
    print("\n=== Integration Terminal Path Smoke Summary ===")
    max_name = max((len(c.name) for c in checks), default=10)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<{max_name}}  {c.detail}")
        if not c.passed:
            all_passed = False
    print("===============================================")
    if all_passed:
        print("RESULT: PASS")
        return 0
    print("RESULT: FAIL")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Integration smoke for worker-driven terminalization path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--gateway-port", type=int, default=50051)
    parser.add_argument("--rpc-timeout", type=float, default=2.0)
    parser.add_argument("--submit-count", type=int, default=2)
    parser.add_argument("--status-poll-attempts", type=int, default=80)
    parser.add_argument("--result-poll-attempts", type=int, default=40)
    parser.add_argument("--poll-sleep-ms", type=int, default=100)
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
    submitted_job_ids: List[str] = []
    terminal_job_id = ""
    terminal_status = public_pb2.JOB_STATUS_UNSPECIFIED
    saw_running = False

    with grpc.insecure_channel(f"{args.host}:{args.gateway_port}") as gateway_channel:
        gateway = public_pb2_grpc.TaskQueuePublicServiceStub(gateway_channel)
        for idx in range(max(1, int(args.submit_count))):
            try:
                submit_resp = gateway.SubmitJob(
                    public_pb2.SubmitJobRequest(
                        spec=public_pb2.JobSpec(
                            job_type=f"integration-terminal-{idx}",
                            work_duration_ms=120,
                            payload_size_bytes=16,
                            labels={"suite": "smoke_integration_terminal_path"},
                        ),
                        client_request_id=f"smoke-integration-{int(time.time() * 1000)}-{idx}",
                    ),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                checks.append(
                    CheckResult(
                        f"submit_{idx + 1}",
                        False,
                        f"{exc.code().name}: {exc.details() or ''}".strip(),
                    )
                )
                continue

            submit_ok = bool(submit_resp.job_id) and submit_resp.initial_status == public_pb2.QUEUED
            checks.append(
                CheckResult(
                    f"submit_{idx + 1}",
                    submit_ok,
                    f"job_id={submit_resp.job_id}, status={_status_name(public_pb2, submit_resp.initial_status)}",
                )
            )
            if submit_ok:
                submitted_job_ids.append(submit_resp.job_id)

    if not submitted_job_ids:
        checks.append(CheckResult("integration_precondition", False, "no submitted jobs available"))
        return _print_summary(checks)

    with grpc.insecure_channel(f"{args.host}:{args.gateway_port}") as gateway_channel:
        gateway = public_pb2_grpc.TaskQueuePublicServiceStub(gateway_channel)
        terminal_statuses = {public_pb2.DONE, public_pb2.FAILED, public_pb2.CANCELED}
        status_resp = None
        for _ in range(max(1, int(args.status_poll_attempts))):
            for job_id in submitted_job_ids:
                status_resp = gateway.GetJobStatus(
                    public_pb2.GetJobStatusRequest(job_id=job_id),
                    timeout=args.rpc_timeout,
                )
                if status_resp.status == public_pb2.RUNNING:
                    saw_running = True
                if status_resp.status in terminal_statuses:
                    terminal_job_id = job_id
                    terminal_status = status_resp.status
                    break
            if terminal_job_id:
                break
            time.sleep(max(20, int(args.poll_sleep_ms)) / 1000.0)

        checks.append(
            CheckResult(
                "gateway.GetJobStatus.running_seen",
                saw_running,
                f"submitted={len(submitted_job_ids)}, running_seen={saw_running}",
            )
        )
        checks.append(
            CheckResult(
                "gateway.GetJobStatus.terminal",
                bool(terminal_job_id),
                f"job_id={terminal_job_id or '<none>'}, status={_status_name(public_pb2, terminal_status)}",
            )
        )

        if not terminal_job_id:
            return _print_summary(checks)

        result_resp = None
        for _ in range(max(1, int(args.result_poll_attempts))):
            result_resp = gateway.GetJobResult(
                public_pb2.GetJobResultRequest(job_id=terminal_job_id),
                timeout=args.rpc_timeout,
            )
            if result_resp.result_ready:
                break
            time.sleep(max(20, int(args.poll_sleep_ms)) / 1000.0)

        if result_resp is None:
            checks.append(CheckResult("gateway.GetJobResult.terminal_ready", False, "no result response"))
        else:
            checksum_ok = result_resp.checksum == hashlib.sha256(bytes(result_resp.output_bytes)).hexdigest()
            checks.append(
                CheckResult(
                    "gateway.GetJobResult.terminal_ready",
                    (
                        result_resp.job_id == terminal_job_id
                        and result_resp.result_ready
                        and result_resp.terminal_status == terminal_status
                        and checksum_ok
                    ),
                    (
                        f"job_id={result_resp.job_id}, ready={result_resp.result_ready}, "
                        f"terminal={_status_name(public_pb2, result_resp.terminal_status)}, "
                        f"runtime_ms={result_resp.runtime_ms}, checksum_ok={checksum_ok}"
                    ),
                )
            )
            checks.append(
                CheckResult(
                    "gateway.GetJobResult.worker_signature",
                    "simulated_success worker_id=" in result_resp.output_summary,
                    f"output_summary={result_resp.output_summary}",
                )
            )

    return _print_summary(checks)


if __name__ == "__main__":
    raise SystemExit(main())
