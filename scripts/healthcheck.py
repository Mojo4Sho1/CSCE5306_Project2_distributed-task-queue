#!/usr/bin/env python3
"""Compatibility wrapper. Canonical path moved; this entrypoint is deprecated."""

from __future__ import annotations

from pathlib import Path
import runpy


def main() -> int:
    target = Path(__file__).resolve().parents[1] / "scripts/dev/healthcheck.py"
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
