import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import grpc

# Path bootstrap for direct unittest module execution.
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[1]
_GENERATED_DIR = _REPO_ROOT / "generated"
for _p in (str(_REPO_ROOT), str(_GENERATED_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from services.coordinator.servicer import CoordinatorServicer
from services.job.servicer import JobServicer
from services.result.servicer import ResultServicer

try:
    import taskqueue_internal_pb2 as pb2
    import taskqueue_public_pb2 as public_pb2
except ModuleNotFoundError:  # pragma: no cover
    from generated import taskqueue_internal_pb2 as pb2
    from generated import taskqueue_public_pb2 as public_pb2


class _FakeRpcError(grpc.RpcError):
    def __init__(self, status_code, details="rpc error"):
        super().__init__()
        self._status_code = status_code
        self._details = details

    def code(self):
        return self._status_code

    def details(self):
        return self._details


class _FakeContext:
    def __init__(self):
        self._code = None
        self._details = ""

    def set_code(self, code):
        self._code = code

    def set_details(self, details):
        self._details = details


class _ResultClientAdapter:
    def __init__(self):
        self._servicer = ResultServicer(config=SimpleNamespace(max_output_bytes=262144))

    def StoreResult(self, request, timeout=None):
        del timeout
        ctx = _FakeContext()
        resp = self._servicer.StoreResult(request, ctx)
        if ctx._code is not None:
            raise _FakeRpcError(ctx._code, ctx._details)
        return resp

    def GetResult(self, request, timeout=None):
        del timeout
        ctx = _FakeContext()
        resp = self._servicer.GetResult(request, ctx)
        if ctx._code is not None:
            raise _FakeRpcError(ctx._code, ctx._details)
        return resp


class _JobClientAdapter:
    def __init__(self):
        self._servicer = JobServicer(config=SimpleNamespace(max_dedup_keys=10000))

    def CreateJob(self, request, timeout=None):
        del timeout
        ctx = _FakeContext()
        resp = self._servicer.CreateJob(request, ctx)
        if ctx._code is not None:
            raise _FakeRpcError(ctx._code, ctx._details)
        return resp

    def TransitionJobStatus(self, request, timeout=None):
        del timeout
        ctx = _FakeContext()
        resp = self._servicer.TransitionJobStatus(request, ctx)
        if ctx._code is not None:
            raise _FakeRpcError(ctx._code, ctx._details)
        return resp

    def GetJobRecord(self, request, timeout=None):
        del timeout
        ctx = _FakeContext()
        resp = self._servicer.GetJobRecord(request, ctx)
        if ctx._code is not None:
            raise _FakeRpcError(ctx._code, ctx._details)
        return resp


class CoordinatorReportOutcomeIdempotencyTests(unittest.TestCase):
    def _build_runtime(self):
        cfg = SimpleNamespace(
            heartbeat_interval_ms=1000,
            worker_timeout_ms=4000,
            internal_rpc_timeout_ms=1000,
            job_addr="",
            queue_addr="",
            result_addr="",
        )
        job_client = _JobClientAdapter()
        result_client = _ResultClientAdapter()
        runtime = CoordinatorServicer(
            config=cfg,
            logger=logging.getLogger("coordinator-test"),
            job_client=job_client,
            queue_client=Mock(),
            result_client=result_client,
        )
        return runtime, job_client, result_client

    def _create_running_job(self, job_client, suffix):
        created = job_client.CreateJob(
            pb2.CreateJobRequest(
                spec=public_pb2.JobSpec(
                    job_type=f"idempotency-{suffix}",
                    work_duration_ms=120,
                    payload_size_bytes=16,
                    labels={"suite": "test_coordinator_report_outcome_idempotency"},
                )
            )
        )
        transitioned = job_client.TransitionJobStatus(
            pb2.TransitionJobStatusRequest(
                job_id=created.job_id,
                expected_from_status=public_pb2.QUEUED,
                to_status=public_pb2.RUNNING,
                actor="test",
                reason="setup-running",
            )
        )
        self.assertTrue(transitioned.applied)
        return created.job_id

    def test_first_terminal_write_is_accepted_and_persisted_for_done_and_failed(self):
        for outcome, expected_status, failure_reason in [
            (public_pb2.JOB_OUTCOME_SUCCEEDED, public_pb2.DONE, ""),
            (public_pb2.JOB_OUTCOME_FAILED, public_pb2.FAILED, "simulated-failure"),
        ]:
            with self.subTest(outcome=outcome):
                coordinator, job_client, result_client = self._build_runtime()
                job_id = self._create_running_job(job_client, suffix=f"first-{outcome}")

                response = coordinator.ReportWorkOutcome(
                    pb2.ReportWorkOutcomeRequest(
                        worker_id="worker-test",
                        job_id=job_id,
                        outcome=outcome,
                        runtime_ms=120,
                        failure_reason=failure_reason,
                        output_summary=f"summary-{outcome}",
                        output_bytes=f"bytes-{outcome}".encode("utf-8"),
                        checksum=f"checksum-{outcome}",
                    ),
                    _FakeContext(),
                )

                self.assertTrue(response.accepted)
                record = job_client.GetJobRecord(pb2.GetJobRecordRequest(job_id=job_id))
                self.assertEqual(record.summary.status, expected_status)
                result = result_client.GetResult(pb2.GetResultRequest(job_id=job_id))
                self.assertTrue(result.found)
                self.assertEqual(result.terminal_status, expected_status)

    def test_duplicate_equivalent_report_is_idempotent_and_stable(self):
        coordinator, job_client, result_client = self._build_runtime()
        job_id = self._create_running_job(job_client, suffix="duplicate")
        request = pb2.ReportWorkOutcomeRequest(
            worker_id="worker-test",
            job_id=job_id,
            outcome=public_pb2.JOB_OUTCOME_SUCCEEDED,
            runtime_ms=120,
            failure_reason="",
            output_summary="first-summary",
            output_bytes=b"first-bytes",
            checksum="checksum-1",
        )

        first = coordinator.ReportWorkOutcome(request, _FakeContext())
        second = coordinator.ReportWorkOutcome(request, _FakeContext())

        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        record = job_client.GetJobRecord(pb2.GetJobRecordRequest(job_id=job_id))
        self.assertEqual(record.summary.status, public_pb2.DONE)
        result = result_client.GetResult(pb2.GetResultRequest(job_id=job_id))
        self.assertTrue(result.found)
        self.assertEqual(result.terminal_status, public_pb2.DONE)
        self.assertEqual(result.output_summary, "first-summary")
        self.assertEqual(result.output_bytes, b"first-bytes")
        self.assertEqual(result.checksum, "checksum-1")

    def test_conflicting_repeated_terminal_report_does_not_corrupt_state(self):
        coordinator, job_client, result_client = self._build_runtime()
        job_id = self._create_running_job(job_client, suffix="conflict")

        succeeded = coordinator.ReportWorkOutcome(
            pb2.ReportWorkOutcomeRequest(
                worker_id="worker-test",
                job_id=job_id,
                outcome=public_pb2.JOB_OUTCOME_SUCCEEDED,
                runtime_ms=120,
                failure_reason="",
                output_summary="done-summary",
                output_bytes=b"done-bytes",
                checksum="done-checksum",
            ),
            _FakeContext(),
        )
        failed_conflict = coordinator.ReportWorkOutcome(
            pb2.ReportWorkOutcomeRequest(
                worker_id="worker-test",
                job_id=job_id,
                outcome=public_pb2.JOB_OUTCOME_FAILED,
                runtime_ms=130,
                failure_reason="late-failure",
                output_summary="failed-summary",
                output_bytes=b"failed-bytes",
                checksum="failed-checksum",
            ),
            _FakeContext(),
        )

        self.assertTrue(succeeded.accepted)
        self.assertTrue(failed_conflict.accepted)
        record = job_client.GetJobRecord(pb2.GetJobRecordRequest(job_id=job_id))
        self.assertEqual(record.summary.status, public_pb2.DONE)
        result = result_client.GetResult(pb2.GetResultRequest(job_id=job_id))
        self.assertTrue(result.found)
        self.assertEqual(result.terminal_status, public_pb2.DONE)
        self.assertEqual(result.output_summary, "done-summary")
        self.assertEqual(result.output_bytes, b"done-bytes")
        self.assertEqual(result.checksum, "done-checksum")


if __name__ == "__main__":
    unittest.main()
