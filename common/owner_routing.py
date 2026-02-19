from __future__ import annotations

import hashlib
from typing import Sequence


def owner_index_for_key(key: str, node_count: int) -> int:
    """
    Deterministic owner index for a routing key.

    Locked formula:
      uint64_be(first_8_bytes(sha256(utf8(key)))) % N
    """
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a non-empty string")
    if node_count <= 0:
        raise ValueError("node_count must be > 0")

    digest = hashlib.sha256(key.encode("utf-8")).digest()
    prefix_u64 = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return prefix_u64 % int(node_count)


def owner_for_key(key: str, ordered_nodes: Sequence[str]) -> str:
    """Select the deterministic owner node from a fixed ordered node list."""
    if not ordered_nodes:
        raise ValueError("ordered_nodes must be non-empty")
    idx = owner_index_for_key(key=key, node_count=len(ordered_nodes))
    return str(ordered_nodes[idx])
