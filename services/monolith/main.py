"""
Design B monolith node process entrypoint.

Supports both:
- python -m services.monolith.main
- python services/monolith/main.py
"""

from __future__ import annotations

try:
    from .node import run
except ImportError:
    from node import run  # type: ignore


def main() -> int:
    """Start the Design B monolith node process."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

