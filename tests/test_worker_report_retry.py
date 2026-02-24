"""Test coverage for test worker report retry."""

import logging
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import grpc
import services.worker.worker as worker_module
import taskqueue_internal_pb2 as pb2


class _FakeStub:
    """Test stub for coordinator RPC responses."""
    def __init__(self, outcomes):
        """Initialize test state."""
        self._outcomes = list(outcomes)
        self.calls = 0

    def ReportWorkOutcome(self, request, timeout=None):
        """Test helper for report work outcome."""
        self.calls += 1
        if not self._outcomes:
            return SimpleNamespace(accepted=False)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeRpcError(grpc.RpcError):
    """Test double for RPC error responses."""
    def __init__(self, status_code, details="transient error"):
        """Initialize test state."""
        super().__init__()
        self._status_code = status_code
        self._details = details

    def code(self):
        """Return the configured status code."""
        return self._status_code

    def details(self):
        """Return the configured error details."""
        return self._details


class WorkerReportRetryTests(unittest.TestCase):
    """Behavioral tests for worker report retry."""
    def _build_runtime(self, *, initial_ms=100, multiplier=2.0, max_ms=1000, attempts=4):
        """Build a runtime instance wired with test doubles."""
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
        """Checks retry wait uses full jitter bounds and window progression."""
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
        """Checks retry window is capped by max backoff."""
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
        """Checks success on first attempt has no retry wait."""
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

    def test_stop_event_set_after_retry_wait_exits_early(self):
        """Checks stop event set after retry wait exits early."""
        runtime = self._build_runtime(initial_ms=100, multiplier=2.0, max_ms=1000, attempts=4)
        runtime._stub = _FakeStub(
            [
                SimpleNamespace(accepted=False),
                SimpleNamespace(accepted=True),
            ]
        )
        runtime._stop_event = Mock()
        runtime._stop_event.is_set.return_value = True

        request = pb2.ReportWorkOutcomeRequest(worker_id="w1", job_id="job-stop")

        with patch.object(worker_module.random, "randint", return_value=25):
            accepted = runtime._report_with_retry(request)

        self.assertFalse(accepted)
        self.assertEqual(runtime._stub.calls, 1)
        runtime._stop_event.wait.assert_called_once_with(0.025)

    def test_transient_rpc_error_retries_and_then_succeeds(self):
        """Checks transient rpc error retries and then succeeds."""
        runtime = self._build_runtime(initial_ms=100, multiplier=2.0, max_ms=1000, attempts=4)
        runtime._stub = _FakeStub(
            [
                _FakeRpcError(grpc.StatusCode.UNAVAILABLE, "coordinator unavailable"),
                SimpleNamespace(accepted=True),
            ]
        )
        runtime._stop_event = Mock()
        runtime._stop_event.is_set.return_value = False

        request = pb2.ReportWorkOutcomeRequest(worker_id="w1", job_id="job-rpc-success")

        with patch.object(worker_module.random, "randint", return_value=40) as randint_mock:
            accepted = runtime._report_with_retry(request)

        self.assertTrue(accepted)
        self.assertEqual(runtime._stub.calls, 2)
        self.assertEqual(randint_mock.call_args_list[0].args, (0, 100))
        runtime._stop_event.wait.assert_called_once_with(0.04)

    def test_transient_rpc_error_retries_until_max_attempts(self):
        """Checks transient rpc error retries until max attempts."""
        runtime = self._build_runtime(initial_ms=100, multiplier=2.0, max_ms=1000, attempts=4)
        runtime._stub = _FakeStub(
            [
                _FakeRpcError(grpc.StatusCode.UNAVAILABLE, "transient-1"),
                _FakeRpcError(grpc.StatusCode.DEADLINE_EXCEEDED, "transient-2"),
                _FakeRpcError(grpc.StatusCode.RESOURCE_EXHAUSTED, "transient-3"),
                _FakeRpcError(grpc.StatusCode.UNAVAILABLE, "transient-4"),
            ]
        )
        runtime._stop_event = Mock()
        runtime._stop_event.is_set.return_value = False

        request = pb2.ReportWorkOutcomeRequest(worker_id="w1", job_id="job-rpc-fail")

        with patch.object(worker_module.random, "randint", side_effect=[10, 20, 30]) as randint_mock:
            accepted = runtime._report_with_retry(request)

        self.assertFalse(accepted)
        self.assertEqual(runtime._stub.calls, 4)
        self.assertEqual(randint_mock.call_args_list[0].args, (0, 100))
        self.assertEqual(randint_mock.call_args_list[1].args, (0, 200))
        self.assertEqual(randint_mock.call_args_list[2].args, (0, 400))
        runtime._stop_event.wait.assert_any_call(0.01)
        runtime._stop_event.wait.assert_any_call(0.02)
        runtime._stop_event.wait.assert_any_call(0.03)


if __name__ == "__main__":
    unittest.main()
