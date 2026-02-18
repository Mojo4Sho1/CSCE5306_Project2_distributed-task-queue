# Current Status

**Last updated:** 2026-02-18  
**Owner:** Joe + Codex

## Current focus

Coordinator service v1 behavior implementation is completed on top of the previously implemented Job/Queue/Result baseline.

## Completed in current focus

- Replaced `services/coordinator/servicer.py` skeleton with spec-compliant v1 Coordinator behavior:
  - thread-safe in-memory worker liveness registry keyed by `worker_id`,
  - implemented `WorkerHeartbeat` validation, liveness refresh, and deterministic `next_heartbeat_in_ms` hints,
  - implemented `FetchWork` idle backoff behavior (`retry_after_ms=200`) with dequeue/CAS dispatch gating (`QUEUED -> RUNNING`),
  - implemented dequeue/CAS rescue attempt (`GetJobRecord` + one immediate `EnqueueJob`) when CAS fails and authoritative status is still `QUEUED`,
  - implemented `ReportWorkOutcome` terminalization orchestration:
    - `JobOutcome` -> terminal `JobStatus` mapping,
    - `StoreResult` write before terminal CAS,
    - guarded `RUNNING -> terminal` CAS,
    - benign terminal-race acceptance when status is already terminal.
- Added `scripts/smoke_coordinator_behavior.py` for focused in-process Coordinator behavior validation (heartbeat, idle fetch hint, CAS dispatch, rescue, and terminalization race handling).
- Updated `scripts/smoke_live_stack.py` Coordinator probe to validate implemented `WorkerHeartbeat` behavior instead of expecting `UNIMPLEMENTED`.

## Passing checks

- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`/Applications/MiniConda/miniconda3/envs/grpc/bin/python`)
- `conda run -n grpc python -m py_compile services/coordinator/servicer.py scripts/smoke_coordinator_behavior.py scripts/smoke_live_stack.py`: PASS
- `conda run -n grpc python scripts/smoke_coordinator_behavior.py`: PASS
  - `heartbeat_accept`: PASS (`accepted=True`, `next=1000`)
  - `fetch_idle_retry_hint`: PASS (`assigned=False`, `retry=200`)
  - `fetch_dispatch_after_cas`: PASS (`assigned=True`, `job_id=job-1`)
  - `fetch_cas_rescue`: PASS (single re-enqueue recorded)
  - `outcome_terminalize_success`: PASS (`accepted=True`)
  - `outcome_terminal_race_benign`: PASS (`accepted=True`)
  - `outcome_invalid_argument`: PASS (`INVALID_ARGUMENT`)

Note: running the same smoke scripts with default/base `python` fails with `ModuleNotFoundError: No module named 'grpc'`; use conda env `grpc` for code/tests.

## Known gaps/blockers

- Gateway public business RPC behavior remains skeleton-level `UNIMPLEMENTED`.
- `FetchWorkResponse.spec` is currently partial (`job_type` only) because `JobInternalService.GetJobRecord` does not expose full `JobSpec` fields (`work_duration_ms`, `payload_size_bytes`, `labels`) in the locked v1 proto contract.
- Full live-stack validation for end-to-end submit/dispatch/result retrieval still depends on Gateway implementation.

## Next task (single target)

Implement Gateway Service (`TaskQueuePublicService`) v1 orchestration behavior for submit/status/result/cancel/list against implemented internal services.

## Definition of done for next task

- `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`, and `ListJobs` return implemented responses (no `UNIMPLEMENTED`) on primary paths.
- Gateway enforces submit compensation and idempotency/error contracts using Job/Queue/Result internal RPCs.
- Gateway terminal/result consistency behavior matches locked contracts (including terminal-mismatch `UNAVAILABLE`).
- Gateway-focused smoke/tests cover submit, status/result readiness, queued cancel path, and key error/idempotency edges.
- Handoff docs capture passing evidence and any unresolved cross-service gaps.
