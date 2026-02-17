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


class ResultServicer(pb2_grpc.ResultInternalServiceServicer):
    """
    Skeleton implementation for taskqueue.internal.v1.ResultInternalService.

    Current scope:
    - All ResultInternalService RPC handlers are explicitly implemented.
    - Every handler returns deterministic UNIMPLEMENTED while service scaffolding
      is being built.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("result.servicer")

    def _unimplemented(
        self,
        method_name: str,
        context: grpc.ServicerContext,
        response_message,
    ):
        detail = f"{method_name} not implemented yet (result skeleton)"
        self._logger.info(
            "result.rpc.unimplemented",
            extra={"method": method_name, "grpc_code": "UNIMPLEMENTED"},
        )
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details(detail)
        return response_message

    def StoreResult(
        self,
        request: pb2.StoreResultRequest,
        context: grpc.ServicerContext,
    ) -> pb2.StoreResultResponse:
        return self._unimplemented(
            "StoreResult",
            context,
            pb2.StoreResultResponse(
                stored=False,
                already_exists=False,
                current_terminal_status=0,  # JOB_STATUS_UNSPECIFIED from taskqueue.v1.JobStatus
            ),
        )

    def GetResult(
        self,
        request: pb2.GetResultRequest,
        context: grpc.ServicerContext,
    ) -> pb2.GetResultResponse:
        return self._unimplemented(
            "GetResult",
            context,
            pb2.GetResultResponse(
                found=False,
                job_id=request.job_id,
                terminal_status=0,  # JOB_STATUS_UNSPECIFIED from taskqueue.v1.JobStatus
                runtime_ms=0,
                output_summary="",
                output_bytes=b"",
                checksum="",
            ),
        )
