"""RPC method implementations for the queue service."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from typing import Optional

import grpc

try:
    # Preferred when PYTHONPATH includes ./generated
    import taskqueue_internal_pb2 as pb2
    import taskqueue_internal_pb2_grpc as pb2_grpc
except ModuleNotFoundError:  # pragma: no cover
    # Fallback if generated modules are imported as a package
    from generated import taskqueue_internal_pb2 as pb2
    from generated import taskqueue_internal_pb2_grpc as pb2_grpc


class QueueServicer(pb2_grpc.QueueInternalServiceServicer):
    """
    QueueInternalService v1 implementation.

    Semantics:
    - Enqueue is idempotent by job_id (no duplicate queue entries)
    - Dequeue is destructive and best-effort FIFO
    - RemoveIfPresent is repeat-safe (idempotent)
    """

    def __init__(self, config: Optional[object] = None, logger: Optional[logging.Logger] = None) -> None:
        """Initialize queue servicer instance state."""
        self._logger = logger or logging.getLogger("queue.servicer")
        self._lock = threading.RLock()
        # Ordered dict behaves as a FIFO set keyed by job_id.
        self._queue: OrderedDict[str, int] = OrderedDict()

    def _set_error(self, context: grpc.ServicerContext, code: grpc.StatusCode, detail: str) -> None:
        """Set gRPC status code and detail text on the current Queue RPC context."""
        context.set_code(code)
        context.set_details(detail)

    def EnqueueJob(
        self,
        request: pb2.EnqueueJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.EnqueueJobResponse:
        """Enqueue job."""
        job_id = request.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.EnqueueJobResponse(accepted=False)

        with self._lock:
            if job_id not in self._queue:
                self._queue[job_id] = int(request.enqueued_at_ms)
            return pb2.EnqueueJobResponse(accepted=True)

    def DequeueJob(
        self,
        request: pb2.DequeueJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.DequeueJobResponse:
        """Dequeue job."""
        if not request.worker_id.strip():
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "worker_id must be non-empty")
            return pb2.DequeueJobResponse(found=False, job_id="")

        with self._lock:
            if not self._queue:
                return pb2.DequeueJobResponse(found=False, job_id="")
            job_id, _ = self._queue.popitem(last=False)
            return pb2.DequeueJobResponse(found=True, job_id=job_id)

    def RemoveJobIfPresent(
        self,
        request: pb2.RemoveJobIfPresentRequest,
        context: grpc.ServicerContext,
    ) -> pb2.RemoveJobIfPresentResponse:
        """Remove job if present."""
        job_id = request.job_id.strip()
        if not job_id:
            self._set_error(context, grpc.StatusCode.INVALID_ARGUMENT, "job_id must be non-empty")
            return pb2.RemoveJobIfPresentResponse(removed=False)

        with self._lock:
            existed = job_id in self._queue
            if existed:
                self._queue.pop(job_id, None)
            return pb2.RemoveJobIfPresentResponse(removed=existed)
