from __future__ import annotations

import csv
import hashlib
import json
import random
import socket
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Iterable, Mapping, Protocol, Sequence

from common.design_b_routing import DesignBClientRouter
from common.rpc_defaults import (
    RETRY_INITIAL_DELAY_MS,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY_MS,
    RETRY_MULTIPLIER,
)

LOCKED_TOTAL_WORKER_SLOTS = 6
VALID_DESIGNS = {"A_microservices", "B_monolith"}
PRIMARY_METHODS = ("SubmitJob", "GetJobStatus", "GetJobResult", "CancelJob", "ListJobs")
JOB_SCOPED_METHODS = frozenset(("GetJobStatus", "GetJobResult", "CancelJob"))
DEFAULT_CLIENT_DEADLINES_S = {
    "SubmitJob": 3.0,
    "CancelJob": 3.0,
    "GetJobStatus": 1.0,
    "GetJobResult": 1.0,
    "ListJobs": 1.0,
}
RETRYABLE_GRPC_CODES = frozenset(("UNAVAILABLE", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED"))
SUBMIT_CLIENT_REQUEST_ID_MODES = frozenset(("empty", "unique_non_empty"))
TERMINAL_JOB_STATUS_NAMES = frozenset(("DONE", "FAILED", "CANCELED"))
JOB_STATUS_VALUE_TO_NAME = {
    0: "JOB_STATUS_UNSPECIFIED",
    1: "QUEUED",
    2: "RUNNING",
    3: "DONE",
    4: "FAILED",
    5: "CANCELED",
}


def _require_non_empty_str(raw: Any, field_name: str) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _require_positive_int(raw: Any, field_name: str) -> int:
    value = int(raw)
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return value


def _require_non_negative_float(raw: Any, field_name: str) -> float:
    value = float(raw)
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value


def _require_positive_float(raw: Any, field_name: str) -> float:
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")
    return value


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    design: str
    concurrency: int
    work_duration_ms: int
    request_mix_profile: str
    request_mix_weights: dict[str, int]
    warmup_seconds: float
    measure_seconds: float
    cooldown_seconds: float
    repetitions: int
    run_seed: int
    total_worker_slots: int
    request_rate_rps: float | None = None
    submit_client_request_id_mode: str = "empty"
    design_a_gateway_target: str | None = None
    design_b_ordered_targets: tuple[str, ...] = ()
    design_b_round_robin_start: int = 0

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "BenchmarkScenario":
        if not isinstance(raw, Mapping):
            raise ValueError("scenario config must be a mapping")

        scenario_id = _require_non_empty_str(raw.get("scenario_id"), "scenario_id")
        design = _require_non_empty_str(raw.get("design"), "design")
        if design not in VALID_DESIGNS:
            raise ValueError(f"design must be one of {sorted(VALID_DESIGNS)}")

        concurrency = _require_positive_int(raw.get("concurrency"), "concurrency")
        work_duration_ms = _require_positive_int(raw.get("work_duration_ms"), "work_duration_ms")
        request_mix_profile = _require_non_empty_str(
            raw.get("request_mix_profile"), "request_mix_profile"
        )
        weights = cls._parse_request_mix_weights(raw.get("request_mix_weights"))

        warmup_seconds = _require_non_negative_float(raw.get("warmup_seconds"), "warmup_seconds")
        measure_seconds = _require_positive_float(raw.get("measure_seconds"), "measure_seconds")
        cooldown_seconds = _require_non_negative_float(
            raw.get("cooldown_seconds"), "cooldown_seconds"
        )
        repetitions = _require_positive_int(raw.get("repetitions"), "repetitions")
        run_seed = int(raw.get("run_seed"))
        total_worker_slots = _require_positive_int(raw.get("total_worker_slots"), "total_worker_slots")
        request_rate_rps_raw = raw.get("request_rate_rps")
        request_rate_rps = (
            _require_positive_float(request_rate_rps_raw, "request_rate_rps")
            if request_rate_rps_raw is not None
            else None
        )
        submit_client_request_id_mode = str(
            raw.get("submit_client_request_id_mode", "empty")
        ).strip()
        if submit_client_request_id_mode not in SUBMIT_CLIENT_REQUEST_ID_MODES:
            raise ValueError(
                "submit_client_request_id_mode must be one of "
                f"{sorted(SUBMIT_CLIENT_REQUEST_ID_MODES)}"
            )
        if total_worker_slots != LOCKED_TOTAL_WORKER_SLOTS:
            raise ValueError(
                f"total_worker_slots must equal locked value {LOCKED_TOTAL_WORKER_SLOTS}"
            )

        design_a_gateway_target = None
        design_b_targets: tuple[str, ...] = ()
        design_b_round_robin_start = int(raw.get("design_b_round_robin_start", 0))

        if design == "A_microservices":
            design_a_gateway_target = _require_non_empty_str(
                raw.get("design_a_gateway_target"), "design_a_gateway_target"
            )
        else:
            raw_targets = raw.get("design_b_ordered_targets")
            if not isinstance(raw_targets, Sequence) or isinstance(raw_targets, (str, bytes)):
                raise ValueError("design_b_ordered_targets must be a non-empty list of host:port targets")
            normalized_targets = tuple(_require_non_empty_str(item, "design_b_ordered_targets[]") for item in raw_targets)
            if not normalized_targets:
                raise ValueError("design_b_ordered_targets must be non-empty")
            design_b_targets = normalized_targets

        return cls(
            scenario_id=scenario_id,
            design=design,
            concurrency=concurrency,
            work_duration_ms=work_duration_ms,
            request_mix_profile=request_mix_profile,
            request_mix_weights=weights,
            warmup_seconds=warmup_seconds,
            measure_seconds=measure_seconds,
            cooldown_seconds=cooldown_seconds,
            repetitions=repetitions,
            run_seed=run_seed,
            total_worker_slots=total_worker_slots,
            request_rate_rps=request_rate_rps,
            submit_client_request_id_mode=submit_client_request_id_mode,
            design_a_gateway_target=design_a_gateway_target,
            design_b_ordered_targets=design_b_targets,
            design_b_round_robin_start=design_b_round_robin_start,
        )

    @staticmethod
    def _parse_request_mix_weights(raw: Any) -> dict[str, int]:
        if not isinstance(raw, Mapping):
            raise ValueError("request_mix_weights must be a mapping")

        parsed: dict[str, int] = {}
        for method in PRIMARY_METHODS:
            value = int(raw.get(method, 0))
            if value < 0:
                raise ValueError(f"request_mix_weights[{method}] must be >= 0")
            parsed[method] = value

        if sum(parsed.values()) <= 0:
            raise ValueError("request_mix_weights must include at least one positive weight")
        return parsed

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["design_b_ordered_targets"] = list(self.design_b_ordered_targets)
        return payload


@dataclass(frozen=True)
class BenchmarkRow:
    design: str
    scenario_id: str
    run_id: str
    method: str
    start_ts_ms: int
    latency_ms: float
    grpc_code: str
    accepted: bool | None
    result_ready: bool | None
    already_terminal: bool | None
    job_terminal: bool | None
    job_id: str | None
    concurrency: int
    work_duration_ms: int
    request_mix_profile: str
    total_worker_slots: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ROW_FIELDS = tuple(BenchmarkRow.__dataclass_fields__.keys())


def write_rows_jsonl(rows: Iterable[BenchmarkRow], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            json.dump(row.to_dict(), handle, separators=(",", ":"), sort_keys=False)
            handle.write("\n")
            count += 1
    return count


def write_rows_csv(rows: Iterable[BenchmarkRow], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())
            count += 1
    return count


def load_scenario_config(config_path: Path) -> BenchmarkScenario:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return BenchmarkScenario.from_dict(payload)


@dataclass(frozen=True)
class RunContext:
    scenario: BenchmarkScenario
    run_id: str
    repeat_index: int
    design_b_router: DesignBClientRouter | None = None

    def resolve_submit_target(self, client_request_id: str) -> tuple[int, str, str]:
        if self.scenario.design == "A_microservices":
            return -1, str(self.scenario.design_a_gateway_target), "gateway"
        if not self.design_b_router:
            raise ValueError("design_b_router is required for Design B scenarios")
        return self.design_b_router.submit_target(client_request_id)

    def resolve_job_target(self, job_id: str) -> tuple[int, str, str]:
        if self.scenario.design == "A_microservices":
            return -1, str(self.scenario.design_a_gateway_target), "gateway"
        if not self.design_b_router:
            raise ValueError("design_b_router is required for Design B scenarios")
        idx, target = self.design_b_router.job_target(job_id)
        return idx, target, "owner"


@dataclass(frozen=True)
class RunArtifacts:
    run_id: str
    run_dir: Path
    rows_jsonl_path: Path
    rows_csv_path: Path
    summary_json_path: Path
    summary_csv_path: Path
    metadata_path: Path
    row_count: int


class PhaseEngine(Protocol):
    def run_phase(
        self,
        *,
        context: RunContext,
        phase_name: str,
        duration_seconds: float,
        recorded: bool,
    ) -> list[BenchmarkRow]:
        ...


class BenchmarkRunner:
    """
    Benchmark execution scaffold implementing:
    warm-up -> measure -> cool-down -> repeat.

    This class does not generate production traffic yet. It exposes an operation
    hook so future load-generation logic can plug into the locked control flow.
    """

    def __init__(
        self,
        scenario: BenchmarkScenario,
        output_root: Path,
        *,
        clock_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._scenario = scenario
        self._output_root = Path(output_root)
        self._clock_fn = clock_fn or time.time
        self._sleep_fn = sleep_fn or time.sleep

    @property
    def scenario(self) -> BenchmarkScenario:
        return self._scenario

    def run(
        self,
        operation_hook: Callable[[RunContext, str], Sequence[BenchmarkRow]] | None = None,
        *,
        phase_engine: PhaseEngine | None = None,
    ) -> list[RunArtifacts]:
        artifacts: list[RunArtifacts] = []
        for repeat_index in range(self._scenario.repetitions):
            run_id = build_stable_run_id(
                scenario_id=self._scenario.scenario_id,
                run_seed=self._scenario.run_seed,
                repeat_index=repeat_index,
            )
            context = RunContext(
                scenario=self._scenario,
                run_id=run_id,
                repeat_index=repeat_index,
                design_b_router=self._build_design_b_router(),
            )
            run_dir = self._output_root / self._scenario.scenario_id / run_id
            phase_metrics, phase_rows = self._execute_phases(context=context, phase_engine=phase_engine)
            if phase_engine is not None:
                rows = phase_rows
            else:
                rows = self._collect_measurement_rows(context=context, operation_hook=operation_hook)
            rows_jsonl_path = run_dir / "rows.jsonl"
            rows_csv_path = run_dir / "rows.csv"
            summary_json_path = run_dir / "summary.json"
            summary_csv_path = run_dir / "summary.csv"
            metadata_path = run_dir / "metadata.json"

            write_rows_jsonl(rows, rows_jsonl_path)
            row_count = write_rows_csv(rows, rows_csv_path)
            summary = summarize_measurement_rows(rows=rows, measure_seconds=self._scenario.measure_seconds)
            write_summary_json(summary, summary_json_path)
            write_summary_csv(summary, summary_csv_path)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata = {
                "scenario": self._scenario.to_dict(),
                "run_id": run_id,
                "repeat_index": repeat_index,
                "phase_metrics": phase_metrics,
                "row_count": row_count,
                "summary": summary,
            }
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            artifacts.append(
                RunArtifacts(
                    run_id=run_id,
                    run_dir=run_dir,
                    rows_jsonl_path=rows_jsonl_path,
                    rows_csv_path=rows_csv_path,
                    summary_json_path=summary_json_path,
                    summary_csv_path=summary_csv_path,
                    metadata_path=metadata_path,
                    row_count=row_count,
                )
            )

        return artifacts

    def _build_design_b_router(self) -> DesignBClientRouter | None:
        if self._scenario.design != "B_monolith":
            return None
        return DesignBClientRouter(
            ordered_nodes=self._scenario.design_b_ordered_targets,
            round_robin_start=self._scenario.design_b_round_robin_start,
        )

    def _execute_phases(
        self,
        *,
        context: RunContext,
        phase_engine: PhaseEngine | None,
    ) -> tuple[dict[str, Any], list[BenchmarkRow]]:
        phases = (
            ("warmup", self._scenario.warmup_seconds, False),
            ("measure", self._scenario.measure_seconds, True),
            ("cooldown", self._scenario.cooldown_seconds, False),
        )
        results: dict[str, Any] = {}
        measured_rows: list[BenchmarkRow] = []
        for phase_name, duration_seconds, recorded in phases:
            start_ms = int(self._clock_fn() * 1000)
            phase_row_count = 0
            if phase_engine is not None:
                phase_rows = phase_engine.run_phase(
                    context=context,
                    phase_name=phase_name,
                    duration_seconds=duration_seconds,
                    recorded=recorded,
                )
                phase_row_count = len(phase_rows)
                if recorded:
                    measured_rows.extend(phase_rows)
            else:
                self._sleep_fn(duration_seconds)
            end_ms = int(self._clock_fn() * 1000)
            results[phase_name] = {
                "duration_seconds": duration_seconds,
                "recorded": recorded,
                "start_ts_ms": start_ms,
                "end_ts_ms": end_ms,
                "row_count": phase_row_count,
            }
        return results, measured_rows

    def _collect_measurement_rows(
        self,
        context: RunContext,
        operation_hook: Callable[[RunContext, str], Sequence[BenchmarkRow]] | None,
    ) -> list[BenchmarkRow]:
        if not operation_hook:
            return []
        return list(operation_hook(context, "measure"))


def build_stable_run_id(scenario_id: str, run_seed: int, repeat_index: int) -> str:
    base = f"{scenario_id}:{int(run_seed)}:{int(repeat_index)}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:10]
    return f"{scenario_id}-r{repeat_index:02d}-{digest}"


class RequestMixScheduler:
    """
    Deterministic weighted scheduler for benchmark operation selection.
    """

    def __init__(self, request_mix_weights: Mapping[str, int], seed: int) -> None:
        methods: list[str] = []
        for method in PRIMARY_METHODS:
            weight = int(request_mix_weights.get(method, 0))
            if weight > 0:
                methods.extend([method] * weight)
        if not methods:
            raise ValueError("request_mix_weights must include at least one positive weight")

        rng = random.Random(int(seed))
        rng.shuffle(methods)
        self._methods = tuple(methods)
        self._index = 0
        self._lock = threading.Lock()

    def next_method(self) -> str:
        with self._lock:
            method = self._methods[self._index]
            self._index = (self._index + 1) % len(self._methods)
            return method


class OperationAdapter(Protocol):
    def known_job_count(self, context: RunContext) -> int:
        ...

    def execute(
        self,
        *,
        context: RunContext,
        method: str,
        rng: random.Random,
        worker_id: int,
        op_index: int,
    ) -> BenchmarkRow:
        ...


class LiveTrafficEngine:
    """
    Executes live request traffic for warmup/measure/cooldown using:
    - scenario request-mix weights,
    - scenario concurrency,
    - optional fixed request-rate pacing.
    """

    def __init__(
        self,
        *,
        scenario: BenchmarkScenario,
        adapter: OperationAdapter,
        request_rate_rps: float | None = None,
        monotonic_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._scenario = scenario
        self._adapter = adapter
        self._request_rate_rps = (
            float(request_rate_rps)
            if request_rate_rps is not None
            else (
                float(scenario.request_rate_rps)
                if scenario.request_rate_rps is not None
                else None
            )
        )
        if self._request_rate_rps is not None and self._request_rate_rps <= 0:
            raise ValueError("request_rate_rps must be > 0 when provided")
        self._monotonic_fn = monotonic_fn or time.monotonic
        self._sleep_fn = sleep_fn or time.sleep

    def run_phase(
        self,
        *,
        context: RunContext,
        phase_name: str,
        duration_seconds: float,
        recorded: bool,
    ) -> list[BenchmarkRow]:
        if duration_seconds <= 0:
            return []

        phase_seed = _phase_seed(
            base_seed=context.scenario.run_seed,
            repeat_index=context.repeat_index,
            phase_name=phase_name,
        )
        scheduler = RequestMixScheduler(context.scenario.request_mix_weights, seed=phase_seed)
        rows: list[BenchmarkRow] = []
        row_lock = threading.Lock()
        phase_start = self._monotonic_fn()
        stop_at = phase_start + float(duration_seconds)
        worker_threads: list[threading.Thread] = []
        request_interval_s = self._request_interval_seconds()

        def _worker_loop(worker_id: int) -> None:
            rng = random.Random(phase_seed + (worker_id * 9_973))
            op_index = 0
            next_due = phase_start
            while True:
                now = self._monotonic_fn()
                if now >= stop_at:
                    break

                if request_interval_s is not None:
                    if now < next_due:
                        self._sleep_fn(min(next_due - now, max(0.0, stop_at - now)))
                        continue
                    next_due += request_interval_s

                method = scheduler.next_method()
                if method in JOB_SCOPED_METHODS and self._adapter.known_job_count(context) <= 0:
                    method = "SubmitJob"

                row = self._adapter.execute(
                    context=context,
                    method=method,
                    rng=rng,
                    worker_id=worker_id,
                    op_index=op_index,
                )
                op_index += 1
                if recorded:
                    with row_lock:
                        rows.append(row)

        for worker_id in range(self._scenario.concurrency):
            thread = threading.Thread(
                target=_worker_loop,
                args=(worker_id,),
                daemon=True,
                name=f"loadgen-{phase_name}-w{worker_id}",
            )
            worker_threads.append(thread)
            thread.start()
        for thread in worker_threads:
            thread.join()

        rows.sort(key=lambda row: (row.start_ts_ms, row.method, row.job_id or ""))
        return rows

    def _request_interval_seconds(self) -> float | None:
        if self._request_rate_rps is None:
            return None
        return float(self._scenario.concurrency) / self._request_rate_rps


class GrpcPublicApiAdapter:
    """
    Live gRPC adapter for benchmark parity methods.
    """

    def __init__(
        self,
        scenario: BenchmarkScenario,
        *,
        grpc_module: ModuleType | None = None,
        public_pb2: ModuleType | None = None,
        public_pb2_grpc: ModuleType | None = None,
        target_stubs: Mapping[str, Any] | None = None,
        monotonic_fn: Callable[[], float] | None = None,
        wall_clock_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._scenario = scenario
        self._monotonic_fn = monotonic_fn or time.monotonic
        self._wall_clock_fn = wall_clock_fn or time.time
        self._sleep_fn = sleep_fn or time.sleep
        self._grpc = grpc_module
        self._public_pb2 = public_pb2
        self._public_pb2_grpc = public_pb2_grpc
        if self._public_pb2 is None or self._public_pb2_grpc is None:
            self._grpc, self._public_pb2, self._public_pb2_grpc = _load_public_proto_modules()

        self._stubs: dict[str, Any] = {}
        self._channels: dict[str, Any] = {}
        self._run_jobs: dict[str, list[str]] = {}
        self._jobs_lock = threading.Lock()

        if target_stubs is not None:
            self._stubs.update({str(k): v for k, v in target_stubs.items()})
        else:
            targets = self._scenario_targets()
            for target in targets:
                channel = self._grpc.insecure_channel(target)
                self._channels[target] = channel
                self._stubs[target] = self._public_pb2_grpc.TaskQueuePublicServiceStub(channel)

    def close(self) -> None:
        for channel in self._channels.values():
            try:
                channel.close()
            except Exception:
                continue

    def known_job_count(self, context: RunContext) -> int:
        with self._jobs_lock:
            return len(self._run_jobs.get(context.run_id, []))

    def execute(
        self,
        *,
        context: RunContext,
        method: str,
        rng: random.Random,
        worker_id: int,
        op_index: int,
    ) -> BenchmarkRow:
        if method not in PRIMARY_METHODS:
            raise ValueError(f"unsupported method: {method}")

        if method == "SubmitJob":
            return self._execute_submit(context=context, rng=rng, worker_id=worker_id, op_index=op_index)
        if method == "GetJobStatus":
            return self._execute_get_status(context=context, rng=rng)
        if method == "GetJobResult":
            return self._execute_get_result(context=context, rng=rng)
        if method == "CancelJob":
            return self._execute_cancel(context=context, rng=rng)
        return self._execute_list_jobs(context=context)

    def _execute_submit(
        self,
        *,
        context: RunContext,
        rng: random.Random,
        worker_id: int,
        op_index: int,
    ) -> BenchmarkRow:
        client_request_id = self._build_client_request_id(
            context=context,
            worker_id=worker_id,
            op_index=op_index,
        )
        _idx, target, _mode = context.resolve_submit_target(client_request_id)
        stub = self._stubs[target]
        submit_request = self._public_pb2.SubmitJobRequest(
            spec=self._public_pb2.JobSpec(
                job_type=f"loadgen-{context.scenario.request_mix_profile}",
                work_duration_ms=int(context.scenario.work_duration_ms),
                payload_size_bytes=16,
                labels={
                    "suite": "loadgen_live",
                    "scenario_id": context.scenario.scenario_id,
                    "run_id": context.run_id,
                    "worker_id": str(worker_id),
                },
            ),
            client_request_id=client_request_id,
        )

        start_ts_ms = int(self._wall_clock_fn() * 1000)
        start_monotonic = self._monotonic_fn()
        result = self._invoke_with_retry(
            method="SubmitJob",
            call_fn=lambda timeout_s: stub.SubmitJob(submit_request, timeout=timeout_s),
            timeout_s=DEFAULT_CLIENT_DEADLINES_S["SubmitJob"],
            allow_retry=bool(client_request_id),
            rng=rng,
        )
        latency_ms = _elapsed_latency_ms(start_monotonic, self._monotonic_fn)
        accepted = bool(result.response is not None and str(result.response.job_id).strip())
        job_id = str(result.response.job_id).strip() if result.response is not None else None
        if result.grpc_code == "OK" and job_id:
            self._register_job_id(context.run_id, job_id)

        return BenchmarkRow(
            design=context.scenario.design,
            scenario_id=context.scenario.scenario_id,
            run_id=context.run_id,
            method="SubmitJob",
            start_ts_ms=start_ts_ms,
            latency_ms=latency_ms,
            grpc_code=result.grpc_code,
            accepted=accepted if result.grpc_code == "OK" else None,
            result_ready=None,
            already_terminal=None,
            job_terminal=None,
            job_id=job_id,
            concurrency=context.scenario.concurrency,
            work_duration_ms=context.scenario.work_duration_ms,
            request_mix_profile=context.scenario.request_mix_profile,
            total_worker_slots=context.scenario.total_worker_slots,
        )

    def _execute_get_status(self, *, context: RunContext, rng: random.Random) -> BenchmarkRow:
        job_id = self._pick_job_id(context.run_id, rng)
        if not job_id:
            return self._execute_submit(context=context, rng=rng, worker_id=0, op_index=-1)

        _idx, target, _mode = context.resolve_job_target(job_id)
        stub = self._stubs[target]
        request = self._public_pb2.GetJobStatusRequest(job_id=job_id)
        start_ts_ms = int(self._wall_clock_fn() * 1000)
        start_monotonic = self._monotonic_fn()
        result = self._invoke_with_retry(
            method="GetJobStatus",
            call_fn=lambda timeout_s: stub.GetJobStatus(request, timeout=timeout_s),
            timeout_s=DEFAULT_CLIENT_DEADLINES_S["GetJobStatus"],
            allow_retry=True,
            rng=rng,
        )
        latency_ms = _elapsed_latency_ms(start_monotonic, self._monotonic_fn)
        job_terminal = None
        if result.grpc_code == "OK" and result.response is not None:
            job_terminal = _is_terminal_job_status(result.response.status)

        return BenchmarkRow(
            design=context.scenario.design,
            scenario_id=context.scenario.scenario_id,
            run_id=context.run_id,
            method="GetJobStatus",
            start_ts_ms=start_ts_ms,
            latency_ms=latency_ms,
            grpc_code=result.grpc_code,
            accepted=None,
            result_ready=None,
            already_terminal=None,
            job_terminal=job_terminal,
            job_id=job_id,
            concurrency=context.scenario.concurrency,
            work_duration_ms=context.scenario.work_duration_ms,
            request_mix_profile=context.scenario.request_mix_profile,
            total_worker_slots=context.scenario.total_worker_slots,
        )

    def _execute_get_result(self, *, context: RunContext, rng: random.Random) -> BenchmarkRow:
        job_id = self._pick_job_id(context.run_id, rng)
        if not job_id:
            return self._execute_submit(context=context, rng=rng, worker_id=0, op_index=-1)

        _idx, target, _mode = context.resolve_job_target(job_id)
        stub = self._stubs[target]
        request = self._public_pb2.GetJobResultRequest(job_id=job_id)
        start_ts_ms = int(self._wall_clock_fn() * 1000)
        start_monotonic = self._monotonic_fn()
        result = self._invoke_with_retry(
            method="GetJobResult",
            call_fn=lambda timeout_s: stub.GetJobResult(request, timeout=timeout_s),
            timeout_s=DEFAULT_CLIENT_DEADLINES_S["GetJobResult"],
            allow_retry=True,
            rng=rng,
        )
        latency_ms = _elapsed_latency_ms(start_monotonic, self._monotonic_fn)
        result_ready = None
        job_terminal = None
        if result.grpc_code == "OK" and result.response is not None:
            result_ready = bool(result.response.result_ready)
            job_terminal = bool(result_ready) and _is_terminal_job_status(
                result.response.terminal_status
            )

        return BenchmarkRow(
            design=context.scenario.design,
            scenario_id=context.scenario.scenario_id,
            run_id=context.run_id,
            method="GetJobResult",
            start_ts_ms=start_ts_ms,
            latency_ms=latency_ms,
            grpc_code=result.grpc_code,
            accepted=None,
            result_ready=result_ready,
            already_terminal=None,
            job_terminal=job_terminal,
            job_id=job_id,
            concurrency=context.scenario.concurrency,
            work_duration_ms=context.scenario.work_duration_ms,
            request_mix_profile=context.scenario.request_mix_profile,
            total_worker_slots=context.scenario.total_worker_slots,
        )

    def _execute_cancel(self, *, context: RunContext, rng: random.Random) -> BenchmarkRow:
        job_id = self._pick_job_id(context.run_id, rng)
        if not job_id:
            return self._execute_submit(context=context, rng=rng, worker_id=0, op_index=-1)

        _idx, target, _mode = context.resolve_job_target(job_id)
        stub = self._stubs[target]
        request = self._public_pb2.CancelJobRequest(
            job_id=job_id,
            reason="loadgen_cancel",
        )
        start_ts_ms = int(self._wall_clock_fn() * 1000)
        start_monotonic = self._monotonic_fn()
        result = self._invoke_with_retry(
            method="CancelJob",
            call_fn=lambda timeout_s: stub.CancelJob(request, timeout=timeout_s),
            timeout_s=DEFAULT_CLIENT_DEADLINES_S["CancelJob"],
            allow_retry=True,
            rng=rng,
        )
        latency_ms = _elapsed_latency_ms(start_monotonic, self._monotonic_fn)
        accepted = None
        already_terminal = None
        job_terminal = None
        if result.grpc_code == "OK" and result.response is not None:
            accepted = bool(result.response.accepted)
            already_terminal = bool(result.response.already_terminal)
            job_terminal = _is_terminal_job_status(result.response.current_status)

        return BenchmarkRow(
            design=context.scenario.design,
            scenario_id=context.scenario.scenario_id,
            run_id=context.run_id,
            method="CancelJob",
            start_ts_ms=start_ts_ms,
            latency_ms=latency_ms,
            grpc_code=result.grpc_code,
            accepted=accepted,
            result_ready=None,
            already_terminal=already_terminal,
            job_terminal=job_terminal,
            job_id=job_id,
            concurrency=context.scenario.concurrency,
            work_duration_ms=context.scenario.work_duration_ms,
            request_mix_profile=context.scenario.request_mix_profile,
            total_worker_slots=context.scenario.total_worker_slots,
        )

    def _execute_list_jobs(self, *, context: RunContext) -> BenchmarkRow:
        if context.scenario.design == "A_microservices":
            target = str(context.scenario.design_a_gateway_target)
        else:
            target = context.scenario.design_b_ordered_targets[0]
        stub = self._stubs[target]
        request = self._public_pb2.ListJobsRequest(
            page=self._public_pb2.PageRequest(page_size=20, page_token=""),
            sort=self._public_pb2.CREATED_AT_DESC,
        )

        start_ts_ms = int(self._wall_clock_fn() * 1000)
        start_monotonic = self._monotonic_fn()
        result = self._invoke_with_retry(
            method="ListJobs",
            call_fn=lambda timeout_s: stub.ListJobs(request, timeout=timeout_s),
            timeout_s=DEFAULT_CLIENT_DEADLINES_S["ListJobs"],
            allow_retry=True,
            rng=random.Random(0),
        )
        latency_ms = _elapsed_latency_ms(start_monotonic, self._monotonic_fn)
        return BenchmarkRow(
            design=context.scenario.design,
            scenario_id=context.scenario.scenario_id,
            run_id=context.run_id,
            method="ListJobs",
            start_ts_ms=start_ts_ms,
            latency_ms=latency_ms,
            grpc_code=result.grpc_code,
            accepted=None,
            result_ready=None,
            already_terminal=None,
            job_terminal=None,
            job_id=None,
            concurrency=context.scenario.concurrency,
            work_duration_ms=context.scenario.work_duration_ms,
            request_mix_profile=context.scenario.request_mix_profile,
            total_worker_slots=context.scenario.total_worker_slots,
        )

    def _scenario_targets(self) -> list[str]:
        if self._scenario.design == "A_microservices":
            return [str(self._scenario.design_a_gateway_target)]
        return list(self._scenario.design_b_ordered_targets)

    def _register_job_id(self, run_id: str, job_id: str) -> None:
        with self._jobs_lock:
            jobs = self._run_jobs.setdefault(run_id, [])
            if job_id not in jobs:
                jobs.append(job_id)

    def _pick_job_id(self, run_id: str, rng: random.Random) -> str | None:
        with self._jobs_lock:
            jobs = self._run_jobs.get(run_id, [])
            if not jobs:
                return None
            return jobs[rng.randrange(len(jobs))]

    def _build_client_request_id(
        self,
        *,
        context: RunContext,
        worker_id: int,
        op_index: int,
    ) -> str:
        mode = context.scenario.submit_client_request_id_mode
        if mode == "empty":
            return ""
        return (
            f"loadgen-{context.run_id}-{worker_id}-{op_index}-"
            f"{int(self._wall_clock_fn() * 1000)}"
        )

    def _invoke_with_retry(
        self,
        *,
        method: str,
        call_fn: Callable[[float], Any],
        timeout_s: float,
        allow_retry: bool,
        rng: random.Random,
    ) -> "_RpcAttemptResult":
        del method
        max_attempts = RETRY_MAX_ATTEMPTS if allow_retry else 1
        backoff_window_s = RETRY_INITIAL_DELAY_MS / 1000.0
        for attempt in range(1, max_attempts + 1):
            try:
                response = call_fn(timeout_s)
                return _RpcAttemptResult(grpc_code="OK", response=response, attempt_count=attempt)
            except Exception as exc:  # noqa: BLE001
                grpc_code = _extract_grpc_code_name(exc)
                retryable = grpc_code in RETRYABLE_GRPC_CODES
                if attempt >= max_attempts or not retryable:
                    return _RpcAttemptResult(grpc_code=grpc_code, response=None, attempt_count=attempt)
                window_s = min(backoff_window_s, RETRY_MAX_DELAY_MS / 1000.0)
                self._sleep_fn(rng.uniform(0.0, window_s))
                backoff_window_s = min(window_s * RETRY_MULTIPLIER, RETRY_MAX_DELAY_MS / 1000.0)
        return _RpcAttemptResult(grpc_code="INTERNAL", response=None, attempt_count=max_attempts)


@dataclass(frozen=True)
class _RpcAttemptResult:
    grpc_code: str
    response: Any | None
    attempt_count: int


def summarize_measurement_rows(rows: Sequence[BenchmarkRow], measure_seconds: float) -> dict[str, Any]:
    effective_seconds = max(float(measure_seconds), 0.001)
    by_method: dict[str, list[BenchmarkRow]] = {}
    for row in rows:
        by_method.setdefault(row.method, []).append(row)

    method_summaries: list[dict[str, Any]] = []
    for method in PRIMARY_METHODS:
        method_rows = by_method.get(method, [])
        total = len(method_rows)
        ok_count = sum(1 for row in method_rows if row.grpc_code == "OK")
        latency_values = [max(0.0, float(row.latency_ms)) for row in method_rows]
        code_counts: dict[str, int] = {}
        for row in method_rows:
            code_counts[row.grpc_code] = code_counts.get(row.grpc_code, 0) + 1
        code_rates = {
            code: round(count / total, 6) if total else 0.0
            for code, count in sorted(code_counts.items())
        }
        method_summaries.append(
            {
                "method": method,
                "total_calls": total,
                "ok_calls": ok_count,
                "throughput_rps": round(ok_count / effective_seconds, 6),
                "latency_ms": {
                    "p50": _percentile(latency_values, 50),
                    "p95": _percentile(latency_values, 95),
                    "p99": _percentile(latency_values, 99),
                },
                "grpc_code_rates": code_rates,
            }
        )

    terminal_jobs = {
        str(row.job_id).strip()
        for row in rows
        if row.grpc_code == "OK" and bool(row.job_terminal) and str(row.job_id or "").strip()
    }
    terminal_job_count = len(terminal_jobs)

    return {
        "measure_seconds": float(measure_seconds),
        "total_rows": len(rows),
        "job_terminal_throughput": {
            "unique_terminal_jobs": terminal_job_count,
            "throughput_rps": round(terminal_job_count / effective_seconds, 6),
        },
        "methods": method_summaries,
    }


def write_summary_json(summary: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def write_summary_csv(summary: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "method",
        "total_calls",
        "ok_calls",
        "throughput_rps",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "grpc_code_rates_json",
        "job_terminal_unique_jobs",
        "job_terminal_throughput_rps",
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        terminal_summary = summary.get("job_terminal_throughput", {})
        for entry in summary.get("methods", []):
            latency = entry.get("latency_ms", {})
            writer.writerow(
                {
                    "method": entry.get("method"),
                    "total_calls": entry.get("total_calls"),
                    "ok_calls": entry.get("ok_calls"),
                    "throughput_rps": entry.get("throughput_rps"),
                    "latency_p50_ms": latency.get("p50"),
                    "latency_p95_ms": latency.get("p95"),
                    "latency_p99_ms": latency.get("p99"),
                    "grpc_code_rates_json": json.dumps(
                        entry.get("grpc_code_rates", {}),
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    "job_terminal_unique_jobs": terminal_summary.get("unique_terminal_jobs", 0),
                    "job_terminal_throughput_rps": terminal_summary.get("throughput_rps", 0.0),
                }
            )


def _percentile(values: Sequence[float], percentile: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    rank = int(round((max(1, int(percentile)) / 100.0) * len(sorted_values) + 0.5)) - 1
    index = max(0, min(rank, len(sorted_values) - 1))
    return round(float(sorted_values[index]), 3)


def validate_stack_health_targets(
    scenario: BenchmarkScenario,
    *,
    timeout_ms: int = 1000,
) -> list[dict[str, str]]:
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be > 0")
    targets = (
        [str(scenario.design_a_gateway_target)]
        if scenario.design == "A_microservices"
        else list(scenario.design_b_ordered_targets)
    )
    failures: list[dict[str, str]] = []
    timeout_s = float(timeout_ms) / 1000.0
    for target in targets:
        host, port = _parse_target_host_port(target)
        try:
            with socket.create_connection((host, port), timeout=timeout_s):
                continue
        except OSError as exc:
            failures.append({"target": target, "error": str(exc)})
    return failures


def _parse_target_host_port(target: str) -> tuple[str, int]:
    raw = str(target or "").strip()
    if ":" not in raw:
        raise ValueError(f"target must be host:port, got {raw!r}")
    host, port_raw = raw.rsplit(":", 1)
    host = host.strip()
    port_raw = port_raw.strip()
    if not host:
        raise ValueError(f"target host must be non-empty, got {raw!r}")
    port = int(port_raw)
    if port <= 0 or port > 65535:
        raise ValueError(f"target port out of range, got {raw!r}")
    return host, port


def _status_name(value: Any) -> str:
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if name is not None:
        return str(name)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int):
        return JOB_STATUS_VALUE_TO_NAME.get(value, str(value))
    return str(value)


def _is_terminal_job_status(value: Any) -> bool:
    return _status_name(value) in TERMINAL_JOB_STATUS_NAMES


def _elapsed_latency_ms(start_monotonic: float, monotonic_fn: Callable[[], float]) -> float:
    elapsed_ms = max(0.0, (monotonic_fn() - start_monotonic) * 1000.0)
    if elapsed_ms <= 0.0:
        return 0.001
    return round(max(elapsed_ms, 0.001), 3)


def _phase_seed(base_seed: int, repeat_index: int, phase_name: str) -> int:
    phase_offset = {"warmup": 11, "measure": 29, "cooldown": 53}.get(phase_name, 71)
    return int(base_seed) + (int(repeat_index) * 100_003) + phase_offset


def _extract_grpc_code_name(exc: Exception) -> str:
    try:
        code = exc.code()  # type: ignore[attr-defined]
        if hasattr(code, "name"):
            return str(code.name)
        return str(code)
    except Exception:  # noqa: BLE001
        return "INTERNAL"


def _load_public_proto_modules() -> tuple[ModuleType, ModuleType, ModuleType]:
    repo_root = Path(__file__).resolve().parents[1]
    generated_dir = repo_root / "generated"
    if str(generated_dir) not in sys.path:
        sys.path.insert(0, str(generated_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    import grpc  # type: ignore
    import taskqueue_public_pb2 as public_pb2  # type: ignore
    import taskqueue_public_pb2_grpc as public_pb2_grpc  # type: ignore

    return grpc, public_pb2, public_pb2_grpc
