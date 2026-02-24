#!/usr/bin/env python3
"""
Design B smoke probe for locked client routing behavior.

Validates:
- SubmitJob with empty client_request_id uses round-robin progression.
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
from typing import Callable, List, Sequence

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


def _ensure_import_paths() -> None:
    """Internal helper to  ensure import paths."""
    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _status_name(public_pb2, status_value: int) -> str:
    """Return a human-readable label for a status value."""
    try:
        return public_pb2.JobStatus.Name(int(status_value))
    except Exception:
        return str(int(status_value))


def _print_summary(checks: List[CheckResult]) -> int:
    """Print structured command output for operators."""
    print("\n=== Design B Client Routing Smoke Summary ===")
    all_passed = True
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"{status:<5}  {c.name:<46}  {c.detail}")
        if not c.passed:
            all_passed = False
    print("=============================================")
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
    """Assert expected behavior for the smoke check."""
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
    """Build derived runtime data for this operation."""
    return [public_pb2_grpc.TaskQueuePublicServiceStub(grpc.insecure_channel(target)) for target in targets]


def _other_index(owner_index: int, node_count: int) -> int:
    """Internal helper to  other index."""
    if node_count <= 1:
        return owner_index
    return 0 if owner_index != 0 else 1


def main() -> int:
    """Run the command-line entrypoint."""
    parser = argparse.ArgumentParser(description="Smoke probe for Design B client routing policy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ports", default="51051,52051,53051,54051,55051,56051")
    parser.add_argument("--rpc-timeout", type=float, default=2.0)
    parser.add_argument("--status-poll-attempts", type=int, default=80)
    parser.add_argument("--poll-sleep-ms", type=int, default=100)
    args = parser.parse_args()

    _ensure_import_paths()
    import taskqueue_public_pb2 as public_pb2
    import taskqueue_public_pb2_grpc as public_pb2_grpc
    from common.design_b_routing import DesignBClientRouter, build_ordered_targets

    ports = [int(p.strip()) for p in args.ports.split(",") if p.strip()]
    if not ports:
        print("No ports provided")
        return 1

    targets = build_ordered_targets(args.host, ports)
    stubs = _build_stubs(public_pb2_grpc, targets)
    router = DesignBClientRouter(ordered_nodes=targets)

    checks: List[CheckResult] = []

    rr_idx_1, rr_target_1, rr_mode_1 = router.submit_target("")
    rr_idx_2, rr_target_2, rr_mode_2 = router.submit_target("")
    checks.append(
        CheckResult(
            "routing.submit_empty_round_robin_step1",
            rr_mode_1 == "round_robin" and rr_idx_1 == 0 and rr_target_1 == targets[0],
            f"mode={rr_mode_1}, idx={rr_idx_1}, target={rr_target_1}",
        )
    )
    checks.append(
        CheckResult(
            "routing.submit_empty_round_robin_step2",
            rr_mode_2 == "round_robin" and rr_idx_2 == 1 and rr_target_2 == targets[1],
            f"mode={rr_mode_2}, idx={rr_idx_2}, target={rr_target_2}",
        )
    )

    rr_submit_spec = public_pb2.JobSpec(
        job_type="design-b-routing-smoke-empty-key",
        work_duration_ms=150,
        payload_size_bytes=8,
        labels={"suite": "smoke_design_b_owner_routing", "mode": "round_robin"},
    )

    rr_submit_1 = stubs[rr_idx_1].SubmitJob(
        public_pb2.SubmitJobRequest(spec=rr_submit_spec, client_request_id=""),
        timeout=args.rpc_timeout,
    )
    rr_submit_2 = stubs[rr_idx_2].SubmitJob(
        public_pb2.SubmitJobRequest(spec=rr_submit_spec, client_request_id=""),
        timeout=args.rpc_timeout,
    )
    checks.append(
        CheckResult(
            "submit.empty_key_1_accepted",
            bool(rr_submit_1.job_id) and rr_submit_1.initial_status == public_pb2.QUEUED,
            f"job_id={rr_submit_1.job_id}, status={_status_name(public_pb2, rr_submit_1.initial_status)}, target={rr_target_1}",
        )
    )
    checks.append(
        CheckResult(
            "submit.empty_key_2_accepted",
            bool(rr_submit_2.job_id) and rr_submit_2.initial_status == public_pb2.QUEUED,
            f"job_id={rr_submit_2.job_id}, status={_status_name(public_pb2, rr_submit_2.initial_status)}, target={rr_target_2}",
        )
    )
    checks.append(
        CheckResult(
            "submit.empty_key_non_idempotent_distinct_jobs",
            bool(rr_submit_1.job_id) and bool(rr_submit_2.job_id) and rr_submit_1.job_id != rr_submit_2.job_id,
            f"job_id_1={rr_submit_1.job_id}, job_id_2={rr_submit_2.job_id}",
        )
    )

    if rr_submit_1.job_id:
        rr_job_owner_idx_1, rr_job_owner_target_1 = router.job_target(rr_submit_1.job_id)
        checks.append(
            CheckResult(
                "routing.empty_key_job1_owner_coherent",
                rr_job_owner_idx_1 == rr_idx_1 and rr_job_owner_target_1 == rr_target_1,
                f"submit_idx={rr_idx_1}, owner_idx={rr_job_owner_idx_1}, owner_target={rr_job_owner_target_1}",
            )
        )
    if rr_submit_2.job_id:
        rr_job_owner_idx_2, rr_job_owner_target_2 = router.job_target(rr_submit_2.job_id)
        checks.append(
            CheckResult(
                "routing.empty_key_job2_owner_coherent",
                rr_job_owner_idx_2 == rr_idx_2 and rr_job_owner_target_2 == rr_target_2,
                f"submit_idx={rr_idx_2}, owner_idx={rr_job_owner_idx_2}, owner_target={rr_job_owner_target_2}",
            )
        )

    client_request_id = f"design-b-routing-{int(time.time() * 1000)}"
    submit_spec = public_pb2.JobSpec(
        job_type="design-b-routing-smoke",
        work_duration_ms=5000,
        payload_size_bytes=16,
        labels={"suite": "smoke_design_b_owner_routing", "mode": "owner"},
    )

    owner_idx_by_key, owner_target, _owner_mode = router.submit_target(client_request_id)
    checks.append(
        CheckResult(
            "routing.submit_non_empty_owner",
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
            "submit.non_empty_first",
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
            "submit.non_empty_idempotent_same_payload",
            submit_2.job_id == job_id,
            f"job_id_first={job_id}, job_id_second={submit_2.job_id}",
        )
    )

    mutated_spec = public_pb2.JobSpec(
        job_type="design-b-routing-smoke-mutated",
        work_duration_ms=submit_spec.work_duration_ms,
        payload_size_bytes=submit_spec.payload_size_bytes,
        labels={"suite": "smoke_design_b_owner_routing", "mode": "owner"},
    )
    checks.append(
        _expect_rpc_error(
            "submit.non_empty_same_key_different_payload",
            lambda: stubs[owner_idx_by_key].SubmitJob(
                public_pb2.SubmitJobRequest(spec=mutated_spec, client_request_id=client_request_id),
                timeout=args.rpc_timeout,
            ),
            grpc.StatusCode.FAILED_PRECONDITION,
        )
    )

    owner_idx_by_job, job_owner_target = router.job_target(job_id)
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
