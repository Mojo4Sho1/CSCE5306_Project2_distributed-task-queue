from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from common.design_b_routing import DesignBClientRouter

LOCKED_TOTAL_WORKER_SLOTS = 6
VALID_DESIGNS = {"A_microservices", "B_monolith"}
PRIMARY_METHODS = ("SubmitJob", "GetJobStatus", "GetJobResult", "CancelJob", "ListJobs")


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
    latency_ms: int
    grpc_code: str
    accepted: bool | None
    result_ready: bool | None
    already_terminal: bool | None
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
    metadata_path: Path
    row_count: int


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
            phase_metrics = self._execute_phases(context=context)
            rows = self._collect_measurement_rows(context=context, operation_hook=operation_hook)
            rows_jsonl_path = run_dir / "rows.jsonl"
            rows_csv_path = run_dir / "rows.csv"
            metadata_path = run_dir / "metadata.json"

            write_rows_jsonl(rows, rows_jsonl_path)
            row_count = write_rows_csv(rows, rows_csv_path)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata = {
                "scenario": self._scenario.to_dict(),
                "run_id": run_id,
                "repeat_index": repeat_index,
                "phase_metrics": phase_metrics,
                "row_count": row_count,
            }
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            artifacts.append(
                RunArtifacts(
                    run_id=run_id,
                    run_dir=run_dir,
                    rows_jsonl_path=rows_jsonl_path,
                    rows_csv_path=rows_csv_path,
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

    def _execute_phases(self, context: RunContext) -> dict[str, Any]:
        phases = (
            ("warmup", self._scenario.warmup_seconds, False),
            ("measure", self._scenario.measure_seconds, True),
            ("cooldown", self._scenario.cooldown_seconds, False),
        )
        results: dict[str, Any] = {}
        for phase_name, duration_seconds, recorded in phases:
            start_ms = int(self._clock_fn() * 1000)
            self._sleep_fn(duration_seconds)
            end_ms = int(self._clock_fn() * 1000)
            results[phase_name] = {
                "duration_seconds": duration_seconds,
                "recorded": recorded,
                "start_ts_ms": start_ms,
                "end_ts_ms": end_ms,
            }
        return results

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
