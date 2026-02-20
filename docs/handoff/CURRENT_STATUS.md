# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Loadgen run-output collision safety (`fail-if-exists` default + explicit `--overwrite`) is completed.

## Completed in current focus

- Updated `common/loadgen_contracts.py`:
  - `BenchmarkRunner.run(...)` now accepts `overwrite: bool = False`.
  - Added deterministic run-dir guard before phase execution.
  - Default behavior raises `FileExistsError` when deterministic run directory already exists.
  - `overwrite=True` removes existing run directory and replaces artifacts intentionally.
- Updated `scripts/loadgen/run_benchmark_scaffold.py`:
  - Added CLI flag `--overwrite`.
  - Added structured fail-fast collision error output and explicit non-zero exit path.
- Expanded deterministic tests in `tests/test_loadgen_contracts.py`:
  - `test_run_dir_collision_fails_by_default`.
  - `test_run_dir_collision_overwrite_replaces_artifacts`.
- Updated operator-facing documentation:
  - `README.md`
  - `scripts/_SCRIPT_INDEX.md`
  - `tests/_TEST_INDEX.md`
  - `docs/spec/fairness-evaluation.md`
  - `docs/spec/runtime-config-design-a.md`
  - `docs/spec/runtime-config-design-b.md`
  - `docs/temp/TEMP_PRE_LOADGEN_READINESS.md`
  - `docs/handoff/NEXT_TASK.md`

## Passing checks

- Run timestamp anchor: `2026-02-19 18:49:14 -0600`.
- `conda run -n grpc python -m py_compile common/loadgen_contracts.py scripts/loadgen/run_benchmark_scaffold.py tests/test_loadgen_contracts.py`: PASS
- `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`: PASS
  - `Ran 9 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`: PASS
  - `Ran 6 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`: PASS
  - `Ran 3 tests ... OK`
- CLI deterministic collision behavior checks:
  - `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario /tmp/loadgen_collision_scenario.json --output-dir /tmp/loadgen-collision-cli`: PASS
  - re-run same command without `--overwrite`: PASS (expected fail-fast) with exit code `3` and structured collision error
  - re-run with `--overwrite`: PASS (intentional replacement succeeds)

## Known gaps/blockers

- Integration smoke commands requiring live localhost gRPC connectivity are blocked in this sandbox (`Operation not permitted` on connect to `127.0.0.1:*`):
  - `tests/integration/smoke_live_stack.py`
  - `tests/integration/smoke_integration_terminal_path.py`
  - `tests/integration/smoke_integration_failure_path.py`
  - `tests/integration/smoke_design_b_owner_routing.py`
- This is an environment/network-execution limitation, not a functional blocker in the loadgen collision-safety change set.

## Next task (single target)

Execute and document a small multi-seed benchmark matrix using the current loadgen scaffold for both designs, with reproducible artifact capture and report-ready summary tables.

## Definition of done for next task

- At least one balanced live scenario is run for Design A and Design B with multiple seeds.
- Output artifacts are captured under `results/loadgen/` with clear scenario/run metadata.
- A concise report-ready summary (throughput + latency + error rates + terminal throughput) is produced from generated artifacts.
- Documentation/runbook notes are updated for reproducible reruns (including `--precheck-health` and `--overwrite` usage boundaries).
- Handoff docs capture exact commands, outcomes, and any residual fairness caveats.
