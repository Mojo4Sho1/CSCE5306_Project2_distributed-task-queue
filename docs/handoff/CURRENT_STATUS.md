# Current Status

**Last updated:** 2026-02-20  
**Owner:** Joe + Codex

## Current focus

Full starter fairness matrix execution and consolidation for Design A vs Design B is complete.

## Completed in current focus

- Added full starter-matrix scenario configs (9 per design) under:
  - `scripts/loadgen/scenarios/starter_matrix/`
- Scenario coverage executed live with precheck and deterministic run IDs:
  - Design A:
    - `design_a_s_low_submit_heavy`
    - `design_a_s_low_poll_heavy`
    - `design_a_s_low_balanced`
    - `design_a_s_medium_submit_heavy`
    - `design_a_s_medium_poll_heavy`
    - `design_a_s_medium_balanced`
    - `design_a_s_high_submit_heavy`
    - `design_a_s_high_poll_heavy`
    - `design_a_s_high_balanced`
  - Design B:
    - `design_b_s_low_submit_heavy`
    - `design_b_s_low_poll_heavy`
    - `design_b_s_low_balanced`
    - `design_b_s_medium_submit_heavy`
    - `design_b_s_medium_poll_heavy`
    - `design_b_s_medium_balanced`
    - `design_b_s_high_submit_heavy`
    - `design_b_s_high_poll_heavy`
    - `design_b_s_high_balanced`
- Repetitions per scenario: `3` (deterministic `r00/r01/r02`).
- Total completed run directories: `54` (`27` per design).
- Full command trace captured in:
  - `results/loadgen/starter_matrix_execution_2026-02-20.log`
- Added aggregation pipeline:
  - `scripts/loadgen/aggregate_starter_matrix.py`
- Produced consolidated report outputs:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_run_method_rows.csv`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_method_agg.csv`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_terminal_agg.csv`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_ab_delta_primary.csv`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_summary.md`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/plots/ab_p95_latency_primary_methods.png`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/plots/ab_terminal_throughput_by_scenario.png`
- Updated notebook to consume consolidated artifacts:
  - `notebooks/benchmark_analysis.ipynb`

## Passing checks

- Baseline deterministic unit gate:
  - `TMPDIR=/tmp/codex-loadgen-matrix-<epoch> conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`
  - Result: `Ran 9 tests ... OK`
- Artifact completeness verification:
  - scenario dirs: `18`
  - run dirs: `54`
  - missing required files (`rows.jsonl/rows.csv/summary.json/summary.csv/metadata.json`): `0`
- Aggregation coverage:
  - `summary_count=54`
  - `run_method_rows=270`
  - `method_agg_rows=90`
  - `terminal_agg_rows=18`
  - `ab_delta_rows=36`

## Key benchmark signals (starter matrix aggregate)

- Primary-method throughput means are identical between designs in this harness slice (all deltas in `starter_matrix_ab_delta_primary.csv` are `0.0 rps`):
  - scheduler/request-rate pacing plus all-OK responses fixed method-level completed-call throughput.
- Primary-method p95 latency global means (ms):
  - `A_microservices`: Submit `35.600`, Status `32.146`, Result `33.511`, Cancel `33.202`
  - `B_monolith`: Submit `25.863`, Status `23.093`, Result `27.187`, Cancel `23.089`
- gRPC non-OK rates:
  - `0.0` across primary methods for both designs in this execution set.
- Terminal-job throughput global means (`summary.md` aggregate):
  - `A_microservices`: `2.470988 rps` (mean CV `0.241133`)
  - `B_monolith`: `5.343827 rps` (mean CV `0.021774`)

## Known gaps/blockers

- Live localhost probing/traffic in this remote MacBook session still required elevated execution due sandbox socket restrictions (`operation not permitted` without elevation).
- Matplotlib is not installed in conda env `grpc`; plots were generated with system Python (`MPLCONFIGDIR=/tmp/mplconfig`) while loadgen execution/testing remained in `grpc`.
- Throughput equality in primary-method tables is expected under fixed request-rate pacing and no error responses; interpret latency/terminal-throughput differences as the more informative signal for this run profile.
- External validity remains bounded to the locked starter matrix and this host environment.

## Next task (single target)

Execute strict post-matrix cleanup only:
- remove legacy/deprecated script surfaces,
- remove temporary readiness file,
- sync all indexes/docs to canonical paths.

## Definition of done for next task

- `scripts/legacy_smoke/` removed.
- Deprecated top-level compatibility wrappers removed:
  - `scripts/smoke_*_behavior.py`
  - `scripts/smoke_*_skeleton.py`
  - `scripts/smoke_live_stack.py`
  - `scripts/smoke_integration_terminal_path.py`
  - `scripts/smoke_integration_failure_path.py`
  - `scripts/manual_gateway_client.py`
  - `scripts/healthcheck.py`
- `docs/temp/TEMP_PRE_LOADGEN_READINESS.md` removed.
- `README.md`, `docs/_INDEX.md`, `scripts/_SCRIPT_INDEX.md`, and handoff docs updated in the same cleanup change set.
