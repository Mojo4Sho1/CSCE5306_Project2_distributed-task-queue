#!/usr/bin/env python3
"""
Smoke test for implemented Queue service behavior.

This validates key v1 semantics:
- Enqueue idempotency by job_id (no duplicates)
- Dequeue destructive best-effort FIFO behavior
- RemoveJobIfPresent repeat-safe semantics
- Basic INVALID_ARGUMENT validation paths
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


def _print_summary_and_exit(checks: List[CheckResult]) -> int:
    print("\n=== Queue Behavior Smoke Test Summary ===")
    max_name = max((len(c.name) for c in checks), default=10)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<{max_name}}  {c.detail}")
        if not c.passed:
            all_passed = False
    print("========================================")
    if all_passed:
        print("RESULT: PASS")
        return 0
    print("RESULT: FAIL")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue behavior smoke test")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=50053)
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

    env = os.environ.copy()
    _prepend_pythonpath(env, repo_root, generated_dir)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("LOG_LEVEL", "INFO")
    env.setdefault("SERVICE_NAME", "queue")
    env["QUEUE_PORT"] = str(args.port)

    cmd = [sys.executable, "-m", "services.queue.main"]
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
        checks.append(CheckResult("process_start", alive, "queue process is running" if alive else f"exited early {proc.returncode}"))
        if not alive:
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
            stub = pb2_grpc.QueueInternalServiceStub(channel)

            e1 = stub.EnqueueJob(pb2.EnqueueJobRequest(job_id="job-a", enqueued_at_ms=1), timeout=args.rpc_timeout)
            checks.append(CheckResult("enqueue_first", e1.accepted, f"accepted={e1.accepted}"))

            e1_dup = stub.EnqueueJob(pb2.EnqueueJobRequest(job_id="job-a", enqueued_at_ms=2), timeout=args.rpc_timeout)
            checks.append(CheckResult("enqueue_duplicate", e1_dup.accepted, f"accepted={e1_dup.accepted}"))

            _ = stub.EnqueueJob(pb2.EnqueueJobRequest(job_id="job-b", enqueued_at_ms=3), timeout=args.rpc_timeout)
            _ = stub.EnqueueJob(pb2.EnqueueJobRequest(job_id="job-c", enqueued_at_ms=4), timeout=args.rpc_timeout)

            rm_b = stub.RemoveJobIfPresent(pb2.RemoveJobIfPresentRequest(job_id="job-b"), timeout=args.rpc_timeout)
            checks.append(CheckResult("remove_present", rm_b.removed, f"removed={rm_b.removed}"))

            rm_b_again = stub.RemoveJobIfPresent(pb2.RemoveJobIfPresentRequest(job_id="job-b"), timeout=args.rpc_timeout)
            checks.append(CheckResult("remove_repeat", not rm_b_again.removed, f"removed={rm_b_again.removed}"))

            d1 = stub.DequeueJob(pb2.DequeueJobRequest(worker_id="w1"), timeout=args.rpc_timeout)
            checks.append(CheckResult("dequeue_first", d1.found and d1.job_id == "job-a", f"found={d1.found}, job_id={d1.job_id}"))

            d2 = stub.DequeueJob(pb2.DequeueJobRequest(worker_id="w1"), timeout=args.rpc_timeout)
            checks.append(CheckResult("dequeue_second", d2.found and d2.job_id == "job-c", f"found={d2.found}, job_id={d2.job_id}"))

            d3 = stub.DequeueJob(pb2.DequeueJobRequest(worker_id="w1"), timeout=args.rpc_timeout)
            checks.append(CheckResult("dequeue_empty", (not d3.found) and d3.job_id == "", f"found={d3.found}, job_id={d3.job_id}"))

            bad_enqueue_ok = False
            try:
                stub.EnqueueJob(pb2.EnqueueJobRequest(job_id="", enqueued_at_ms=0), timeout=args.rpc_timeout)
            except grpc.RpcError as exc:
                bad_enqueue_ok = exc.code() == grpc.StatusCode.INVALID_ARGUMENT
            checks.append(CheckResult("enqueue_invalid", bad_enqueue_ok, "INVALID_ARGUMENT expected"))

            bad_dequeue_ok = False
            try:
                stub.DequeueJob(pb2.DequeueJobRequest(worker_id=""), timeout=args.rpc_timeout)
            except grpc.RpcError as exc:
                bad_dequeue_ok = exc.code() == grpc.StatusCode.INVALID_ARGUMENT
            checks.append(CheckResult("dequeue_invalid", bad_dequeue_ok, "INVALID_ARGUMENT expected"))

        still_alive = proc.poll() is None
        checks.append(CheckResult("process_stability", still_alive, "queue still running" if still_alive else "queue exited unexpectedly"))

    finally:
        if proc is not None:
            ok, detail = _terminate_process(proc)
            checks.append(CheckResult("graceful_shutdown", ok, detail))

    return _print_summary_and_exit(checks)


if __name__ == "__main__":
    raise SystemExit(main())
