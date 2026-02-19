# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Kick off Design B implementation baseline by adding runnable Design B skeleton runtime topology (compose + monolith node entrypoint wiring) while preserving frozen v1 external contracts and keeping Design A validation green.

## Why this task is next

- Design A now has deterministic worker retry and coordinator terminal idempotency unit coverage with live non-regression evidence.
- The next project milestone is beginning Design B implementation (monolith-per-node architecture) under the same v1 semantics.
- Establishing a runnable baseline topology early reduces downstream integration risk and clarifies implementation boundaries.

## Scope (in)

- Add Design B runtime scaffold with clear, runnable entrypoints:
  - Design B compose file under `docker/` (parallel to Design A naming style),
  - monolith node service module/entrypoint wiring for process startup and health visibility.
- Preserve frozen v1 API/proto/state semantics (no contract drift).
- Keep Design A non-regression checks operational:
  - `tests/test_worker_report_retry.py`
  - `tests/test_coordinator_report_outcome_idempotency.py`
  - `tests/integration/smoke_live_stack.py`
  - `tests/integration/smoke_integration_terminal_path.py`
  - `tests/integration/smoke_integration_failure_path.py`
- Record exact command evidence, timestamps, and residual risk notes in handoff docs.

## Scope (out)

- Design B fairness benchmarking/tuning.
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

- Treat `docs/spec/architecture.md`, `docs/spec/state-machine.md`, `docs/spec/fairness-evaluation.md`, and `docs/spec/constants.md` as lock references.
- Keep behavior parity with Design A external semantics; this task is scaffold/bring-up focused.
- Avoid introducing speculative Design B optimizations before baseline runtime is stable.
- Do not alter existing Design A service contracts or test harness expectations.

## Acceptance criteria (definition of done)

- Design B scaffold is runnable via explicit compose command and starts expected containers/processes.
- Locked constants/defaults and env controls remain unchanged unless explicitly documented.
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py` passes.
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py` passes.
- `conda run -n grpc python tests/integration/smoke_live_stack.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py` passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `CURRENT_STATUS.md`.
- Handoff/runtime docs updated with concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Add Design B runtime scaffold files (compose + monolith node entrypoints/wiring).
- [ ] Verify Design B stack bring-up command and container health visibility.
- [ ] Re-run existing deterministic worker retry test module (`tests/test_worker_report_retry.py`).
- [ ] Re-run coordinator idempotency unit module (`tests/test_coordinator_report_outcome_idempotency.py`).
- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Run `docker compose -f docker/docker-compose.design-a.yml up --build -d` and confirm healthy services with `docker compose -f docker/docker-compose.design-a.yml ps`.
- [ ] Run `conda run -n grpc python tests/integration/smoke_live_stack.py`.
- [ ] Run `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`.
- [ ] Run `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`.
- [ ] Record command outputs and residual risk notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Scaffold-only Design B startup can give false confidence before functional parity is implemented.
- Parallel Design A/Design B compose maintenance can drift without strict command/document updates.
- Rollback path is low risk: isolate/remove Design B scaffold files if baseline bring-up proves unstable.
