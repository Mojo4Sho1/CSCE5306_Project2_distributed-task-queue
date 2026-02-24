"""RPC method implementations for the result service."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Optional

import grpc

try:
    # Preferred when PYTHONPATH includes ./generated
    import taskqueue_internal_pb2 as pb2
    import taskqueue_internal_pb2_grpc as pb2_grpc
    import taskqueue_public_pb2 as public_pb2
except ModuleNotFoundError:  # pragma: no cover
    # Fallback if generated modules are imported as a package
    from generated import taskqueue_internal_pb2 as pb2
    from generated import taskqueue_internal_pb2_grpc as pb2_grpc
    from generated import taskqueue_public_pb2 as public_pb2


_DEFAULT_MAX_OUTPUT_BYTES = 262144
_TERMINAL_STATUSES = {
    public_pb2.DONE,
    public_pb2.FAILED,
    public_pb2.CANCELED,
}


@dataclass
class _ResultRecord:
    """In-memory result payload and metadata stored per job id."""
    job_id: str
    terminal_status: int
    runtime_ms: int
    output_summary: str
    output_bytes: bytes
    checksum: str


class ResultServicer(pb2_grpc.ResultInternalServiceServicer):
    """ResultInternalService v1 implementation for terminal result envelopes."""

    def __init__(self, config: Optional[object] = None, logger: Optional[logging.Logger] = None) -> None:
        """Initialize result servicer instance state."""
        self._logger = logger or logging.getLogger("result.servicer")
        configured_cap = int(getattr(config, "max_output_bytes", _DEFAULT_MAX_OUTPUT_BYTES))
        self._max_output_bytes = configured_cap if configured_cap > 0 else _DEFAULT_MAX_OUTPUT_BYTES

        self._lock = threading.RLock()
        self._results: dict[str, _ResultRecord] = {}

    def _set_error(self, context: grpc.ServicerContext, code: grpc.StatusCode, detail: str) -> None:
        """Set gRPC status code and detail text on the current Result RPC context."""
        context.set_code(code)
        context.set_details(detail)

    def StoreResult(
        self,
        request: pb2.StoreResultRequest,
        context: grpc.ServicerContext,
    ) -> pb2.StoreResultResponse:
        """Store result."""
        job_id = request.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.StoreResultResponse(
                stored=False,
                already_exists=False,
                current_terminal_status=public_pb2.JOB_STATUS_UNSPECIFIED,
            )

        if request.terminal_status not in _TERMINAL_STATUSES:
            self._set_error(
                context,
                grpc.StatusCode.INVALID_ARGUMENT,
                "terminal_status must be one of DONE, FAILED, CANCELED",
            )
            return pb2.StoreResultResponse(
                stored=False,
                already_exists=False,
                current_terminal_status=public_pb2.JOB_STATUS_UNSPECIFIED,
            )

        output_size = len(request.output_bytes)
        if output_size > self._max_output_bytes:
            self._set_error(
                context,
                grpc.StatusCode.INVALID_ARGUMENT,
                f"output_bytes exceeds MAX_OUTPUT_BYTES ({self._max_output_bytes})",
            )
            return pb2.StoreResultResponse(
                stored=False,
                already_exists=False,
                current_terminal_status=public_pb2.JOB_STATUS_UNSPECIFIED,
            )

        with self._lock:
            existing = self._results.get(job_id)
            if existing is not None:
                return pb2.StoreResultResponse(
                    stored=False,
                    already_exists=True,
                    current_terminal_status=existing.terminal_status,
                )

            self._results[job_id] = _ResultRecord(
                job_id=job_id,
                terminal_status=request.terminal_status,
                runtime_ms=int(request.runtime_ms),
                output_summary=request.output_summary,
                output_bytes=bytes(request.output_bytes),
                checksum=request.checksum,
            )

            return pb2.StoreResultResponse(
                stored=True,
                already_exists=False,
                current_terminal_status=request.terminal_status,
            )

    def GetResult(
        self,
        request: pb2.GetResultRequest,
        context: grpc.ServicerContext,
    ) -> pb2.GetResultResponse:
        """Get result."""
        job_id = request.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.GetResultResponse(
                found=False,
                job_id="",
                terminal_status=public_pb2.JOB_STATUS_UNSPECIFIED,
                runtime_ms=0,
                output_summary="",
                output_bytes=b"",
                checksum="",
            )

        with self._lock:
            rec = self._results.get(job_id)
            if rec is None:
                return pb2.GetResultResponse(
                    found=False,
                    job_id=job_id,
                    terminal_status=public_pb2.JOB_STATUS_UNSPECIFIED,
                    runtime_ms=0,
                    output_summary="",
                    output_bytes=b"",
                    checksum="",
                )

            return pb2.GetResultResponse(
                found=True,
                job_id=rec.job_id,
                terminal_status=rec.terminal_status,
                runtime_ms=rec.runtime_ms,
                output_summary=rec.output_summary,
                output_bytes=rec.output_bytes,
                checksum=rec.checksum,
            )
