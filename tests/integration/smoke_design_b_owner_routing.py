#!/usr/bin/env python3
"""
Design B smoke probe for deterministic owner routing.

Validates:
- SubmitJob with non-empty client_request_id routes deterministically to owner node.
- Repeated SubmitJob with same key/spec returns the same job_id (idempotency).
- GetJobStatus/GetJobResult/CancelJob routed by job_id to owner node.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Sequence, Tuple

import grpc


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_import_paths() -> None:
    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _status_name(public_pb2, status_value: int) -> str:
    try:
        return public_pb2.JobStatus.Name(int(status_value))
    except Exception:
        return str(int(status_value))


def _print_summary(checks: List[CheckResult]) -> int:
    print("\n=== Design B Owner Routing Smoke Summary ===")
    max_name = max((len(c.name) for c in checks), default=10)
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<42}  {c.detail}")
        if not c.passed:
            all_passed = False
    print("============================================")
    if all_passed:
        print("RESULT: PASS")
        return 0
    print("RESULT: FAIL")
    return 1


def _expect_rpc_error(
    name: str,
    call: Callable[[], object],
    expected_code: grpc.StatusCode,
) -> CheckResult:
    try:
        call()
        return CheckResult(name=name, passed=False, detail=f"expected {expected_code.name}, got OK")
    except grpc.RpcError as exc:
        return CheckResult(
            name=name,
            passed=exc.code() == expected_code,
            detail=f"code={exc.code().name}, detail={exc.details() or ''}".strip(),
        )


def _build_stubs(public_pb2_grpc, targets: Sequence[str]) -> List[object]:
    stubs = []
    for target in targets:
        channel = grpc.insecure_channel(target)
        stubs.append(public_pb2_grpc.TaskQueuePublicServiceStub(channel))
    return stubs


def _other_index(owner_index: int, node_count: int) -> int:
    if node_count <= 1:
        return owner_index
    return 0 if owner_index != 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke probe for Design B deterministic owner routing")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ports", default="51051,52051,53051,54051,55051,56051")
    parser.add_argument("--rpc-timeout", type=float, default=2.0)
    parser.add_argument("--status-poll-attempts", type=int, default=80)
    parser.add_argument("--poll-sleep-ms", type=int, default=100)
    args = parser.parse_args()

    _ensure_import_paths()
    import taskqueue_public_pb2 as public_pb2
    import taskqueue_public_pb2_grpc as public_pb2_grpc
    from common.owner_routing import owner_for_key, owner_index_for_key

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    if not ports:
        print("No ports provided")
        return 1
    targets = [f"{args.host}:{p}" for p in ports]

    checks: List[CheckResult] = []
    stubs = _build_stubs(public_pb2_grpc, targets)

    client_request_id = f"design-b-routing-{int(time.time() * 1000)}"
    submit_spec = public_pb2.JobSpec(
        job_type="design-b-routing-smoke",
        work_duration_ms=5000,
        payload_size_bytes=16,
        labels={"suite": "smoke_design_b_owner_routing"},
    )

    owner_idx_by_key = owner_index_for_key(client_request_id, len(targets))
    owner_target = owner_for_key(client_request_id, targets)
    checks.append(
        CheckResult(
            "routing.submit_owner_index",
            owner_target == targets[owner_idx_by_key],
            f"owner_index={owner_idx_by_key}, owner_target={owner_target}",
        )
    )

    submit_1 = stubs[owner_idx_by_key].SubmitJob(
        public_pb2.SubmitJobRequest(spec=submit_spec, client_request_id=client_request_id),
        timeout=args.rpc_timeout,
    )
    checks.append(
        CheckResult(
            "submit.first",
            bool(submit_1.job_id) and submit_1.initial_status == public_pb2.QUEUED,
            f"job_id={submit_1.job_id}, status={_status_name(public_pb2, submit_1.initial_status)}, owner={owner_target}",
        )
    )
    if not submit_1.job_id:
        return _print_summary(checks)
    job_id = submit_1.job_id

    submit_2 = stubs[owner_idx_by_key].SubmitJob(
        public_pb2.SubmitJobRequest(spec=submit_spec, client_request_id=client_request_id),
        timeout=args.rpc_timeout,
    )
    checks.append(
        CheckResult(
            "submit.idempotent_same_key_same_payload",
            submit_2.job_id == job_id,
            f"job_id_first={job_id}, job_id_second={submit_2.job_id}",
        )
    )

    mutated_spec = public_pb2.JobSpec(
        job_type="design-b-routing-smoke-mutated",
        work_duration_ms=submit_spec.work_duration_ms,
        payload_size_bytes=submit_spec.payload_size_bytes,
        labels={"suite": "smoke_design_b_owner_routing"},
    )
    checks.append(
        _expect_rpc_error(
            "submit.idempotent_same_key_different_payload",
            lambda: stubs[owner_idx_by_key].SubmitJob(
                public_pb2.SubmitJobRequest(spec=mutated_spec, client_request_id=client_request_id),
                timeout=args.rpc_timeout,
            ),
            grpc.StatusCode.FAILED_PRECONDITION,
        )
    )

    owner_idx_by_job = owner_index_for_key(job_id, len(targets))
    job_owner_target = owner_for_key(job_id, targets)
    checks.append(
        CheckResult(
            "routing.job_owner_index",
            job_owner_target == targets[owner_idx_by_job],
            f"job_id={job_id}, owner_index={owner_idx_by_job}, owner_target={job_owner_target}",
        )
    )

    other_idx = _other_index(owner_idx_by_job, len(targets))
    if other_idx == owner_idx_by_job:
        checks.append(CheckResult("precondition.multi_node", False, "need at least two distinct nodes"))
        return _print_summary(checks)

    checks.append(
        _expect_rpc_error(
            "status.non_owner_not_found",
            lambda: stubs[other_idx].GetJobStatus(
                public_pb2.GetJobStatusRequest(job_id=job_id),
                timeout=args.rpc_timeout,
            ),
            grpc.StatusCode.NOT_FOUND,
        )
    )

    terminal_statuses = {public_pb2.DONE, public_pb2.FAILED, public_pb2.CANCELED}
    owner_status = None
    running_seen = False
    for _ in range(max(1, int(args.status_poll_attempts))):
        owner_status = stubs[owner_idx_by_job].GetJobStatus(
            public_pb2.GetJobStatusRequest(job_id=job_id),
            timeout=args.rpc_timeout,
        )
        if owner_status.status == public_pb2.RUNNING:
            running_seen = True
        if owner_status.status in terminal_statuses:
            break
        time.sleep(max(20, int(args.poll_sleep_ms)) / 1000.0)

    checks.append(
        CheckResult(
            "status.owner_routed_ok",
            owner_status is not None and owner_status.job_id == job_id,
            (
                f"owner_status={_status_name(public_pb2, owner_status.status)}"
                if owner_status is not None
                else "no response"
            ),
        )
    )
    checks.append(
        CheckResult(
            "status.owner_running_or_terminal",
            owner_status is not None and (running_seen or owner_status.status in terminal_statuses),
            (
                f"running_seen={running_seen}, status={_status_name(public_pb2, owner_status.status)}"
                if owner_status is not None
                else "no response"
            ),
        )
    )

    checks.append(
        _expect_rpc_error(
            "result.non_owner_not_found",
            lambda: stubs[other_idx].GetJobResult(
                public_pb2.GetJobResultRequest(job_id=job_id),
                timeout=args.rpc_timeout,
            ),
            grpc.StatusCode.NOT_FOUND,
        )
    )

    owner_result = stubs[owner_idx_by_job].GetJobResult(
        public_pb2.GetJobResultRequest(job_id=job_id),
        timeout=args.rpc_timeout,
    )
    checks.append(
        CheckResult(
            "result.owner_routed_ok",
            owner_result.job_id == job_id,
            f"result_ready={owner_result.result_ready}, terminal={_status_name(public_pb2, owner_result.terminal_status)}",
        )
    )

    checks.append(
        _expect_rpc_error(
            "cancel.non_owner_not_found",
            lambda: stubs[other_idx].CancelJob(
                public_pb2.CancelJobRequest(job_id=job_id, reason="design_b_non_owner_cancel"),
                timeout=args.rpc_timeout,
            ),
            grpc.StatusCode.NOT_FOUND,
        )
    )

    owner_cancel = stubs[owner_idx_by_job].CancelJob(
        public_pb2.CancelJobRequest(job_id=job_id, reason="design_b_owner_routed_cancel"),
        timeout=args.rpc_timeout,
    )
    checks.append(
        CheckResult(
            "cancel.owner_routed_ok",
            owner_cancel.job_id == job_id and owner_cancel.accepted,
            (
                f"accepted={owner_cancel.accepted}, "
                f"current_status={_status_name(public_pb2, owner_cancel.current_status)}, "
                f"already_terminal={owner_cancel.already_terminal}"
            ),
        )
    )

    return _print_summary(checks)


if __name__ == "__main__":
    raise SystemExit(main())
