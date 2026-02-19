# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Design B deterministic owner-routing client path + coherence validation, with Design A non-regression matrix.

## Completed in current focus

- Added deterministic routing utility:
  - `common/owner_routing.py`
  - locked algorithm: `uint64_be(first_8_bytes(sha256(key_utf8))) % N`.
- Added owner-routing automated checks:
  - `tests/test_owner_routing.py` (formula + node-order behavior + argument validation),
  - `tests/integration/smoke_design_b_owner_routing.py` (routed submit/status/result/cancel evidence).
- Implemented Design B runtime coherence fix:
  - `services/job/servicer.py` now supports owner-affine `job_id` generation when owner-routing config is present,
  - `services/monolith/node.py` now provides node-order/index config to `JobServicer` using `MONOLITH_NODE_ORDER` + `MONOLITH_NODE_ID`.
- Preserved frozen v1 contracts:
  - no proto/schema changes (`proto/*` unchanged),
  - no public API service/method signature changes.
- Updated docs for routing utilities/tests and runtime behavior:
  - `README.md`,
  - `tests/_TEST_INDEX.md`,
  - `docs/spec/runtime-config-design-b.md`.

## Passing checks

- Run timestamp anchor: `2026-02-19 14:21:18 -06:00` (local host clock start), `2026-02-19 14:25:03 -06:00` (end).
- `conda run -n grpc python -m py_compile common/owner_routing.py tests/test_owner_routing.py tests/integration/smoke_design_b_owner_routing.py`: PASS
- `conda run -n grpc python -m py_compile services/job/servicer.py services/monolith/node.py`: PASS
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
  - all checks `PASS`, final `RESULT: PASS`,
  - evidence includes:
    - submit owner selection by `client_request_id`,
    - idempotent same-key submit returns same `job_id`,
    - same-key/different-payload returns `FAILED_PRECONDITION`,
    - `GetJobStatus`/`GetJobResult`/`CancelJob` non-owner calls return `NOT_FOUND`,
    - owner-routed job-scoped calls succeed.
- `docker compose -f docker/docker-compose.design-a.yml up --build -d`: PASS
- `docker compose -f docker/docker-compose.design-a.yml ps`: PASS
  - `gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `Up (... healthy)`.
- `conda run -n grpc python tests/integration/smoke_live_stack.py`: PASS
  - all probe lines reported `PASS` and final `RESULT: PASS`.
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`: PASS
  - all probe lines reported `PASS` and final `RESULT: PASS`.
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`: PASS
  - all probe lines reported `PASS` and final `RESULT: PASS`.

## Known gaps/blockers

- No functional blockers for this routing milestone.
- Residual risk: `MONOLITH_NODE_ORDER` is currently configured implicitly by default ordering in runtime (`monolith-1..monolith-6`) and mirrored by client/script target ordering; drift across environments can still cause routing mismatch if ordering is changed inconsistently.
- Operational note: running both compose files concurrently under the same compose project name shows cross-file containers as orphans in compose warnings; this is expected in current local workflow.

## Timing/race observations

- Initial Design B routing smoke attempt failed before runtime fix: `GetJobStatus` on `job_id`-owner returned `NOT_FOUND` due to random UUID placement mismatch.
- After owner-affine `job_id` generation was added for monolith runtime, Design B routing smoke passed end-to-end.
- Design A unit + integration smoke matrix remained green after routing changes.

## Next task (single target)

Implement Design B client utility for locked ingress behavior parity:
- round-robin `SubmitJob` when `client_request_id` is empty,
- deterministic owner routing when `client_request_id` is non-empty,
- reusable shared node-order config surface to reduce routing-order drift across scripts/load-generator.

## Definition of done for next task

- Add a Design B client helper/module that implements both empty-key round-robin and non-empty-key deterministic routing in one place.
- Ensure helper consumes explicit ordered node list config and can be reused by future load-generator code.
- Add/extend tests proving empty-key round-robin behavior and non-empty-key deterministic owner behavior.
- Keep current required Design A and Design B smoke commands green.
- Update docs/handoff with command evidence, exact timestamps, and residual-risk notes.
