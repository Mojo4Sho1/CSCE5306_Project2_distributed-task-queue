# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Add deterministic automated coverage for coordinator `ReportWorkOutcome` terminal-write idempotency behavior (first valid terminal write wins; repeated/conflicting reports stay stable), while keeping current worker retry tests and live integration checks green.

## Why this task is next

- Worker-side retry coverage now includes timing + control-flow safety paths.
- Next high-value correctness gap is coordinator-side terminal-write idempotency under repeated outcome reports.
- Deterministic tests here reduce risk of terminal-state corruption without changing runtime contracts.

## Scope (in)

- Add deterministic tests for coordinator `ReportWorkOutcome` behavior on repeated calls for the same `job_id`:
  - first terminal write (`DONE`/`FAILED`) is accepted and persisted,
  - duplicate-equivalent terminal report is stable/idempotent,
  - conflicting repeated terminal report does not corrupt stored terminal state.
- Keep runtime semantics/config/constants unchanged.
- Validate non-regression across:
  - `tests/integration/smoke_live_stack.py`
  - `tests/integration/smoke_integration_terminal_path.py`
  - `tests/integration/smoke_integration_failure_path.py`
- Record exact command evidence, timestamps, and residual risk notes in handoff docs.

## Scope (out)

- Design B implementation changes.
- Proto/schema/contract changes.
- Fairness benchmark report generation.
- Durability/lease/ack redesigns.
- New external dependencies.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests in this repo.
- Prefer explicit command form:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc python -m unittest <test_path.py>`
- Run Design A services via `docker compose -f docker/docker-compose.design-a.yml up --build -d` before live smokes.

## Implementation notes

- Treat `docs/spec/error-idempotency.md`, `docs/spec/state-machine.md`, and `docs/spec/constants.md` as primary lock references.
- Keep runtime semantics unchanged; this task is coverage-focused.
- Prefer deterministic control of persistence/service stubs to avoid flaky tests.
- Do not alter terminal transition guards or soft-outcome contracts.

## Acceptance criteria (definition of done)

- Automated coverage verifies first-write-wins terminal idempotency behavior for repeated `ReportWorkOutcome`.
- Locked constants/defaults and env controls remain unchanged.
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py` passes.
- Any new coordinator-targeted unit module passes.
- `conda run -n grpc python tests/integration/smoke_live_stack.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py` passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `CURRENT_STATUS.md`.
- Handoff/runtime docs updated with concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Add deterministic tests for coordinator `ReportWorkOutcome` repeated terminal-report idempotency.
- [ ] Re-run existing deterministic worker retry test module (`tests/test_worker_report_retry.py`).
- [ ] Run any new coordinator-targeted unit test module.
- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Run `docker compose -f docker/docker-compose.design-a.yml up --build -d` and confirm healthy services with `docker compose -f docker/docker-compose.design-a.yml ps`.
- [ ] Run `conda run -n grpc python tests/integration/smoke_live_stack.py`.
- [ ] Run `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`.
- [ ] Run `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`.
- [ ] Record command outputs and residual risk notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Tests can overfit internal call sequencing if assertions target implementation details instead of behavior contracts.
- Idempotency tests that bypass realistic data-store transitions can miss integration race edges.
- Rollback path is low risk: remove/adjust tests without touching runtime behavior if coverage design proves unstable.
