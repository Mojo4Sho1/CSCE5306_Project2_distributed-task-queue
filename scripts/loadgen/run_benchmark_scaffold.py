from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.loadgen_contracts import (
    BenchmarkRunner,
    GrpcPublicApiAdapter,
    LiveTrafficEngine,
    load_scenario_config,
    validate_stack_health_targets,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run benchmark scaffold phases and write contract artifacts."
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Path to scenario JSON config",
    )
    parser.add_argument(
        "--output-dir",
        default="results/loadgen",
        help="Artifact output root directory (default: results/loadgen)",
    )
    parser.add_argument(
        "--live-traffic",
        action="store_true",
        help="Execute live RPC traffic for warmup/measure/cooldown phases.",
    )
    parser.add_argument(
        "--request-rate-rps",
        type=float,
        default=None,
        help="Optional global request-rate override (RPS). If omitted, scenario value is used.",
    )
    parser.add_argument(
        "--precheck-health",
        action="store_true",
        help="Run pre-run TCP health probes for required ingress targets and fail fast on unhealthy state.",
    )
    parser.add_argument(
        "--precheck-timeout-ms",
        type=int,
        default=1000,
        help="Timeout for each precheck probe in milliseconds (default: 1000).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing deterministic run directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenario_path = Path(args.scenario)
    output_dir = Path(args.output_dir)

    scenario = load_scenario_config(scenario_path)
    if args.precheck_health:
        if args.precheck_timeout_ms <= 0:
            print(
                json.dumps(
                    {
                        "error": "invalid precheck timeout",
                        "precheck_timeout_ms": args.precheck_timeout_ms,
                    }
                ),
                file=sys.stderr,
            )
            return 2
        failures = validate_stack_health_targets(
            scenario,
            timeout_ms=args.precheck_timeout_ms,
        )
        if failures:
            print(
                json.dumps(
                    {
                        "error": "precheck failed",
                        "scenario_id": scenario.scenario_id,
                        "design": scenario.design,
                        "failures": failures,
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 2

    runner = BenchmarkRunner(scenario=scenario, output_root=output_dir)
    adapter = None
    try:
        if args.live_traffic:
            adapter = GrpcPublicApiAdapter(scenario=scenario)
            phase_engine = LiveTrafficEngine(
                scenario=scenario,
                adapter=adapter,
                request_rate_rps=args.request_rate_rps,
            )
            artifacts = runner.run(phase_engine=phase_engine, overwrite=args.overwrite)
        else:
            artifacts = runner.run(overwrite=args.overwrite)
    except FileExistsError as exc:
        print(
            json.dumps(
                {
                    "error": "run directory already exists",
                    "scenario_id": scenario.scenario_id,
                    "detail": str(exc),
                    "hint": "rerun with --overwrite to replace existing artifacts",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 3
    finally:
        if adapter is not None:
            adapter.close()

    summary = [
        {
            "run_id": item.run_id,
            "run_dir": str(item.run_dir),
            "row_count": item.row_count,
            "rows_jsonl": str(item.rows_jsonl_path),
            "rows_csv": str(item.rows_csv_path),
            "summary_json": str(item.summary_json_path),
            "summary_csv": str(item.summary_csv_path),
            "metadata_json": str(item.metadata_path),
        }
        for item in artifacts
    ]
    print(json.dumps({"scenario_id": scenario.scenario_id, "runs": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
