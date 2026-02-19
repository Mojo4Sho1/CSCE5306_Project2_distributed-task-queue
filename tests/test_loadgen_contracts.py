from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from common.loadgen_contracts import (
    BenchmarkRow,
    BenchmarkRunner,
    BenchmarkScenario,
    GrpcPublicApiAdapter,
    LiveTrafficEngine,
    RequestMixScheduler,
    build_stable_run_id,
    load_scenario_config,
    summarize_measurement_rows,
    validate_stack_health_targets,
)


class _FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += max(0.0, float(seconds))


class _FakeAdapter:
    def __init__(self) -> None:
        self._jobs: dict[str, list[str]] = {}

    def known_job_count(self, context) -> int:
        return len(self._jobs.get(context.run_id, []))

    def execute(self, *, context, method, rng, worker_id, op_index):
        del rng, worker_id
        start_ts_ms = int(op_index * 100)
        job_id = None
        if method == "SubmitJob":
            job_id = f"job-{context.run_id}-{op_index}"
            self._jobs.setdefault(context.run_id, []).append(job_id)
        elif self.known_job_count(context):
            job_id = self._jobs[context.run_id][0]
        return BenchmarkRow(
            design=context.scenario.design,
            scenario_id=context.scenario.scenario_id,
            run_id=context.run_id,
            method=method,
            start_ts_ms=start_ts_ms,
            latency_ms=5,
            grpc_code="OK",
            accepted=True if method == "SubmitJob" else None,
            result_ready=None,
            already_terminal=None,
            job_terminal=False if job_id else None,
            job_id=job_id,
            concurrency=context.scenario.concurrency,
            work_duration_ms=context.scenario.work_duration_ms,
            request_mix_profile=context.scenario.request_mix_profile,
            total_worker_slots=context.scenario.total_worker_slots,
        )


class _FakeRpcError(Exception):
    def __init__(self, code_name: str) -> None:
        super().__init__(code_name)
        self._code_name = code_name

    def code(self):
        return SimpleNamespace(name=self._code_name)


