"""
Shared configuration loader for all task-queue services.

Design goals:
- Single source of truth for env parsing/validation.
- Typed config objects per service.
- Fail fast with aggregated, readable errors.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Union


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when service configuration is missing or invalid."""


# ---------------------------------------------------------------------------
# Public typed configs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BaseServiceConfig:
    service_name: str
    host: str
    port: int
    log_level: str
    grpc_max_workers: int


@dataclass(frozen=True)
class GatewayConfig(BaseServiceConfig):
    job_addr: str
    queue_addr: str
    result_addr: str


@dataclass(frozen=True)
class JobConfig(BaseServiceConfig):
    pass


@dataclass(frozen=True)
class QueueConfig(BaseServiceConfig):
    pass


@dataclass(frozen=True)
class CoordinatorConfig(BaseServiceConfig):
    job_addr: str
    queue_addr: str
    result_addr: str
    heartbeat_interval_ms: int
    worker_timeout_ms: int


@dataclass(frozen=True)
class WorkerConfig(BaseServiceConfig):
    coordinator_addr: str
    worker_id: str
    heartbeat_interval_ms: int
    fetch_idle_sleep_ms: int


@dataclass(frozen=True)
class ResultConfig(BaseServiceConfig):
    pass


ServiceConfig = Union[
    GatewayConfig,
    JobConfig,
    QueueConfig,
    CoordinatorConfig,
    WorkerConfig,
    ResultConfig,
]


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

_CANONICAL_SERVICE_NAMES = {
    "gateway",
    "job",
    "queue",
    "coordinator",
    "worker",
    "result",
}

