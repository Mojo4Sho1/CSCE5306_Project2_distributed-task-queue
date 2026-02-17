from __future__ import annotations

import logging
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
    Skeleton implementation for taskqueue.internal.v1.QueueInternalService.

    Current scope:
    - All QueueInternalService RPC handlers are explicitly implemented.
    - Every handler returns deterministic UNIMPLEMENTED while service scaffolding
      is being built.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("queue.servicer")

    def _unimplemented(
        self,
        method_name: str,
        context: grpc.ServicerContext,
        response_message,
    ):
        detail = f"{method_name} not implemented yet (queue skeleton)"
        self._logger.info(
            "queue.rpc.unimplemented",
            extra={"method": method_name, "grpc_code": "UNIMPLEMENTED"},
        )
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details(detail)
        return response_message

    def EnqueueJob(
        self,
        request: pb2.EnqueueJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.EnqueueJobResponse:
        return self._unimplemented(
            "EnqueueJob",
            context,
            pb2.EnqueueJobResponse(accepted=False),
        )

    def DequeueJob(
        self,
        request: pb2.DequeueJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.DequeueJobResponse:
        return self._unimplemented(
            "DequeueJob",
            context,
            pb2.DequeueJobResponse(found=False, job_id=""),
        )

    def RemoveJobIfPresent(
        self,
        request: pb2.RemoveJobIfPresentRequest,
        context: grpc.ServicerContext,
    ) -> pb2.RemoveJobIfPresentResponse:
        return self._unimplemented(
            "RemoveJobIfPresent",
            context,
            pb2.RemoveJobIfPresentResponse(removed=False),
        )
