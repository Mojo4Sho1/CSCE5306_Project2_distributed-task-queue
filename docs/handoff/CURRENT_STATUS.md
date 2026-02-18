# Current Status

**Last updated:** 2026-02-18  
**Owner:** Joe + Codex

## Current focus

Queue service v1 behavior implementation is completed on top of the previously validated runtime/dependency baseline.

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
- Added `docker/Dockerfile.runtime` to install runtime dependencies required by services and generated stubs (`grpcio`, `protobuf`, `grpcio-tools`).
- Updated `docker-compose.yml` to build each service from the shared runtime Dockerfile instead of `python:3.11-slim` without dependencies.
- Extended `common/config.py` `JobConfig` to include `MAX_DEDUP_KEYS` parsing (default `10000`).
- Replaced `services/job/servicer.py` skeleton with spec-compliant v1 behavior:
  - thread-safe in-memory canonical job store,
  - bounded in-memory dedup map keyed by `client_request_id`,
  - implemented `CreateJob`, `DeleteJobIfStatus`, `GetJobRecord`, `ListJobRecords`,
    `TransitionJobStatus`, `SetCancelRequested`,
  - enforced CAS and lifecycle transition rules,
  - applied timestamp authority updates for `created_at_ms`, `started_at_ms`, `finished_at_ms`,
  - implemented internal status/error semantics (`FAILED_PRECONDITION`, `INVALID_ARGUMENT`, `NOT_FOUND`) for key edge cases.
- Added `scripts/smoke_job_behavior.py` for focused Job-service behavior validation (dedup, CAS, pagination, conditionals).
- Replaced `services/queue/servicer.py` skeleton with spec-compliant v1 behavior:
  - thread-safe in-memory FIFO queue with unique `job_id` membership,
  - implemented `EnqueueJob`, `DequeueJob`, `RemoveJobIfPresent`,
  - idempotent enqueue-by-key semantics (no duplicates),
  - destructive dequeue semantics with repeat-safe remove behavior,
  - request validation for malformed required IDs (`INVALID_ARGUMENT`).
- Added `scripts/smoke_queue_behavior.py` for focused Queue-service behavior validation (idempotency, dequeue order, remove/dequeue edge cases).
- Added `scripts/smoke_live_stack.py` for representative gRPC probes against an already-running Compose stack.
- Updated `scripts/smoke_live_stack.py` to validate mixed phase behavior (implemented Job/Queue + skeleton Gateway/Coordinator/Result).
- Kept Compose healthcheck wiring and timing aligned with `docs/spec/runtime-config.md`.

## Passing checks

- `python -m py_compile common/config.py scripts/smoke_job_skeleton.py scripts/smoke_queue_skeleton.py scripts/smoke_result_skeleton.py scripts/smoke_coordinator_skeleton.py scripts/smoke_worker_skeleton.py`: PASS
- `rg -n "GATEWAY_PORT|JOB_PORT|QUEUE_PORT|COORDINATOR_PORT|RESULT_PORT|JOB_SERVICE_ADDR|QUEUE_SERVICE_ADDR|RESULT_SERVICE_ADDR|COORDINATOR_ADDR" common/config.py docker-compose.yml scripts`: PASS
- `conda run -n grpc python scripts/smoke_gateway_skeleton.py`: PASS
- `conda run -n grpc python scripts/smoke_result_skeleton.py`: PASS
- `conda run -n grpc python scripts/smoke_coordinator_skeleton.py`: PASS
- `conda run -n grpc python scripts/smoke_worker_skeleton.py`: PASS
- `conda run -n grpc python scripts/smoke_job_behavior.py`: PASS
- `conda run -n grpc python scripts/smoke_queue_behavior.py`: PASS
- `docker compose up --build -d`: PASS
- `docker compose ps`: PASS (`gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `healthy`)
- `conda run -n grpc python scripts/smoke_live_stack.py`: PASS (after services reached healthy state)
- `docker compose down --remove-orphans`: PASS (stack shut down cleanly after integration validation)

Note: running the same smoke scripts with default/base `python` fails with `ModuleNotFoundError: No module named 'grpc'`; use conda env `grpc` for code/tests.

## Known gaps/blockers

- Job and Queue services are now implemented, but Gateway/Coordinator/Result business RPC behavior remains skeleton-level `UNIMPLEMENTED`.

## Next task (single target)

Implement Result Service (`ResultInternalService`) v1 behavior with terminal-envelope storage semantics per spec.

## Definition of done for next task

- `StoreResult` enforces terminal-status-only input validation and idempotent conflict reporting semantics.
- `GetResult` returns stored envelopes deterministically with expected not-found behavior.
- Maximum output payload bound (`MAX_OUTPUT_BYTES`) is enforced per locked constants.
- Result behavior is validated with focused smoke/tests (including duplicate store and invalid-status paths).
- Handoff docs capture concrete validation evidence and remaining gaps.
