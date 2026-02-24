"""
Design B monolith-per-node baseline runtime.

This process hosts the public API and internal RPC services in one gRPC server
and starts one in-process worker loop (1 slot per node baseline).
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent import futures
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import grpc


_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
_GENERATED_DIR = _REPO_ROOT / "generated"

for _p in (str(_REPO_ROOT), str(_GENERATED_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import taskqueue_internal_pb2_grpc  # type: ignore
import taskqueue_public_pb2_grpc  # type: ignore

from common.logging import init_logger, log_event
from common.rpc_defaults import (
    FETCH_WORK_RPC_TIMEOUT_MS,
    INTERNAL_UNARY_RPC_TIMEOUT_MS,
    RETRY_INITIAL_DELAY_MS,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY_MS,
    RETRY_MULTIPLIER,
    WORKER_HEARTBEAT_RPC_TIMEOUT_MS,
)
from services.coordinator.servicer import CoordinatorServicer
from services.gateway.servicer import GatewayServicer
from services.job.servicer import JobServicer
from services.queue.servicer import QueueServicer
from services.result.servicer import ResultServicer
from services.worker.worker import WorkerRuntime


def _env_str(name: str, default: str) -> str:
    """Read optional string environment variable with fallback default."""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Read optional integer environment variable with fallback default."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Read optional float environment variable with fallback default."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, minimum)


def _default_monolith_node_order() -> list[str]:
    """Return default monolith node order used for deterministic owner routing."""
    return [f"monolith-{idx}" for idx in range(1, 7)]


def _parse_monolith_node_order(raw: str) -> list[str]:
    """Parse comma-separated MONOLITH_NODE_ORDER into normalized node identifiers."""
    parts = [token.strip() for token in raw.split(",")]
    ordered = [token for token in parts if token]
    return ordered or _default_monolith_node_order()


def _resolve_logger(node_id: str, log_level: str) -> logging.Logger:
    """Create monolith runtime logger with node and service metadata fields."""
    try:
        return init_logger(service_name=f"monolith.{node_id}", level=log_level)
    except Exception:
        logger = logging.getLogger(f"monolith.{node_id}")
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.propagate = False
        return logger


def _emit(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit structured monolith node lifecycle and bootstrap events."""
    try:
        log_event(logger, event=event, **fields)
        return
    except Exception:
        payload = {"event": event, **fields}
        logger.info(json.dumps(payload, separators=(",", ":"), sort_keys=True))


