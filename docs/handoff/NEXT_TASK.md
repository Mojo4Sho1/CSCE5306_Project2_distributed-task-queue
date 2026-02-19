# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Add full-jitter behavior to worker outcome-report retries while preserving locked retry defaults and non-regressing integration coverage.

## Why this task is next

- Failure-path integration coverage for worker-reported `FAILED` is now implemented and passing.
- Remaining known gap is retry jitter behavior: backoff timing is deterministic exponential today.
- Specs lock retry constants/profile and jitter mode; implementation should align without changing public/internal contracts.

## Scope (in)

- Implement full-jitter wait selection for worker `ReportWorkOutcome` retry path.
- Keep locked defaults and config surface unchanged (`initial`, `multiplier`, `max`, `attempts`).
- Validate no behavior regression across:
  - `scripts/smoke_live_stack.py`
  - `scripts/smoke_integration_terminal_path.py`
  - `scripts/smoke_integration_failure_path.py`
- Record exact command evidence, timestamps, and residual flake risk in handoff docs.

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

- Treat `docs/spec/error-idempotency.md` and `docs/spec/constants.md` as primary lock references for retry/jitter semantics.
- Apply jitter only to retry wait duration calculation; do not alter retryable-code selection or attempt count behavior.
- Keep behavior non-breaking for existing compose/env defaults.
- Ensure logging still provides enough context to diagnose retry attempt timing.

## Acceptance criteria (definition of done)

- Worker retry waits use full jitter under bounded exponential backoff windows.
- `conda run -n grpc python scripts/smoke_live_stack.py` passes.
- `conda run -n grpc python scripts/smoke_integration_terminal_path.py` passes.
- `conda run -n grpc python scripts/smoke_integration_failure_path.py` passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `CURRENT_STATUS.md`.
- Handoff/runtime docs updated with concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Implement full-jitter retry wait behavior in worker outcome-report path.
- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Run `docker compose -f docker/docker-compose.design-a.yml up --build -d` and confirm healthy services with `docker compose -f docker/docker-compose.design-a.yml ps`.
- [ ] Run `conda run -n grpc python scripts/smoke_live_stack.py`.
- [ ] Run `conda run -n grpc python scripts/smoke_integration_terminal_path.py`.
- [ ] Run `conda run -n grpc python scripts/smoke_integration_failure_path.py`.
- [ ] Record command outputs and residual risk notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Jitter can increase execution-time variance and expose latent polling-window flakiness in smokes.
- Overly large jitter window could delay completion and raise timeout risk under loaded hosts.
- Misapplied jitter logic could reduce effective retry attempts if sleep behavior is not bounded correctly.
