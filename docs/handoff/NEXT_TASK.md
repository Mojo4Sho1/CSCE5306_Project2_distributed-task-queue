# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Implement a reusable Design B client-routing utility that covers both locked ingress modes (round-robin for empty submit key, deterministic owner for non-empty key/job-scoped operations) and validate it with focused tests.

## Why this task is next

- Deterministic owner routing is now implemented and smoke-validated for non-empty submit keys and job-scoped operations.
- Remaining parity gap from fairness lock is explicit empty-key `SubmitJob` round-robin behavior for Design B client path.
- Routing logic is currently spread across script-local assumptions; centralizing ingress policy reduces drift risk before load-generator integration.

## Scope (in)

- Add reusable Design B client-routing utility/module for:
  - `SubmitJob` with empty `client_request_id`: round-robin across fixed ordered node list,
  - `SubmitJob` with non-empty `client_request_id`: deterministic owner by locked hash formula,
  - `GetJobStatus`/`GetJobResult`/`CancelJob`: deterministic owner by `job_id`.
- Add tests/smokes to verify:
  - round-robin progression for empty-key submits,
  - deterministic repeatability for non-empty submit keys and job-scoped routing.
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

- Reusable client-routing utility exists with explicit node-order input and deterministic behavior.
- Utility behavior demonstrates:
  - empty-key `SubmitJob` round-robin progression,
  - non-empty-key `SubmitJob` deterministic owner routing,
  - deterministic job-scoped routing by `job_id`.
- Design B smoke/test evidence covers both routing modes (round-robin + deterministic owner).
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py` passes.
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py` passes.
- `conda run -n grpc python tests/integration/smoke_live_stack.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py` passes.
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py` passes.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `docs/handoff/CURRENT_STATUS.md`.
- Documentation updated for any new Design B routing scripts/commands.

## Verification checklist

- [ ] Add reusable Design B client-routing utility for empty-key round-robin + non-empty deterministic routing.
- [ ] Add/update tests/smokes for round-robin + deterministic routing behavior.
- [ ] Bring up Design B stack and confirm monolith health via compose `ps`.
- [ ] Verify conda execution path (`conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`).
- [ ] Re-run `tests/test_worker_report_retry.py`.
- [ ] Re-run `tests/test_coordinator_report_outcome_idempotency.py`.
- [ ] Re-run `tests/integration/smoke_live_stack.py`.
- [ ] Re-run `tests/integration/smoke_integration_terminal_path.py`.
- [ ] Re-run `tests/integration/smoke_integration_failure_path.py`.
- [ ] Record command outputs/timestamps/residual risks in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Without centralized ingress logic, empty-key submit traffic can drift from locked fairness assumptions.
- Duplicated routing-order definitions across scripts/runtime remain a drift vector.
- Rollback path is low risk: keep routing utility additive and keep existing runtime contract unchanged.
