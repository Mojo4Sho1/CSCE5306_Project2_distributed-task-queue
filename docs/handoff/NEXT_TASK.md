# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Implement deterministic Design B owner-routing client path and smoke validation so job-scoped operations consistently target the correct monolith owner node under frozen v1 rules.

## Why this task is next

- Design B baseline scaffold runtime is now runnable (`docker-compose.design-b.yml`) with healthy monolith nodes.
- The next correctness risk is routing coherence across six independent in-memory nodes.
- Locked specs require deterministic owner routing for idempotency and job-scoped consistency in Design B v1.

## Scope (in)

- Add deterministic owner-routing helper logic per locked algorithm:
  - hash: `SHA-256`,
  - owner index: `uint64_be(first_8_bytes(sha256(key))) % N`,
  - node-order-driven owner selection.
- Apply routing rules for Design B client path:
  - `SubmitJob` with non-empty `client_request_id` routes by `client_request_id`,
  - `GetJobStatus`, `GetJobResult`, `CancelJob` route by `job_id`.
- Add/extend Design B smoke script(s) to validate routed submit + job-scoped read/cancel behavior against monolith node ports.
- Keep Design A non-regression command matrix operational and documented.
- Record exact command evidence, timestamps, and residual risks in handoff docs.

## Scope (out)

- Cross-node forwarding implementation inside monolith services.
- Fairness benchmark/tuning runs.
- Proto/schema/contract changes.
- Durability/lease/ack redesign.
- New external dependencies.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc python -m unittest <test_path.py>`
- Bring up Design B baseline:
  - `docker compose -f docker/docker-compose.design-b.yml up --build -d`
  - `docker compose -f docker/docker-compose.design-b.yml ps`
- Keep Design A bring-up available for non-regression:
  - `docker compose -f docker/docker-compose.design-a.yml up --build -d`

## Implementation notes

- Treat these as lock references:
  - `docs/spec/fairness-evaluation.md`
  - `docs/spec/constants.md`
  - `docs/spec/error-idempotency.md`
  - `docs/spec/state-machine.md`
- Keep contracts frozen: no proto/schema changes.
- Prefer additive utilities/scripts over invasive service rewrites for this routing milestone.

## Acceptance criteria (definition of done)

- Deterministic owner-routing helper behavior matches locked formula and node ordering.
- Design B smoke evidence demonstrates:
  - routed idempotent submit behavior for non-empty `client_request_id`,
  - routed status/result/cancel calls by `job_id`.
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py` passes.
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py` passes.
- `conda run -n grpc python tests/integration/smoke_live_stack.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py` passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `docs/handoff/CURRENT_STATUS.md`.
- Documentation updated for any new Design B routing scripts/commands.

## Verification checklist

- [ ] Add deterministic owner-routing utility aligned to locked hash/index formula.
- [ ] Add/update Design B smoke script(s) for routed submit/status/result/cancel.
- [ ] Bring up Design B stack and confirm monolith health via compose `ps`.
- [ ] Verify conda execution path (`conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`).
- [ ] Re-run `tests/test_worker_report_retry.py`.
- [ ] Re-run `tests/test_coordinator_report_outcome_idempotency.py`.
- [ ] Re-run `tests/integration/smoke_live_stack.py`.
- [ ] Re-run `tests/integration/smoke_integration_terminal_path.py`.
- [ ] Re-run `tests/integration/smoke_integration_failure_path.py`.
- [ ] Record command outputs/timestamps/residual risks in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Without deterministic routing, Design B per-node in-memory state can violate submit idempotency/read coherence expectations.
- Script-level routing and runtime-level behavior can drift if node ordering and hash formula are duplicated in multiple places.
- Rollback path is low risk: isolate routing utilities/scripts while keeping Design B runtime scaffold intact.
