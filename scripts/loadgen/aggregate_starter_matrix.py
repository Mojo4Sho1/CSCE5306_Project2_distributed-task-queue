"""Command-line helper for aggregate starter matrix."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

PRIMARY_METHODS = ("SubmitJob", "GetJobStatus", "GetJobResult", "CancelJob")
DESIGN_ORDER = ("A_microservices", "B_monolith")
SCENARIO_CORE_ORDER = (
    "s_low_submit_heavy",
    "s_low_poll_heavy",
    "s_low_balanced",
    "s_medium_submit_heavy",
    "s_medium_poll_heavy",
    "s_medium_balanced",
    "s_high_submit_heavy",
    "s_high_poll_heavy",
    "s_high_balanced",
)
SCENARIO_REPORT_IDS = {
    "s_low_submit_heavy": "S1",
    "s_low_balanced": "S2",
    "s_low_poll_heavy": "S3",
    "s_medium_submit_heavy": "S4",
    "s_medium_balanced": "S5",
    "s_medium_poll_heavy": "S6",
    "s_high_submit_heavy": "S7",
    "s_high_balanced": "S8",
    "s_high_poll_heavy": "S9",
}
SCENARIO_PLOT_ORDER = tuple(SCENARIO_REPORT_IDS.keys())


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for this command."""
    parser = argparse.ArgumentParser(
        description="Aggregate starter-matrix loadgen artifacts into A/B comparison tables and plots."
    )
    parser.add_argument(
        "--results-root",
        default="results/loadgen",
        help="Root directory containing run scenario folders (default: results/loadgen).",
    )
    parser.add_argument(
        "--output-dir",
        default="results/loadgen/analysis/starter_matrix_2026-02-20",
        help="Output directory for aggregate tables/plots.",
    )
    return parser.parse_args()


