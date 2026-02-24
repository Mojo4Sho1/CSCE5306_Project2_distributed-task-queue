"""
Coordinator service gRPC server bootstrap (skeleton phase).

Responsibilities in this phase:
- load coordinator config
- initialize logging
- register CoordinatorInternalService servicer
- bind/start gRPC server
- emit deterministic startup/ready/shutdown logs

Business logic remains in servicer.py (currently placeholder handlers).
"""

from __future__ import annotations

import inspect
import json
import logging
import signal
import sys
import threading
import time
from concurrent import futures
from pathlib import Path
from typing import Any, Optional, Type

import grpc


# -----------------------------------------------------------------------------
# Path bootstrap so this file works when run either as:
#   - python -m services.coordinator.server
#   - python services/coordinator/server.py
# -----------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
_GENERATED_DIR = _REPO_ROOT / "generated"

for _p in (str(_REPO_ROOT), str(_GENERATED_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# Generated stubs
import taskqueue_internal_pb2_grpc  # type: ignore

# Local servicer module
try:
    from . import servicer as coordinator_servicer_module
except ImportError:
    import servicer as coordinator_servicer_module  # type: ignore


# Common utilities (use if present; fallback behavior is built in below)
try:
    import common as _common  # type: ignore
except ModuleNotFoundError as e:
    # Fallback only when the top-level 'common' package is missing.
    # If a nested dependency is missing, re-raise.
    if e.name != "common":
        raise
    _common = None

if _common is None:
    load_service_config = None
    init_logger = None
    log_event = None
else:
    # If 'common' exists, required exports must exist too.
    missing = [
        name
        for name in ("load_service_config", "init_logger", "log_event")
        if not hasattr(_common, name)
    ]
    if missing:
        raise ImportError(f"'common' is missing required exports: {', '.join(missing)}")

    load_service_config = _common.load_service_config  # type: ignore[attr-defined]
    init_logger = _common.init_logger  # type: ignore[attr-defined]
    log_event = _common.log_event  # type: ignore[attr-defined]


def _coerce_int(value: Any, default: int) -> int:
    """Parse integer configuration values for coordinator server startup."""
    try:
        return int(value)
    except Exception:
        return default


def _resolve_coordinator_config() -> Any:
    """
    Supports multiple common.load_service_config signatures:
      - load_service_config("coordinator")
      - load_service_config(service_name="coordinator")
      - load_service_config()
    Falls back to environment defaults if common config is unavailable.
    """
    if load_service_config is not None:
        # Try positional first.
        try:
            return load_service_config("coordinator")
        except TypeError:
            pass
        except Exception:
            pass

        # Try keyword.
        try:
            return load_service_config(service_name="coordinator")
        except TypeError:
            pass
        except Exception:
            pass

        # Try no args.
        try:
            return load_service_config()
        except Exception:
            pass

    class _FallbackConfig:
        """Environment-backed defaults used when shared config loading is unavailable."""
        service_name = "coordinator"
        log_level = "INFO"
        bind_host = "0.0.0.0"
        host = "0.0.0.0"
        port = 50054
        coordinator_port = 50054
        grpc_max_workers = 32
        shutdown_grace_seconds = 3

    return _FallbackConfig()


def _resolve_logger(cfg: Any) -> logging.Logger:
    """Create the coordinator service logger from config and environment settings."""
    service_name = getattr(cfg, "service_name", "coordinator")
    level = getattr(cfg, "log_level", "INFO")

    if init_logger is not None:
        # Try common init signatures.
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

    # Fallback stdlib logger.
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
    """
    Emit structured logs. Uses common.log_event if available, else JSON line.
    """
    if log_event is not None:
        # Try common log_event signatures.
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


def _resolve_servicer_class() -> Type[Any]:
    """
    Resolve the servicer class from servicer.py with compatibility for common names.
    """
    candidates = [
        "CoordinatorServicer",
        "CoordinatorInternalServicer",
        "CoordinatorInternalServiceServicerImpl",
    ]
    for name in candidates:
        cls = getattr(coordinator_servicer_module, name, None)
        if inspect.isclass(cls):
            return cls  # type: ignore[return-value]

    raise RuntimeError(
        "Could not find a Coordinator servicer class in services/coordinator/servicer.py. "
        f"Tried: {', '.join(candidates)}"
    )


def _instantiate_servicer(servicer_cls: Type[Any], cfg: Any, logger: logging.Logger) -> Any:
    """
    Instantiate servicer with best-effort constructor compatibility.
    """
    for kwargs in (
        {"config": cfg, "logger": logger},
        {"cfg": cfg, "logger": logger},
        {"logger": logger},
        {"config": cfg},
        {"cfg": cfg},
        {},
    ):
        try:
            return servicer_cls(**kwargs)
        except TypeError:
            continue

    # Final fallback with positional attempts.
    for args in ((cfg, logger), (cfg,), (logger,), ()):
        try:
            return servicer_cls(*args)
        except TypeError:
            continue

    raise RuntimeError(
        f"Unable to instantiate servicer class '{servicer_cls.__name__}'. "
        "Please align its __init__ signature with server.py expectations."
    )


def _bind_addr(cfg: Any) -> str:
    """Return the coordinator gRPC server bind address as "host:port"."""
    host = getattr(cfg, "bind_host", None) or getattr(cfg, "host", "0.0.0.0")
    port = _coerce_int(getattr(cfg, "port", getattr(cfg, "coordinator_port", 50054)), 50054)
    return f"{host}:{port}"


def _serve() -> None:
    """
    Starts the Coordinator gRPC server and blocks until shutdown signal.
    """
    cfg = _resolve_coordinator_config()
    logger = _resolve_logger(cfg)

    service_name = getattr(cfg, "service_name", "coordinator")
    bind_addr = _bind_addr(cfg)
    max_workers = _coerce_int(getattr(cfg, "grpc_max_workers", 32), 32)
    shutdown_grace = _coerce_int(getattr(cfg, "shutdown_grace_seconds", 3), 3)

    _emit(
        logger,
        "startup.begin",
        service=service_name,
        bind_addr=bind_addr,
        max_workers=max_workers,
    )

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))

    servicer_cls = _resolve_servicer_class()
    servicer_instance = _instantiate_servicer(servicer_cls, cfg=cfg, logger=logger)

    taskqueue_internal_pb2_grpc.add_CoordinatorInternalServiceServicer_to_server(
        servicer_instance,
        server,
    )

    bound_port = server.add_insecure_port(bind_addr)
    if bound_port == 0:
        raise RuntimeError(f"Failed to bind Coordinator gRPC server to '{bind_addr}'")

    stop_event = threading.Event()

    def _shutdown_handler(signum: int, _frame: Optional[Any]) -> None:
        _emit(logger, "shutdown.signal", service=service_name, signal=signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    server.start()
    _emit(
        logger,
        "startup.ready",
        service=service_name,
        bind_addr=bind_addr,
        grpc_service="taskqueue.internal.v1.CoordinatorInternalService",
    )

    try:
        while not stop_event.is_set():
            time.sleep(0.2)
    finally:
        _emit(logger, "shutdown.begin", service=service_name, grace_seconds=shutdown_grace)
        server.stop(grace=shutdown_grace).wait()
        _emit(logger, "shutdown.complete", service=service_name)


def run_server() -> int:
    """
    Programmatic entrypoint used by service main module.
    Returns process-style exit code.
    """
    _serve()
    return 0


def main() -> int:
    """
    Backward-compatible entrypoint alias.
    """
    return run_server()


if __name__ == "__main__":
    raise SystemExit(main())
