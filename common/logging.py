"""
Structured JSON-lines logging utilities for task-queue services.

Public API:
- init_logger(service_name: str, level: str = "INFO")
- log_event(logger, *, event: str, level: str = "INFO",
            method: Optional[str] = None, message: str = "", **fields) -> None
"""

import json
import logging
import sys
from typing import Any, Dict, Optional

from .time_utils import now_ms


_ALLOWED_LEVEL_NAMES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_HANDLER_MARKER_ATTR = "_taskqueue_jsonl_handler"
_SERVICE_ATTR = "_taskqueue_service_name"


def init_logger(service_name: str, level: str = "INFO") -> logging.Logger:
    """
    Initialize and return a service logger configured for JSON-lines output.

    Behavior:
    - Prevents duplicate stream handlers on repeated calls.
    - Writes to stdout.
    - Uses a minimal formatter because log_event() emits JSON strings directly.
    - Sets logger.propagate = False to avoid duplicate emission via root logger.
    """
    service = (service_name or "").strip() or "unknown_service"
    logger_name = "taskqueue.{0}".format(service)
    logger = logging.getLogger(logger_name)

    logger.setLevel(_normalize_level(level))
    logger.propagate = False

    # Add exactly one marked handler.
    handler_exists = any(getattr(h, _HANDLER_MARKER_ATTR, False) for h in logger.handlers)
    if not handler_exists:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        setattr(handler, _HANDLER_MARKER_ATTR, True)
        logger.addHandler(handler)

    # Store service name on logger for consistent record construction.
    setattr(logger, _SERVICE_ATTR, service)
    return logger


def log_event(
    logger: logging.Logger,
    *,
    event: str,
    level: str = "INFO",
    method: Optional[str] = None,
    message: str = "",
    **fields: Any
) -> None:
    """
    Emit one structured JSON-lines log event.

    Required fields in every record:
    - ts_ms
    - level
    - service
    - event

    Optional fields:
    - method
    - message
    - any user-provided **fields (except reserved key collisions)

    Collision policy:
    - reserved keys (ts_ms, level, service, event) cannot be overridden by **fields.
    """
    # Best-effort logging: never raise to caller.
    service = _get_service_name(logger)

    try:
        event_name = str(event).strip() if event is not None else ""
        if not event_name:
            event_name = "unknown_event"

        level_name = _level_name(level)
        level_no = _normalize_level(level)

        record: Dict[str, Any] = {
            "ts_ms": now_ms(),
            "level": level_name,
            "service": service,
            "event": event_name,
        }

        if method is not None:
            method_value = str(method).strip()
            if method_value:
                record["method"] = method_value

        if message:
            record["message"] = str(message)

        # Reserved keys must not be overridden.
        reserved = {"ts_ms", "level", "service", "event"}
        for key, value in fields.items():
            if key in reserved:
                continue
            record[key] = value

        payload = json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_safe_json_default,
        )
        logger.log(level_no, payload)

    except Exception as exc:  # pragma: no cover (defensive path)
        fallback = {
            "ts_ms": now_ms(),
            "level": "ERROR",
            "service": service,
            "event": "logging_failure",
            "message": "{0}: {1}".format(type(exc).__name__, str(exc)),
        }
        try:
            logger.error(json.dumps(fallback, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            # Last-resort fallback to stderr.
            sys.stderr.write(json.dumps(fallback, ensure_ascii=False, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_service_name(logger: logging.Logger) -> str:
    service = getattr(logger, _SERVICE_ATTR, None)
    if isinstance(service, str) and service.strip():
        return service.strip()

    # Fallback from logger name if present.
    name = getattr(logger, "name", "") or ""
    if name.startswith("taskqueue.") and len(name) > len("taskqueue."):
        return name.split(".", 1)[1]

    return "unknown_service"


def _normalize_level(level: Any) -> int:
    if isinstance(level, int):
        return level

    if not isinstance(level, str):
        return logging.INFO

    name = level.strip().upper()
    if name == "DEBUG":
        return logging.DEBUG
    if name == "INFO":
        return logging.INFO
    if name == "WARNING":
        return logging.WARNING
    if name == "ERROR":
        return logging.ERROR
    if name == "CRITICAL":
        return logging.CRITICAL
    return logging.INFO


def _level_name(level: Any) -> str:
    if isinstance(level, str):
        name = level.strip().upper()
        return name if name in _ALLOWED_LEVEL_NAMES else "INFO"

    if isinstance(level, int):
        maybe = logging.getLevelName(level)
        if isinstance(maybe, str) and maybe in _ALLOWED_LEVEL_NAMES:
            return maybe

    return "INFO"


def _safe_json_default(obj: Any) -> Any:
    """
    Fallback serializer for non-JSON-native objects.
    Keeps logs robust and machine-readable.
    """
    if isinstance(obj, bytes):
        return "<bytes:{0}>".format(len(obj))
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, Exception):
        return "{0}: {1}".format(type(obj).__name__, str(obj))
    return str(obj)


__all__ = ["init_logger", "log_event"]
