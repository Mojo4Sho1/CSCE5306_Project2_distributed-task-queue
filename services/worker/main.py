"""
Worker process entrypoint.

Supports both:
- python -m services.worker.main
- python services/worker/main.py
"""

from __future__ import annotations


try:
    # Package-style execution: python -m services.worker.main
    from .worker import run
except ImportError:
    # Script-style execution: python services/worker/main.py
    from worker import run  # type: ignore


def main() -> int:
    """Start the Worker runtime process."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
