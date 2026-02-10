"""
Shared gRPC server bootstrap utilities for task-queue services.

Public API:
- create_grpc_server(*, max_workers: int, options: Optional[List[Tuple[str, int]]] = None)
- serve_grpc(*, host: str, port: int, register_servicers, logger,
             max_workers: int, shutdown_grace_s: float = 5.0,
             enable_health: bool = False,
             options: Optional[List[Tuple[str, int]]] = None) -> None
"""

from __future__ import annotations

import signal
import threading
import time
from concurrent import futures
from typing import Callable, List, Optional, Tuple

import grpc

from .logging import log_event


# Conservative defaults for v1.
_DEFAULT_SERVER_OPTIONS: List[Tuple[str, int]] = [
    ("grpc.max_receive_message_length", 4 * 1024 * 1024),   # 4 MiB
    ("grpc.max_send_message_length", 4 * 1024 * 1024),      # 4 MiB
    ("grpc.keepalive_time_ms", 60_000),
    ("grpc.keepalive_timeout_ms", 20_000),
    ("grpc.keepalive_permit_without_calls", 1),
]


def create_grpc_server(
    *,
    max_workers: int,
    options: Optional[List[Tuple[str, int]]] = None
) -> grpc.Server:
    """
    Create and return a configured grpc.Server.

    Args:
        max_workers: Size of ThreadPoolExecutor. Must be >= 1.
        options: Optional gRPC server options.

    Returns:
        grpc.Server

    Raises:
        ValueError: if max_workers is invalid.
    """
    if not isinstance(max_workers, int) or isinstance(max_workers, bool) or max_workers < 1:
        raise ValueError("max_workers must be an integer >= 1")

    merged_options = _normalize_options(options)

    return grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=merged_options,
    )


