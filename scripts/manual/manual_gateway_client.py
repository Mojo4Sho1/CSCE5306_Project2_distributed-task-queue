#!/usr/bin/env python3
"""
Manual Gateway client for Design A demos.

This script is intentionally user-facing and interactive by workflow:
- submit a job and capture job_id
- check status later
- fetch result later
- cancel if needed
- list jobs
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

import grpc


def _repo_root() -> Path:
    """Return repository root path used for local import setup."""
    return Path(__file__).resolve().parents[2]


def _ensure_import_paths() -> None:
    """Ensure repo root is on sys.path so generated/client modules import cleanly."""
    repo_root = _repo_root()
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


def _parse_labels(label_args: Iterable[str]) -> Dict[str, str]:
    """Parse repeated key=value labels from CLI flags into a dictionary."""
    labels: Dict[str, str] = {}
    for raw in label_args:
        if "=" not in raw:
            raise ValueError(f"Invalid label format {raw!r}; expected key=value")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"Invalid label format {raw!r}; key must be non-empty")
        labels[key] = value
    return labels


def _load_spec_json(spec_file: str) -> Dict[str, object]:
    """Load a JSON job spec from disk for SubmitJob requests."""
    with open(spec_file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError("spec JSON must be an object")
    return payload


def _status_name(public_pb2, status_value: int) -> str:
    """Return a human-readable label for a status value."""
    try:
        return public_pb2.JobStatus.Name(int(status_value))
    except Exception:
        return str(int(status_value))


def _build_spec(args, public_pb2):
    """Build final SubmitJob spec from CLI options and optional JSON file."""
    spec_payload: Dict[str, object] = {}
    if getattr(args, "spec_file", ""):
        spec_payload = _load_spec_json(args.spec_file)

    job_type = str(spec_payload.get("job_type", getattr(args, "job_type", ""))).strip()
    work_duration_ms = int(spec_payload.get("work_duration_ms", getattr(args, "work_duration_ms", 120)))
    payload_size_bytes = int(spec_payload.get("payload_size_bytes", getattr(args, "payload_size_bytes", 16)))

    labels_from_file = spec_payload.get("labels", {})
    if labels_from_file and not isinstance(labels_from_file, dict):
        raise ValueError("spec.labels must be an object of string key/value entries")
    labels: Dict[str, str] = {}
    for key, value in dict(labels_from_file).items():
        labels[str(key)] = str(value)
    labels.update(_parse_labels(getattr(args, "label", [])))

    if not job_type:
        raise ValueError("job_type must be non-empty")
    if work_duration_ms < 0:
        raise ValueError("work_duration_ms must be >= 0")
    if payload_size_bytes < 0:
        raise ValueError("payload_size_bytes must be >= 0")

    return public_pb2.JobSpec(
        job_type=job_type,
        work_duration_ms=work_duration_ms,
        payload_size_bytes=payload_size_bytes,
        labels=labels,
    )


def _print_json(payload: Dict[str, object]) -> None:
    """Print structured command output for operators."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def main() -> int:
    """Run manual Gateway API calls from the command line for ad-hoc debugging."""
    parser = argparse.ArgumentParser(description="Manual user client for Gateway public API")
    parser.add_argument("--host", default="127.0.0.1", help="Gateway host")
    parser.add_argument("--port", type=int, default=50051, help="Gateway port")
    parser.add_argument("--rpc-timeout", type=float, default=2.0, help="Unary RPC timeout in seconds")

    subparsers = parser.add_subparsers(dest="command", required=True)

    submit = subparsers.add_parser("submit", help="Submit a job")
    submit.add_argument("--spec-file", default="", help="Optional JSON file with JobSpec fields")
    submit.add_argument("--job-type", default="manual-demo-job", help="Job type when not provided by spec file")
    submit.add_argument("--work-duration-ms", type=int, default=120, help="Work duration hint")
    submit.add_argument("--payload-size-bytes", type=int, default=16, help="Payload size hint")
    submit.add_argument(
        "--label",
        action="append",
        default=[],
        help="Optional label entry in key=value format; repeatable",
    )
    submit.add_argument(
        "--client-request-id",
        default="",
        help="Optional idempotency key; empty means non-idempotent submit",
    )

    status = subparsers.add_parser("status", help="Get job status")
    status.add_argument("--job-id", required=True)

    result = subparsers.add_parser("result", help="Get job result")
    result.add_argument("--job-id", required=True)
    result.add_argument(
        "--include-output-bytes",
        action="store_true",
        help="Include raw output bytes decoded as utf-8 (best effort)",
    )

    cancel = subparsers.add_parser("cancel", help="Cancel a job")
    cancel.add_argument("--job-id", required=True)
    cancel.add_argument("--reason", default="manual_cancel")

    list_jobs = subparsers.add_parser("list", help="List jobs")
    list_jobs.add_argument("--page-size", type=int, default=25)
    list_jobs.add_argument("--page-token", default="")
    list_jobs.add_argument(
        "--sort",
        choices=["CREATED_AT_DESC", "CREATED_AT_ASC"],
        default="CREATED_AT_DESC",
    )

    args = parser.parse_args()

    _ensure_import_paths()
    import taskqueue_public_pb2 as public_pb2
    import taskqueue_public_pb2_grpc as public_pb2_grpc

    target = f"{args.host}:{args.port}"
    with grpc.insecure_channel(target) as channel:
        stub = public_pb2_grpc.TaskQueuePublicServiceStub(channel)

        if args.command == "submit":
            spec = _build_spec(args, public_pb2)
            client_request_id = args.client_request_id.strip()
            if not client_request_id:
                client_request_id = f"manual-{int(time.time() * 1000)}"
            resp = stub.SubmitJob(
                public_pb2.SubmitJobRequest(spec=spec, client_request_id=client_request_id),
                timeout=args.rpc_timeout,
            )
            _print_json(
                {
                    "command": "submit",
                    "target": target,
                    "job_id": resp.job_id,
                    "initial_status": _status_name(public_pb2, resp.initial_status),
                    "accepted_at_ms": int(resp.accepted_at_ms),
                    "client_request_id": client_request_id,
                    "spec": {
                        "job_type": spec.job_type,
                        "work_duration_ms": int(spec.work_duration_ms),
                        "payload_size_bytes": int(spec.payload_size_bytes),
                        "labels": dict(spec.labels),
                    },
                }
            )
            return 0

        if args.command == "status":
            resp = stub.GetJobStatus(
                public_pb2.GetJobStatusRequest(job_id=args.job_id),
                timeout=args.rpc_timeout,
            )
            _print_json(
                {
                    "command": "status",
                    "target": target,
                    "job_id": resp.job_id,
                    "status": _status_name(public_pb2, resp.status),
                    "cancel_requested": bool(resp.cancel_requested),
                    "created_at_ms": int(resp.created_at_ms),
                    "started_at_ms": int(resp.started_at_ms),
                    "finished_at_ms": int(resp.finished_at_ms),
                    "failure_reason": resp.failure_reason,
                }
            )
            return 0

        if args.command == "result":
            resp = stub.GetJobResult(
                public_pb2.GetJobResultRequest(job_id=args.job_id),
                timeout=args.rpc_timeout,
            )
            payload: Dict[str, object] = {
                "command": "result",
                "target": target,
                "job_id": resp.job_id,
                "result_ready": bool(resp.result_ready),
                "terminal_status": _status_name(public_pb2, resp.terminal_status),
                "output_summary": resp.output_summary,
                "runtime_ms": int(resp.runtime_ms),
                "checksum": resp.checksum,
                "output_bytes_len": len(resp.output_bytes),
            }
            if args.include_output_bytes:
                payload["output_bytes_text"] = bytes(resp.output_bytes).decode("utf-8", errors="replace")
            _print_json(payload)
            return 0

        if args.command == "cancel":
            resp = stub.CancelJob(
                public_pb2.CancelJobRequest(job_id=args.job_id, reason=args.reason),
                timeout=args.rpc_timeout,
            )
            _print_json(
                {
                    "command": "cancel",
                    "target": target,
                    "job_id": resp.job_id,
                    "accepted": bool(resp.accepted),
                    "current_status": _status_name(public_pb2, resp.current_status),
                    "already_terminal": bool(resp.already_terminal),
                    "reason": args.reason,
                }
            )
            return 0

        if args.command == "list":
            sort_value = (
                public_pb2.CREATED_AT_ASC
                if args.sort == "CREATED_AT_ASC"
                else public_pb2.CREATED_AT_DESC
            )
            resp = stub.ListJobs(
                public_pb2.ListJobsRequest(
                    page=public_pb2.PageRequest(
                        page_size=args.page_size,
                        page_token=args.page_token,
                    ),
                    sort=sort_value,
                ),
                timeout=args.rpc_timeout,
            )
            jobs: List[Dict[str, object]] = []
            for j in resp.jobs:
                jobs.append(
                    {
                        "job_id": j.job_id,
                        "status": _status_name(public_pb2, j.status),
                        "job_type": j.job_type,
                        "created_at_ms": int(j.created_at_ms),
                        "started_at_ms": int(j.started_at_ms),
                        "finished_at_ms": int(j.finished_at_ms),
                        "cancel_requested": bool(j.cancel_requested),
                    }
                )
            _print_json(
                {
                    "command": "list",
                    "target": target,
                    "count": len(jobs),
                    "next_page_token": resp.page.next_page_token,
                    "jobs": jobs,
                }
            )
            return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
