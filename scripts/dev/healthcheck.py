#!/usr/bin/env python3
"""Shared container healthcheck probes for runtime contract parity."""

from __future__ import annotations

import argparse
import socket
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    host: str
    port: int


def _parse_target(value: str) -> Target:
    raw = (value or "").strip()
    if not raw or ":" not in raw:
        raise argparse.ArgumentTypeError("target must be in host:port format")

    host, port_str = raw.rsplit(":", 1)
    host = host.strip()
    port_str = port_str.strip()

    if not host:
        raise argparse.ArgumentTypeError("target host must not be empty")
    if not port_str.isdigit():
        raise argparse.ArgumentTypeError("target port must be numeric")

    port = int(port_str)
    if port < 1 or port > 65535:
        raise argparse.ArgumentTypeError("target port must be between 1 and 65535")

    return Target(host=host, port=port)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Shared runtime healthcheck")
    parser.add_argument(
        "--mode",
        required=True,
        choices=("tcp", "worker"),
        help="Probe mode: tcp socket probe or worker coordinator reachability probe",
    )
    parser.add_argument(
        "--target",
        required=True,
        type=_parse_target,
        help="Probe target in host:port format",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=1000,
        help="Probe timeout in milliseconds (default: 1000)",
    )
    parser.add_argument(
        "--service",
        default="",
        help="Optional service label for status output",
    )
    return parser


def _probe_tcp(target: Target, timeout_ms: int) -> tuple[bool, str]:
    timeout_s = timeout_ms / 1000.0
    try:
        with socket.create_connection((target.host, target.port), timeout=timeout_s):
            return True, "tcp_connect_ok"
    except OSError as exc:
        return False, f"tcp_connect_failed:{exc}"


def _probe_worker(target: Target, timeout_ms: int) -> tuple[bool, str]:
    # Worker health in v1 is defined as coordinator reachability.
    return _probe_tcp(target, timeout_ms)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.timeout_ms <= 0:
        print("status=unhealthy reason=invalid_timeout timeout_ms_must_be_positive", file=sys.stderr)
        return 2

    probe = _probe_tcp if args.mode == "tcp" else _probe_worker
    healthy, detail = probe(args.target, args.timeout_ms)

    service_label = args.service if args.service else "-"
    target_label = f"{args.target.host}:{args.target.port}"

    if healthy:
        print(
            f"status=healthy service={service_label} mode={args.mode} target={target_label} detail={detail}"
        )
        return 0

    print(
        f"status=unhealthy service={service_label} mode={args.mode} target={target_label} detail={detail}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
