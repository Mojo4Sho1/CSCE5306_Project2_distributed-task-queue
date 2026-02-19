# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Repository navigation migration for test/tooling paths (canonical integration under `tests/integration`, manual/dev/legacy split under `scripts/`) with compatibility wrappers and non-regression validation.

## Completed in current focus

- Added deterministic unit tests for worker retry timing in `tests/test_worker_report_retry.py`:
  - verifies full-jitter draw bounds via `randint(0, backoff_window_ms)`,
  - verifies bounded exponential retry-window progression (`initial`, `multiplier`, `max`),
  - verifies max-attempt behavior remains unchanged (4 total attempts),
  - verifies no retry wait is applied on first-attempt success.
- Migrated canonical integration scripts to `tests/integration/`:
  - `smoke_live_stack.py`,
  - `smoke_integration_terminal_path.py`,
  - `smoke_integration_failure_path.py`.
- Migrated manual/dev utilities to dedicated folders:
  - `scripts/manual/manual_gateway_client.py`,
  - `scripts/dev/healthcheck.py`.
- Migrated retained helper harnesses to `scripts/legacy_smoke/`.
- Added deprecated compatibility wrappers at old `scripts/*.py` paths to avoid breaking existing commands.
- Updated documentation for navigation/taxonomy and canonical command matrix:
  - `README.md`,
  - `scripts/SMOKE_INDEX.md`,
  - `docs/INDEX.md`,
  - `docs/handoff/NEXT_TASK.md`.

## Passing checks

- Run timestamp anchor: `2026-02-19 12:04:17 -06:00` (local host clock).
- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`D:\Programming\anaconda3\envs\grpc\python.exe`)
- `conda run -n grpc python -m py_compile tests/integration/smoke_live_stack.py tests/integration/smoke_integration_terminal_path.py tests/integration/smoke_integration_failure_path.py scripts/manual/manual_gateway_client.py scripts/dev/healthcheck.py scripts/smoke_live_stack.py scripts/smoke_integration_terminal_path.py scripts/smoke_integration_failure_path.py scripts/manual_gateway_client.py scripts/healthcheck.py`: PASS
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`: PASS
  - `Ran 3 tests ... OK`
- `docker compose -f docker/docker-compose.design-a.yml up --build -d`: PASS
- `docker compose -f docker/docker-compose.design-a.yml ps`: PASS
  - `gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `Up (... healthy)`.
- `conda run -n grpc python scripts/manual/manual_gateway_client.py --help`: PASS
- `conda run -n grpc python scripts/manual_gateway_client.py --help`: PASS (wrapper compatibility)
- `conda run -n grpc python tests/integration/smoke_live_stack.py`: PASS
  - `gateway.SubmitJob`: PASS
  - `gateway.GetJobStatus`: PASS
  - `gateway.GetJobResult.not_ready_or_terminal`: PASS
  - `gateway.CancelJob`: PASS
  - `gateway.ListJobs`: PASS
  - `job.ListJobRecords`: PASS
  - `queue.RemoveJobIfPresent`: PASS
  - `coordinator.WorkerHeartbeat`: PASS
  - `result.GetResult`: PASS
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`: PASS
  - `submit_1..submit_2`: PASS
  - `gateway.GetJobStatus.running_seen`: PASS
  - `gateway.GetJobStatus.terminal`: PASS (`DONE`)
  - `gateway.GetJobResult.terminal_ready`: PASS (`DONE` + checksum match)
  - `gateway.GetJobResult.worker_signature`: PASS
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`: PASS
  - `submit_failure_case`: PASS
  - `gateway.GetJobStatus.running_seen`: PASS
  - `gateway.GetJobStatus.failed_terminal`: PASS (`FAILED`)
  - `gateway.GetJobStatus.failure_reason`: PASS (`simulated_failure force-fail ...`)
  - `gateway.GetJobResult.failed_ready`: PASS (`FAILED` + checksum match)
  - `gateway.GetJobResult.failure_summary`: PASS
- `conda run -n grpc python scripts/smoke_live_stack.py`: PASS (wrapper compatibility)

## Known gaps/blockers

- No functional blockers identified for this coverage milestone.
- Residual risk: compatibility wrappers can hide stale command usage if not removed on schedule after Design B/load-generator stabilization.

## Timing/race observations

- All three live smokes passed with no observed regressions in terminal/result consistency after adding unit coverage.
- Success path still showed `RUNNING` before terminal `DONE`; failure path still showed `RUNNING` before terminal `FAILED`.
- Retry waits in worker remain non-deterministic by design (full jitter), while bounded by locked backoff window caps.

## Next task (single target)

Add deterministic automated coverage for worker `_report_with_retry` interrupt/error paths (stop-event interruption between attempts and transient `grpc.RpcError` retry flow), without changing runtime semantics.

## Definition of done for next task

- Add focused automated test(s) for:
  - stop-event interruption causing retry loop early exit, and
  - retry continuation across transient `grpc.RpcError` outcomes.
- Keep worker retry defaults/config surface unchanged.
- Keep existing deterministic retry tests and live smokes green.
- Update handoff docs with command evidence and residual risk notes.
