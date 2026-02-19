# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Add deterministic automated coverage for worker `_report_with_retry` interrupt/error handling paths (stop-event early exit and transient RPC failures), while keeping current retry timing coverage and live integration checks green.

## Why this task is next

- Retry wait-selection behavior now has deterministic unit coverage.
- Remaining uncovered retry behavior is control-flow safety: interruption and transient error handling.
- Deterministic coverage for these paths reduces regression risk without changing runtime contracts.

## Scope (in)

- Add automated test(s) for `_report_with_retry` control-flow behavior:
  - if stop event is set after a retry wait, loop exits early and returns `False`,
  - transient `grpc.RpcError` retries continue until success or max attempts.
- Keep existing retry timing test coverage passing:
  - full jitter draws in `[0, backoff_window_ms]`,
  - bounded exponential window progression respects locked `initial/multiplier/max`,
  - attempt count behavior remains unchanged.
- Keep worker config surface and defaults unchanged.
- Validate non-regression across:
  - `scripts/smoke_live_stack.py`
  - `scripts/smoke_integration_terminal_path.py`
  - `scripts/smoke_integration_failure_path.py`
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

- Treat `docs/spec/error-idempotency.md` and `docs/spec/constants.md` as primary lock references for retry/jitter semantics.
- Keep runtime semantics unchanged; this task is coverage-focused.
- Prefer deterministic test control (for example, patching RNG calls) to avoid flaky tests.
- Do not alter retryable control-flow semantics or attempt-count behavior.

## Acceptance criteria (definition of done)

- Automated test coverage verifies stop-event interruption and transient RPC retry handling for `_report_with_retry`.
- Locked retry defaults and env controls remain unchanged.
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py` passes.
- `conda run -n grpc python scripts/smoke_live_stack.py` passes.
- `conda run -n grpc python scripts/smoke_integration_terminal_path.py` passes.
- `conda run -n grpc python scripts/smoke_integration_failure_path.py` passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `CURRENT_STATUS.md`.
- Handoff/runtime docs updated with concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Add deterministic tests for stop-event early-exit and transient RPC retry handling in worker report-retry path.
- [ ] Re-run existing deterministic retry timing test module (`tests/test_worker_report_retry.py`).
- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Run `docker compose -f docker/docker-compose.design-a.yml up --build -d` and confirm healthy services with `docker compose -f docker/docker-compose.design-a.yml ps`.
- [ ] Run `conda run -n grpc python scripts/smoke_live_stack.py`.
- [ ] Run `conda run -n grpc python scripts/smoke_integration_terminal_path.py`.
- [ ] Run `conda run -n grpc python scripts/smoke_integration_failure_path.py`.
- [ ] Record command outputs and residual risk notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Tests that patch RPC/stop-event paths can overfit implementation details if assertions target internals instead of behavior contracts.
- Timing-sensitive assertions can become flaky if tests rely on real sleeping or wall-clock timing.
- Rollback path is low risk: remove/adjust tests without touching runtime behavior if coverage design proves unstable.
