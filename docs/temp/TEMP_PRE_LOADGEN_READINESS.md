# TEMP: Pre-Loadgen Readiness Checklist

**Status:** Temporary planning artifact  
**Owner:** Joe + Codex  
**Created:** 2026-02-19
**Last updated:** 2026-02-20

## Temporary File Notice

This file is intentionally temporary and should be removed after load-generator implementation and benchmark protocol stabilization.

Removal trigger:
- Load generator is implemented, validated for both Design A and Design B, and benchmark runs are reproducible from canonical docs.

Then delete:
- `docs/temp/TEMP_PRE_LOADGEN_READINESS.md`

Trigger status (2026-02-20):
- Trigger is now satisfied.
- File retained only until the dedicated strict-cleanup task executes.

## Purpose

Track remaining prerequisites between current Design B routing correctness and full benchmark execution (throughput/latency/fairness runs).

## Exit Criteria (Ready to Build Load Generator)

- [x] A reusable client-routing library exists for Design B and is used by integration/benchmark client code.
- [x] Routing behavior is fully covered:
  - [x] `SubmitJob` with empty `client_request_id` uses round-robin.
  - [x] `SubmitJob` with non-empty `client_request_id` uses deterministic owner routing.
  - [x] `GetJobStatus` / `GetJobResult` / `CancelJob` route by `job_id` owner.
- [x] Routing node-order source is explicit and shared (single config surface; no duplicate hardcoded order lists).
- [x] Scenario config format exists for workload matrix (concurrency, mix, durations, run windows, seeds).
- [x] Benchmark output schema is defined and machine-readable.
- [x] A runner workflow exists for warm-up -> measure -> cool-down -> repeat.
- [x] Design A and Design B parity checks are executable and documented.

## Workstreams Before Loadgen

## 1) Client Routing Library (Design B)

- [x] Create importable module in `common/` for client-side routing policy.
- [x] Keep deterministic hash implementation centralized (reuse existing owner-routing helper).
- [x] Add unit tests for:
  - [x] deterministic owner mapping repeatability,
  - [x] round-robin progression behavior,
  - [x] edge conditions (node list changes, empty key handling).

Definition of done:
- All Design B client-facing scripts/tests that need routing import this module instead of re-implementing logic.

## 2) Benchmark Scenario Specification

- [x] Add a scenario definition artifact (likely under `docs/spec/` and/or config file under `scripts/` or `tests/`).
- [x] Encode locked fairness controls from `docs/spec/fairness-evaluation.md`:
  - [x] identical total worker slots,
  - [x] consistent deadlines/retries,
  - [x] fixed warm-up/measurement windows,
  - [x] same request mix and pacing model.
- [x] Define minimum scenario matrix:
  - [x] low, medium, high load,
  - [x] submit-heavy, poll-heavy, balanced profiles.

Definition of done:
- Scenario settings can be consumed programmatically by load generator and runner.

## 3) Metrics and Output Contract

- [x] Define output rows to include at least:
  - [x] design, scenario_id, run_id, method,
  - [x] start_ts_ms, latency_ms, grpc_code,
  - [x] accepted/result_ready/already_terminal where applicable,
  - [x] concurrency, work_duration_ms, request_mix_profile, total_worker_slots.
- [x] Define summary outputs:
  - [x] per-method throughput,
  - [x] p50/p95/p99 latency,
  - [x] error-rate by grpc code,
  - [x] job terminal throughput.

Definition of done:
- One run produces parseable artifacts suitable for A/B comparison scripts.

## 4) Runner and Reproducibility

- [x] Add run wrapper that orchestrates:
  - [x] stack health precheck,
  - [x] warm-up traffic (not recorded),
  - [x] measurement window (recorded),
  - [x] cool-down handling,
  - [x] repeated runs with stable naming.
- [x] Add reproducibility controls:
  - [x] explicit random seed,
  - [x] fixed timeout/deadline defaults,
  - [x] run metadata capture,
  - [x] deterministic run-directory collision safety (`fail-if-exists` default + explicit `--overwrite`).

Definition of done:
- Repeated runs are easy to execute and compare with minimal manual steps.

Progress note:
- Minimal artifact safety is now implemented: deterministic run directories are protected by default and only replaced when `--overwrite` is provided.

## Benchmark Execution Snapshot (2026-02-20)

Execution scope completed in this session:
- Full starter matrix completed for both designs (`low/medium/high` x `submit_heavy/poll_heavy/balanced`) with `3` deterministic repetitions per scenario.
- Total run directories: `54` (`27` per design).
- Artifact completeness confirmed:
  - `rows.jsonl`, `rows.csv`, `summary.json`, `summary.csv`, `metadata.json` present for all runs.
- Consolidated tables and plots generated:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/`
- Command trace captured:
  - `results/loadgen/starter_matrix_execution_2026-02-20.log`

Residual temporary-file relevance:
- None from execution readiness standpoint.
- Remaining action is removal in the dedicated strict-cleanup task.

## 5) Pre-Benchmark Gate

- [x] Confirm required unit and smoke tests pass for current baseline.
- [x] Confirm Design B routing smoke passes with deterministic evidence.
- [x] Confirm documentation includes benchmark run commands and artifact locations.

Definition of done:
- Team can start load-generator implementation with clear acceptance targets.

## Post-Validation Cleanup Plan (Repository Tidiness)

Execute only after both conditions are true:
1. Design B routing path is validated and stable.
2. Load generator is implemented and validated for benchmark workflow.

Cleanup candidates:
- `docs/temp/TEMP_PRE_LOADGEN_READINESS.md` (this file)
- `scripts/legacy_smoke/` legacy scripts no longer needed for current validation path
- Deprecated top-level compatibility wrappers (strict cleanup target):
  - `scripts/smoke_*_behavior.py`
  - `scripts/smoke_*_skeleton.py`
  - `scripts/smoke_live_stack.py`
  - `scripts/smoke_integration_terminal_path.py`
  - `scripts/smoke_integration_failure_path.py`
  - `scripts/manual_gateway_client.py`
  - `scripts/healthcheck.py`

Cleanup checklist:
- [ ] Verify no canonical docs reference legacy smoke paths.
- [ ] Verify no CI/local validation commands depend on legacy smoke scripts.
- [ ] Verify no CI/local validation commands depend on deprecated top-level compatibility wrappers.
- [ ] Remove legacy files and deprecated wrappers in one focused cleanup change set with doc index updates.
- [ ] Remove this temp file in that same cleanup/docs-sync change set.
