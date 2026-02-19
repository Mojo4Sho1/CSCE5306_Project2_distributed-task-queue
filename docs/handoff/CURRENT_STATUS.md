# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Pre-loadgen benchmark contract scaffold: scenario schema/loader, runner phase control flow, output row schema/writers, and Design B router wiring.

## Completed in current focus

- Added loadgen contract scaffold module:
  - `common/loadgen_contracts.py`
  - includes:
    - `BenchmarkScenario` machine-readable schema + validation,
    - `BenchmarkRunner` warm-up -> measure -> cool-down -> repeat flow,
    - deterministic stable run ID generation,
    - `BenchmarkRow` schema aligned to fairness Section 11 fields,
    - JSONL + CSV artifact writers,
    - Design B routing integration through `DesignBClientRouter`.
- Added loadgen scaffold CLI:
  - `scripts/loadgen/run_benchmark_scaffold.py`
  - loads scenario config and writes per-run artifacts to `results/loadgen/...`.
- Added canonical Design B scenario artifact:
  - `scripts/loadgen/scenarios/design_b_balanced_baseline.json`
  - includes locked fairness controls: concurrency, request mix, warm-up/measure/cool-down windows, repetitions, run seed, and `total_worker_slots=6`.
- Added deterministic non-live tests:
  - `tests/test_loadgen_contracts.py`
  - verifies scenario parsing/validation + Design B router path,
  - verifies output serialization and per-run artifact writing.
- Updated documentation/indexes:
  - `README.md`,
  - `docs/spec/fairness-evaluation.md`,
  - `docs/spec/runtime-config-design-b.md`,
  - `tests/_TEST_INDEX.md`,
  - `scripts/_SCRIPT_INDEX.md`.

## Passing checks

- Run timestamp anchor: `2026-02-19 15:03:28 -06:00`.
- `conda run -n grpc python -m py_compile common/loadgen_contracts.py scripts/loadgen/run_benchmark_scaffold.py tests/test_loadgen_contracts.py`: PASS
- `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`: PASS
  - `Ran 2 tests ... OK`
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
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_baseline.json --output-dir results/loadgen`: PASS
  - produced 3 run directories with deterministic run IDs and parseable `rows.jsonl`, `rows.csv`, `metadata.json`.

## Known gaps/blockers

- No functional blocker for this scaffold milestone.
- Runner is intentionally pre-traffic: measurement rows are empty unless `operation_hook` is provided by future load-generation logic.
- Summary aggregations (percentile/throughput/error-rate tables) are not yet implemented.

## Timing/race observations

- First attempt of scaffold CLI verification timed out due scenario durations (`10s + 30s + 5s`, repeated 3 times); reran with extended command timeout and verified PASS.

## Next task (single target)

Implement live benchmark traffic execution on top of scaffold contracts (request scheduling + RPC execution + retry/deadline controls + summary aggregations).

## Definition of done for next task

- Implement live RPC operation engine for primary parity methods (`SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`) using scenario request-mix controls.
- Preserve locked retry/deadline semantics from `docs/spec/error-idempotency.md` and `docs/spec/constants.md`.
- Populate measurement rows during measure window with real call outcomes (grpc code + soft outcome fields).
- Add summary artifact generation (per-method throughput, p50/p95/p99 latency, grpc-code error rates) per fairness spec Section 11.
- Add deterministic unit tests for scheduler/mix logic and at least one non-live integration-style test with mocked RPC client adapter.
- Update docs/spec + handoff docs with commands, assumptions, and residual risks.
