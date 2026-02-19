import logging
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import services.worker.worker as worker_module
import taskqueue_internal_pb2 as pb2


class _FakeStub:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def ReportWorkOutcome(self, request, timeout=None):
        self.calls += 1
        if not self._outcomes:
            return SimpleNamespace(accepted=False)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class WorkerReportRetryTests(unittest.TestCase):
    def _build_runtime(self, *, initial_ms=100, multiplier=2.0, max_ms=1000, attempts=4):
        cfg = SimpleNamespace(
            service_name="worker",
            log_level="INFO",
            coordinator_addr="coordinator:50054",
            worker_id="worker-test",
            heartbeat_interval_ms=1000,
            fetch_idle_sleep_ms=200,
            internal_rpc_timeout_ms=1000,
            fetch_work_timeout_ms=1500,
            worker_heartbeat_timeout_ms=1000,
            report_retry_initial_backoff_ms=initial_ms,
            report_retry_multiplier=multiplier,
            report_retry_max_backoff_ms=max_ms,
            report_retry_max_attempts=attempts,
        )
        with patch.object(worker_module.grpc, "insecure_channel", return_value=Mock()), patch.object(
            worker_module.pb2_grpc, "CoordinatorInternalServiceStub", return_value=Mock()
        ):
            runtime = worker_module.WorkerRuntime(config=cfg, logger=logging.getLogger("worker-test"))
        return runtime

    def test_retry_wait_uses_full_jitter_bounds_and_window_progression(self):
        runtime = self._build_runtime(initial_ms=100, multiplier=2.0, max_ms=1000, attempts=4)
        runtime._stub = _FakeStub(
            [
                SimpleNamespace(accepted=False),
                SimpleNamespace(accepted=False),
                SimpleNamespace(accepted=False),
                SimpleNamespace(accepted=False),
            ]
        )
        runtime._stop_event = Mock()
        runtime._stop_event.is_set.return_value = False

        request = pb2.ReportWorkOutcomeRequest(worker_id="w1", job_id="job-1")

        with patch.object(worker_module.random, "randint", side_effect=[0, 50, 400]) as randint_mock:
            accepted = runtime._report_with_retry(request)

        self.assertFalse(accepted)
        self.assertEqual(runtime._stub.calls, 4)
        self.assertEqual(randint_mock.call_args_list[0].args, (0, 100))
        self.assertEqual(randint_mock.call_args_list[1].args, (0, 200))
        self.assertEqual(randint_mock.call_args_list[2].args, (0, 400))
        runtime._stop_event.wait.assert_any_call(0.0)
        runtime._stop_event.wait.assert_any_call(0.05)
        runtime._stop_event.wait.assert_any_call(0.4)

    def test_retry_window_is_capped_by_max_backoff(self):
        runtime = self._build_runtime(initial_ms=700, multiplier=2.0, max_ms=1000, attempts=4)
        runtime._stub = _FakeStub(
            [
                SimpleNamespace(accepted=False),
                SimpleNamespace(accepted=False),
                SimpleNamespace(accepted=False),
                SimpleNamespace(accepted=False),
            ]
        )
        runtime._stop_event = Mock()
        runtime._stop_event.is_set.return_value = False

        request = pb2.ReportWorkOutcomeRequest(worker_id="w1", job_id="job-2")

        with patch.object(worker_module.random, "randint", side_effect=[1, 2, 3]) as randint_mock:
            accepted = runtime._report_with_retry(request)

        self.assertFalse(accepted)
        self.assertEqual(runtime._stub.calls, 4)
        self.assertEqual(randint_mock.call_args_list[0].args, (0, 700))
        self.assertEqual(randint_mock.call_args_list[1].args, (0, 1000))
        self.assertEqual(randint_mock.call_args_list[2].args, (0, 1000))

    def test_success_on_first_attempt_has_no_retry_wait(self):
        runtime = self._build_runtime(initial_ms=100, multiplier=2.0, max_ms=1000, attempts=4)
        runtime._stub = _FakeStub([SimpleNamespace(accepted=True)])
        runtime._stop_event = Mock()
        runtime._stop_event.is_set.return_value = False

        request = pb2.ReportWorkOutcomeRequest(worker_id="w1", job_id="job-3")

        with patch.object(worker_module.random, "randint") as randint_mock:
            accepted = runtime._report_with_retry(request)

        self.assertTrue(accepted)
        self.assertEqual(runtime._stub.calls, 1)
        randint_mock.assert_not_called()
        runtime._stop_event.wait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
