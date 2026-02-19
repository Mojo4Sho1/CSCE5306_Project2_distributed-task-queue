# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Design A worker failure-path integration coverage (`RUNNING -> FAILED`) and terminal/result consistency validation.

## Completed in current focus

- Added deterministic worker-side failure trigger in `services/worker/worker.py`:
  - when `job_type` contains `force-fail`, worker reports `JOB_OUTCOME_FAILED`,
  - includes deterministic `failure_reason`, `output_summary`, `output_bytes`, and checksum.
- Added dedicated failure-path integration smoke:
  - `scripts/smoke_integration_failure_path.py`,
  - validates `RUNNING -> FAILED`, `GetJobStatus.failure_reason`, and `GetJobResult` terminal-envelope consistency.
- Updated `README.md`:
  - added live smoke workflow section including the new failure-path smoke command,
  - documented deterministic `force-fail` marker behavior for integration testing,
  - updated repo structure list with new smoke script.

## Passing checks

- Run timestamp anchor: `2026-02-19 11:02:40 -06:00` (local host clock).
- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`D:\Programming\anaconda3\envs\grpc\python.exe`)
- `conda run -n grpc python -m py_compile services/worker/worker.py scripts/smoke_integration_failure_path.py`: PASS
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
- `conda run -n grpc python scripts/smoke_integration_failure_path.py`: PASS
  - `submit_failure_case`: PASS
  - `gateway.GetJobStatus.running_seen`: PASS
  - `gateway.GetJobStatus.failed_terminal`: PASS (`FAILED`)
  - `gateway.GetJobStatus.failure_reason`: PASS (`simulated_failure force-fail ...`)
  - `gateway.GetJobResult.failed_ready`: PASS (`FAILED` + checksum match)
  - `gateway.GetJobResult.failure_summary`: PASS

## Known gaps/blockers

- Worker retry implementation remains deterministic exponential backoff without explicit jitter injection (locked defaults are preserved for initial/multiplier/cap/attempts, but jitter behavior is not yet modeled).

## Timing/race observations

- Success-path terminal smoke remained stable after adding failure trigger; sampled terminal status was `DONE` with checksum match.
- Failure-path smoke consistently observed `RUNNING` before terminal `FAILED`, and both `failure_reason` and result summary carried the deterministic marker.

## Next task (single target)

Add full-jitter behavior to worker `ReportWorkOutcome` retry waits while preserving locked retry defaults (initial/multiplier/cap/attempts), then validate non-regression via live smokes.

## Definition of done for next task

- Worker report-retry waits include full jitter derived from bounded exponential backoff window.
- Existing timeout/retry config defaults and env controls remain unchanged.
- `smoke_live_stack.py`, `smoke_integration_terminal_path.py`, and `smoke_integration_failure_path.py` pass after jitter change.
- Handoff docs updated with command evidence and any flake/risk notes.
