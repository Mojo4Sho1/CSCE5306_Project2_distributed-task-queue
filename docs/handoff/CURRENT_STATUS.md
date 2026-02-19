# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Live benchmark traffic execution on top of loadgen scaffold contracts (scheduler + RPC execution + retry/deadline policy + summary artifacts).

## Completed in current focus

- Extended loadgen contract/runtime module:
  - `common/loadgen_contracts.py`
  - includes:
    - `RequestMixScheduler` deterministic weighted operation selection,
    - `LiveTrafficEngine` concurrency/pacing phase runner,
    - `GrpcPublicApiAdapter` parity-method RPC execution (`SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`, optional `ListJobs`),
    - locked retry/deadline behavior in benchmark client path:
      - retryable codes: `UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`,
      - full-jitter exponential backoff with locked constants,
      - `SubmitJob` auto-retry only when non-empty `client_request_id`,
    - summary artifact generation:
      - per-method throughput,
      - p50/p95/p99 latency,
      - grpc-code rate table.
- Extended runner artifacts:
  - per run now writes:
    - `rows.jsonl`,
    - `rows.csv`,
    - `summary.json`,
    - `summary.csv`,
    - `metadata.json` (includes summary + per-phase row counts).
- Updated loadgen CLI:
  - `scripts/loadgen/run_benchmark_scaffold.py`
  - added:
    - `--live-traffic`,
    - optional `--request-rate-rps` override.
- Updated canonical Design B scenario:
  - `scripts/loadgen/scenarios/design_b_balanced_baseline.json`
  - set `ListJobs=0` for primary parity runs and added `request_rate_rps`.
- Added short live smoke scenario artifact:
  - `scripts/loadgen/scenarios/design_a_live_smoke_short.json`.
- Expanded deterministic test coverage:
  - `tests/test_loadgen_contracts.py`
  - now verifies:
    - scheduler distribution,
    - live phase row production via mocked adapter,
    - retry policy behavior for submit idempotency-key mode,
    - serialization/artifact path outputs.
- Updated docs/indexes:
  - `README.md`,
  - `docs/spec/fairness-evaluation.md`,
  - `docs/spec/runtime-config-design-b.md`,
  - `tests/_TEST_INDEX.md`,
  - `scripts/_SCRIPT_INDEX.md`,
  - `docs/temp/TEMP_PRE_LOADGEN_READINESS.md`,
  - `docs/handoff/NEXT_TASK.md`.

## Passing checks

- Run timestamp anchor: `2026-02-19 15:56:52 -06:00`.
- `conda run -n grpc python -m py_compile common/loadgen_contracts.py scripts/loadgen/run_benchmark_scaffold.py tests/test_loadgen_contracts.py`: PASS
- `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`: PASS
  - `Ran 5 tests ... OK`
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
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic`: PASS
  - produced run:
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/rows.jsonl`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/rows.csv`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/summary.json`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/summary.csv`,
    - `results/loadgen/design_a_live_smoke_short/design_a_live_smoke_short-r00-64f99fd582/metadata.json`.

## Known gaps/blockers

- No functional blocker for live benchmark traffic path.
- `summary` currently reports near-zero/zero latency values in very short local smoke runs due millisecond resolution and low local loopback latency; acceptable for contract correctness but should be refined before report-quality runs.
- Loadgen CLI does not yet enforce stack health precheck before run start.
- Job-terminal throughput summary metric is still not emitted in summary artifacts.
- Re-running the same scenario/repetition in the same output directory overwrites prior artifacts because run IDs are deterministic by `(scenario_id, run_seed, repeat_index)`.

## Timing/race observations

- First write of `design_a_live_smoke_short.json` used UTF-8 BOM and failed JSON parse (`JSONDecodeError: Unexpected UTF-8 BOM`); rewritten in ASCII and rerun PASS.
- Running scaffold mode and live mode with identical scenario/run tuple in the same output dir re-used the same deterministic run ID and replaced prior files; reran live command to restore live artifact evidence.

## Next task (single target)

Harden loadgen for report-quality execution: add CLI precheck gate, job-terminal throughput summary metric, and latency precision refinement.

## Definition of done for next task

- CLI supports optional pre-run health validation for design targets and fails fast on unhealthy state.
- Summary artifacts add job-terminal throughput metric.
- Latency summary path avoids degenerate all-zero output for short live smoke runs.
- Existing unit/integration baseline remains green.
