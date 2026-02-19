#!/usr/bin/env python3
"""
Live integration smoke for terminalization across Gateway + Coordinator paths.

Flow:
1) Submit jobs through Gateway.
2) Worker-compatible client heartbeats and fetches work via Coordinator.
3) Report terminal outcome for an assigned submitted job.
4) Verify terminal status/result retrieval through public API.
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
    return Path(__file__).resolve().parents[1]


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
    parser = argparse.ArgumentParser(description="Integration smoke for terminalization path")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--gateway-port", type=int, default=50051)
    parser.add_argument("--coordinator-port", type=int, default=50054)
    parser.add_argument("--rpc-timeout", type=float, default=2.0)
    parser.add_argument("--submit-count", type=int, default=4)
    parser.add_argument("--fetch-attempts", type=int, default=40)
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
    submitted_job_ids: List[str] = []
    worker_id = f"smoke-integration-worker-{int(time.time() * 1000)}"
    matched_job_id = ""
    reported_checksum = ""
    reported_runtime_ms = 17
    reported_summary = "integration-terminal-done"
    reported_output_bytes = b"integration-output"

    with grpc.insecure_channel(f"{args.host}:{args.gateway_port}") as gateway_channel:
        gateway = public_pb2_grpc.TaskQueuePublicServiceStub(gateway_channel)
        for idx in range(max(1, int(args.submit_count))):
            try:
                submit_resp = gateway.SubmitJob(
                    public_pb2.SubmitJobRequest(
                        spec=public_pb2.JobSpec(
                            job_type=f"integration-terminal-{idx}",
                            work_duration_ms=10,
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

    with grpc.insecure_channel(f"{args.host}:{args.coordinator_port}") as coord_channel:
        coordinator = internal_pb2_grpc.CoordinatorInternalServiceStub(coord_channel)
        checks.append(
            _expect_ok(
                "coordinator.WorkerHeartbeat",
                lambda: coordinator.WorkerHeartbeat(
                    internal_pb2.WorkerHeartbeatRequest(
                        worker_id=worker_id,
                        heartbeat_at_ms=int(time.time() * 1000),
                        capacity_hint=1,
                    ),
                    timeout=args.rpc_timeout,
                ),
                lambda resp: resp.accepted and int(resp.next_heartbeat_in_ms) > 0,
                lambda resp: f"accepted={resp.accepted}, next={resp.next_heartbeat_in_ms}",
            )
        )

        submitted_set = set(submitted_job_ids)
        for _ in range(max(1, int(args.fetch_attempts))):
            try:
                fetch = coordinator.FetchWork(
                    internal_pb2.FetchWorkRequest(worker_id=worker_id),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                checks.append(
                    CheckResult(
                        "coordinator.FetchWork",
                        False,
                        f"{exc.code().name}: {exc.details() or ''}".strip(),
                    )
                )
                break

            if not fetch.assigned:
                sleep_ms = int(fetch.retry_after_ms) if int(fetch.retry_after_ms) > 0 else 75
                time.sleep(max(50, sleep_ms) / 1000.0)
                continue

            if fetch.job_id not in submitted_set:
                # Benign background queue noise; skip and continue probing.
                continue

            matched_job_id = fetch.job_id
            reported_checksum = hashlib.sha256(reported_output_bytes).hexdigest()
            try:
                report = coordinator.ReportWorkOutcome(
                    internal_pb2.ReportWorkOutcomeRequest(
                        worker_id=worker_id,
                        job_id=matched_job_id,
                        outcome=public_pb2.JOB_OUTCOME_SUCCEEDED,
                        runtime_ms=reported_runtime_ms,
                        output_summary=reported_summary,
                        output_bytes=reported_output_bytes,
                        checksum=reported_checksum,
                    ),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                checks.append(
                    CheckResult(
                        "coordinator.ReportWorkOutcome",
                        False,
                        f"{exc.code().name}: {exc.details() or ''}".strip(),
                    )
                )
                break

            checks.append(
                CheckResult(
                    "coordinator.ReportWorkOutcome",
                    bool(report.accepted),
                    f"job_id={matched_job_id}, accepted={report.accepted}",
                )
            )
            break

    checks.append(
        CheckResult(
            "coordinator.FetchWork.assigned_submitted_job",
            bool(matched_job_id),
            f"matched_job_id={matched_job_id or '<none>'}",
        )
    )

    if not matched_job_id:
        return _print_summary(checks)

    with grpc.insecure_channel(f"{args.host}:{args.gateway_port}") as gateway_channel:
        gateway = public_pb2_grpc.TaskQueuePublicServiceStub(gateway_channel)

        status_resp = None
        for _ in range(20):
            status_resp = gateway.GetJobStatus(
                public_pb2.GetJobStatusRequest(job_id=matched_job_id),
                timeout=args.rpc_timeout,
            )
            if status_resp.status == public_pb2.DONE:
                break
            time.sleep(0.1)
        if status_resp is None:
            checks.append(CheckResult("gateway.GetJobStatus.terminal", False, "no status response"))
        else:
            checks.append(
                CheckResult(
                    "gateway.GetJobStatus.terminal",
                    status_resp.job_id == matched_job_id and status_resp.status == public_pb2.DONE,
                    f"job_id={status_resp.job_id}, status={_status_name(public_pb2, status_resp.status)}",
                )
            )

        result_resp = None
        for _ in range(20):
            result_resp = gateway.GetJobResult(
                    public_pb2.GetJobResultRequest(job_id=matched_job_id),
                    timeout=args.rpc_timeout,
            )
            if result_resp.result_ready and result_resp.terminal_status == public_pb2.DONE:
                break
            time.sleep(0.1)
        if result_resp is None:
            checks.append(CheckResult("gateway.GetJobResult.terminal_ready", False, "no result response"))
        else:
            checks.append(
                CheckResult(
                    "gateway.GetJobResult.terminal_ready",
                    (
                        result_resp.job_id == matched_job_id
                        and result_resp.result_ready
                        and result_resp.terminal_status == public_pb2.DONE
                        and result_resp.runtime_ms == reported_runtime_ms
                        and result_resp.output_summary == reported_summary
                        and bytes(result_resp.output_bytes) == reported_output_bytes
                        and result_resp.checksum == reported_checksum
                    ),
                    (
                        f"job_id={result_resp.job_id}, ready={result_resp.result_ready}, "
                        f"terminal={_status_name(public_pb2, result_resp.terminal_status)}, checksum={result_resp.checksum}"
                    ),
                )
            )

    return _print_summary(checks)


if __name__ == "__main__":
    raise SystemExit(main())
