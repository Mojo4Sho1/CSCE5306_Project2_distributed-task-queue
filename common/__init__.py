"""
Common shared utilities for all task-queue services.
Public interfaces are re-exported here to keep imports consistent.
"""

from .config import (
    ConfigError,
    BaseServiceConfig,
    GatewayConfig,
    JobConfig,
    QueueConfig,
    CoordinatorConfig,
    WorkerConfig,
    ResultConfig,
    load_service_config,
    validate_addr,
)

from .time_utils import now_ms, monotonic_ms, elapsed_ms

from .logging import init_logger, log_event

from .grpc_server import create_grpc_server, serve_grpc
from .rpc_defaults import (
    INTERNAL_UNARY_RPC_TIMEOUT_MS,
    FETCH_WORK_RPC_TIMEOUT_MS,
    WORKER_HEARTBEAT_RPC_TIMEOUT_MS,
    RETRY_INITIAL_DELAY_MS,
    RETRY_MULTIPLIER,
    RETRY_MAX_DELAY_MS,
    RETRY_MAX_ATTEMPTS,
    FETCHWORK_RETRY_AFTER_DEFAULT_MS,
    FETCHWORK_RETRY_AFTER_MIN_MS,
    FETCHWORK_RETRY_AFTER_MAX_MS,
)

__all__ = [
    # config
    "ConfigError",
    "BaseServiceConfig",
    "GatewayConfig",
    "JobConfig",
    "QueueConfig",
    "CoordinatorConfig",
    "WorkerConfig",
    "ResultConfig",
    "load_service_config",
    "validate_addr",
    # time
    "now_ms",
    "monotonic_ms",
    "elapsed_ms",
    # logging
    "init_logger",
    "log_event",
    # grpc server
    "create_grpc_server",
    "serve_grpc",
    # rpc defaults
    "INTERNAL_UNARY_RPC_TIMEOUT_MS",
    "FETCH_WORK_RPC_TIMEOUT_MS",
    "WORKER_HEARTBEAT_RPC_TIMEOUT_MS",
    "RETRY_INITIAL_DELAY_MS",
    "RETRY_MULTIPLIER",
    "RETRY_MAX_DELAY_MS",
    "RETRY_MAX_ATTEMPTS",
    "FETCHWORK_RETRY_AFTER_DEFAULT_MS",
    "FETCHWORK_RETRY_AFTER_MIN_MS",
    "FETCHWORK_RETRY_AFTER_MAX_MS",
]
