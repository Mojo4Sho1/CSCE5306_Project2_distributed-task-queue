#!/usr/bin/env python3
"""
Smoke test for Result service behavior (in-process, no network bind).

This validates key v1 semantics directly against ResultServicer RPC handlers:
- StoreResult accepts terminal statuses only (DONE/FAILED/CANCELED)
- StoreResult enforces MAX_OUTPUT_BYTES bounds
- Duplicate/conflicting StoreResult calls are idempotent and observable
- GetResult returns deterministic not-found and found payloads
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



def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _print_summary_and_exit(checks: List[CheckResult]) -> int:
    print("\n=== Result Behavior Smoke Test Summary ===")
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
    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import taskqueue_internal_pb2 as pb2
    import taskqueue_public_pb2 as public_pb2
    from services.result.servicer import ResultServicer

    checks: List[CheckResult] = []
    svc = ResultServicer(config=SimpleNamespace(max_output_bytes=8))

    ctx = FakeContext()
    missing = svc.GetResult(pb2.GetResultRequest(job_id="missing-job"), ctx)
    missing_ok = (
        ctx.code == grpc.StatusCode.OK
        and (not missing.found)
        and missing.job_id == "missing-job"
        and missing.terminal_status == public_pb2.JOB_STATUS_UNSPECIFIED
        and missing.output_bytes == b""
    )
    checks.append(CheckResult("get_missing", missing_ok, f"code={ctx.code.name}, found={missing.found}"))

    ctx = FakeContext()
    invalid_terminal = svc.StoreResult(
        pb2.StoreResultRequest(
            job_id="job-invalid-status",
            terminal_status=public_pb2.QUEUED,
            runtime_ms=1,
            output_summary="bad",
            output_bytes=b"ok",
            checksum="",
        ),
        ctx,
    )
    invalid_terminal_ok = (
        ctx.code == grpc.StatusCode.INVALID_ARGUMENT
        and (not invalid_terminal.stored)
        and (not invalid_terminal.already_exists)
    )
    checks.append(CheckResult("store_invalid_terminal", invalid_terminal_ok, f"code={ctx.code.name}"))

    ctx = FakeContext()
    oversized = svc.StoreResult(
        pb2.StoreResultRequest(
            job_id="job-oversized",
            terminal_status=public_pb2.DONE,
            runtime_ms=2,
            output_summary="oversized",
            output_bytes=b"x" * 9,
            checksum="",
        ),
        ctx,
    )
    oversized_ok = (
        ctx.code == grpc.StatusCode.INVALID_ARGUMENT
        and (not oversized.stored)
        and (not oversized.already_exists)
    )
    checks.append(CheckResult("store_oversized", oversized_ok, f"code={ctx.code.name}"))

    ctx = FakeContext()
    first = svc.StoreResult(
        pb2.StoreResultRequest(
            job_id="job-1",
            terminal_status=public_pb2.DONE,
            runtime_ms=123,
            output_summary="done",
            output_bytes=b"abc",
            checksum="deadbeef",
        ),
        ctx,
    )
    first_ok = (
        ctx.code == grpc.StatusCode.OK
        and first.stored
        and (not first.already_exists)
        and first.current_terminal_status == public_pb2.DONE
    )
    checks.append(CheckResult("store_first", first_ok, f"stored={first.stored}, already_exists={first.already_exists}"))

    ctx = FakeContext()
    get_found = svc.GetResult(pb2.GetResultRequest(job_id="job-1"), ctx)
    get_found_ok = (
        ctx.code == grpc.StatusCode.OK
        and get_found.found
        and get_found.job_id == "job-1"
        and get_found.terminal_status == public_pb2.DONE
        and get_found.runtime_ms == 123
        and get_found.output_summary == "done"
        and get_found.output_bytes == b"abc"
        and get_found.checksum == "deadbeef"
    )
    checks.append(CheckResult("get_found", get_found_ok, f"found={get_found.found}, status={get_found.terminal_status}"))

    ctx = FakeContext()
    dup = svc.StoreResult(
        pb2.StoreResultRequest(
            job_id="job-1",
            terminal_status=public_pb2.DONE,
            runtime_ms=123,
            output_summary="done",
            output_bytes=b"abc",
            checksum="deadbeef",
        ),
        ctx,
    )
    dup_ok = (
        ctx.code == grpc.StatusCode.OK
        and (not dup.stored)
        and dup.already_exists
        and dup.current_terminal_status == public_pb2.DONE
    )
    checks.append(CheckResult("store_duplicate", dup_ok, f"stored={dup.stored}, already_exists={dup.already_exists}"))

    ctx = FakeContext()
    conflict = svc.StoreResult(
        pb2.StoreResultRequest(
            job_id="job-1",
            terminal_status=public_pb2.FAILED,
            runtime_ms=999,
            output_summary="conflict",
            output_bytes=b"zzz",
            checksum="",
        ),
        ctx,
    )
    conflict_ok = (
        ctx.code == grpc.StatusCode.OK
        and (not conflict.stored)
        and conflict.already_exists
        and conflict.current_terminal_status == public_pb2.DONE
    )
    checks.append(CheckResult("store_conflict_status", conflict_ok, f"current_status={conflict.current_terminal_status}"))

    return _print_summary_and_exit(checks)


if __name__ == "__main__":
    raise SystemExit(main())
