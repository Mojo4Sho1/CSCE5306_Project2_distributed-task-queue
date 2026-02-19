from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common.loadgen_contracts import (
    BenchmarkRow,
    BenchmarkRunner,
    BenchmarkScenario,
    build_stable_run_id,
    load_scenario_config,
)


class LoadgenContractTests(unittest.TestCase):
    def test_scenario_parse_and_design_b_router_wiring(self) -> None:
        raw = {
            "scenario_id": "b_scaffold_parse",
            "design": "B_monolith",
            "concurrency": 12,
            "work_duration_ms": 200,
            "request_mix_profile": "balanced",
            "request_mix_weights": {
                "SubmitJob": 5,
                "GetJobStatus": 5,
                "GetJobResult": 4,
                "CancelJob": 1,
                "ListJobs": 0,
            },
            "warmup_seconds": 0,
            "measure_seconds": 1,
            "cooldown_seconds": 0,
            "repetitions": 1,
            "run_seed": 1234,
            "total_worker_slots": 6,
            "design_b_ordered_targets": [
                "127.0.0.1:51051",
                "127.0.0.1:52051",
                "127.0.0.1:53051",
                "127.0.0.1:54051",
                "127.0.0.1:55051",
                "127.0.0.1:56051",
            ],
        }
        scenario = BenchmarkScenario.from_dict(raw)
        capture: dict[str, tuple[int, str, str] | None] = {"submit": None}
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = BenchmarkRunner(
                scenario=scenario,
                output_root=Path(tmp_dir) / "out",
                sleep_fn=lambda _: None,
                clock_fn=lambda: 1700000000.0,
            )

            def _hook(context, _phase_name):
                capture["submit"] = context.resolve_submit_target("")
                return []

            runner.run(operation_hook=_hook)
        self.assertEqual((0, "127.0.0.1:51051", "round_robin"), capture["submit"])

    def test_output_serialization_and_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            scenario_path = tmp_path / "scenario.json"
            scenario_path.write_text(
                json.dumps(
                    {
                        "scenario_id": "a_scaffold_serialization",
                        "design": "A_microservices",
                        "concurrency": 8,
                        "work_duration_ms": 100,
                        "request_mix_profile": "submit-heavy",
                        "request_mix_weights": {
                            "SubmitJob": 10,
                            "GetJobStatus": 3,
                            "GetJobResult": 2,
                            "CancelJob": 1,
                            "ListJobs": 0,
                        },
                        "warmup_seconds": 0,
                        "measure_seconds": 1,
                        "cooldown_seconds": 0,
                        "repetitions": 1,
                        "run_seed": 99,
                        "total_worker_slots": 6,
                        "design_a_gateway_target": "127.0.0.1:50051",
                    }
                ),
                encoding="utf-8",
            )
            scenario = load_scenario_config(scenario_path)
            runner = BenchmarkRunner(
                scenario=scenario,
                output_root=tmp_path / "out",
                sleep_fn=lambda _: None,
                clock_fn=lambda: 1700000001.0,
            )

            def _hook(context, _phase_name):
                run_id = context.run_id
                return [
                    BenchmarkRow(
                        design=scenario.design,
                        scenario_id=scenario.scenario_id,
                        run_id=run_id,
                        method="SubmitJob",
                        start_ts_ms=1700000001000,
                        latency_ms=7,
                        grpc_code="OK",
                        accepted=True,
                        result_ready=None,
                        already_terminal=None,
                        job_id="job-123",
                        concurrency=scenario.concurrency,
                        work_duration_ms=scenario.work_duration_ms,
                        request_mix_profile=scenario.request_mix_profile,
                        total_worker_slots=scenario.total_worker_slots,
                    )
                ]

            artifacts = runner.run(operation_hook=_hook)
            self.assertEqual(1, len(artifacts))
            artifact = artifacts[0]
            self.assertEqual(1, artifact.row_count)
            self.assertTrue(artifact.rows_jsonl_path.exists())
            self.assertTrue(artifact.rows_csv_path.exists())
            self.assertTrue(artifact.metadata_path.exists())

            rows_jsonl = artifact.rows_jsonl_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(1, len(rows_jsonl))
            parsed_jsonl = json.loads(rows_jsonl[0])
            self.assertEqual("SubmitJob", parsed_jsonl["method"])
            self.assertEqual("OK", parsed_jsonl["grpc_code"])
            self.assertEqual("job-123", parsed_jsonl["job_id"])

            csv_lines = artifact.rows_csv_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(2, len(csv_lines))
            self.assertIn("scenario_id", csv_lines[0])
            self.assertIn("a_scaffold_serialization", csv_lines[1])

            metadata = json.loads(artifact.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(1, metadata["row_count"])
            self.assertEqual("a_scaffold_serialization", metadata["scenario"]["scenario_id"])
            self.assertEqual(
                build_stable_run_id("a_scaffold_serialization", 99, 0),
                metadata["run_id"],
            )


if __name__ == "__main__":
    unittest.main()