class MonolithNodeRuntime:
    """Baseline single-node monolith runtime for Design B bring-up."""

    def __init__(self) -> None:
        """Initialize monolith node runtime instance state."""
        self._node_id = _env_str("MONOLITH_NODE_ID", "monolith-1")
        self._host = _env_str("MONOLITH_BIND_HOST", "0.0.0.0")
        self._public_port = _env_int("MONOLITH_PUBLIC_PORT", 50051, minimum=1)
        self._grpc_max_workers = _env_int("GRPC_MAX_WORKERS", 32, minimum=1)
        self._shutdown_grace_seconds = _env_int("SHUTDOWN_GRACE_SECONDS", 3, minimum=0)
        self._log_level = _env_str("LOG_LEVEL", "INFO").upper()
        self._worker_enabled = _env_str("MONOLITH_ENABLE_WORKER", "1") != "0"
        raw_node_order = _env_str("MONOLITH_NODE_ORDER", ",".join(_default_monolith_node_order()))
        self._node_order = _parse_monolith_node_order(raw_node_order)
        try:
            self._node_index = self._node_order.index(self._node_id)
        except ValueError:
            self._node_order = _default_monolith_node_order()
            self._node_index = self._node_order.index(self._node_id) if self._node_id in self._node_order else 0

        self._internal_rpc_timeout_ms = _env_int(
            "INTERNAL_RPC_TIMEOUT_MS",
            INTERNAL_UNARY_RPC_TIMEOUT_MS,
            minimum=1,
        )
        self._heartbeat_interval_ms = _env_int("HEARTBEAT_INTERVAL_MS", 1000, minimum=1)
        self._worker_timeout_ms = _env_int("WORKER_TIMEOUT_MS", 4000, minimum=1)
        self._max_dedup_keys = _env_int("MAX_DEDUP_KEYS", 10000, minimum=1)
        self._max_output_bytes = _env_int("MAX_OUTPUT_BYTES", 262144, minimum=1)

        loopback_addr = f"127.0.0.1:{self._public_port}"
        worker_id = _env_str("WORKER_ID", f"{self._node_id}-worker")
        self._worker_cfg = SimpleNamespace(
            service_name=f"worker.{self._node_id}",
            log_level=self._log_level,
            coordinator_addr=loopback_addr,
            worker_id=worker_id,
            heartbeat_interval_ms=self._heartbeat_interval_ms,
            fetch_idle_sleep_ms=_env_int("FETCH_IDLE_SLEEP_MS", 200, minimum=1),
            internal_rpc_timeout_ms=self._internal_rpc_timeout_ms,
            fetch_work_timeout_ms=_env_int(
                "FETCH_WORK_RPC_TIMEOUT_MS",
                FETCH_WORK_RPC_TIMEOUT_MS,
                minimum=1,
            ),
            worker_heartbeat_timeout_ms=_env_int(
                "WORKER_HEARTBEAT_RPC_TIMEOUT_MS",
                WORKER_HEARTBEAT_RPC_TIMEOUT_MS,
                minimum=1,
            ),
            report_retry_initial_backoff_ms=_env_int(
                "REPORT_RETRY_INITIAL_DELAY_MS",
                RETRY_INITIAL_DELAY_MS,
                minimum=1,
            ),
            report_retry_multiplier=_env_float(
                "REPORT_RETRY_MULTIPLIER",
                RETRY_MULTIPLIER,
                minimum=1.0,
            ),
            report_retry_max_backoff_ms=_env_int(
                "REPORT_RETRY_MAX_DELAY_MS",
                RETRY_MAX_DELAY_MS,
                minimum=1,
            ),
            report_retry_max_attempts=_env_int(
                "REPORT_RETRY_MAX_ATTEMPTS",
                RETRY_MAX_ATTEMPTS,
                minimum=1,
            ),
        )

        self._gateway_cfg = SimpleNamespace(
            service_name=f"gateway.{self._node_id}",
            internal_rpc_timeout_ms=self._internal_rpc_timeout_ms,
            job_addr=loopback_addr,
            queue_addr=loopback_addr,
            result_addr=loopback_addr,
        )
        self._coordinator_cfg = SimpleNamespace(
            service_name=f"coordinator.{self._node_id}",
            internal_rpc_timeout_ms=self._internal_rpc_timeout_ms,
            heartbeat_interval_ms=self._heartbeat_interval_ms,
            worker_timeout_ms=self._worker_timeout_ms,
            job_addr=loopback_addr,
            queue_addr=loopback_addr,
            result_addr=loopback_addr,
        )
        self._job_cfg = SimpleNamespace(
            service_name=f"job.{self._node_id}",
            max_dedup_keys=self._max_dedup_keys,
            owner_node_index=self._node_index,
            owner_node_count=len(self._node_order),
        )
        self._queue_cfg = SimpleNamespace(service_name=f"queue.{self._node_id}")
        self._result_cfg = SimpleNamespace(
            service_name=f"result.{self._node_id}",
            max_output_bytes=self._max_output_bytes,
        )

        self._logger = _resolve_logger(node_id=self._node_id, log_level=self._log_level)
        self._stop_event = threading.Event()
        self._worker_runtime: Optional[WorkerRuntime] = None
        self._worker_thread: Optional[threading.Thread] = None

    def _register_services(self, server: grpc.Server) -> None:
        """Register public/internal servicers on the shared monolith gRPC server."""
        taskqueue_internal_pb2_grpc.add_JobInternalServiceServicer_to_server(
            JobServicer(config=self._job_cfg, logger=self._logger),
            server,
        )
        taskqueue_internal_pb2_grpc.add_QueueInternalServiceServicer_to_server(
            QueueServicer(config=self._queue_cfg, logger=self._logger),
            server,
        )
        taskqueue_internal_pb2_grpc.add_ResultInternalServiceServicer_to_server(
            ResultServicer(config=self._result_cfg, logger=self._logger),
            server,
        )
        taskqueue_internal_pb2_grpc.add_CoordinatorInternalServiceServicer_to_server(
            CoordinatorServicer(config=self._coordinator_cfg, logger=self._logger),
            server,
        )
        taskqueue_public_pb2_grpc.add_TaskQueuePublicServiceServicer_to_server(
            GatewayServicer(config=self._gateway_cfg, logger=self._logger),
            server,
        )

    def _start_worker(self) -> None:
        """Start embedded worker runtime when this monolith node owns worker execution."""
        if not self._worker_enabled:
            _emit(self._logger, "monolith.worker.disabled", node_id=self._node_id)
            return

        self._worker_runtime = WorkerRuntime(config=self._worker_cfg, logger=self._logger)
        self._worker_thread = threading.Thread(
            target=self._worker_runtime.run,
            name=f"{self._node_id}-worker-thread",
            daemon=True,
        )
        self._worker_thread.start()
        _emit(
            self._logger,
            "monolith.worker.started",
            node_id=self._node_id,
            worker_id=getattr(self._worker_runtime, "_worker_id", ""),
        )

    def _stop_worker(self) -> None:
        """Stop embedded worker runtime during monolith shutdown."""
        if self._worker_runtime is None:
            return
        self._worker_runtime.stop()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=5.0)
        _emit(self._logger, "monolith.worker.stopped", node_id=self._node_id)

    def run(self) -> int:
        """Run monolith node gRPC server and embedded components until shutdown signal."""
        bind_addr = f"{self._host}:{self._public_port}"
        _emit(
            self._logger,
            "monolith.startup.begin",
            node_id=self._node_id,
            bind_addr=bind_addr,
            grpc_max_workers=self._grpc_max_workers,
            worker_enabled=self._worker_enabled,
            node_index=self._node_index,
            node_count=len(self._node_order),
        )

        server = grpc.server(futures.ThreadPoolExecutor(max_workers=self._grpc_max_workers))
        self._register_services(server)

        bound_port = server.add_insecure_port(bind_addr)
        if bound_port == 0:
            raise RuntimeError(f"Failed to bind monolith node to '{bind_addr}'")

        def _handle_shutdown(signum: int, _frame: Optional[Any]) -> None:
            _emit(
                self._logger,
                "monolith.shutdown.signal",
                node_id=self._node_id,
                signal=signum,
            )
            self._stop_event.set()

        signal.signal(signal.SIGINT, _handle_shutdown)
        signal.signal(signal.SIGTERM, _handle_shutdown)

        server.start()
        _emit(
            self._logger,
            "monolith.startup.ready",
            node_id=self._node_id,
            bind_addr=bind_addr,
            public_grpc_service="taskqueue.v1.TaskQueuePublicService",
            internal_grpc_services="taskqueue.internal.v1.*",
        )
        self._start_worker()

        try:
            while not self._stop_event.is_set():
                time.sleep(0.2)
        finally:
            self._stop_worker()
            _emit(
                self._logger,
                "monolith.shutdown.begin",
                node_id=self._node_id,
                grace_seconds=self._shutdown_grace_seconds,
            )
            server.stop(grace=self._shutdown_grace_seconds).wait()
            _emit(self._logger, "monolith.shutdown.complete", node_id=self._node_id)

        return 0


def run() -> int:
    """Programmatic monolith-node entrypoint."""
    runtime = MonolithNodeRuntime()
    return runtime.run()


def main() -> int:
    """Start monolith node runtime from environment-driven configuration."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
