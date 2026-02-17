"""
Coordinator service process entrypoint.

Supports both:
- python -m services.coordinator.main
- python services/coordinator/main.py
"""

from __future__ import annotations


try:
    # Package-style execution: python -m services.coordinator.main
    from .server import run_server
except ImportError:
    # Script-style execution: python services/coordinator/main.py
    from server import run_server  # type: ignore


def main() -> int:
    """Start the Coordinator gRPC server process."""
    return run_server()


if __name__ == "__main__":
    raise SystemExit(main())
