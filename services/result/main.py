"""
Result service process entrypoint.

Supports both:
- python -m services.result.main
- python services/result/main.py
"""

from __future__ import annotations


try:
    # Package-style execution: python -m services.result.main
    from .server import run_server
except ImportError:
    # Script-style execution: python services/result/main.py
    from server import run_server  # type: ignore


def main() -> int:
    """Start the Result gRPC server process."""
    return run_server()


if __name__ == "__main__":
    raise SystemExit(main())
