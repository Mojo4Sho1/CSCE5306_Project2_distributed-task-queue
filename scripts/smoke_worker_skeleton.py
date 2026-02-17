#!/usr/bin/env python3
"""
Smoke test for Worker skeleton runtime.

What this validates:
1) Worker process starts and stays alive.
2) Worker loop reaches ready state.
3) Worker emits deterministic heartbeat/fetch loop attempt logs.
4) Worker process shuts down cleanly after probes.

Notes:
- Worker has no inbound gRPC endpoint in v1.
- This test uses an intentionally non-routable coordinator target to validate
  skeleton liveness without requiring live upstream orchestration.

Usage:
    python scripts/smoke_worker_skeleton.py
    python scripts/smoke_worker_skeleton.py --coordinator-addr 127.0.0.1:59999
"""

from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


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
        except Exception as exc:
            return False, f"failed to kill process: {exc}"


def _stream_reader(stdout, output_q: "queue.Queue[str]") -> None:
    try:
        for line in iter(stdout.readline, ""):
            if not line:
                break
            output_q.put(line.rstrip("\n"))
    finally:
        try:
            stdout.close()
        except Exception:
            pass


def _wait_for_log_markers(
    output_q: "queue.Queue[str]",
    markers: List[str],
    timeout_s: float,
    proc: subprocess.Popen,
) -> Tuple[bool, str, List[str]]:
    found = {m: False for m in markers}
    captured: List[str] = []
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        if proc.poll() is not None:
            break

        try:
            line = output_q.get(timeout=0.2)
        except queue.Empty:
            continue

        captured.append(line)
        for marker in markers:
            if marker in line:
                found[marker] = True

        if all(found.values()):
            return True, "all expected markers observed", captured

    missing = [m for m, ok in found.items() if not ok]
    if missing:
        return False, f"missing markers: {', '.join(missing)}", captured
    return True, "markers observed", captured


def _print_summary_and_exit(checks: List[CheckResult]) -> int:
    print("\n=== Worker Skeleton Smoke Test Summary ===")
    max_name = max((len(c.name) for c in checks), default=10)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<{max_name}}  {c.detail}")
        if not c.passed:
            all_passed = False

    print("=========================================")
    if all_passed:
        print("RESULT: PASS")
        return 0
    print("RESULT: FAIL")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Worker skeleton smoke test")
    parser.add_argument(
        "--coordinator-addr",
        default="127.0.0.1:59999",
        help="Coordinator address used by worker during smoke probes",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=12.0,
        help="Seconds to wait for startup/loop markers",
    )
    parser.add_argument(
        "--min-runtime",
        type=float,
        default=1.2,
        help="Seconds worker should remain alive after startup",
    )
    args = parser.parse_args()

    repo_root = _repo_root()
    generated_dir = repo_root / "generated"

    env = os.environ.copy()
    _prepend_pythonpath(env, repo_root, generated_dir)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("LOG_LEVEL", "INFO")
    env.setdefault("SERVICE_NAME", "worker")
    env.setdefault("HEARTBEAT_INTERVAL_MS", "200")
    env.setdefault("FETCH_IDLE_SLEEP_MS", "120")
    env.setdefault("WORKER_ID", "smoke-worker")
    env["COORDINATOR_ADDR"] = args.coordinator_addr
    env["PORT"] = env.get("PORT", "50056")

    cmd = [sys.executable, "-m", "services.worker.main"]

    checks: List[CheckResult] = []
    proc: Optional[subprocess.Popen] = None
    output_q: "queue.Queue[str]" = queue.Queue()
    reader_thread: Optional[threading.Thread] = None
    captured_lines: List[str] = []

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

        if proc.stdout is not None:
            reader_thread = threading.Thread(target=_stream_reader, args=(proc.stdout, output_q), daemon=True)
            reader_thread.start()

        time.sleep(0.4)
        alive = proc.poll() is None
        checks.append(
            CheckResult(
                name="process_start",
                passed=alive,
                detail="worker process is running" if alive else f"exited early with code {proc.returncode}",
            )
        )
        if not alive:
            return _print_summary_and_exit(checks)

        markers = [
            "worker.startup.ready",
            "worker.heartbeat.attempt",
            "worker.fetch.attempt",
        ]
        marker_ok, marker_detail, lines = _wait_for_log_markers(
            output_q=output_q,
            markers=markers,
            timeout_s=args.startup_timeout,
            proc=proc,
        )
        captured_lines.extend(lines)
        checks.append(CheckResult(name="startup_and_loop_markers", passed=marker_ok, detail=marker_detail))
        if not marker_ok:
            return _print_summary_and_exit(checks)

        time.sleep(max(args.min_runtime, 0.1))
        still_alive = proc.poll() is None
        checks.append(
            CheckResult(
                name="process_stability",
                passed=still_alive,
                detail="worker remained alive during liveness window"
                if still_alive
                else f"worker exited unexpectedly with code {proc.returncode}",
            )
        )

    finally:
        if proc is not None:
            shutdown_ok, shutdown_detail = _terminate_process(proc)
            checks.append(CheckResult(name="graceful_shutdown", passed=shutdown_ok, detail=shutdown_detail))

        if reader_thread is not None:
            reader_thread.join(timeout=1.0)

    if any(not c.passed for c in checks):
        if captured_lines:
            print("\n--- worker output (partial) ---")
            for line in captured_lines[-40:]:
                print(line)
            print("--- end worker output ---")

    return _print_summary_and_exit(checks)


if __name__ == "__main__":
    raise SystemExit(main())
