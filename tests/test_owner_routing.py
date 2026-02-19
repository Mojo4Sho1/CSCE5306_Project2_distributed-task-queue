from __future__ import annotations

import hashlib
import unittest

from common.owner_routing import owner_for_key, owner_index_for_key


class OwnerRoutingTests(unittest.TestCase):
    def test_owner_index_matches_locked_formula(self) -> None:
        key = "client-request-abc-123"
        node_count = 6
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        expected = int.from_bytes(digest[:8], byteorder="big", signed=False) % node_count
        self.assertEqual(expected, owner_index_for_key(key=key, node_count=node_count))

    def test_owner_for_key_uses_ordered_node_list(self) -> None:
        nodes = [
            "127.0.0.1:51051",
            "127.0.0.1:52051",
            "127.0.0.1:53051",
            "127.0.0.1:54051",
            "127.0.0.1:55051",
            "127.0.0.1:56051",
        ]
        key = "job-123"
        idx = owner_index_for_key(key=key, node_count=len(nodes))
        self.assertEqual(nodes[idx], owner_for_key(key=key, ordered_nodes=nodes))

    def test_invalid_arguments(self) -> None:
        with self.assertRaises(ValueError):
            owner_index_for_key(key="", node_count=6)
        with self.assertRaises(ValueError):
            owner_index_for_key(key="x", node_count=0)
        with self.assertRaises(ValueError):
            owner_for_key(key="x", ordered_nodes=[])


if __name__ == "__main__":
    unittest.main()
