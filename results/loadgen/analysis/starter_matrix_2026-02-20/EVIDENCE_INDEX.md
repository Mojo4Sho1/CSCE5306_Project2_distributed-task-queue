# Starter Matrix Evidence Index (2026-02-20)

**Last updated:** 2026-02-23  
**Scope:** canonical artifact index for the completed starter fairness matrix (Design A vs Design B).

## Canonical Entry Points

- Execution log (full run/aggregation chronology):
  - `results/loadgen/starter_matrix_execution_2026-02-20.log`
- Aggregate analysis directory (this dataset):
  - `results/loadgen/analysis/starter_matrix_2026-02-20/`
- Reproducibility runbook:
  - `docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md`
- Notebook entrypoint:
  - `notebooks/benchmark_analysis.ipynb`

## Per-Run Artifacts (Raw Benchmark Outputs)

Starter-matrix run outputs are stored under scenario/run directories:

- Root: `results/loadgen/`
- Pattern: `results/loadgen/<scenario_id>/<run_id>/`
- Per-run files:
  - `rows.jsonl`
  - `rows.csv`
  - `summary.json`
  - `summary.csv`
  - `metadata.json`

Representative scenario roots (full matrix contains A/B low/medium/high x submit_heavy/poll_heavy/balanced):

- `results/loadgen/design_a_s_low_submit_heavy/`
- `results/loadgen/design_a_s_medium_balanced/`
- `results/loadgen/design_a_s_high_poll_heavy/`
- `results/loadgen/design_b_s_low_submit_heavy/`
- `results/loadgen/design_b_s_medium_balanced/`
- `results/loadgen/design_b_s_high_poll_heavy/`

## Aggregate Outputs (Primary Report Inputs)

- Human-readable aggregate summary:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_summary.md`
- Method-level aggregate table:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_method_agg.csv`
- Terminal-throughput aggregate table:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_terminal_agg.csv`
- A-vs-B delta table for primary methods:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_ab_delta_primary.csv`
- Per-run method rows used for downstream slicing:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_run_method_rows.csv`

## Primary Plots

- P95 latency comparison (primary methods):
  - `results/loadgen/analysis/starter_matrix_2026-02-20/plots/ab_p95_latency_primary_methods.png`
- Terminal throughput by scenario:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/plots/ab_terminal_throughput_by_scenario.png`

## Headline Signals (Traceability Anchors)

From `starter_matrix_summary.md`:

- Run coverage:
  - `A_microservices`: 27 run IDs
  - `B_monolith`: 27 run IDs
- Global terminal throughput averages:
  - `A_microservices`: 2.470988 jobs/sec
  - `B_monolith`: 5.343827 jobs/sec

Use these only with the guardrails below.

## Interpretation Guardrails (Required for Report/Presentation)

1. Fixed-pacing caveat:
   - Starter scenarios are fixed offered-load profiles and do not establish absolute saturation ceilings for either design.
2. Environment-bounded external validity:
   - Results were produced in one concrete local environment and should be interpreted as bounded to this setup unless replicated elsewhere.
3. Locked interpretation controls from fairness spec (`docs/spec/fairness-evaluation.md`):
   - equal node count across designs (6 vs 6) for this starter matrix,
   - as-run effective worker-loop capacity differs for recorded runs (Design A: 1 loop, Design B: 6 loops),
   - primary parity conclusions are based on `SubmitJob/GetJobStatus/GetJobResult/CancelJob`,
   - starter primary scenarios use `ListJobs = 0%`,
   - deterministic owner routing is required in Design B for job-scoped operations,
   - fixed warmup/measure/cooldown windows and shared measurement logic are required.

## As-Run Capacity Note

The 2026-02-20 starter matrix should be interpreted as a comparison with equal node count but different effective execution capacity: Design A executed one worker loop while Design B executed six embedded worker loops. Any throughput/latency deltas should be read with that as-run capacity difference explicitly in scope.

## Consumption Rule

For report writing, cite this index first, then reference exact artifact paths above for every numeric claim or figure.
