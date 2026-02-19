# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Design B implementation baseline: runnable monolith-per-node scaffold (compose + node entrypoint wiring) with Design A non-regression validation.

## Completed in current focus

- Added Design B runtime scaffold files:
  - `docker/docker-compose.design-b.yml`
  - `services/monolith/__init__.py`
  - `services/monolith/main.py`
  - `services/monolith/node.py`
- Implemented monolith-node process wiring:
  - single gRPC server process per node hosting public + internal services,
  - node-local loopback wiring for gateway/coordinator upstream calls,
  - in-process worker runtime startup (`1` slot baseline per node),
  - startup/ready/shutdown structured logs and health visibility.
- Preserved frozen v1 contracts:
  - no proto/schema changes (`proto/*` unchanged),
  - no Design A service contract changes.
- Updated documentation for Design B scaffold bring-up and boundaries:
  - `README.md`,
  - `docs/_INDEX.md`,
  - `docs/spec/runtime-config.md`,
  - `docs/spec/runtime-config-design-a.md`,
  - `docs/spec/runtime-config-design-b.md`.

## Passing checks

- Run timestamp anchor: `2026-02-19 13:25:42 -06:00` (local host clock).
- `conda run -n grpc python -m py_compile services/monolith/main.py services/monolith/node.py`: PASS
- `docker compose -f docker/docker-compose.design-b.yml up --build -d`: PASS
- `docker compose -f docker/docker-compose.design-b.yml ps`: PASS
  - `monolith-1..monolith-6` all `Up (... healthy)`.
- `docker compose -f docker/docker-compose.design-b.yml logs monolith-1 | Select-String -Pattern "monolith.startup.ready|monolith.worker.started"`: PASS
  - startup ready + worker started events present.
- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`D:\Programming\anaconda3\envs\grpc\python.exe`)
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`: PASS
  - `Ran 6 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`: PASS
  - `Ran 3 tests ... OK`
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

- No functional blockers for Design B scaffold bring-up.
- Residual risk: Design B scaffold currently validates process topology + health only; it does not yet validate deterministic cross-node owner routing behavior under multi-node client traffic.
- Operational note: running both compose files concurrently under the same compose project name shows cross-file containers as orphans in compose warnings; this is expected in current local workflow.

## Timing/race observations

- Design A smokes remained green after introducing Design B scaffold files.
- Design B monolith nodes stabilized to healthy quickly and showed periodic worker heartbeat/fetch loop activity in logs.
- No observed regressions in Design A terminal/result behavior during this milestone.

## Next task (single target)

Implement and validate deterministic Design B owner-routing client path for job-scoped operations (`SubmitJob` keyed by non-empty `client_request_id`, and status/result/cancel keyed by `job_id`) with runnable smoke evidence.

## Definition of done for next task

- Add deterministic owner routing helper(s) per locked hash algorithm in `docs/spec/fairness-evaluation.md` and `docs/spec/constants.md`.
- Add Design B-focused smoke/validation script(s) demonstrating routed submit + job-scoped reads/cancel against monolith-node ports.
- Keep Design A command matrix green (same unit + integration commands).
- Update docs/handoff with command evidence, exact timestamps, and residual risk notes.
