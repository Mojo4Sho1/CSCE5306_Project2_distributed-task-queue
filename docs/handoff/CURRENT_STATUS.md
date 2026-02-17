# Current Status

**Last updated:** 2026-02-17  
**Owner:** Joe + Codex

## Current focus

Documentation refactor is complete and the repository currently contains a runnable Gateway skeleton baseline plus shared utilities, while most service implementations are still pending.

## Completed in current focus

- Refactored docs so `docs/INDEX.md` is the controlling documentation entry point.
- Reduced `README.md` to orientation/navigation and moved duplicated lock content into spec docs.
- Added handoff templates: `docs/handoff/CURRENT_STATUS.md` and `docs/handoff/NEXT_TASK.md`.
- Added spec docs for previously README-only content:
  - `docs/spec/requirements.md`
  - `docs/spec/governance.md`
- Confirmed proto files and generated stubs exist for public/internal APIs.
- Confirmed Gateway servicer exposes all 5 public RPC handlers with deterministic `UNIMPLEMENTED` placeholder behavior.

## Passing checks

- `rg -n "rpc (SubmitJob|GetJobStatus|GetJobResult|CancelJob|ListJobs)" proto/taskqueue_public.proto`: PASS (all 5 public RPCs present in proto)
- `rg -n "def (SubmitJob|GetJobStatus|GetJobResult|CancelJob|ListJobs)\(" services/gateway/servicer.py`: PASS (all 5 handlers present in Gateway servicer)
- Generated stubs present:
  - `generated/taskqueue_public_pb2.py`
  - `generated/taskqueue_public_pb2_grpc.py`
  - `generated/taskqueue_internal_pb2.py`
  - `generated/taskqueue_internal_pb2_grpc.py`

Note: runtime smoke test did not pass due to missing dependency in local environment (`ModuleNotFoundError: No module named 'grpc'` when running `python scripts/smoke_gateway_skeleton.py`).

## Known gaps/blockers

- Only Gateway has implementation files; `services/job`, `services/queue`, `services/coordinator`, `services/worker`, and `services/result` are placeholders (`.gitkeep` only).
- Runtime contract artifacts referenced by specs are missing from repo:
  - `scripts/healthcheck.py` not present
  - no compose file present (`docker-compose.yml` / `docker-compose.yaml` not found)
- Config/runtime naming drift:
  - `common/config.py` expects `PORT`, `JOB_ADDR`, `QUEUE_ADDR`, `RESULT_ADDR`
  - runtime spec documents `GATEWAY_PORT`, `JOB_SERVICE_ADDR`, `QUEUE_SERVICE_ADDR`, `RESULT_SERVICE_ADDR` (and analogous names for other services)
- Gateway server currently uses fallback config behavior if strict shared config loading fails, which can hide config-contract mismatches.
- Local environment is missing `grpcio`, blocking smoke-test execution until dependencies are installed.

## Next task (single target)

Implement Job service skeleton (`services/job`) with all `JobInternalService` RPC handlers returning deterministic `UNIMPLEMENTED`, plus process bootstrap wiring consistent with the v1 proto/runtime contracts.

## Definition of done for next task

- `services/job` has bootstrapping/server/servicer/store scaffold committed and importable.
- All six `JobInternalService` RPCs are callable and return deterministic `UNIMPLEMENTED`.
- Job service starts cleanly with structured startup logs and clean shutdown behavior.
- A job-skeleton smoke check exists and passes in an environment with required Python dependencies installed.
