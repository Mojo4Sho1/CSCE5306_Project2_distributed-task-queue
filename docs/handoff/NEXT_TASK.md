# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Add minimal output-collision safety to loadgen runs: fail if run directory exists by default, with explicit `--overwrite` for intentional replacement.

## Why this task is next

- Report-quality loadgen hardening is now complete:
  - pre-run health precheck gate exists in CLI,
  - summary artifacts include job-terminal throughput,
  - latency summaries avoid degenerate all-zero behavior in short live runs.
- Remaining operational gap is artifact safety:
  - deterministic run IDs currently make reruns replace prior artifacts silently.
- Scope-control decision for class-project simplicity:
  - keep this change minimal and avoid advanced reproducibility framework work.
  - final benchmark/report runs are expected to use multiple seeds; this task is about preventing accidental overwrite, not changing fairness methodology.

## Scope (in)

- Add run-dir existence guard before artifact write.
- Default behavior: fail fast if deterministic run directory already exists.
- Add explicit `--overwrite` path for intentional replacement.
- Add deterministic tests for both default and overwrite behaviors.
- Update docs/handoff/runbook with operator guidance.

## Scope (out)

- Proto/schema changes.
- Service runtime behavior changes.
- Fairness lock modifications.
- Advanced run management features (run registry, auto-suffix naming, retention policies).

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests.
- Keep design stacks healthy when running live benchmark checks.

## Acceptance criteria (definition of done)

- Re-running the same scenario tuple fails by default when output path already exists.
- `--overwrite` allows explicit replacement of existing artifacts.
- Behavior is documented as operational safety and kept intentionally low-complexity.
- Existing baseline unit/integration suites remain green.

## Verification checklist

- [ ] Implement run-dir collision handling in loadgen runner/CLI.
- [ ] Add/extend deterministic tests for fail-if-exists and `--overwrite`.
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
- Mitigation: keep deterministic naming unchanged and use explicit `--overwrite` only when intended.