class _SubmitStub:
    def __init__(self, failure_count: int) -> None:
        self.failure_count = int(failure_count)
        self.calls = 0

    def SubmitJob(self, request, timeout=None):
        del request, timeout
        self.calls += 1
        if self.calls <= self.failure_count:
            raise _FakeRpcError("UNAVAILABLE")
        return SimpleNamespace(job_id=f"job-{self.calls}")


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
                return [
                    BenchmarkRow(
                        design=scenario.design,
                        scenario_id=scenario.scenario_id,
                        run_id=context.run_id,
                        method="SubmitJob",
                        start_ts_ms=1700000001000,
                        latency_ms=7,
                        grpc_code="OK",
                        accepted=True,
                        result_ready=None,
                        already_terminal=None,
                        job_terminal=False,
                        job_id="job-123",
                        concurrency=scenario.concurrency,
                        work_duration_ms=scenario.work_duration_ms,
                        request_mix_profile=scenario.request_mix_profile,
                        total_worker_slots=scenario.total_worker_slots,
                    )
                ]

            artifacts = runner.run(operation_hook=_hook)
            artifact = artifacts[0]
            self.assertTrue(artifact.summary_json_path.exists())
            self.assertTrue(artifact.summary_csv_path.exists())
            metadata = json.loads(artifact.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(1, metadata["row_count"])
            self.assertEqual(
                build_stable_run_id("a_scaffold_serialization", 99, 0),
                metadata["run_id"],
            )

    def test_request_mix_scheduler_distribution(self) -> None:
        scheduler = RequestMixScheduler(
            {"SubmitJob": 2, "GetJobStatus": 1, "GetJobResult": 0, "CancelJob": 0, "ListJobs": 0},
            seed=42,
        )
        seen = [scheduler.next_method() for _ in range(300)]
        self.assertEqual(200, sum(1 for item in seen if item == "SubmitJob"))
        self.assertEqual(100, sum(1 for item in seen if item == "GetJobStatus"))

    def test_live_engine_with_mocked_adapter_records_measure_rows(self) -> None:
        scenario = BenchmarkScenario.from_dict(
            {
                "scenario_id": "live_mock",
                "design": "A_microservices",
                "concurrency": 1,
                "work_duration_ms": 100,
                "request_mix_profile": "submit-heavy",
                "request_mix_weights": {"SubmitJob": 1, "GetJobStatus": 0, "GetJobResult": 0, "CancelJob": 0, "ListJobs": 0},
                "warmup_seconds": 0,
                "measure_seconds": 0.3,
                "cooldown_seconds": 0,
                "repetitions": 1,
                "run_seed": 7,
                "total_worker_slots": 6,
                "request_rate_rps": 10,
                "design_a_gateway_target": "127.0.0.1:50051",
            }
        )
        fake_clock = _FakeClock()
        runner = BenchmarkRunner(scenario=scenario, output_root=Path(tempfile.gettempdir()))
        engine = LiveTrafficEngine(
            scenario=scenario,
            adapter=_FakeAdapter(),
            monotonic_fn=fake_clock.monotonic,
            sleep_fn=fake_clock.sleep,
        )
        artifacts = runner.run(phase_engine=engine)
        self.assertEqual(3, artifacts[0].row_count)

    def test_submit_retry_policy_non_empty_vs_empty_idempotency_key(self) -> None:
        scenario = BenchmarkScenario.from_dict(
            {
                "scenario_id": "retry_policy",
                "design": "A_microservices",
                "concurrency": 1,
                "work_duration_ms": 50,
                "request_mix_profile": "submit-only",
                "request_mix_weights": {"SubmitJob": 1, "GetJobStatus": 0, "GetJobResult": 0, "CancelJob": 0, "ListJobs": 0},
                "warmup_seconds": 0,
                "measure_seconds": 1,
                "cooldown_seconds": 0,
                "repetitions": 1,
                "run_seed": 11,
                "total_worker_slots": 6,
                "submit_client_request_id_mode": "unique_non_empty",
                "design_a_gateway_target": "127.0.0.1:50051",
            }
        )
        stub = _SubmitStub(failure_count=2)
        adapter = GrpcPublicApiAdapter(
            scenario=scenario,
            public_pb2=SimpleNamespace(
                SubmitJobRequest=lambda **kwargs: SimpleNamespace(**kwargs),
                JobSpec=lambda **kwargs: SimpleNamespace(**kwargs),
            ),
            public_pb2_grpc=SimpleNamespace(),
            target_stubs={"127.0.0.1:50051": stub},
            sleep_fn=lambda _: None,
        )
        context = SimpleNamespace(
            scenario=scenario,
            run_id="r1",
            resolve_submit_target=lambda _k: (-1, "127.0.0.1:50051", "gateway"),
        )
        row = adapter.execute(context=context, method="SubmitJob", rng=random.Random(0), worker_id=0, op_index=0)
        self.assertEqual("OK", row.grpc_code)
        self.assertEqual(3, stub.calls)

        empty_key_scenario = BenchmarkScenario.from_dict(
            {
                "scenario_id": "retry_policy_empty",
                "design": "A_microservices",
                "concurrency": 1,
                "work_duration_ms": 50,
                "request_mix_profile": "submit-only",
                "request_mix_weights": {"SubmitJob": 1, "GetJobStatus": 0, "GetJobResult": 0, "CancelJob": 0, "ListJobs": 0},
                "warmup_seconds": 0,
                "measure_seconds": 1,
                "cooldown_seconds": 0,
                "repetitions": 1,
                "run_seed": 12,
                "total_worker_slots": 6,
                "submit_client_request_id_mode": "empty",
                "design_a_gateway_target": "127.0.0.1:50051",
            }
        )
        empty_stub = _SubmitStub(failure_count=1)
        empty_adapter = GrpcPublicApiAdapter(
            scenario=empty_key_scenario,
            public_pb2=SimpleNamespace(
                SubmitJobRequest=lambda **kwargs: SimpleNamespace(**kwargs),
                JobSpec=lambda **kwargs: SimpleNamespace(**kwargs),
            ),
            public_pb2_grpc=SimpleNamespace(),
            target_stubs={"127.0.0.1:50051": empty_stub},
            sleep_fn=lambda _: None,
        )
        empty_context = SimpleNamespace(
            scenario=empty_key_scenario,
            run_id="r2",
            resolve_submit_target=lambda _k: (-1, "127.0.0.1:50051", "gateway"),
        )
        empty_row = empty_adapter.execute(
            context=empty_context,
            method="SubmitJob",
            rng=random.Random(0),
            worker_id=0,
            op_index=0,
        )
        self.assertEqual("UNAVAILABLE", empty_row.grpc_code)
        self.assertEqual(1, empty_stub.calls)

    def test_summary_latency_precision_and_job_terminal_throughput(self) -> None:
        rows = [
            BenchmarkRow(
                design="A_microservices",
                scenario_id="summary_precision",
                run_id="r1",
                method="GetJobStatus",
                start_ts_ms=1,
                latency_ms=0.111,
                grpc_code="OK",
                accepted=None,
                result_ready=None,
                already_terminal=None,
                job_terminal=False,
                job_id="job-1",
                concurrency=1,
                work_duration_ms=100,
                request_mix_profile="balanced",
                total_worker_slots=6,
            ),
            BenchmarkRow(
                design="A_microservices",
                scenario_id="summary_precision",
                run_id="r1",
                method="GetJobStatus",
                start_ts_ms=2,
                latency_ms=0.444,
                grpc_code="OK",
                accepted=None,
                result_ready=None,
                already_terminal=None,
                job_terminal=True,
                job_id="job-2",
                concurrency=1,
                work_duration_ms=100,
                request_mix_profile="balanced",
                total_worker_slots=6,
            ),
        ]
        summary = summarize_measurement_rows(rows=rows, measure_seconds=2.0)
        get_status_entry = next(item for item in summary["methods"] if item["method"] == "GetJobStatus")
        self.assertGreater(get_status_entry["latency_ms"]["p50"], 0.0)
        self.assertEqual(1, summary["job_terminal_throughput"]["unique_terminal_jobs"])
        self.assertEqual(0.5, summary["job_terminal_throughput"]["throughput_rps"])

    def test_precheck_health_targets_reports_unhealthy(self) -> None:
        scenario = BenchmarkScenario.from_dict(
            {
                "scenario_id": "precheck_probe",
                "design": "A_microservices",
                "concurrency": 1,
                "work_duration_ms": 10,
                "request_mix_profile": "submit-only",
                "request_mix_weights": {"SubmitJob": 1, "GetJobStatus": 0, "GetJobResult": 0, "CancelJob": 0, "ListJobs": 0},
                "warmup_seconds": 0,
                "measure_seconds": 1,
                "cooldown_seconds": 0,
                "repetitions": 1,
                "run_seed": 1,
                "total_worker_slots": 6,
                "design_a_gateway_target": "127.0.0.1:1",
            }
        )
        failures = validate_stack_health_targets(scenario, timeout_ms=100)
        self.assertEqual(1, len(failures))
        self.assertEqual("127.0.0.1:1", failures[0]["target"])


if __name__ == "__main__":
    unittest.main()
