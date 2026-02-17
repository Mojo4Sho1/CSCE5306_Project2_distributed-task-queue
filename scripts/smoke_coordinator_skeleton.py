#!/usr/bin/env python3
"""
Smoke test for Coordinator skeleton server.

What this validates:
1) Coordinator process starts and stays alive.
2) gRPC endpoint becomes reachable.
3) All 3 Coordinator internal RPCs are registered and callable.
4) Each RPC returns UNIMPLEMENTED (skeleton-phase expected behavior).
5) Coordinator service shuts down cleanly after test.

Usage:
    python scripts/smoke_coordinator_skeleton.py
    python scripts/smoke_coordinator_skeleton.py --host 127.0.0.1 --port 50054
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
    # scripts/smoke_coordinator_skeleton.py -> repo root is parent of scripts
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
        except Exception as exc:  # intentionally broad for startup probing
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
        try:
            proc.kill()
            proc.wait(timeout=2.0)
            return False, "did not terminate in time; killed"
        except Exception as exc:  # defensive
            return False, f"failed to kill process: {exc}"


def _read_remaining_output(proc: subprocess.Popen) -> str:
    try:
        if proc.stdout is None:
            return ""
        return proc.stdout.read() or ""
    except Exception:
        return ""


def _expect_unimplemented(rpc_call) -> Tuple[bool, str]:
    try:
        _ = rpc_call()
        return False, "returned OK; expected UNIMPLEMENTED during skeleton phase"
    except grpc.RpcError as exc:
        code = exc.code()
        detail = exc.details() or ""
        if code == grpc.StatusCode.UNIMPLEMENTED:
            return True, f"UNIMPLEMENTED ({detail})" if detail else "UNIMPLEMENTED"
        return False, f"{code.name}: {detail}" if detail else code.name


def _print_summary_and_exit(checks: List[CheckResult]) -> int:
    print("\n=== Coordinator Skeleton Smoke Test Summary ===")
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
    parser = argparse.ArgumentParser(description="Coordinator skeleton smoke test")
    parser.add_argument("--host", default="127.0.0.1", help="Coordinator bind host to probe")
    parser.add_argument("--port", type=int, default=50054, help="Coordinator bind port to probe")
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for server startup/readiness",
    )
    parser.add_argument(
        "--rpc-timeout",
        type=float,
        default=2.0,
        help="Per-RPC timeout in seconds",
    )
    args = parser.parse_args()

    repo_root = _repo_root()
    generated_dir = repo_root / "generated"

    # Make generated stubs importable for this script.
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        import taskqueue_internal_pb2 as pb2
        import taskqueue_internal_pb2_grpc as pb2_grpc
    except Exception as exc:
        print(f"[FAIL] Unable to import generated stubs: {exc}")
        return 1

    env = os.environ.copy()
    _prepend_pythonpath(env, repo_root, generated_dir)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("LOG_LEVEL", "INFO")
    env.setdefault("SERVICE_NAME", "coordinator")
    env["COORDINATOR_PORT"] = str(args.port)

    cmd = [sys.executable, "-m", "services.coordinator.main"]

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

        # 1) Process alive shortly after launch
        time.sleep(0.4)
        alive = proc.poll() is None
        checks.append(
            CheckResult(
                name="process_start",
                passed=alive,
                detail="coordinator process is running"
                if alive
                else f"exited early with code {proc.returncode}",
            )
        )
        if not alive:
            logs = _read_remaining_output(proc)
            if logs.strip():
                print("\n--- coordinator output ---")
                print(logs.rstrip())
                print("--- end coordinator output ---")
            return _print_summary_and_exit(checks)

        # 2) TCP port check
        port_ok = _wait_for_port(args.host, args.port, timeout_s=args.startup_timeout)
        checks.append(
            CheckResult(
                name="tcp_port_open",
                passed=port_ok,
                detail=f"{args.host}:{args.port} reachable" if port_ok else f"{args.host}:{args.port} not reachable",
            )
        )
        if not port_ok:
            logs = _read_remaining_output(proc)
            if logs.strip():
                print("\n--- coordinator output ---")
                print(logs.rstrip())
                print("--- end coordinator output ---")
            return _print_summary_and_exit(checks)

        # 3) gRPC readiness
        addr = f"{args.host}:{args.port}"
        grpc_ok, grpc_detail = _wait_for_grpc_ready(addr, timeout_s=args.startup_timeout)
        checks.append(
            CheckResult(
                name="grpc_ready",
                passed=grpc_ok,
                detail=grpc_detail if grpc_ok else f"not ready: {grpc_detail}",
            )
        )
        if not grpc_ok:
            logs = _read_remaining_output(proc)
            if logs.strip():
                print("\n--- coordinator output ---")
                print(logs.rstrip())
                print("--- end coordinator output ---")
            return _print_summary_and_exit(checks)

        # 4) RPC surface + expected placeholder behavior
        with grpc.insecure_channel(addr) as channel:
            stub = pb2_grpc.CoordinatorInternalServiceStub(channel)

            rpc_cases = [
                (
                    "WorkerHeartbeat",
                    lambda: stub.WorkerHeartbeat(
                        pb2.WorkerHeartbeatRequest(worker_id="smoke-worker", heartbeat_at_ms=0, capacity_hint=1),
                        timeout=args.rpc_timeout,
                    ),
                ),
                (
                    "FetchWork",
                    lambda: stub.FetchWork(
                        pb2.FetchWorkRequest(worker_id="smoke-worker"),
                        timeout=args.rpc_timeout,
                    ),
                ),
                (
                    "ReportWorkOutcome",
                    lambda: stub.ReportWorkOutcome(
                        pb2.ReportWorkOutcomeRequest(
                            worker_id="smoke-worker",
                            job_id="smoke-job",
                            outcome=0,
                            runtime_ms=0,
                            failure_reason="",
                            output_summary="",
                            output_bytes=b"",
                            checksum="",
                        ),
                        timeout=args.rpc_timeout,
                    ),
                ),
            ]

            for rpc_name, rpc_call in rpc_cases:
                passed, detail = _expect_unimplemented(rpc_call)
                checks.append(CheckResult(name=f"rpc_{rpc_name}", passed=passed, detail=detail))

        # 5) Process should still be alive after calls
        still_alive = proc.poll() is None
        checks.append(
            CheckResult(
                name="process_stability",
                passed=still_alive,
                detail="coordinator still running after RPC probes"
                if still_alive
                else f"coordinator exited unexpectedly with code {proc.returncode}",
            )
        )

    finally:
        if proc is not None:
            shutdown_ok, shutdown_detail = _terminate_process(proc)
            checks.append(
                CheckResult(
                    name="graceful_shutdown",
                    passed=shutdown_ok,
                    detail=shutdown_detail,
                )
            )

    return _print_summary_and_exit(checks)


if __name__ == "__main__":
    raise SystemExit(main())
