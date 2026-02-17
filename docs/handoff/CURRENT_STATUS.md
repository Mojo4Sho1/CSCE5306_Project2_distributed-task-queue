# Current Status

**Last updated:** 2026-02-17  
**Owner:** Joe + Codex

## Current focus

Runtime env-key normalization is completed: runtime-spec keys are now used consistently across config loading, Compose wiring, and smoke scripts.

## Completed in current focus

- Updated `common/config.py` to use runtime-spec env keys only:
  - Gateway: `GATEWAY_PORT`, `JOB_SERVICE_ADDR`, `QUEUE_SERVICE_ADDR`, `RESULT_SERVICE_ADDR`
  - Job: `JOB_PORT`
  - Queue: `QUEUE_PORT`
  - Coordinator: `COORDINATOR_PORT`, `JOB_SERVICE_ADDR`, `QUEUE_SERVICE_ADDR`, `RESULT_SERVICE_ADDR`
  - Result: `RESULT_PORT`
  - Worker: `COORDINATOR_ADDR`
- Removed non-spec legacy alias env keys from Compose wiring in `docker-compose.yml`.
- Updated smoke scripts to use runtime-spec keys:
  - `scripts/smoke_job_skeleton.py` -> `JOB_PORT`
  - `scripts/smoke_queue_skeleton.py` -> `QUEUE_PORT`
  - `scripts/smoke_result_skeleton.py` -> `RESULT_PORT`
  - `scripts/smoke_coordinator_skeleton.py` -> `COORDINATOR_PORT`
  - `scripts/smoke_worker_skeleton.py` no longer sets non-spec legacy port alias
- Kept existing Compose healthcheck wiring and timing aligned with `docs/spec/runtime-config.md`.

## Passing checks

- `python -m py_compile common/config.py scripts/smoke_job_skeleton.py scripts/smoke_queue_skeleton.py scripts/smoke_result_skeleton.py scripts/smoke_coordinator_skeleton.py scripts/smoke_worker_skeleton.py`: PASS
- `rg -n "GATEWAY_PORT|JOB_PORT|QUEUE_PORT|COORDINATOR_PORT|RESULT_PORT|JOB_SERVICE_ADDR|QUEUE_SERVICE_ADDR|RESULT_SERVICE_ADDR|COORDINATOR_ADDR" common/config.py docker-compose.yml scripts`: PASS

Note: dependency-backed runtime bring-up remains deferred until conda environment access is available (`grpcio` missing in current local environment).

## Known gaps/blockers

- Local environment still lacks `grpcio`, blocking full runtime smoke/compose execution validation outside conda.

## Next task (single target)

Run dependency-backed runtime validation in conda (`docker compose up`/smoke checks) and confirm service health transitions under the normalized env-key contract.

## Definition of done for next task

- In conda/runtime environment, `docker compose up` succeeds with spec-key-only env wiring.
- Service healthchecks pass using `scripts.healthcheck` mode/target mapping from `docs/spec/runtime-config.md`.
- Optional smoke scripts execute against started services without env-key mismatch failures.
- Handoff docs record validation outcomes and any remaining blockers.
