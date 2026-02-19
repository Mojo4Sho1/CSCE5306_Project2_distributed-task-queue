# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Centralize and standardize internal RPC deadline/retry defaults across Design A services.

## Why this task is next

- Live-stack Gateway/control-plane integration smoke coverage now passes.
- Real worker execution/reporting terminalization now passes in live stack.
- The highest remaining reliability gap is drift-prone hard-coded deadline/retry literals in internal client call paths.

## Scope (in)

- Identify all internal unary RPC call paths in Gateway/Coordinator/Worker using literal timeout values.
- Introduce shared deadline/retry defaults via common config/constants without changing proto contracts.
- Apply shared defaults consistently at call sites while preserving current behavior.
- Validate no regression via existing live smokes.
- Document resulting config surface and residual risks.

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
- Keep retry profile aligned to locked defaults (`100ms`, `2.0`, cap `1000ms`, max `4` attempts).
- Keep behavior changes non-breaking for existing compose/env defaults.

## Acceptance criteria (definition of done)

- Internal timeout/retry literals are removed or minimized in Gateway/Coordinator/Worker in favor of shared defaults.
- `conda run -n grpc python scripts/smoke_live_stack.py` passes.
- `conda run -n grpc python scripts/smoke_integration_terminal_path.py` passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `CURRENT_STATUS.md`.
- Handoff/runtime docs updated with concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Implement shared internal deadline/retry defaults in common configuration/constants.
- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Run `docker compose -f docker/docker-compose.design-a.yml up --build -d` and confirm healthy services with `docker compose -f docker/docker-compose.design-a.yml ps`.
- [ ] Run `conda run -n grpc python scripts/smoke_live_stack.py`.
- [ ] Run `conda run -n grpc python scripts/smoke_integration_terminal_path.py`.
- [ ] Record command outputs and residual risk notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Timeout centralization can unintentionally widen/narrow call behavior if defaults are misapplied; verify by service path.
- Short RPC deadlines may create false-negative `UNAVAILABLE` outcomes under container jitter.
- Retry expansion must avoid violating idempotency constraints on non-idempotent paths.
