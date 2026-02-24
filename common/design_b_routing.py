"""Shared design b routing utilities used across services and scripts."""

from __future__ import annotations

import threading
from typing import Sequence

from common.owner_routing import owner_index_for_key


def default_monolith_node_ids(node_count: int = 6) -> list[str]:
    """Return the default Design B monolith node-id order."""
    if node_count <= 0:
        raise ValueError("node_count must be > 0")
    return [f"monolith-{idx}" for idx in range(1, int(node_count) + 1)]


def parse_node_order_csv(raw: str, fallback: Sequence[str] | None = None) -> list[str]:
    """Parse comma-separated node order with optional fallback when input is empty."""
    if not isinstance(raw, str):
        raise ValueError("raw must be a string")
    ordered = [token.strip() for token in raw.split(",") if token.strip()]
    if ordered:
        return ordered
    if fallback:
        return [str(node).strip() for node in fallback if str(node).strip()]
    return default_monolith_node_ids()


def build_ordered_targets(host: str, ports: Sequence[int]) -> list[str]:
    """Build ordered host:port targets for Design B client routing."""
    host_clean = (host or "").strip()
    if not host_clean:
        raise ValueError("host must be non-empty")
    if not ports:
        raise ValueError("ports must be non-empty")

    targets: list[str] = []
    for port in ports:
        port_int = int(port)
        if port_int <= 0:
            raise ValueError("ports must contain positive integers")
        targets.append(f"{host_clean}:{port_int}")
    return targets


class DesignBClientRouter:
    """
    Locked Design B client-routing policy:
    - SubmitJob(empty key): round-robin over ordered nodes.
    - SubmitJob(non-empty key): deterministic owner by key hash.
    - Job-scoped ops: deterministic owner by job_id.
    """

    def __init__(self, ordered_nodes: Sequence[str], round_robin_start: int = 0) -> None:
        """Initialize design bclient router instance state."""
        nodes = [str(node).strip() for node in ordered_nodes if str(node).strip()]
        if not nodes:
            raise ValueError("ordered_nodes must be non-empty")
        self._nodes = tuple(nodes)
        self._rr_index = int(round_robin_start) % len(self._nodes)
        self._lock = threading.Lock()

    @property
    def ordered_nodes(self) -> tuple[str, ...]:
        """Return items in deterministic order for stable routing."""
        return self._nodes

    def next_round_robin_target(self) -> tuple[int, str]:
        """Return the next value in the scheduling sequence."""
        with self._lock:
            idx = self._rr_index
            self._rr_index = (self._rr_index + 1) % len(self._nodes)
        return idx, self._nodes[idx]

    def owner_target_for_key(self, key: str) -> tuple[int, str]:
        """Owner target for key."""
        idx = owner_index_for_key(key=key, node_count=len(self._nodes))
        return idx, self._nodes[idx]

    def submit_target(self, client_request_id: str) -> tuple[int, str, str]:
        """Submit target."""
        dedup_key = (client_request_id or "").strip()
        if dedup_key:
            idx, node = self.owner_target_for_key(dedup_key)
            return idx, node, "owner"
        idx, node = self.next_round_robin_target()
        return idx, node, "round_robin"

    def job_target(self, job_id: str) -> tuple[int, str]:
        """Job target."""
        job_key = (job_id or "").strip()
        if not job_key:
            raise ValueError("job_id must be non-empty")
        return self.owner_target_for_key(job_key)
