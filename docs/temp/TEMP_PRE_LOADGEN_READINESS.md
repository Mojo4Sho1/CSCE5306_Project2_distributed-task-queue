# TEMP: Pre-Loadgen Readiness Checklist

**Status:** Temporary planning artifact  
**Owner:** Joe + Codex  
**Created:** 2026-02-19

## Temporary File Notice

This file is intentionally temporary and should be removed after load-generator implementation and benchmark protocol stabilization.

Removal trigger:
- Load generator is implemented, validated for both Design A and Design B, and benchmark runs are reproducible from canonical docs.

Then delete:
- `docs/temp/TEMP_PRE_LOADGEN_READINESS.md`

## Purpose

Track remaining prerequisites between current Design B routing correctness and full benchmark execution (throughput/latency/fairness runs).

## Exit Criteria (Ready to Build Load Generator)

- [ ] A reusable client-routing library exists for Design B and is used by integration/benchmark client code.
- [ ] Routing behavior is fully covered:
  - [ ] `SubmitJob` with empty `client_request_id` uses round-robin.
  - [ ] `SubmitJob` with non-empty `client_request_id` uses deterministic owner routing.
  - [ ] `GetJobStatus` / `GetJobResult` / `CancelJob` route by `job_id` owner.
- [ ] Routing node-order source is explicit and shared (single config surface; no duplicate hardcoded order lists).
- [ ] Scenario config format exists for workload matrix (concurrency, mix, durations, run windows, seeds).
- [ ] Benchmark output schema is defined and machine-readable.
- [ ] A runner workflow exists for warm-up -> measure -> cool-down -> repeat.
- [ ] Design A and Design B parity checks are executable and documented.

## Workstreams Before Loadgen

## 1) Client Routing Library (Design B)

- [ ] Create importable module in `common/` for client-side routing policy.
- [ ] Keep deterministic hash implementation centralized (reuse existing owner-routing helper).
- [ ] Add unit tests for:
  - [ ] deterministic owner mapping repeatability,
  - [ ] round-robin progression behavior,
  - [ ] edge conditions (node list changes, empty key handling).

Definition of done:
- All Design B client-facing scripts/tests that need routing import this module instead of re-implementing logic.

## 2) Benchmark Scenario Specification

- [ ] Add a scenario definition artifact (likely under `docs/spec/` and/or config file under `scripts/` or `tests/`).
- [ ] Encode locked fairness controls from `docs/spec/fairness-evaluation.md`:
  - [ ] identical total worker slots,
  - [ ] consistent deadlines/retries,
  - [ ] fixed warm-up/measurement windows,
  - [ ] same request mix and pacing model.
- [ ] Define minimum scenario matrix:
  - [ ] low, medium, high load,
  - [ ] submit-heavy, poll-heavy, balanced profiles.

Definition of done:
- Scenario settings can be consumed programmatically by load generator and runner.

## 3) Metrics and Output Contract

- [ ] Define output rows to include at least:
  - [ ] design, scenario_id, run_id, method,
  - [ ] start_ts_ms, latency_ms, grpc_code,
  - [ ] accepted/result_ready/already_terminal where applicable,
  - [ ] concurrency, work_duration_ms, request_mix_profile, total_worker_slots.
- [ ] Define summary outputs:
  - [ ] per-method throughput,
  - [ ] p50/p95/p99 latency,
  - [ ] error-rate by grpc code,
  - [ ] job terminal throughput.

Definition of done:
- One run produces parseable artifacts suitable for A/B comparison scripts.

## 4) Runner and Reproducibility

- [ ] Add run wrapper that orchestrates:
  - [ ] stack health precheck,
  - [ ] warm-up traffic (not recorded),
  - [ ] measurement window (recorded),
  - [ ] cool-down handling,
  - [ ] repeated runs with stable naming.
- [ ] Add reproducibility controls:
  - [ ] explicit random seed,
  - [ ] fixed timeout/deadline defaults,
  - [ ] run metadata capture.

Definition of done:
- Repeated runs are easy to execute and compare with minimal manual steps.

## 5) Pre-Benchmark Gate

- [ ] Confirm required unit and smoke tests pass for current baseline.
- [ ] Confirm Design B routing smoke passes with deterministic evidence.
- [ ] Confirm documentation includes benchmark run commands and artifact locations.

Definition of done:
- Team can start load-generator implementation with clear acceptance targets.

## Post-Validation Cleanup Plan (Repository Tidiness)

Execute only after both conditions are true:
1. Design B routing path is validated and stable.
2. Load generator is implemented and validated for benchmark workflow.

Cleanup candidates:
- `docs/temp/TEMP_PRE_LOADGEN_READINESS.md` (this file)
- `scripts/legacy_smoke/` legacy scripts no longer needed for current validation path

Cleanup checklist:
- [ ] Verify no canonical docs reference legacy smoke paths.
- [ ] Verify no CI/local validation commands depend on legacy smoke scripts.
- [ ] Remove legacy files in one focused cleanup change set with doc index updates.

