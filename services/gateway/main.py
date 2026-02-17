"""
Gateway service process entrypoint.

Supports both:
- python -m services.gateway.main
- python services/gateway/main.py
"""

from __future__ import annotations


try:
    # Package-style execution: python -m services.gateway.main
    from .server import run_server
except ImportError:
    # Script-style execution: python services/gateway/main.py
    from server import run_server  # type: ignore


def main() -> int:
    """Start the Gateway gRPC server process."""
    return run_server()


if __name__ == "__main__":
    raise SystemExit(main())
