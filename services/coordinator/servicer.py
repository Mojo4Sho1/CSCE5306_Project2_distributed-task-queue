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


class CoordinatorServicer(pb2_grpc.CoordinatorInternalServiceServicer):
    """
    Skeleton implementation for taskqueue.internal.v1.CoordinatorInternalService.

    Current scope:
    - All CoordinatorInternalService RPC handlers are explicitly implemented.
    - Every handler returns deterministic UNIMPLEMENTED while service scaffolding
      is being built.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("coordinator.servicer")

    def _unimplemented(
        self,
        method_name: str,
        context: grpc.ServicerContext,
        response_message,
    ):
        detail = f"{method_name} not implemented yet (coordinator skeleton)"
        self._logger.info(
            "coordinator.rpc.unimplemented",
            extra={"method": method_name, "grpc_code": "UNIMPLEMENTED"},
        )
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details(detail)
        return response_message

    def WorkerHeartbeat(
        self,
        request: pb2.WorkerHeartbeatRequest,
        context: grpc.ServicerContext,
    ) -> pb2.WorkerHeartbeatResponse:
        return self._unimplemented(
            "WorkerHeartbeat",
            context,
            pb2.WorkerHeartbeatResponse(
                accepted=False,
                next_heartbeat_in_ms=0,
            ),
        )

    def FetchWork(
        self,
        request: pb2.FetchWorkRequest,
        context: grpc.ServicerContext,
    ) -> pb2.FetchWorkResponse:
        return self._unimplemented(
            "FetchWork",
            context,
            pb2.FetchWorkResponse(
                assigned=False,
                job_id="",
                retry_after_ms=0,
            ),
        )

    def ReportWorkOutcome(
        self,
        request: pb2.ReportWorkOutcomeRequest,
        context: grpc.ServicerContext,
    ) -> pb2.ReportWorkOutcomeResponse:
        return self._unimplemented(
            "ReportWorkOutcome",
            context,
            pb2.ReportWorkOutcomeResponse(accepted=False),
        )
