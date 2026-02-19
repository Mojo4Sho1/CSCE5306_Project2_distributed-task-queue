# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Add a failure-path integration smoke for worker-reported `FAILED` outcomes and validate terminal/result semantics end-to-end.

## Why this task is next

- Internal RPC deadline/retry defaults are now centralized and wired through shared config/constants.
- Live-stack and terminal-path success smokes pass after centralization.
- The main remaining behavior coverage gap is missing end-to-end validation for the `RUNNING -> FAILED` path.

## Scope (in)

- Add a deterministic way to exercise a worker failure outcome in integration testing (without proto changes).
- Validate `RUNNING -> FAILED` canonical terminalization through Gateway APIs.
- Validate `GetJobResult` returns terminal envelope with failure-consistent summary/reason fields.
- Re-run existing success-path live smokes to ensure no regression.
- Record exact evidence and residual risks in handoff docs.

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
  - `conda run -n grpc pytest` (if/when pytest suites are added)
- Run Design A services via `docker compose -f docker/docker-compose.design-a.yml up --build -d` before live smokes.

## Implementation notes

- Treat `docs/spec/state-machine.md` and `docs/spec/error-idempotency.md` as primary lock references for integration drift triage.
- Preserve canonical-status-first logic for result readiness in all integration checks.
- Keep behavior non-breaking for existing compose/env defaults.
- Failure-path validation should assert terminal/result consistency invariants, not just gRPC reachability.

## Acceptance criteria (definition of done)

- Dedicated failure-path smoke evidence exists for worker-reported `FAILED`.
- `conda run -n grpc python scripts/smoke_live_stack.py` passes.
- `conda run -n grpc python scripts/smoke_integration_terminal_path.py` passes.
- New/updated failure-path smoke passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `CURRENT_STATUS.md`.
- Handoff/runtime docs updated with concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Implement deterministic failure-path integration smoke coverage for worker outcome `FAILED`.
- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Run `docker compose -f docker/docker-compose.design-a.yml up --build -d` and confirm healthy services with `docker compose -f docker/docker-compose.design-a.yml ps`.
- [ ] Run `conda run -n grpc python scripts/smoke_live_stack.py`.
- [ ] Run `conda run -n grpc python scripts/smoke_integration_terminal_path.py`.
- [ ] Run new/updated failure-path smoke command.
- [ ] Record command outputs and residual risk notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Failure-path triggering approach may accidentally perturb success-path determinism if not isolated.
- Assertion design must distinguish expected business `FAILED` terminalization from transport-level transient failures.
- Additional smoke runtime may increase CI/local flake surface if polling windows are too tight.
