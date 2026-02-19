# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Harden loadgen benchmark execution for report-quality runs by adding pre-run stack health validation, method-level latency precision improvements, and job-terminal throughput aggregation.

## Why this task is next

- Live benchmark traffic execution is now implemented and verified:
  - deterministic mix scheduler + concurrency pacing,
  - parity-method RPC adapter (`SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`) with locked retry/deadline controls,
  - measure-window row capture,
  - per-method summary artifacts (throughput, p50/p95/p99 latency, grpc-code rates).
- Remaining gap for polished benchmark runs is operational guardrails and one missing summary metric from temporary readiness tracking (`job terminal throughput`).

## Scope (in)

- Add stack precheck option to benchmark CLI before run start:
  - Design A: gateway target health validation,
  - Design B: all ordered target health validation.
- Add job terminal throughput aggregation to summary artifacts.
- Improve latency precision handling to avoid all-zero latency artifacts in short/fast runs.
- Update docs/spec + handoff artifacts with final benchmark runbook expectations.

## Scope (out)

- Proto/schema changes.
- Service runtime behavior changes.
- Fairness lock modifications.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests.
- Keep design stacks healthy when running live benchmark checks.

## Acceptance criteria (definition of done)

- CLI can fail fast on unhealthy stack state when precheck is enabled.
- Summary artifacts include job-terminal throughput metric.
- Latency summaries show non-degenerate values for short live smoke scenarios.
- Existing baseline unit/integration suites remain green.

## Verification checklist

- [ ] Implement benchmark precheck mode in loadgen CLI.
- [ ] Add job-terminal throughput summary output.
- [ ] Improve latency precision in row/summary path.
- [ ] Re-run `tests/test_loadgen_contracts.py`.
- [ ] Re-run `tests/test_worker_report_retry.py`.
- [ ] Re-run `tests/test_coordinator_report_outcome_idempotency.py`.
- [ ] Re-run `tests/integration/smoke_live_stack.py`.
- [ ] Re-run `tests/integration/smoke_integration_terminal_path.py`.
- [ ] Re-run `tests/integration/smoke_integration_failure_path.py`.
- [ ] Re-run `tests/integration/smoke_design_b_owner_routing.py`.
- [ ] Update `docs/handoff/CURRENT_STATUS.md` with command outputs/timestamps/residual risks.

## Risks / rollback notes

- Precheck false positives may block runs if health probe assumptions differ from deployment shape.
- Latency precision changes can alter comparability with previously generated artifacts; note this explicitly in handoff.
