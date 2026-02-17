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


class JobServicer(pb2_grpc.JobInternalServiceServicer):
    """
    Skeleton implementation for taskqueue.internal.v1.JobInternalService.

    Current scope:
    - All JobInternalService RPC handlers are explicitly implemented.
    - Every handler returns deterministic UNIMPLEMENTED while service scaffolding
      is being built.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("job.servicer")

    def _unimplemented(
        self,
        method_name: str,
        context: grpc.ServicerContext,
        response_message,
    ):
        detail = f"{method_name} not implemented yet (job skeleton)"
        self._logger.info(
            "job.rpc.unimplemented",
            extra={"method": method_name, "grpc_code": "UNIMPLEMENTED"},
        )
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details(detail)
        return response_message

    def CreateJob(
        self,
        request: pb2.CreateJobRequest,
        context: grpc.ServicerContext,
    ) -> pb2.CreateJobResponse:
        return self._unimplemented(
            "CreateJob",
            context,
            pb2.CreateJobResponse(
                job_id="",
                status=0,  # JOB_STATUS_UNSPECIFIED from taskqueue.v1.JobStatus
            ),
        )

    def DeleteJobIfStatus(
        self,
        request: pb2.DeleteJobIfStatusRequest,
        context: grpc.ServicerContext,
    ) -> pb2.DeleteJobIfStatusResponse:
        return self._unimplemented(
            "DeleteJobIfStatus",
            context,
            pb2.DeleteJobIfStatusResponse(
                deleted=False,
                current_status=0,  # JOB_STATUS_UNSPECIFIED from taskqueue.v1.JobStatus
            ),
        )

    def GetJobRecord(
        self,
        request: pb2.GetJobRecordRequest,
        context: grpc.ServicerContext,
    ) -> pb2.GetJobRecordResponse:
        return self._unimplemented(
            "GetJobRecord",
            context,
            pb2.GetJobRecordResponse(
                summary={
                    "job_id": request.job_id,
                    "status": 0,  # JOB_STATUS_UNSPECIFIED from taskqueue.v1.JobStatus
                },
                failure_reason="",
            ),
        )

    def ListJobRecords(
        self,
        request: pb2.ListJobRecordsRequest,
        context: grpc.ServicerContext,
    ) -> pb2.ListJobRecordsResponse:
        return self._unimplemented(
            "ListJobRecords",
            context,
            pb2.ListJobRecordsResponse(),
        )

    def TransitionJobStatus(
        self,
        request: pb2.TransitionJobStatusRequest,
        context: grpc.ServicerContext,
    ) -> pb2.TransitionJobStatusResponse:
        return self._unimplemented(
            "TransitionJobStatus",
            context,
            pb2.TransitionJobStatusResponse(
                applied=False,
                current_status=0,  # JOB_STATUS_UNSPECIFIED from taskqueue.v1.JobStatus
            ),
        )

    def SetCancelRequested(
        self,
        request: pb2.SetCancelRequestedRequest,
        context: grpc.ServicerContext,
    ) -> pb2.SetCancelRequestedResponse:
        return self._unimplemented(
            "SetCancelRequested",
            context,
            pb2.SetCancelRequestedResponse(
                applied=False,
                current_status=0,  # JOB_STATUS_UNSPECIFIED from taskqueue.v1.JobStatus
            ),
        )
