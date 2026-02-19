# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Design A internal RPC deadline/retry default centralization across Gateway/Coordinator/Worker.

## Completed in current focus

- Added shared RPC default authority in `common/rpc_defaults.py`:
  - internal unary deadline default (`1000 ms`),
  - worker `FetchWork` deadline default (`1500 ms`),
  - worker `WorkerHeartbeat` deadline default (`1000 ms`),
  - locked retry profile defaults (`100 ms`, `2.0`, cap `1000 ms`, max attempts `4`),
  - shared `FetchWork` retry-after bounds (`200/50/1000 ms`).
- Extended typed config in `common/config.py`:
  - `GatewayConfig.internal_rpc_timeout_ms`,
  - `CoordinatorConfig.internal_rpc_timeout_ms`,
  - `WorkerConfig` timeout/retry fields:
    - `internal_rpc_timeout_ms`,
    - `fetch_work_timeout_ms`,
    - `worker_heartbeat_timeout_ms`,
    - `report_retry_initial_backoff_ms`,
    - `report_retry_multiplier`,
    - `report_retry_max_backoff_ms`,
    - `report_retry_max_attempts`.
- Replaced call-site timeout literals and missing deadlines:
  - `services/gateway/servicer.py` now uses config-backed shared downstream timeout for all Job/Queue/Result calls.
  - `services/coordinator/servicer.py` now applies shared timeout to all downstream unary calls (Queue/Job/Result).
  - `services/worker/worker.py` now uses dedicated per-method timeouts (`heartbeat`, `fetch`, `report`) and shared retry defaults with configurable multiplier/caps.
- Updated spec docs for new config surface:
  - `docs/spec/runtime-config.md`
  - `docs/spec/constants.md`
- Added lightweight manual demo tooling for user-facing Gateway interaction:
  - `scripts/manual_gateway_client.py` (`submit/status/result/cancel/list`),
  - `examples/jobs/hello_distributed.json` sample JobSpec payload,
  - README user workflow section for presentation-friendly manual operation.

## Passing checks

- Run timestamp anchor: `2026-02-19 10:15:18 -06:00` (local host clock).
- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`D:\Programming\anaconda3\envs\grpc\python.exe`)
- `conda run -n grpc python -m py_compile common/rpc_defaults.py common/config.py common/__init__.py services/gateway/servicer.py services/coordinator/servicer.py services/worker/worker.py`: PASS
- `docker compose -f docker/docker-compose.design-a.yml up --build -d`: PASS
- `docker compose -f docker/docker-compose.design-a.yml ps`: PASS
  - `gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `Up (... healthy)`.
- `conda run -n grpc python scripts/smoke_live_stack.py`: PASS
  - `gateway.SubmitJob`: PASS
  - `gateway.GetJobStatus`: PASS
  - `gateway.GetJobResult.not_ready_or_terminal`: PASS
  - `gateway.CancelJob`: PASS
  - `gateway.ListJobs`: PASS
  - `job.ListJobRecords`: PASS
  - `queue.RemoveJobIfPresent`: PASS
  - `coordinator.WorkerHeartbeat`: PASS
  - `result.GetResult`: PASS
- `conda run -n grpc python scripts/smoke_integration_terminal_path.py`: PASS
  - `submit_1..submit_2`: PASS
  - `gateway.GetJobStatus.running_seen`: PASS
  - `gateway.GetJobStatus.terminal`: PASS (`DONE`)
  - `gateway.GetJobResult.terminal_ready`: PASS (`DONE` + checksum match)
  - `gateway.GetJobResult.worker_signature`: PASS

## Known gaps/blockers

- No dedicated failure-path smoke exists yet for worker-reported `FAILED` outcomes; current integration validation still exercises deterministic success-path terminalization.
- Worker retry implementation remains deterministic exponential backoff without explicit jitter injection (locked defaults are preserved for initial/multiplier/cap/attempts, but jitter behavior is not yet modeled).

## Timing/race observations

- Integration smoke terminal path remained stable after timeout centralization; both submitted jobs observed `RUNNING` and then terminalized, with checksum validation passing on first sampled terminal result.
- No downstream deadline-related regressions surfaced in live stack smoke or integration terminal-path smoke in this run.

## Next task (single target)

Add and validate a worker failure-path integration smoke that drives `RUNNING -> FAILED` terminalization and verifies `GetJobResult` failure envelope semantics.

## Definition of done for next task

- A dedicated smoke test (or extension of existing integration smoke) covers worker outcome `FAILED`.
- Validation includes canonical status terminalization to `FAILED`, result envelope readiness, and deterministic failure-reason propagation.
- Existing success-path smokes continue to pass.
- Handoff docs updated with exact command evidence and residual risks.