def serve_grpc(
    *,
    host: str,
    port: int,
    register_servicers: Callable[[grpc.Server], None],
    logger,
    max_workers: int,
    shutdown_grace_s: float = 5.0,
    enable_health: bool = False,
    options: Optional[List[Tuple[str, int]]] = None,
) -> None:
    """
    Start, run, and gracefully stop a gRPC server.

    Lifecycle:
    1) validate args
    2) create server
    3) optional health registration
    4) register servicers
    5) bind host:port
    6) start
    7) block until signal/interrupt
    8) graceful shutdown

    Raises:
        ValueError: on invalid arguments.
        RuntimeError: on registration/bind/start failures.
    """
    _validate_serve_args(
        host=host,
        port=port,
        register_servicers=register_servicers,
        max_workers=max_workers,
        shutdown_grace_s=shutdown_grace_s,
    )

    service_name = _logger_service_name(logger)
    address = "{0}:{1}".format(host, port)

    stop_event = threading.Event()
    server_started = False
    server = None
    health_servicer = None

    def _request_stop(signum=None, frame=None):  # noqa: ARG001
        # Idempotent stop signal.
        if not stop_event.is_set():
            log_event(
                logger,
                event="service_stop_requested",
                level="INFO",
                message="Shutdown signal received",
                signal=signum,
            )
            stop_event.set()

    previous_handlers = []

    try:
        log_event(
            logger,
            event="grpc_server_create",
            level="INFO",
            host=host,
            port=port,
            max_workers=max_workers,
            shutdown_grace_s=shutdown_grace_s,
        )

        server = create_grpc_server(max_workers=max_workers, options=options)

        if enable_health:
            health_servicer = _try_register_health(server, logger)

        try:
            register_servicers(server)
        except Exception as exc:
            log_event(
                logger,
                event="service_start_failure",
                level="ERROR",
                message="Failed during servicer registration",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise RuntimeError("Servicer registration failed") from exc

        bound_port = server.add_insecure_port(address)
        if bound_port == 0:
            log_event(
                logger,
                event="service_start_failure",
                level="ERROR",
                message="Failed to bind address",
                host=host,
                port=port,
                bind_address=address,
            )
            raise RuntimeError("Failed to bind gRPC server to address: {0}".format(address))

        log_event(
            logger,
            event="grpc_server_bind",
            level="INFO",
            bind_address=address,
            bound_port=bound_port,
        )

        server.start()
        server_started = True

        if health_servicer is not None:
            _set_health_serving(health_servicer, logger)

        log_event(
            logger,
            event="service_start",
            level="INFO",
            service=service_name,  # extra field; canonical service remains from logger
            host=host,
            port=port,
            bind_address=address,
            max_workers=max_workers,
        )

        previous_handlers = _install_signal_handlers(_request_stop)

        # Main block loop.
        while not stop_event.is_set():
            time.sleep(0.2)

    except KeyboardInterrupt:
        _request_stop(signal.SIGINT, None)

    finally:
        _restore_signal_handlers(previous_handlers)

        if server is not None and server_started:
            try:
                if health_servicer is not None:
                    _set_health_not_serving(health_servicer, logger)

                stop_result = server.stop(shutdown_grace_s)
                _wait_stop_result(stop_result, timeout=max(0.0, shutdown_grace_s) + 2.0)

                # Additional bounded wait for full termination.
                try:
                    server.wait_for_termination(timeout=max(0.0, shutdown_grace_s) + 2.0)
                except Exception:
                    # Best effort; do not crash shutdown path.
                    pass

                log_event(
                    logger,
                    event="service_stop_complete",
                    level="INFO",
                    host=host,
                    port=port,
                    shutdown_grace_s=shutdown_grace_s,
                )
            except Exception as exc:
                log_event(
                    logger,
                    event="service_stop_error",
                    level="ERROR",
                    message="Error during server shutdown",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_serve_args(
    *,
    host: str,
    port: int,
    register_servicers,
    max_workers: int,
    shutdown_grace_s: float,
) -> None:
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")

    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        raise ValueError("port must be an integer in range 1..65535")

    if not callable(register_servicers):
        raise ValueError("register_servicers must be callable")

    if not isinstance(max_workers, int) or isinstance(max_workers, bool) or max_workers < 1:
        raise ValueError("max_workers must be an integer >= 1")

    if not isinstance(shutdown_grace_s, (int, float)) or shutdown_grace_s < 0:
        raise ValueError("shutdown_grace_s must be a non-negative number")


def _normalize_options(
    options: Optional[List[Tuple[str, int]]]
) -> List[Tuple[str, int]]:
    if options is None:
        return list(_DEFAULT_SERVER_OPTIONS)

    normalized: List[Tuple[str, int]] = []
    for idx, opt in enumerate(options):
        if (
            not isinstance(opt, tuple)
            or len(opt) != 2
            or not isinstance(opt[0], str)
            or not isinstance(opt[1], int)
        ):
            raise ValueError(
                "Invalid options[{0}]={1!r}; expected Tuple[str, int]".format(idx, opt)
            )
        normalized.append(opt)
    return normalized


def _install_signal_handlers(handler) -> List[Tuple[int, object]]:
    """
    Best-effort signal handler install.
    Returns list of previous handlers to restore later.
    """
    previous: List[Tuple[int, object]] = []

    signals_to_try = [signal.SIGINT]
    if hasattr(signal, "SIGTERM"):
        signals_to_try.append(signal.SIGTERM)

    for sig in signals_to_try:
        try:
            prev = signal.getsignal(sig)
            signal.signal(sig, handler)
            previous.append((sig, prev))
        except Exception:
            # Happens e.g. outside main thread; ignore.
            continue

    return previous


def _restore_signal_handlers(previous: List[Tuple[int, object]]) -> None:
    for sig, prev in previous:
        try:
            signal.signal(sig, prev)
        except Exception:
            continue


def _wait_stop_result(stop_result, timeout: float) -> None:
    """
    gRPC returns different stop result types depending on implementation versions.
    Handle common wait/result patterns safely.
    """
    if stop_result is None:
        return

    # threading.Event-like
    if hasattr(stop_result, "wait") and callable(getattr(stop_result, "wait")):
        try:
            stop_result.wait(timeout=timeout)
            return
        except Exception:
            pass

    # Future-like
    if hasattr(stop_result, "result") and callable(getattr(stop_result, "result")):
        try:
            stop_result.result(timeout=timeout)
            return
        except Exception:
            pass


def _logger_service_name(logger) -> str:
    # Best-effort extraction from custom attribute set by init_logger.
    service_name = getattr(logger, "_taskqueue_service_name", None)
    if isinstance(service_name, str) and service_name.strip():
        return service_name.strip()

    name = getattr(logger, "name", "")
    if isinstance(name, str) and name.startswith("taskqueue.") and len(name) > len("taskqueue."):
        return name.split(".", 1)[1]
    return "unknown_service"


def _try_register_health(server: grpc.Server, logger):
    """
    Optional health service registration.
    If grpc health package is unavailable, log warning and continue.
    """
    try:
        from grpc_health.v1 import health, health_pb2, health_pb2_grpc  # type: ignore

        servicer = health.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(servicer, server)

        # Set unknown/default service to NOT_SERVING until start.
        servicer.set("", health_pb2.HealthCheckResponse.NOT_SERVING)
        return servicer
    except Exception as exc:
        log_event(
            logger,
            event="health_registration_skipped",
            level="WARNING",
            message="Health service unavailable or failed to register",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return None


def _set_health_serving(health_servicer, logger) -> None:
    try:
        from grpc_health.v1 import health_pb2  # type: ignore

        health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    except Exception as exc:
        log_event(
            logger,
            event="health_status_update_failed",
            level="WARNING",
            message="Failed to set health SERVING",
            error_type=type(exc).__name__,
            error=str(exc),
        )


def _set_health_not_serving(health_servicer, logger) -> None:
    try:
        from grpc_health.v1 import health_pb2  # type: ignore

        health_servicer.set("", health_pb2.HealthCheckResponse.NOT_SERVING)
    except Exception as exc:
        log_event(
            logger,
            event="health_status_update_failed",
            level="WARNING",
            message="Failed to set health NOT_SERVING",
            error_type=type(exc).__name__,
            error=str(exc),
        )


__all__ = ["create_grpc_server", "serve_grpc"]
