#!/usr/bin/env python3
"""
Smoke test for implemented Job service behavior.

This validates key v1 semantics:
- CreateJob happy path + idempotent dedup behavior
- GetJobRecord success + NOT_FOUND path
- ListJobRecords sort/pagination
- TransitionJobStatus CAS + invalid-transition handling
- SetCancelRequested + DeleteJobIfStatus behavior
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import grpc


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _prepend_pythonpath(env: dict, *paths: Path) -> None:
    existing = env.get("PYTHONPATH", "")
    prefix = os.pathsep.join(str(p) for p in paths)
    env["PYTHONPATH"] = f"{prefix}{os.pathsep}{existing}" if existing else prefix


def _wait_for_port(host: str, port: int, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _wait_for_grpc_ready(addr: str, timeout_s: float) -> Tuple[bool, str]:
    deadline = time.time() + timeout_s
    last_err = "unknown error"
    while time.time() < deadline:
        try:
            with grpc.insecure_channel(addr) as channel:
                grpc.channel_ready_future(channel).result(timeout=0.8)
                return True, "channel ready"
        except Exception as exc:
            last_err = str(exc)
            time.sleep(0.2)
    return False, last_err


def _terminate_process(proc: subprocess.Popen, timeout_s: float = 5.0) -> Tuple[bool, str]:
    if proc.poll() is not None:
        return True, "already exited"
    try:
        proc.terminate()
        proc.wait(timeout=timeout_s)
        return True, f"terminated with code {proc.returncode}"
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)
        return False, "did not terminate in time; killed"


def _read_remaining_output(proc: subprocess.Popen) -> str:
    try:
        if proc.stdout is None:
            return ""
        return proc.stdout.read() or ""
    except Exception:
        return ""


def _print_summary_and_exit(checks: List[CheckResult]) -> int:
    print("\n=== Job Behavior Smoke Test Summary ===")
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
    parser = argparse.ArgumentParser(description="Job behavior smoke test")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=50052)
    parser.add_argument("--startup-timeout", type=float, default=15.0)
    parser.add_argument("--rpc-timeout", type=float, default=2.0)
    args = parser.parse_args()

    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import taskqueue_internal_pb2 as pb2
    import taskqueue_internal_pb2_grpc as pb2_grpc
    import taskqueue_public_pb2 as public_pb2

    env = os.environ.copy()
    _prepend_pythonpath(env, repo_root, generated_dir)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("LOG_LEVEL", "INFO")
    env.setdefault("SERVICE_NAME", "job")
    env["JOB_PORT"] = str(args.port)
    env["MAX_DEDUP_KEYS"] = "3"

    cmd = [sys.executable, "-m", "services.job.main"]
    checks: List[CheckResult] = []
    proc: subprocess.Popen | None = None

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        time.sleep(0.4)
        alive = proc.poll() is None
        checks.append(CheckResult("process_start", alive, "job process is running" if alive else f"exited early {proc.returncode}"))
        if not alive:
            logs = _read_remaining_output(proc)
            if logs.strip():
                print(logs.rstrip())
            return _print_summary_and_exit(checks)

        port_ok = _wait_for_port(args.host, args.port, timeout_s=args.startup_timeout)
        checks.append(CheckResult("tcp_port_open", port_ok, f"{args.host}:{args.port} reachable" if port_ok else "port not reachable"))
        if not port_ok:
            return _print_summary_and_exit(checks)

        addr = f"{args.host}:{args.port}"
        grpc_ok, detail = _wait_for_grpc_ready(addr, timeout_s=args.startup_timeout)
        checks.append(CheckResult("grpc_ready", grpc_ok, detail if grpc_ok else f"not ready: {detail}"))
        if not grpc_ok:
            return _print_summary_and_exit(checks)

        with grpc.insecure_channel(addr) as channel:
            stub = pb2_grpc.JobInternalServiceStub(channel)

            create_1 = stub.CreateJob(
                pb2.CreateJobRequest(
                    spec=public_pb2.JobSpec(job_type="smoke-a", work_duration_ms=10, payload_size_bytes=1),
                    client_request_id="dedup-1",
                ),
                timeout=args.rpc_timeout,
            )
            checks.append(
                CheckResult(
                    "create_job",
                    bool(create_1.job_id) and create_1.status == public_pb2.QUEUED,
                    f"job_id={create_1.job_id}, status={create_1.status}",
                )
            )

            create_2 = stub.CreateJob(
                pb2.CreateJobRequest(
                    spec=public_pb2.JobSpec(job_type="smoke-a", work_duration_ms=10, payload_size_bytes=1),
                    client_request_id="dedup-1",
                ),
                timeout=args.rpc_timeout,
            )
            checks.append(
                CheckResult(
                    "dedup_same_payload",
                    create_2.job_id == create_1.job_id,
                    f"repeat_job_id={create_2.job_id}",
                )
            )

            mismatch_ok = False
            mismatch_detail = ""
            try:
                stub.CreateJob(
                    pb2.CreateJobRequest(
                        spec=public_pb2.JobSpec(job_type="smoke-b", work_duration_ms=10, payload_size_bytes=1),
                        client_request_id="dedup-1",
                    ),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                mismatch_ok = exc.code() == grpc.StatusCode.FAILED_PRECONDITION
                mismatch_detail = exc.code().name
            checks.append(CheckResult("dedup_payload_mismatch", mismatch_ok, mismatch_detail or "expected FAILED_PRECONDITION"))

            get_ok = False
            rec = stub.GetJobRecord(pb2.GetJobRecordRequest(job_id=create_1.job_id), timeout=args.rpc_timeout)
            get_ok = rec.summary.job_id == create_1.job_id and rec.summary.status == public_pb2.QUEUED
            checks.append(CheckResult("get_job_record", get_ok, f"status={rec.summary.status}"))

            not_found_ok = False
            try:
                stub.GetJobRecord(pb2.GetJobRecordRequest(job_id="missing-job"), timeout=args.rpc_timeout)
            except grpc.RpcError as exc:
                not_found_ok = exc.code() == grpc.StatusCode.NOT_FOUND
            checks.append(CheckResult("get_job_record_not_found", not_found_ok, "NOT_FOUND expected"))

            invalid_transition_ok = False
            try:
                stub.TransitionJobStatus(
                    pb2.TransitionJobStatusRequest(
                        job_id=create_1.job_id,
                        expected_from_status=public_pb2.QUEUED,
                        to_status=public_pb2.DONE,
                        actor="smoke",
                        reason="invalid",
                    ),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                invalid_transition_ok = exc.code() == grpc.StatusCode.INVALID_ARGUMENT
            checks.append(CheckResult("transition_invalid", invalid_transition_ok, "INVALID_ARGUMENT expected"))

            missing_expected_ok = False
            try:
                stub.TransitionJobStatus(
                    pb2.TransitionJobStatusRequest(
                        job_id=create_1.job_id,
                        expected_from_status=public_pb2.JOB_STATUS_UNSPECIFIED,
                        to_status=public_pb2.RUNNING,
                        actor="smoke",
                        reason="invalid",
                    ),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                missing_expected_ok = exc.code() == grpc.StatusCode.INVALID_ARGUMENT
            checks.append(CheckResult("transition_missing_expected", missing_expected_ok, "INVALID_ARGUMENT expected"))

            t1 = stub.TransitionJobStatus(
                pb2.TransitionJobStatusRequest(
                    job_id=create_1.job_id,
                    expected_from_status=public_pb2.QUEUED,
                    to_status=public_pb2.RUNNING,
                    actor="smoke",
                    reason="start",
                ),
                timeout=args.rpc_timeout,
            )
            checks.append(CheckResult("transition_to_running", t1.applied and t1.current_status == public_pb2.RUNNING, f"applied={t1.applied}"))

            t2 = stub.TransitionJobStatus(
                pb2.TransitionJobStatusRequest(
                    job_id=create_1.job_id,
                    expected_from_status=public_pb2.RUNNING,
                    to_status=public_pb2.DONE,
                    actor="smoke",
                    reason="finish",
                ),
                timeout=args.rpc_timeout,
            )
            checks.append(CheckResult("transition_to_done", t2.applied and t2.current_status == public_pb2.DONE, f"applied={t2.applied}"))

            cancel_terminal = stub.SetCancelRequested(
                pb2.SetCancelRequestedRequest(job_id=create_1.job_id, cancel_requested=True, reason="noop"),
                timeout=args.rpc_timeout,
            )
            checks.append(CheckResult("set_cancel_terminal", (not cancel_terminal.applied) and cancel_terminal.current_status == public_pb2.DONE, f"applied={cancel_terminal.applied}"))

            create_3 = stub.CreateJob(
                pb2.CreateJobRequest(
                    spec=public_pb2.JobSpec(job_type="smoke-c", work_duration_ms=5, payload_size_bytes=1),
                    client_request_id="dedup-2",
                ),
                timeout=args.rpc_timeout,
            )
            create_4 = stub.CreateJob(
                pb2.CreateJobRequest(
                    spec=public_pb2.JobSpec(job_type="smoke-d", work_duration_ms=5, payload_size_bytes=1),
                    client_request_id="dedup-3",
                ),
                timeout=args.rpc_timeout,
            )
            _ = (create_3, create_4)

            lst_page1 = stub.ListJobRecords(
                pb2.ListJobRecordsRequest(
                    page=public_pb2.PageRequest(page_size=2, page_token="0"),
                    sort=public_pb2.CREATED_AT_ASC,
                ),
                timeout=args.rpc_timeout,
            )
            page1_ok = len(lst_page1.jobs) == 2 and lst_page1.page.next_page_token != ""
            checks.append(CheckResult("list_page_1", page1_ok, f"count={len(lst_page1.jobs)}, next={lst_page1.page.next_page_token}"))

            lst_page2 = stub.ListJobRecords(
                pb2.ListJobRecordsRequest(
                    page=public_pb2.PageRequest(page_size=2, page_token=lst_page1.page.next_page_token),
                    sort=public_pb2.CREATED_AT_ASC,
                ),
                timeout=args.rpc_timeout,
            )
            checks.append(CheckResult("list_page_2", len(lst_page2.jobs) >= 1, f"count={len(lst_page2.jobs)}"))

            bad_token_ok = False
            try:
                stub.ListJobRecords(
                    pb2.ListJobRecordsRequest(
                        page=public_pb2.PageRequest(page_size=2, page_token="bad-token"),
                    ),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                bad_token_ok = exc.code() == grpc.StatusCode.INVALID_ARGUMENT
            checks.append(CheckResult("list_bad_token", bad_token_ok, "INVALID_ARGUMENT expected"))

            bad_filter_ok = False
            try:
                stub.ListJobRecords(
                    pb2.ListJobRecordsRequest(
                        status_filter=[public_pb2.JOB_STATUS_UNSPECIFIED],
                        page=public_pb2.PageRequest(page_size=2, page_token="0"),
                    ),
                    timeout=args.rpc_timeout,
                )
            except grpc.RpcError as exc:
                bad_filter_ok = exc.code() == grpc.StatusCode.INVALID_ARGUMENT
            checks.append(CheckResult("list_bad_filter", bad_filter_ok, "INVALID_ARGUMENT expected"))

            delete_miss = stub.DeleteJobIfStatus(
                pb2.DeleteJobIfStatusRequest(job_id=create_1.job_id, expected_status=public_pb2.QUEUED),
                timeout=args.rpc_timeout,
            )
            checks.append(CheckResult("delete_status_mismatch", (not delete_miss.deleted) and delete_miss.current_status == public_pb2.DONE, f"deleted={delete_miss.deleted}"))

            delete_hit = stub.DeleteJobIfStatus(
                pb2.DeleteJobIfStatusRequest(job_id=create_4.job_id, expected_status=public_pb2.QUEUED),
                timeout=args.rpc_timeout,
            )
            checks.append(CheckResult("delete_status_match", delete_hit.deleted, f"deleted={delete_hit.deleted}"))

        still_alive = proc.poll() is None
        checks.append(CheckResult("process_stability", still_alive, "job still running" if still_alive else "job exited unexpectedly"))

    finally:
        if proc is not None:
            ok, detail = _terminate_process(proc)
            checks.append(CheckResult("graceful_shutdown", ok, detail))

    return _print_summary_and_exit(checks)


if __name__ == "__main__":
    raise SystemExit(main())
