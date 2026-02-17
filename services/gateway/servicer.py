# services/gateway/servicer.py
from __future__ import annotations

import logging
from typing import Optional

import grpc

try:
    # Preferred when PYTHONPATH includes ./generated
    import taskqueue_public_pb2 as pb2
    import taskqueue_public_pb2_grpc as pb2_grpc
except ModuleNotFoundError:  # pragma: no cover
    # Fallback if generated modules are imported as a package
    from generated import taskqueue_public_pb2 as pb2
    from generated import taskqueue_public_pb2_grpc as pb2_grpc


class GatewayServicer(pb2_grpc.TaskQueuePublicServiceServicer):
    """
    Skeleton implementation of the public TaskQueue gRPC API.

    Step 2.5 behavior lock:
    - All public RPCs return gRPC UNIMPLEMENTED for now.
    - Handlers are present with correct signatures and typed response objects.
    - No business logic or downstream service calls yet.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("gateway.servicer")

    def _unimplemented(
        self,
        method_name: str,
        context: grpc.ServicerContext,
        response_message,
    ):
        detail = f"{method_name} not implemented yet (gateway skeleton)"
        self._logger.info(
            "gateway.rpc.unimplemented",
            extra={"method": method_name, "grpc_code": "UNIMPLEMENTED"},
        )
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details(detail)
        return response_message

    def SubmitJob(
        self,
        request: pb2.SubmitJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.SubmitJobResponse:
        return self._unimplemented(
            "SubmitJob",
            context,
            pb2.SubmitJobResponse(),
        )

    def GetJobStatus(
        self,
        request: pb2.GetJobStatusRequest,
        context: grpc.ServicerContext,
    ) -> pb2.GetJobStatusResponse:
        return self._unimplemented(
            "GetJobStatus",
            context,
            pb2.GetJobStatusResponse(job_id=request.job_id),
        )

    def GetJobResult(
        self,
        request: pb2.GetJobResultRequest,
        context: grpc.ServicerContext,
    ) -> pb2.GetJobResultResponse:
        return self._unimplemented(
            "GetJobResult",
            context,
            pb2.GetJobResultResponse(job_id=request.job_id),
        )

    def CancelJob(
        self,
        request: pb2.CancelJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.CancelJobResponse:
        return self._unimplemented(
            "CancelJob",
            context,
            pb2.CancelJobResponse(
                job_id=request.job_id,
                accepted=False,
                current_status=pb2.JOB_STATUS_UNSPECIFIED,
                already_terminal=False,
            ),
        )

    def ListJobs(
        self,
        request: pb2.ListJobsRequest,
        context: grpc.ServicerContext,
    ) -> pb2.ListJobsResponse:
        return self._unimplemented(
            "ListJobs",
            context,
            pb2.ListJobsResponse(),
        )
