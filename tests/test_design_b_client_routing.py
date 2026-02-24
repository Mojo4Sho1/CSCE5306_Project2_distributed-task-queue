"""Test coverage for test design b client routing."""

from __future__ import annotations

import unittest

from common.design_b_routing import DesignBClientRouter, build_ordered_targets
from common.owner_routing import owner_index_for_key


class DesignBClientRoutingTests(unittest.TestCase):
    """Behavioral tests for Design B client routing."""
    def setUp(self) -> None:
        """Create shared fixtures for each test."""
        self.targets = [
            "127.0.0.1:51051",
            "127.0.0.1:52051",
            "127.0.0.1:53051",
            "127.0.0.1:54051",
            "127.0.0.1:55051",
            "127.0.0.1:56051",
        ]

    def test_submit_empty_key_round_robin_progression(self) -> None:
        """Checks submit empty key round robin progression."""
        router = DesignBClientRouter(self.targets)
        first = router.submit_target("")
        second = router.submit_target("   ")
        third = router.submit_target("")

        self.assertEqual((0, self.targets[0], "round_robin"), first)
        self.assertEqual((1, self.targets[1], "round_robin"), second)
        self.assertEqual((2, self.targets[2], "round_robin"), third)

    def test_submit_non_empty_key_uses_deterministic_owner(self) -> None:
        """Checks submit non empty key uses deterministic owner."""
        router = DesignBClientRouter(self.targets)
        key = "client-request-abc-123"
        expected_idx = owner_index_for_key(key=key, node_count=len(self.targets))

        first = router.submit_target(key)
        second = router.submit_target(key)

        self.assertEqual((expected_idx, self.targets[expected_idx], "owner"), first)
        self.assertEqual((expected_idx, self.targets[expected_idx], "owner"), second)

    def test_job_scoped_routing_uses_job_id_owner(self) -> None:
        """Checks job scoped routing uses job id owner."""
        router = DesignBClientRouter(self.targets)
        job_id = "91509fd2-8bf0-4c6e-a0b3-730a4b8f0dc8"
        expected_idx = owner_index_for_key(key=job_id, node_count=len(self.targets))

        actual_idx, actual_target = router.job_target(job_id)
        self.assertEqual(expected_idx, actual_idx)
        self.assertEqual(self.targets[expected_idx], actual_target)

    def test_round_robin_wraps_after_node_count(self) -> None:
        """Checks round robin wraps after node count."""
        router = DesignBClientRouter(self.targets, round_robin_start=5)
        first = router.submit_target("")
        second = router.submit_target("")

        self.assertEqual((5, self.targets[5], "round_robin"), first)
        self.assertEqual((0, self.targets[0], "round_robin"), second)

    def test_build_ordered_targets(self) -> None:
        """Checks build ordered targets."""
        ports = [51051, 52051, 53051]
        self.assertEqual(
            ["127.0.0.1:51051", "127.0.0.1:52051", "127.0.0.1:53051"],
            build_ordered_targets(host="127.0.0.1", ports=ports),
        )

    def test_invalid_arguments(self) -> None:
        """Checks invalid arguments."""
        with self.assertRaises(ValueError):
            DesignBClientRouter([])
        with self.assertRaises(ValueError):
            DesignBClientRouter(self.targets).job_target("")
        with self.assertRaises(ValueError):
            build_ordered_targets(host="", ports=[51051])
        with self.assertRaises(ValueError):
            build_ordered_targets(host="127.0.0.1", ports=[])


if __name__ == "__main__":
    unittest.main()
