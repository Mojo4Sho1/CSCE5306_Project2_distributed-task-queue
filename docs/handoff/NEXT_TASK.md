# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Implement the pre-loadgen benchmark contract scaffold: scenario configuration schema, runner skeleton, and output artifact schema, with Design B ingress wired through the shared client-routing utility.

## Why this task is next

- Design B client routing parity is now implemented and validated for both locked ingress modes.
- Remaining blocker before full benchmark implementation is a reproducible scenario + output contract.
- Locking scenario/output structure now reduces rework when full load traffic generation is added.

## Scope (in)

- Add machine-readable scenario config artifact and loader for benchmark runs.
- Add runner scaffold implementing warm-up -> measure -> cool-down -> repeat control flow.
- Add output row schema/writer aligned with fairness spec required fields.
- Ensure Design B path uses shared routing utility (`common/design_b_routing.py`) and explicit ordered target list.
- Add deterministic tests for scenario parsing/validation and output serialization.
- Update docs and handoff with commands/evidence.

## Scope (out)

- Full high-throughput load-generation engine implementation.
- Benchmark result interpretation/plotting.
- Proto/schema/contract changes.
- Inter-node forwarding or storage durability redesign.
- New external dependencies.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc python -m unittest <test_path.py>`
- Keep both runtime stacks available for smoke/non-regression:
  - `docker compose -f docker/docker-compose.design-a.yml up --build -d`
  - `docker compose -f docker/docker-compose.design-b.yml up --build -d`

## Implementation notes

- Treat these as lock references:
  - `docs/spec/fairness-evaluation.md`
  - `docs/spec/constants.md`
  - `docs/spec/error-idempotency.md`
  - `docs/spec/state-machine.md`
- Reuse shared Design B routing utility:
  - `common/design_b_routing.py`
- Keep contracts frozen: no proto/schema changes.
- Keep scaffolding additive and separable from core service runtime.

## Acceptance criteria (definition of done)

- Scenario config schema exists with validation for workload/fairness controls.
- Runner scaffold exists for warm-up/measure/cool-down/repeat flow and stable run IDs.
- Output row schema includes required fairness fields and writes parseable artifacts.
- Design B scaffold path resolves targets and routing through shared helper.
- Deterministic tests for config parse/validation and output serialization pass.
- Existing baseline checks remain green:
  - `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`
  - `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`
  - `conda run -n grpc python tests/integration/smoke_live_stack.py`
  - `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`
  - `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`
  - `conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py`
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `docs/handoff/CURRENT_STATUS.md`.

## Verification checklist

- [ ] Add scenario config schema + loader.
- [ ] Add runner scaffold for warm-up/measure/cool-down/repeat.
- [ ] Add output row schema/writer for benchmark artifacts.
- [ ] Add deterministic tests for scenario parsing and artifact serialization.
- [ ] Ensure Design B runner path uses `common/design_b_routing.py`.
- [ ] Re-run `tests/test_worker_report_retry.py`.
- [ ] Re-run `tests/test_coordinator_report_outcome_idempotency.py`.
- [ ] Re-run `tests/integration/smoke_live_stack.py`.
- [ ] Re-run `tests/integration/smoke_integration_terminal_path.py`.
- [ ] Re-run `tests/integration/smoke_integration_failure_path.py`.
- [ ] Re-run `tests/integration/smoke_design_b_owner_routing.py`.
- [ ] Record command outputs/timestamps/residual risks in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Scenario/output drift without a fixed schema can invalidate A/B comparability.
- If runner control-flow semantics drift from fairness spec (timing windows, seeds), benchmark reproducibility degrades.
- Rollback path is low risk: scaffolding is additive and can be isolated from service runtime.
