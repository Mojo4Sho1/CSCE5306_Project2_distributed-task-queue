# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Design B client-routing parity utility (empty-key round-robin + deterministic owner routing) and non-regression validation.

## Completed in current focus

- Added reusable Design B client-routing module:
  - `common/design_b_routing.py`
  - provides `DesignBClientRouter` and `build_ordered_targets` for one shared ingress policy surface.
- Added focused unit coverage for client-routing behaviors:
  - `tests/test_design_b_client_routing.py`
  - verifies empty-key round-robin progression/wrap,
  - verifies non-empty submit-key deterministic owner routing,
  - verifies job-scoped routing by `job_id`,
  - verifies invalid-argument guards.
- Extended Design B live smoke to cover both locked ingress modes using shared helper:
  - `tests/integration/smoke_design_b_owner_routing.py`
  - now validates:
    - empty-key round-robin submit progression,
    - empty-key non-idempotent distinct `job_id` behavior,
    - empty-key submit-to-job-owner coherence,
    - existing non-empty key owner-routing/idempotency checks,
    - existing job-scoped owner-routing checks (`GetJobStatus`/`GetJobResult`/`CancelJob`).
- Updated docs for new utility and verification matrix:
  - `README.md`,
  - `tests/_TEST_INDEX.md`,
  - `docs/spec/runtime-config-design-b.md`.

## Passing checks

- Run timestamp anchor: `2026-02-19 14:44:31 -06:00` (start), `2026-02-19 14:47:39 -06:00` (end).
- `conda run -n grpc python -m py_compile common/design_b_routing.py tests/test_design_b_client_routing.py tests/integration/smoke_design_b_owner_routing.py`: PASS
- `conda run -n grpc python -m unittest tests/test_design_b_client_routing.py`: PASS
  - `Ran 6 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_owner_routing.py`: PASS
  - `Ran 3 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`: PASS
  - `Ran 6 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`: PASS
  - `Ran 3 tests ... OK`
- `docker compose -f docker/docker-compose.design-b.yml up --build -d`: PASS
- `docker compose -f docker/docker-compose.design-b.yml ps`: PASS
  - `monolith-1..monolith-6` all `Up (... healthy)` during verification window.
- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`D:\Programming\anaconda3\envs\grpc\python.exe`)
- `conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py`: PASS
  - all probe lines `PASS`, final `RESULT: PASS`,
  - includes explicit empty-key round-robin and non-empty deterministic owner evidence.
- `docker compose -f docker/docker-compose.design-a.yml up --build -d`: PASS (services started healthy; one tool invocation timed out at 12s but subsequent `ps` was healthy).
- `docker compose -f docker/docker-compose.design-a.yml ps`: PASS
  - `gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `Up (... healthy)`.
- `conda run -n grpc python tests/integration/smoke_live_stack.py`: PASS
  - final `RESULT: PASS`.
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`: PASS
  - final `RESULT: PASS`.
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`: PASS
  - final `RESULT: PASS`.

## Known gaps/blockers

- No functional blockers for this routing milestone.
- Residual risk: round-robin cursor is process-local to the client/router instance; multi-process load generators must share or partition submit streams intentionally for globally balanced distribution.
- Operational note: running both compose files concurrently under one compose project still produces orphan warnings; expected in current local workflow.

## Timing/race observations

- Initial smoke run after refactor failed with script unpacking bug (`submit_target` returns three values); fixed and re-verified in same session.
- Empty-key submits validated as non-idempotent and distributed in configured round-robin order.

## Next task (single target)

Define and implement load-generator scenario/output contract scaffold (config schema + runner skeleton + artifact schema) that consumes `common/design_b_routing.py` for Design B ingress policy.

## Definition of done for next task

- Add machine-readable scenario config format covering locked fairness controls (concurrency, request mix, warm-up/measure/cool-down windows, run seed).
- Add loadgen runner scaffold that can execute warm-up -> measure -> cool-down -> repeat and write per-run artifacts.
- Add benchmark row schema/output writer aligned with `docs/spec/fairness-evaluation.md` Section 10 fields.
- Wire Design B path to shared `DesignBClientRouter` and explicit ordered targets config.
- Add at least one deterministic non-live unit test for scenario parsing and output row serialization.
- Update docs/spec + handoff docs with commands, assumptions, and residual risk notes.