def _safe_mean(values: list[float]) -> float:
    """Return the arithmetic mean, defaulting to 0.0 for empty samples."""
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _safe_std(values: list[float]) -> float:
    """Return sample standard deviation, defaulting to 0.0 for fewer than two samples."""
    if len(values) < 2:
        return 0.0
    mean = _safe_mean(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return float(math.sqrt(max(0.0, variance)))


def _safe_cv(values: list[float]) -> float:
    """Return coefficient of variation (std/mean), or 0.0 when mean is zero."""
    mean = _safe_mean(values)
    if mean == 0.0:
        return 0.0
    return _safe_std(values) / mean


def _round(value: float) -> float:
    """Round numeric aggregates to six decimals for stable CSV/markdown output."""
    return round(float(value), 6)


def _scenario_sort_key(scenario_id: str) -> tuple[int, str]:
    """Build a stable sort key so starter-matrix scenarios appear in pedagogical order."""
    core = _scenario_core(scenario_id)
    try:
        idx = SCENARIO_CORE_ORDER.index(core)
    except ValueError:
        idx = 10_000
    return idx, scenario_id


def _scenario_core(scenario_id: str) -> str:
    """Strip design prefix from scenario ids so A/B variants share a common key."""
    core = scenario_id
    if core.startswith("design_a_"):
        core = core[len("design_a_") :]
    elif core.startswith("design_b_"):
        core = core[len("design_b_") :]
    return core


def _non_ok_rate(grpc_rates: dict[str, Any]) -> float:
    """Compute non-OK gRPC rate from per-code proportions in summary artifacts."""
    ok = float(grpc_rates.get("OK", 0.0))
    rate = 1.0 - ok
    if rate < 0.0:
        return 0.0
    return float(rate)


def _iter_run_summary_files(results_root: Path) -> list[Path]:
    """Enumerate summary.json files for starter-matrix scenario run directories."""
    matches: list[Path] = []
    for scenario_dir in sorted(results_root.glob("design_*_s_*")):
        if not scenario_dir.is_dir():
            continue
        for run_dir in sorted(scenario_dir.iterdir()):
            summary_path = run_dir / "summary.json"
            metadata_path = run_dir / "metadata.json"
            if summary_path.exists() and metadata_path.exists():
                matches.append(summary_path)
    return matches


def _load_run_rows(summary_paths: list[Path]) -> list[dict[str, Any]]:
    """Load per-run summary/metadata files into normalized method-level rows."""
    rows: list[dict[str, Any]] = []
    for summary_path in summary_paths:
        run_dir = summary_path.parent
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
        scenario = metadata.get("scenario", {})
        scenario_id = str(scenario.get("scenario_id", ""))
        design = str(scenario.get("design", ""))
        run_id = str(metadata.get("run_id", run_dir.name))
        terminal = summary.get("job_terminal_throughput", {})
        terminal_jobs = int(terminal.get("unique_terminal_jobs", 0))
        terminal_tps = float(terminal.get("throughput_rps", 0.0))

        for method_entry in summary.get("methods", []):
            method = str(method_entry.get("method", ""))
            grpc_rates = method_entry.get("grpc_code_rates", {}) or {}
            row = {
                "design": design,
                "scenario_id": scenario_id,
                "run_id": run_id,
                "method": method,
                "total_calls": int(method_entry.get("total_calls", 0)),
                "ok_calls": int(method_entry.get("ok_calls", 0)),
                "throughput_rps": float(method_entry.get("throughput_rps", 0.0)),
                "latency_p50_ms": float(method_entry.get("latency_ms", {}).get("p50", 0.0)),
                "latency_p95_ms": float(method_entry.get("latency_ms", {}).get("p95", 0.0)),
                "latency_p99_ms": float(method_entry.get("latency_ms", {}).get("p99", 0.0)),
                "grpc_non_ok_rate": _non_ok_rate(grpc_rates),
                "terminal_jobs": terminal_jobs,
                "terminal_throughput_rps": terminal_tps,
            }
            rows.append(row)
    return rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """Write aggregate tables to CSV with deterministic headers and ordering."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _aggregate_by_scenario_design_method(run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate run rows by scenario, design, and RPC method."""
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in run_rows:
        key = (row["scenario_id"], row["design"], row["method"])
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for (scenario_id, design, method), rows in grouped.items():
        values_tps = [float(item["throughput_rps"]) for item in rows]
        values_p95 = [float(item["latency_p95_ms"]) for item in rows]
        values_non_ok = [float(item["grpc_non_ok_rate"]) for item in rows]
        output.append(
            {
                "scenario_id": scenario_id,
                "design": design,
                "method": method,
                "run_count": len(rows),
                "throughput_rps_mean": _round(_safe_mean(values_tps)),
                "throughput_rps_std": _round(_safe_std(values_tps)),
                "latency_p95_ms_mean": _round(_safe_mean(values_p95)),
                "latency_p95_ms_std": _round(_safe_std(values_p95)),
                "grpc_non_ok_rate_mean": _round(_safe_mean(values_non_ok)),
                "grpc_non_ok_rate_std": _round(_safe_std(values_non_ok)),
            }
        )
    output.sort(key=lambda row: (_scenario_sort_key(row["scenario_id"]), row["design"], row["method"]))
    return output


def _aggregate_terminal_by_scenario_design(run_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate terminal-job throughput metrics by scenario and design."""
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in run_rows:
        method = str(row["method"])
        if method != "SubmitJob":
            continue
        key = (str(row["scenario_id"]), str(row["design"]), str(row["run_id"]))
        grouped[key] = {
            "scenario_id": str(row["scenario_id"]),
            "design": str(row["design"]),
            "run_id": str(row["run_id"]),
            "terminal_jobs": int(row["terminal_jobs"]),
            "terminal_throughput_rps": float(row["terminal_throughput_rps"]),
        }

    grouped2: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for entry in grouped.values():
        grouped2[(entry["scenario_id"], entry["design"])].append(entry)

    output: list[dict[str, Any]] = []
    for (scenario_id, design), entries in grouped2.items():
        throughput_values = [float(item["terminal_throughput_rps"]) for item in entries]
        terminal_values = [float(item["terminal_jobs"]) for item in entries]
        output.append(
            {
                "scenario_id": scenario_id,
                "design": design,
                "run_count": len(entries),
                "terminal_jobs_mean": _round(_safe_mean(terminal_values)),
                "terminal_jobs_std": _round(_safe_std(terminal_values)),
                "terminal_throughput_rps_mean": _round(_safe_mean(throughput_values)),
                "terminal_throughput_rps_std": _round(_safe_std(throughput_values)),
                "terminal_throughput_cv": _round(_safe_cv(throughput_values)),
            }
        )
    output.sort(key=lambda row: (_scenario_sort_key(row["scenario_id"]), row["design"]))
    return output


def _ab_delta_table(method_agg_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute primary-method A vs B delta table for throughput and p95 latency."""
    bucket: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in method_agg_rows:
        scenario_id = _scenario_core(str(row["scenario_id"]))
        method = str(row["method"])
        design = str(row["design"])
        bucket[(scenario_id, method)][design] = row

    output: list[dict[str, Any]] = []
    for (scenario_id, method), mapping in bucket.items():
        if method not in PRIMARY_METHODS:
            continue
        a = mapping.get("A_microservices")
        b = mapping.get("B_monolith")
        if not a or not b:
            continue
        a_tps = float(a["throughput_rps_mean"])
        b_tps = float(b["throughput_rps_mean"])
        a_p95 = float(a["latency_p95_ms_mean"])
        b_p95 = float(b["latency_p95_ms_mean"])
        output.append(
            {
                "scenario_id": scenario_id,
                "method": method,
                "a_throughput_rps_mean": _round(a_tps),
                "b_throughput_rps_mean": _round(b_tps),
                "throughput_delta_b_minus_a_rps": _round(b_tps - a_tps),
                "a_latency_p95_ms_mean": _round(a_p95),
                "b_latency_p95_ms_mean": _round(b_p95),
                "latency_p95_delta_b_minus_a_ms": _round(b_p95 - a_p95),
                "a_non_ok_rate_mean": _round(float(a["grpc_non_ok_rate_mean"])),
                "b_non_ok_rate_mean": _round(float(b["grpc_non_ok_rate_mean"])),
            }
        )
    output.sort(key=lambda row: (_scenario_sort_key(row["scenario_id"]), row["method"]))
    return output


def _write_markdown_summary(
    output_path: Path,
    *,
    run_rows: list[dict[str, Any]],
    method_agg_rows: list[dict[str, Any]],
    terminal_rows: list[dict[str, Any]],
) -> None:
    """Write a human-readable starter-matrix summary with global rollups."""
    design_run_dirs: dict[str, set[str]] = defaultdict(set)
    for row in run_rows:
        design_run_dirs[str(row["design"])].add(str(row["run_id"]))

    global_by_design_method: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in method_agg_rows:
        method = str(row["method"])
        if method in PRIMARY_METHODS:
            global_by_design_method[(str(row["design"]), method)].append(row)

    lines: list[str] = []
    lines.append("# Starter Matrix Aggregate Summary")
    lines.append("")
    lines.append("## Run Coverage")
    lines.append("")
    for design in DESIGN_ORDER:
        runs = sorted(design_run_dirs.get(design, set()))
        lines.append(f"- {design}: {len(runs)} run IDs")
    lines.append("")

    lines.append("## Global Method Averages (across all starter scenarios)")
    lines.append("")
    lines.append("| design | method | mean throughput_rps | mean p95_ms | mean non_ok_rate |")
    lines.append("|---|---|---:|---:|---:|")
    for design in DESIGN_ORDER:
        for method in PRIMARY_METHODS:
            rows = global_by_design_method.get((design, method), [])
            lines.append(
                "| "
                + " | ".join(
                    [
                        design,
                        method,
                        f"{_safe_mean([float(r['throughput_rps_mean']) for r in rows]):.6f}",
                        f"{_safe_mean([float(r['latency_p95_ms_mean']) for r in rows]):.6f}",
                        f"{_safe_mean([float(r['grpc_non_ok_rate_mean']) for r in rows]):.6f}",
                    ]
                )
                + " |"
            )
    lines.append("")

    lines.append("## Global Terminal Throughput Averages")
    lines.append("")
    lines.append("| design | mean terminal throughput_rps | mean terminal throughput cv |")
    lines.append("|---|---:|---:|")
    by_design_terminal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in terminal_rows:
        by_design_terminal[str(row["design"])].append(row)
    for design in DESIGN_ORDER:
        rows = by_design_terminal.get(design, [])
        lines.append(
            "| "
            + " | ".join(
                [
                    design,
                    f"{_safe_mean([float(r['terminal_throughput_rps_mean']) for r in rows]):.6f}",
                    f"{_safe_mean([float(r['terminal_throughput_cv']) for r in rows]):.6f}",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("Generated by `scripts/loadgen/aggregate_starter_matrix.py`.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_plots(
    output_dir: Path,
    *,
    method_agg_rows: list[dict[str, Any]],
    terminal_rows: list[dict[str, Any]],
) -> list[str]:
    """Render optional A/B comparison plots when matplotlib is available."""
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return []

    plot_paths: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) Mean p95 latency A vs B per scenario for each primary method.
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.6), constrained_layout=True)
    for idx, method in enumerate(PRIMARY_METHODS):
        ax = axes[idx // 2][idx % 2]
        scenarios: list[str] = []
        values_a: list[float] = []
        values_b: list[float] = []
        for scenario in SCENARIO_PLOT_ORDER:
            a_sid = f"design_a_{scenario}"
            b_sid = f"design_b_{scenario}"
            a_row = next(
                (
                    row
                    for row in method_agg_rows
                    if row["scenario_id"] == a_sid
                    and row["design"] == "A_microservices"
                    and row["method"] == method
                ),
                None,
            )
            b_row = next(
                (
                    row
                    for row in method_agg_rows
                    if row["scenario_id"] == b_sid
                    and row["design"] == "B_monolith"
                    and row["method"] == method
                ),
                None,
            )
            if not a_row or not b_row:
                continue
            scenarios.append(scenario)
            values_a.append(float(a_row["latency_p95_ms_mean"]))
            values_b.append(float(b_row["latency_p95_ms_mean"]))

        x = list(range(len(scenarios)))
        width = 0.4
        ax.bar([p - width / 2 for p in x], values_a, width=width, label="A_microservices")
        ax.bar([p + width / 2 for p in x], values_b, width=width, label="B_monolith")
        ax.set_title(method, fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels([SCENARIO_REPORT_IDS[s] for s in scenarios], rotation=0)
        if idx % 2 == 0:
            ax.set_ylabel("p95 latency (ms)", fontsize=12)
        ax.tick_params(axis="both", labelsize=11)
    handles, labels = axes[0][0].get_legend_handles_labels()
    if handles and labels:
        axes[0][0].legend(handles, labels, loc="upper left", fontsize=11)
    p1 = output_dir / "ab_p95_latency_primary_methods.png"
    fig.savefig(p1, dpi=300, bbox_inches="tight")
    plt.close(fig)
    plot_paths.append(str(p1))

    # 2) Terminal throughput mean per scenario (A vs B).
    fig2, ax2 = plt.subplots(figsize=(7.2, 3.2), constrained_layout=True)
    scenarios2: list[str] = []
    values2_a: list[float] = []
    values2_b: list[float] = []
    for scenario in SCENARIO_PLOT_ORDER:
        a_sid = f"design_a_{scenario}"
        b_sid = f"design_b_{scenario}"
        a_row = next(
            (
                row
                for row in terminal_rows
                if row["scenario_id"] == a_sid and row["design"] == "A_microservices"
            ),
            None,
        )
        b_row = next(
            (
                row
                for row in terminal_rows
                if row["scenario_id"] == b_sid and row["design"] == "B_monolith"
            ),
            None,
        )
        if not a_row or not b_row:
            continue
        scenarios2.append(scenario)
        values2_a.append(float(a_row["terminal_throughput_rps_mean"]))
        values2_b.append(float(b_row["terminal_throughput_rps_mean"]))

    x2 = list(range(len(scenarios2)))
    width2 = 0.4
    ax2.bar([p - width2 / 2 for p in x2], values2_a, width=width2, label="A_microservices")
    ax2.bar([p + width2 / 2 for p in x2], values2_b, width=width2, label="B_monolith")
    ax2.set_ylabel("jobs/s", fontsize=12)
    ax2.set_xlabel("Scenario", fontsize=12)
    ax2.set_xticks(x2)
    ax2.set_xticklabels([SCENARIO_REPORT_IDS[s] for s in scenarios2], rotation=0)
    ax2.tick_params(axis="both", labelsize=11)
    ax2.legend(fontsize=11)
    p2 = output_dir / "ab_terminal_throughput_by_scenario.png"
    fig2.savefig(p2, dpi=300, bbox_inches="tight")
    plt.close(fig2)
    plot_paths.append(str(p2))
    return plot_paths


def main() -> int:
    """Build starter-matrix aggregate artifacts (CSV, markdown, optional plots) from run outputs."""
    args = parse_args()
    results_root = Path(args.results_root)
    output_dir = Path(args.output_dir)
    plot_dir = output_dir / "plots"

    summary_paths = _iter_run_summary_files(results_root)
    if not summary_paths:
        print(
            json.dumps(
                {
                    "error": "no starter-matrix summaries found",
                    "results_root": str(results_root),
                },
                indent=2,
            )
        )
        return 1

    run_rows = _load_run_rows(summary_paths)
    method_agg_rows = _aggregate_by_scenario_design_method(run_rows)
    terminal_rows = _aggregate_terminal_by_scenario_design(run_rows)
    ab_rows = _ab_delta_table(method_agg_rows)

    raw_rows_csv = output_dir / "starter_matrix_run_method_rows.csv"
    method_agg_csv = output_dir / "starter_matrix_method_agg.csv"
    terminal_csv = output_dir / "starter_matrix_terminal_agg.csv"
    ab_csv = output_dir / "starter_matrix_ab_delta_primary.csv"
    md_path = output_dir / "starter_matrix_summary.md"

    _write_csv(
        raw_rows_csv,
        [
            "design",
            "scenario_id",
            "run_id",
            "method",
            "total_calls",
            "ok_calls",
            "throughput_rps",
            "latency_p50_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "grpc_non_ok_rate",
            "terminal_jobs",
            "terminal_throughput_rps",
        ],
        run_rows,
    )
    _write_csv(
        method_agg_csv,
        [
            "scenario_id",
            "design",
            "method",
            "run_count",
            "throughput_rps_mean",
            "throughput_rps_std",
            "latency_p95_ms_mean",
            "latency_p95_ms_std",
            "grpc_non_ok_rate_mean",
            "grpc_non_ok_rate_std",
        ],
        method_agg_rows,
    )
    _write_csv(
        terminal_csv,
        [
            "scenario_id",
            "design",
            "run_count",
            "terminal_jobs_mean",
            "terminal_jobs_std",
            "terminal_throughput_rps_mean",
            "terminal_throughput_rps_std",
            "terminal_throughput_cv",
        ],
        terminal_rows,
    )
    _write_csv(
        ab_csv,
        [
            "scenario_id",
            "method",
            "a_throughput_rps_mean",
            "b_throughput_rps_mean",
            "throughput_delta_b_minus_a_rps",
            "a_latency_p95_ms_mean",
            "b_latency_p95_ms_mean",
            "latency_p95_delta_b_minus_a_ms",
            "a_non_ok_rate_mean",
            "b_non_ok_rate_mean",
        ],
        ab_rows,
    )
    _write_markdown_summary(md_path, run_rows=run_rows, method_agg_rows=method_agg_rows, terminal_rows=terminal_rows)
    plots = _write_plots(plot_dir, method_agg_rows=method_agg_rows, terminal_rows=terminal_rows)

    print(
        json.dumps(
            {
                "summary_count": len(summary_paths),
                "run_method_rows": len(run_rows),
                "method_agg_rows": len(method_agg_rows),
                "terminal_agg_rows": len(terminal_rows),
                "ab_delta_rows": len(ab_rows),
                "outputs": {
                    "raw_rows_csv": str(raw_rows_csv),
                    "method_agg_csv": str(method_agg_csv),
                    "terminal_agg_csv": str(terminal_csv),
                    "ab_delta_csv": str(ab_csv),
                    "summary_md": str(md_path),
                    "plots": plots,
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
