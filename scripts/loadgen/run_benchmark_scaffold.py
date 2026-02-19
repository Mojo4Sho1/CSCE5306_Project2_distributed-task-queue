from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.loadgen_contracts import BenchmarkRunner, load_scenario_config


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenario_path = Path(args.scenario)
    output_dir = Path(args.output_dir)

    scenario = load_scenario_config(scenario_path)
    runner = BenchmarkRunner(scenario=scenario, output_root=output_dir)
    artifacts = runner.run()

    summary = [
        {
            "run_id": item.run_id,
            "run_dir": str(item.run_dir),
            "row_count": item.row_count,
            "rows_jsonl": str(item.rows_jsonl_path),
            "rows_csv": str(item.rows_csv_path),
            "metadata_json": str(item.metadata_path),
        }
        for item in artifacts
    ]
    print(json.dumps({"scenario_id": scenario.scenario_id, "runs": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
