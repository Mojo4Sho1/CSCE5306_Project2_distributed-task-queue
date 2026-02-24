"""
Worker runtime process with deterministic simulated execution.

Responsibilities:
- load/accept worker config
- initialize coordinator client stub
- run heartbeat/fetch loop
- execute deterministic simulated work for assigned jobs
- report outcomes to Coordinator via ReportWorkOutcome
"""

from __future__ import annotations

import json
import hashlib
import logging
import os
import random
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import grpc
from common.rpc_defaults import (
    FETCH_WORK_RPC_TIMEOUT_MS,
    INTERNAL_UNARY_RPC_TIMEOUT_MS,
    RETRY_INITIAL_DELAY_MS,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY_MS,
    RETRY_MULTIPLIER,
    WORKER_HEARTBEAT_RPC_TIMEOUT_MS,
)


# -----------------------------------------------------------------------------
# Path bootstrap so this file works when run either as:
#   - python -m services.worker.worker
#   - python services/worker/worker.py
# -----------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
_GENERATED_DIR = _REPO_ROOT / "generated"

for _p in (str(_REPO_ROOT), str(_GENERATED_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# Generated stubs
import taskqueue_internal_pb2 as pb2  # type: ignore
import taskqueue_internal_pb2_grpc as pb2_grpc  # type: ignore
import taskqueue_public_pb2 as public_pb2  # type: ignore


# Common utilities (use if present; fallback behavior is built in below)
try:
    import common as _common  # type: ignore
except ModuleNotFoundError as e:
    if e.name != "common":
        raise
    _common = None

if _common is None:
    load_service_config = None
    init_logger = None
    log_event = None
else:
    missing = [
        name
        for name in ("load_service_config", "init_logger", "log_event", "now_ms")
        if not hasattr(_common, name)
    ]
    if missing:
        raise ImportError(f"'common' is missing required exports: {', '.join(missing)}")

    load_service_config = _common.load_service_config  # type: ignore[attr-defined]
    init_logger = _common.init_logger  # type: ignore[attr-defined]
    log_event = _common.log_event  # type: ignore[attr-defined]
    now_ms = _common.now_ms  # type: ignore[attr-defined]


def _coerce_int(value: Any, default: int) -> int:
    """Coerce a raw value into the expected runtime type."""
    try:
        return int(value)
    except Exception:
        return default


def _resolve_worker_config() -> Any:
    """
    Supports multiple common.load_service_config signatures:
      - load_service_config("worker")
      - load_service_config(service_name="worker")
      - load_service_config()
    Falls back to environment defaults if common config is unavailable.
    """
    if load_service_config is not None:
        try:
            return load_service_config("worker")
        except TypeError:
            pass
        except Exception:
            pass

        try:
            return load_service_config(service_name="worker")
        except TypeError:
            pass
        except Exception:
            pass

        try:
            return load_service_config()
        except Exception:
            pass

    class _FallbackConfig:
        """ fallback config state and behavior."""
        service_name = "worker"
        log_level = "INFO"
        coordinator_addr = "127.0.0.1:50054"
        worker_id = ""
        heartbeat_interval_ms = 1000
        fetch_idle_sleep_ms = 200
        internal_rpc_timeout_ms = INTERNAL_UNARY_RPC_TIMEOUT_MS
        fetch_work_timeout_ms = FETCH_WORK_RPC_TIMEOUT_MS
        worker_heartbeat_timeout_ms = WORKER_HEARTBEAT_RPC_TIMEOUT_MS
        report_retry_initial_backoff_ms = RETRY_INITIAL_DELAY_MS
        report_retry_multiplier = RETRY_MULTIPLIER
        report_retry_max_backoff_ms = RETRY_MAX_DELAY_MS
        report_retry_max_attempts = RETRY_MAX_ATTEMPTS

    return _FallbackConfig()


def _resolve_logger(cfg: Any) -> logging.Logger:
    """Resolve a runtime dependency from configuration."""
    service_name = getattr(cfg, "service_name", "worker")
    level = getattr(cfg, "log_level", "INFO")

    if init_logger is not None:
        try:
            return init_logger(service_name=service_name, level=level)
        except TypeError:
            pass
        except Exception:
            pass
        try:
            return init_logger(service_name, level)
        except TypeError:
            pass
        except Exception:
            pass
        try:
            return init_logger(service_name)
        except Exception:
            pass

    logger = logging.getLogger(service_name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    logger.propagate = False
    return logger


def _emit(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Internal helper to  emit."""
    if log_event is not None:
        try:
            log_event(logger, event=event, **fields)
            return
        except TypeError:
            pass
        except Exception:
            pass
        try:
            log_event(logger, "INFO", event, **fields)
            return
        except Exception:
            pass

    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _now_ms() -> int:
    """Internal helper to  now ms."""
    if _common is not None:
        return int(now_ms())  # type: ignore[misc]
    return int(time.time() * 1000)


def _resolve_worker_id(cfg: Any) -> str:
    """Resolve a runtime dependency from configuration."""
    candidate = str(getattr(cfg, "worker_id", "") or "").strip()
    if candidate:
        return candidate

    env_id = str(os.getenv("WORKER_ID", "")).strip()
    if env_id:
        return env_id

    return socket.gethostname().strip() or "worker-unknown"


def _should_force_failure(spec: Any) -> bool:
    """
    Deterministic integration trigger without contract changes:
    any job_type containing "force-fail" is reported as FAILED by worker.
    """
    job_type = str(getattr(spec, "job_type", "")).strip().lower()
    return "force-fail" in job_type


class WorkerRuntime:
    """Deterministic worker loop with coordinator RPC integration."""

    def __init__(self, config: Any, logger: logging.Logger) -> None:
        """Initialize worker runtime instance state."""
        self._cfg = config
        self._logger = logger
        self._stop_event = threading.Event()

        self._coordinator_addr = str(getattr(config, "coordinator_addr", "127.0.0.1:50054"))
        self._worker_id = _resolve_worker_id(config)
        self._heartbeat_interval_ms = _coerce_int(getattr(config, "heartbeat_interval_ms", 1000), 1000)
        self._fetch_idle_sleep_ms = _coerce_int(getattr(config, "fetch_idle_sleep_ms", 200), 200)
        self._internal_rpc_timeout_s = (
            max(_coerce_int(getattr(config, "internal_rpc_timeout_ms", INTERNAL_UNARY_RPC_TIMEOUT_MS), INTERNAL_UNARY_RPC_TIMEOUT_MS), 1)
            / 1000.0
        )
        self._fetch_work_timeout_s = (
            max(_coerce_int(getattr(config, "fetch_work_timeout_ms", FETCH_WORK_RPC_TIMEOUT_MS), FETCH_WORK_RPC_TIMEOUT_MS), 1)
            / 1000.0
        )
        self._heartbeat_timeout_s = (
            max(
                _coerce_int(
                    getattr(config, "worker_heartbeat_timeout_ms", WORKER_HEARTBEAT_RPC_TIMEOUT_MS),
                    WORKER_HEARTBEAT_RPC_TIMEOUT_MS,
                ),
                1,
            )
            / 1000.0
        )
        self._report_max_attempts = max(
            _coerce_int(getattr(config, "report_retry_max_attempts", RETRY_MAX_ATTEMPTS), RETRY_MAX_ATTEMPTS),
            1,
        )
        self._report_initial_backoff_ms = max(
            _coerce_int(
                getattr(config, "report_retry_initial_backoff_ms", RETRY_INITIAL_DELAY_MS),
                RETRY_INITIAL_DELAY_MS,
            ),
            1,
        )
        self._report_max_backoff_ms = max(
            _coerce_int(
                getattr(config, "report_retry_max_backoff_ms", RETRY_MAX_DELAY_MS),
                RETRY_MAX_DELAY_MS,
            ),
            self._report_initial_backoff_ms,
        )
        self._report_retry_multiplier = max(
            float(getattr(config, "report_retry_multiplier", RETRY_MULTIPLIER)),
            1.0,
        )

        if self._heartbeat_interval_ms < 1:
            self._heartbeat_interval_ms = 1000
        if self._fetch_idle_sleep_ms < 1:
            self._fetch_idle_sleep_ms = 200

        self._channel = grpc.insecure_channel(self._coordinator_addr)
        self._stub = pb2_grpc.CoordinatorInternalServiceStub(self._channel)
        self._last_heartbeat_at_ms = 0

    def start(self) -> None:
        """Start."""
        _emit(
            self._logger,
            "worker.startup.ready",
            worker_id=self._worker_id,
            coordinator_addr=self._coordinator_addr,
            heartbeat_interval_ms=self._heartbeat_interval_ms,
            fetch_idle_sleep_ms=self._fetch_idle_sleep_ms,
        )

    def stop(self) -> None:
        """Stop."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        _emit(self._logger, "worker.shutdown.begin", worker_id=self._worker_id)
        self._channel.close()
        _emit(self._logger, "worker.shutdown.complete", worker_id=self._worker_id)

    def run(self) -> int:
        """Execute the configured workflow."""
        self.start()
        try:
            while not self._stop_event.is_set():
                self._run_iteration()
        finally:
            self.stop()
        return 0

    def _run_iteration(self) -> None:
        """Internal helper to  run iteration."""
        now = _now_ms()
        if now - self._last_heartbeat_at_ms >= self._heartbeat_interval_ms:
            self._send_heartbeat(now)
            self._last_heartbeat_at_ms = now

        assignment, retry_after_ms = self._fetch_work()
        if assignment is not None:
            self._execute_and_report(assignment)
            return

        sleep_ms = retry_after_ms if retry_after_ms > 0 else self._fetch_idle_sleep_ms
        sleep_ms = max(sleep_ms, 50)
        _emit(
            self._logger,
            "worker.loop.idle_sleep",
            worker_id=self._worker_id,
            sleep_ms=sleep_ms,
        )
        self._stop_event.wait(sleep_ms / 1000.0)

    def _send_heartbeat(self, heartbeat_at_ms: int) -> None:
        """Internal helper to  send heartbeat."""
        _emit(
            self._logger,
            "worker.heartbeat.attempt",
            worker_id=self._worker_id,
            coordinator_addr=self._coordinator_addr,
        )
        try:
            response = self._stub.WorkerHeartbeat(
                pb2.WorkerHeartbeatRequest(
                    worker_id=self._worker_id,
                    heartbeat_at_ms=heartbeat_at_ms,
                    capacity_hint=1,
                ),
                timeout=self._heartbeat_timeout_s,
            )
            _emit(
                self._logger,
                "worker.heartbeat.response",
                worker_id=self._worker_id,
                accepted=bool(getattr(response, "accepted", False)),
                next_heartbeat_in_ms=int(getattr(response, "next_heartbeat_in_ms", 0)),
            )
        except grpc.RpcError as exc:
            _emit(
                self._logger,
                "worker.heartbeat.rpc_error",
                level="WARNING",
                worker_id=self._worker_id,
                grpc_code=exc.code().name if exc.code() is not None else "UNKNOWN",
                detail=exc.details() or "",
            )
        except Exception as exc:
            _emit(
                self._logger,
                "worker.heartbeat.error",
                level="WARNING",
                worker_id=self._worker_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _fetch_work(self) -> tuple[Optional[pb2.FetchWorkResponse], int]:
        """Internal helper to  fetch work."""
        _emit(
            self._logger,
            "worker.fetch.attempt",
            worker_id=self._worker_id,
            coordinator_addr=self._coordinator_addr,
        )
        try:
            response = self._stub.FetchWork(
                pb2.FetchWorkRequest(worker_id=self._worker_id),
                timeout=self._fetch_work_timeout_s,
            )
            assigned = bool(getattr(response, "assigned", False))
            retry_after_ms = int(getattr(response, "retry_after_ms", 0))
            _emit(
                self._logger,
                "worker.fetch.response",
                worker_id=self._worker_id,
                assigned=assigned,
                retry_after_ms=retry_after_ms,
            )
            if assigned and str(getattr(response, "job_id", "")).strip():
                return response, retry_after_ms
            return None, retry_after_ms
        except grpc.RpcError as exc:
            _emit(
                self._logger,
                "worker.fetch.rpc_error",
                level="WARNING",
                worker_id=self._worker_id,
                grpc_code=exc.code().name if exc.code() is not None else "UNKNOWN",
                detail=exc.details() or "",
            )
            return None, self._fetch_idle_sleep_ms
        except Exception as exc:
            _emit(
                self._logger,
                "worker.fetch.error",
                level="WARNING",
                worker_id=self._worker_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            return None, self._fetch_idle_sleep_ms

    def _execute_and_report(self, fetch: pb2.FetchWorkResponse) -> None:
        """Internal helper to  execute and report."""
        job_id = str(fetch.job_id).strip()
        spec = getattr(fetch, "spec", public_pb2.JobSpec())
        job_type = str(getattr(spec, "job_type", "")).strip()
        runtime_ms = self._planned_runtime_ms(spec)
        force_failed = _should_force_failure(spec)

        if force_failed:
            failure_reason = f"simulated_failure force-fail worker_id={self._worker_id} job_type={job_type}"
            output_bytes = failure_reason.encode("utf-8")
            output_summary = (
                f"simulated_failure worker_id={self._worker_id} "
                f"runtime_ms={runtime_ms} reason={failure_reason}"
            )
            outcome = public_pb2.JOB_OUTCOME_FAILED
        else:
            failure_reason = ""
            output_bytes = self._build_output_bytes(job_id, spec, runtime_ms)
            output_summary = (
                f"simulated_success worker_id={self._worker_id} "
                f"runtime_ms={runtime_ms} bytes={len(output_bytes)}"
            )
            outcome = public_pb2.JOB_OUTCOME_SUCCEEDED

        checksum = hashlib.sha256(output_bytes).hexdigest()

        _emit(
            self._logger,
            "worker.execute.begin",
            worker_id=self._worker_id,
            job_id=job_id,
            planned_runtime_ms=runtime_ms,
            job_type=job_type,
            force_failed=force_failed,
        )
        self._stop_event.wait(runtime_ms / 1000.0)
        if self._stop_event.is_set():
            _emit(
                self._logger,
                "worker.execute.interrupted",
                worker_id=self._worker_id,
                job_id=job_id,
            )
            return

        request = pb2.ReportWorkOutcomeRequest(
            worker_id=self._worker_id,
            job_id=job_id,
            outcome=outcome,
            runtime_ms=runtime_ms,
            failure_reason=failure_reason,
            output_summary=output_summary,
            output_bytes=output_bytes,
            checksum=checksum,
        )

        accepted = self._report_with_retry(request=request)
        _emit(
            self._logger,
            "worker.execute.complete",
            worker_id=self._worker_id,
            job_id=job_id,
            accepted=accepted,
            checksum=checksum,
        )

    def _planned_runtime_ms(self, spec: Any) -> int:
        """Internal helper to  planned runtime ms."""
        raw = _coerce_int(getattr(spec, "work_duration_ms", 0), 0)
        if raw <= 0:
            return 120
        return max(20, min(raw, 2000))

    def _build_output_bytes(self, job_id: str, spec: Any, runtime_ms: int) -> bytes:
        """Build derived runtime data for this operation."""
        job_type = str(getattr(spec, "job_type", "")).strip()
        payload_size_bytes = max(0, _coerce_int(getattr(spec, "payload_size_bytes", 0), 0))
        base = (
            f"worker={self._worker_id};job_id={job_id};job_type={job_type};"
            f"runtime_ms={runtime_ms};payload_size={payload_size_bytes}"
        )
        return base.encode("utf-8")

    def _report_with_retry(self, request: pb2.ReportWorkOutcomeRequest) -> bool:
        """Internal helper to  report with retry."""
        backoff_ms = self._report_initial_backoff_ms
        for attempt in range(1, self._report_max_attempts + 1):
            _emit(
                self._logger,
                "worker.report.attempt",
                worker_id=self._worker_id,
                job_id=request.job_id,
                attempt=attempt,
            )
            try:
                response = self._stub.ReportWorkOutcome(request, timeout=self._internal_rpc_timeout_s)
                accepted = bool(getattr(response, "accepted", False))
                _emit(
                    self._logger,
                    "worker.report.response",
                    worker_id=self._worker_id,
                    job_id=request.job_id,
                    accepted=accepted,
                    attempt=attempt,
                )
                if accepted:
                    return True
            except grpc.RpcError as exc:
                _emit(
                    self._logger,
                    "worker.report.rpc_error",
                    level="WARNING",
                    worker_id=self._worker_id,
                    job_id=request.job_id,
                    attempt=attempt,
                    grpc_code=exc.code().name if exc.code() is not None else "UNKNOWN",
                    detail=exc.details() or "",
                )
            except Exception as exc:
                _emit(
                    self._logger,
                    "worker.report.error",
                    level="WARNING",
                    worker_id=self._worker_id,
                    job_id=request.job_id,
                    attempt=attempt,
                    error=f"{type(exc).__name__}: {exc}",
                )

            if attempt < self._report_max_attempts:
                backoff_window_ms = max(50, min(backoff_ms, self._report_max_backoff_ms))
                wait_ms = random.randint(0, backoff_window_ms)
                _emit(
                    self._logger,
                    "worker.report.retry_wait",
                    worker_id=self._worker_id,
                    job_id=request.job_id,
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    jitter_mode="full",
                    backoff_window_ms=backoff_window_ms,
                    wait_ms=wait_ms,
                )
                self._stop_event.wait(wait_ms / 1000.0)
                if self._stop_event.is_set():
                    return False
                backoff_ms = min(
                    int(backoff_ms * self._report_retry_multiplier),
                    self._report_max_backoff_ms,
                )

        return False


def run() -> int:
    """Programmatic worker process entrypoint."""
    cfg = _resolve_worker_config()
    logger = _resolve_logger(cfg)
    runtime = WorkerRuntime(config=cfg, logger=logger)

    def _handle_signal(signum: int, _frame: Optional[Any]) -> None:
        _emit(
            logger,
            "worker.shutdown.signal",
            worker_id=getattr(runtime, "_worker_id", "unknown"),
            signal=signum,
        )
        runtime.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    return runtime.run()


def main() -> int:
    """Backward-compatible entrypoint alias."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