# Lightweight alias map for convenience.
_SERVICE_NAME_ALIASES = {
    "gateway-service": "gateway",
    "job-service": "job",
    "queue-service": "queue",
    "coordinator-service": "coordinator",
    "worker-service": "worker",
    "result-service": "result",
    "gateway_service": "gateway",
    "job_service": "job",
    "queue_service": "queue",
    "coordinator_service": "coordinator",
    "worker_service": "worker",
    "result_service": "result",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def validate_addr(value: str) -> str:
    """
    Validate and normalize a host:port address string.

    Rules:
    - non-empty string
    - contains ':' separator
    - host portion non-empty
    - port is integer in [1, 65535]

    Returns the normalized "host:port" string.

    Raises:
        ValueError: if invalid.
    """
    if not isinstance(value, str):
        raise ValueError("must be a string in 'host:port' format")

    candidate = value.strip()
    if not candidate:
        raise ValueError("must not be empty")

    if ":" not in candidate:
        raise ValueError("must be in 'host:port' format")

    host, port_str = candidate.rsplit(":", 1)
    host = host.strip()
    port_str = port_str.strip()

    if not host:
        raise ValueError("host part must not be empty")

    try:
        port = int(port_str)
    except ValueError as exc:
        raise ValueError("port must be an integer in range 1..65535") from exc

    if not (1 <= port <= 65535):
        raise ValueError("port must be in range 1..65535")

    return f"{host}:{port}"


def load_service_config(service_name: Optional[str] = None) -> ServiceConfig:
    """
    Load and validate configuration for a specific service.

    Args:
        service_name: Optional canonical/alias service name. If omitted,
            SERVICE_NAME environment variable is required.

    Returns:
        A typed config dataclass for the resolved service.

    Raises:
        ConfigError: on missing/invalid configuration.
    """
    resolved_name = _resolve_service_name(service_name)

    errors: list[str] = []

    # Base/common fields
    host = _get_optional_str("HOST", "0.0.0.0")
    port = _get_required_int("PORT", errors, min_value=1, max_value=65535)
    log_level_raw = _get_optional_str("LOG_LEVEL", "INFO").upper()
    grpc_max_workers = _get_optional_int(
        "GRPC_MAX_WORKERS",
        default=10,
        errors=errors,
        min_value=1,
        max_value=None,
    )

    if log_level_raw not in _ALLOWED_LOG_LEVELS:
        errors.append(
            f"LOG_LEVEL={log_level_raw!r} must be one of "
            f"{sorted(_ALLOWED_LOG_LEVELS)}"
        )

    # Service-specific fields
    gateway_job_addr: Optional[str] = None
    gateway_queue_addr: Optional[str] = None
    gateway_result_addr: Optional[str] = None

    coordinator_job_addr: Optional[str] = None
    coordinator_queue_addr: Optional[str] = None
    coordinator_result_addr: Optional[str] = None
    heartbeat_interval_ms: Optional[int] = None
    worker_timeout_ms: Optional[int] = None

    worker_coordinator_addr: Optional[str] = None
    worker_id: str = ""
    worker_heartbeat_interval_ms: Optional[int] = None
    fetch_idle_sleep_ms: Optional[int] = None

    if resolved_name == "gateway":
        gateway_job_addr = _get_required_addr("JOB_ADDR", errors)
        gateway_queue_addr = _get_required_addr("QUEUE_ADDR", errors)
        gateway_result_addr = _get_required_addr("RESULT_ADDR", errors)

    elif resolved_name == "coordinator":
        coordinator_job_addr = _get_required_addr("JOB_ADDR", errors)
        coordinator_queue_addr = _get_required_addr("QUEUE_ADDR", errors)
        coordinator_result_addr = _get_required_addr("RESULT_ADDR", errors)

        heartbeat_interval_ms = _get_optional_int(
            "HEARTBEAT_INTERVAL_MS",
            default=1000,
            errors=errors,
            min_value=1,
            max_value=None,
        )
        worker_timeout_ms = _get_optional_int(
            "WORKER_TIMEOUT_MS",
            default=4000,
            errors=errors,
            min_value=1,
            max_value=None,
        )

    elif resolved_name == "worker":
        worker_coordinator_addr = _get_required_addr("COORDINATOR_ADDR", errors)
        worker_id = _get_optional_str("WORKER_ID", "")
        worker_heartbeat_interval_ms = _get_optional_int(
            "HEARTBEAT_INTERVAL_MS",
            default=1000,
            errors=errors,
            min_value=1,
            max_value=None,
        )
        fetch_idle_sleep_ms = _get_optional_int(
            "FETCH_IDLE_SLEEP_MS",
            default=200,
            errors=errors,
            min_value=1,
            max_value=None,
        )

    elif resolved_name in {"job", "queue", "result"}:
        # No extra fields in v1.
        pass

    else:
        # Should not happen due to _resolve_service_name.
        errors.append(f"Unsupported service_name={resolved_name!r}")

    _raise_if_errors(errors, resolved_name)

    # Safe after validation.
    assert port is not None
    assert grpc_max_workers is not None

    base_kwargs = dict(
        service_name=resolved_name,
        host=host,
        port=port,
        log_level=log_level_raw,
        grpc_max_workers=grpc_max_workers,
    )

    if resolved_name == "gateway":
        assert gateway_job_addr is not None
        assert gateway_queue_addr is not None
        assert gateway_result_addr is not None
        return GatewayConfig(
            **base_kwargs,
            job_addr=gateway_job_addr,
            queue_addr=gateway_queue_addr,
            result_addr=gateway_result_addr,
        )

    if resolved_name == "job":
        return JobConfig(**base_kwargs)

    if resolved_name == "queue":
        return QueueConfig(**base_kwargs)

    if resolved_name == "coordinator":
        assert coordinator_job_addr is not None
        assert coordinator_queue_addr is not None
        assert coordinator_result_addr is not None
        assert heartbeat_interval_ms is not None
        assert worker_timeout_ms is not None
        return CoordinatorConfig(
            **base_kwargs,
            job_addr=coordinator_job_addr,
            queue_addr=coordinator_queue_addr,
            result_addr=coordinator_result_addr,
            heartbeat_interval_ms=heartbeat_interval_ms,
            worker_timeout_ms=worker_timeout_ms,
        )

    if resolved_name == "worker":
        assert worker_coordinator_addr is not None
        assert worker_heartbeat_interval_ms is not None
        assert fetch_idle_sleep_ms is not None
        return WorkerConfig(
            **base_kwargs,
            coordinator_addr=worker_coordinator_addr,
            worker_id=worker_id,
            heartbeat_interval_ms=worker_heartbeat_interval_ms,
            fetch_idle_sleep_ms=fetch_idle_sleep_ms,
        )

    if resolved_name == "result":
        return ResultConfig(**base_kwargs)

    # Defensive fallback (should be unreachable).
    raise ConfigError(f"Unhandled service_name={resolved_name!r}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_service_name(service_name: Optional[str]) -> str:
    raw = service_name if service_name is not None else os.getenv("SERVICE_NAME")

    if raw is None or not raw.strip():
        raise ConfigError(
            "Missing SERVICE_NAME. "
            "Set SERVICE_NAME environment variable or pass service_name explicitly."
        )

    return _normalize_service_name(raw)


def _normalize_service_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in _SERVICE_NAME_ALIASES:
        normalized = _SERVICE_NAME_ALIASES[normalized]

    if normalized not in _CANONICAL_SERVICE_NAMES:
        allowed = ", ".join(sorted(_CANONICAL_SERVICE_NAMES))
        raise ConfigError(
            f"Unknown service name {value!r}. "
            f"Expected one of: {allowed}"
        )

    return normalized


def _get_required_str(name: str, errors: list[str]) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        errors.append(f"{name} is required and must be non-empty")
        return None
    return raw.strip()


def _get_optional_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    stripped = raw.strip()
    return default if stripped == "" else stripped


def _get_required_int(
    name: str,
    errors: list[str],
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        errors.append(f"{name} is required and must be an integer")
        return None

    raw_str = raw.strip()
    try:
        value = int(raw_str)
    except ValueError:
        errors.append(f"{name}={raw_str!r} must be an integer")
        return None

    _validate_int_range(name, value, errors, min_value=min_value, max_value=max_value)
    return value


def _get_optional_int(
    name: str,
    default: int,
    errors: list[str],
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        value = default
    else:
        raw_str = raw.strip()
        try:
            value = int(raw_str)
        except ValueError:
            errors.append(f"{name}={raw_str!r} must be an integer")
            return default

    _validate_int_range(name, value, errors, min_value=min_value, max_value=max_value)
    return value


def _validate_int_range(
    name: str,
    value: int,
    errors: list[str],
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> None:
    if min_value is not None and value < min_value:
        errors.append(f"{name}={value} must be >= {min_value}")
    if max_value is not None and value > max_value:
        errors.append(f"{name}={value} must be <= {max_value}")


def _get_required_addr(name: str, errors: list[str]) -> Optional[str]:
    raw = _get_required_str(name, errors)
    if raw is None:
        return None

    try:
        return validate_addr(raw)
    except ValueError as exc:
        errors.append(f"{name}={raw!r} is invalid: {exc}")
        return None


def _raise_if_errors(errors: list[str], service_name: str) -> None:
    if not errors:
        return

    formatted = "\n - ".join(errors)
    raise ConfigError(
        f"Invalid configuration for service '{service_name}':\n - {formatted}"
    )


__all__ = [
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
]
