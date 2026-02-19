# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Prevent accidental benchmark artifact overwrite when rerunning identical `(scenario_id, run_seed, repeat_index)` tuples in the same output directory.

## Why this task is next

- Report-quality loadgen hardening is now complete:
  - pre-run health precheck gate exists in CLI,
  - summary artifacts include job-terminal throughput,
  - latency summaries avoid degenerate all-zero behavior in short live runs.
- Remaining operational gap is reproducibility safety:
  - deterministic run IDs currently make reruns replace prior artifacts silently.

## Scope (in)

- Add explicit collision policy for run directory creation in benchmark runner/CLI.
- Support a safe default that preserves existing run artifacts.
- Add an explicit override path for intentional replacement (for example `--overwrite`).
- Update docs/handoff/runbook to reflect new collision behavior and operator guidance.

## Scope (out)

- Proto/schema changes.
- Service runtime behavior changes.
- Fairness lock modifications.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests.
- Keep design stacks healthy when running live benchmark checks.

## Acceptance criteria (definition of done)

- Re-running the same scenario tuple does not silently overwrite existing artifacts by default.
- Overwrite behavior (if selected) is explicit and documented.
- Existing baseline unit/integration suites remain green.

## Verification checklist

- [ ] Implement run-dir collision handling in loadgen runner/CLI.
- [ ] Add/extend deterministic tests for collision policy.
- [ ] Re-run `tests/test_loadgen_contracts.py`.
- [ ] Re-run `tests/test_worker_report_retry.py`.
- [ ] Re-run `tests/test_coordinator_report_outcome_idempotency.py`.
- [ ] Re-run `tests/integration/smoke_live_stack.py`.
- [ ] Re-run `tests/integration/smoke_integration_terminal_path.py`.
- [ ] Re-run `tests/integration/smoke_integration_failure_path.py`.
- [ ] Re-run `tests/integration/smoke_design_b_owner_routing.py`.
- [ ] Update `docs/handoff/CURRENT_STATUS.md` with command outputs/timestamps/residual risks.

## Risks / rollback notes

- Changing run-dir policy can impact downstream scripts expecting exact deterministic path naming.
- If suffix-based preservation is used, analysis scripts must handle multiple runs per base tuple.
