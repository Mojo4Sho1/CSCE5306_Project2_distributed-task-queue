# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Loadgen report-quality hardening (pre-run health gate + terminal-throughput summary + latency precision).

## Completed in current focus

- Hardened loadgen contracts/runtime:
  - `common/loadgen_contracts.py`
  - includes:
    - optional stack target health validation helper (`validate_stack_health_targets`) for design ingress targets,
    - `BenchmarkRow.latency_ms` precision promotion to floating-point milliseconds,
    - latency capture floor for observed calls (`0.001 ms`) to avoid degenerate zero-only local summaries,
    - terminal-status detection for status/result/cancel responses (`job_terminal`),
    - top-level summary metric:
      - `job_terminal_throughput.unique_terminal_jobs`,
      - `job_terminal_throughput.throughput_rps`,
    - summary CSV columns for terminal-throughput parity with JSON:
      - `job_terminal_unique_jobs`,
      - `job_terminal_throughput_rps`.
- Hardened loadgen CLI:
  - `scripts/loadgen/run_benchmark_scaffold.py`
  - added:
    - `--precheck-health`,
    - `--precheck-timeout-ms`,
    - fail-fast unhealthy precheck exit (`2`) with structured stderr JSON.
- Expanded deterministic tests:
  - `tests/test_loadgen_contracts.py`
  - added coverage for:
    - latency precision + terminal-throughput summary,
    - precheck unhealthy-target detection.
- Updated docs/indexes/checklists:
  - `README.md`
  - `docs/spec/fairness-evaluation.md`
  - `docs/spec/runtime-config-design-a.md`
  - `docs/spec/runtime-config-design-b.md`
  - `scripts/_SCRIPT_INDEX.md`
  - `tests/_TEST_INDEX.md`
  - `docs/temp/TEMP_PRE_LOADGEN_READINESS.md`
  - `docs/handoff/NEXT_TASK.md`

## Passing checks

- Run timestamp anchor: `2026-02-19 16:47:57 -06:00`.
- `conda run -n grpc python -m py_compile common/loadgen_contracts.py scripts/loadgen/run_benchmark_scaffold.py tests/test_loadgen_contracts.py`: PASS
- `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`: PASS
  - `Ran 7 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`: PASS
  - `Ran 6 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`: PASS
  - `Ran 3 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_owner_routing.py`: PASS
  - `Ran 3 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_design_b_client_routing.py`: PASS
  - `Ran 6 tests ... OK`
- `docker compose -f docker/docker-compose.design-a.yml ps`: PASS
  - `gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `Up (... healthy)` during verification window.
- `docker compose -f docker/docker-compose.design-b.yml ps`: PASS
  - `monolith-1..monolith-6` all `Up (... healthy)` during verification window.
- `conda run -n grpc python tests/integration/smoke_live_stack.py`: PASS
  - final `RESULT: PASS`
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`: PASS
  - final `RESULT: PASS`
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`: PASS
  - final `RESULT: PASS`
- `conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py`: PASS
  - final `RESULT: PASS`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic --precheck-health`: PASS
  - produced run:
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/rows.jsonl`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/rows.csv`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/summary.json`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/summary.csv`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/metadata.json`.
  - summary evidence:
    - `job_terminal_throughput.unique_terminal_jobs = 6`,
    - `job_terminal_throughput.throughput_rps = 3.0`,
    - non-degenerate live latency percentiles observed (for example `SubmitJob p50=0.001 ms`).

## Known gaps/blockers

- No functional blocker for report-quality baseline scope completed in this task.
- Re-running the same scenario/repetition in the same output directory still overwrites prior artifacts because run IDs are deterministic by `(scenario_id, run_seed, repeat_index)`.
- Precheck is connectivity-level (`TCP host:port`) and not deep service semantic health.

## Timing/race observations

- Running scaffold mode and live mode with identical scenario/run tuple in the same output directory still reuses the deterministic run ID and replaces prior files.

## Next task (single target)

Harden artifact reproducibility by preventing accidental overwrite on repeated identical scenario/repetition executions.

## Definition of done for next task

- Runner/CLI can preserve prior artifacts when deterministic run ID collisions occur (for example suffixing or explicit `--overwrite` policy).
- Collision behavior is explicit and documented.
- Existing unit/integration baseline remains green.
