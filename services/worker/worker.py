"""
Worker runtime scaffold (skeleton phase).

Responsibilities in this phase:
- load/accept worker config
- initialize coordinator client stub
- run deterministic heartbeat/fetch loop with no business execution
- emit structured lifecycle and loop logs

Business execution/reporting logic is intentionally out of scope.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

import grpc


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
        service_name = "worker"
        log_level = "INFO"
        coordinator_addr = "127.0.0.1:50054"
        worker_id = ""
        heartbeat_interval_ms = 1000
        fetch_idle_sleep_ms = 200
        rpc_timeout_ms = 1000

    return _FallbackConfig()


def _resolve_logger(cfg: Any) -> logging.Logger:
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
    if _common is not None:
        return int(now_ms())  # type: ignore[misc]
    return int(time.time() * 1000)


def _resolve_worker_id(cfg: Any) -> str:
    candidate = str(getattr(cfg, "worker_id", "") or "").strip()
    if candidate:
        return candidate

    env_id = str(os.getenv("WORKER_ID", "")).strip()
    if env_id:
        return env_id

    return socket.gethostname().strip() or "worker-unknown"


class WorkerRuntime:
    """Deterministic skeleton worker loop with coordinator RPC integration points."""

    def __init__(self, config: Any, logger: logging.Logger) -> None:
        self._cfg = config
        self._logger = logger
        self._stop_event = threading.Event()

        self._coordinator_addr = str(getattr(config, "coordinator_addr", "127.0.0.1:50054"))
        self._worker_id = _resolve_worker_id(config)
        self._heartbeat_interval_ms = _coerce_int(getattr(config, "heartbeat_interval_ms", 1000), 1000)
        self._fetch_idle_sleep_ms = _coerce_int(getattr(config, "fetch_idle_sleep_ms", 200), 200)
        self._rpc_timeout_s = max(_coerce_int(getattr(config, "rpc_timeout_ms", 1000), 1000), 1) / 1000.0

        if self._heartbeat_interval_ms < 1:
            self._heartbeat_interval_ms = 1000
        if self._fetch_idle_sleep_ms < 1:
            self._fetch_idle_sleep_ms = 200

        self._channel = grpc.insecure_channel(self._coordinator_addr)
        self._stub = pb2_grpc.CoordinatorInternalServiceStub(self._channel)
        self._last_heartbeat_at_ms = 0

    def start(self) -> None:
        _emit(
            self._logger,
            "worker.startup.ready",
            worker_id=self._worker_id,
            coordinator_addr=self._coordinator_addr,
            heartbeat_interval_ms=self._heartbeat_interval_ms,
            fetch_idle_sleep_ms=self._fetch_idle_sleep_ms,
        )

    def stop(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        _emit(self._logger, "worker.shutdown.begin", worker_id=self._worker_id)
        self._channel.close()
        _emit(self._logger, "worker.shutdown.complete", worker_id=self._worker_id)

    def run(self) -> int:
        self.start()
        try:
            while not self._stop_event.is_set():
                self._run_iteration()
        finally:
            self.stop()
        return 0

    def _run_iteration(self) -> None:
        now = _now_ms()
        if now - self._last_heartbeat_at_ms >= self._heartbeat_interval_ms:
            self._send_heartbeat(now)
            self._last_heartbeat_at_ms = now

        assigned, retry_after_ms = self._fetch_work()
        if assigned:
            # Skeleton phase: no business execution path yet.
            _emit(
                self._logger,
                "worker.loop.assignment.received",
                worker_id=self._worker_id,
                action="ignored_in_skeleton",
            )
            time.sleep(max(self._fetch_idle_sleep_ms, 50) / 1000.0)
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
                timeout=self._rpc_timeout_s,
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

    def _fetch_work(self) -> tuple[bool, int]:
        _emit(
            self._logger,
            "worker.fetch.attempt",
            worker_id=self._worker_id,
            coordinator_addr=self._coordinator_addr,
        )
        try:
            response = self._stub.FetchWork(
                pb2.FetchWorkRequest(worker_id=self._worker_id),
                timeout=self._rpc_timeout_s,
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
            return assigned, retry_after_ms
        except grpc.RpcError as exc:
            _emit(
                self._logger,
                "worker.fetch.rpc_error",
                level="WARNING",
                worker_id=self._worker_id,
                grpc_code=exc.code().name if exc.code() is not None else "UNKNOWN",
                detail=exc.details() or "",
            )
            return False, self._fetch_idle_sleep_ms
        except Exception as exc:
            _emit(
                self._logger,
                "worker.fetch.error",
                level="WARNING",
                worker_id=self._worker_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            return False, self._fetch_idle_sleep_ms


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
