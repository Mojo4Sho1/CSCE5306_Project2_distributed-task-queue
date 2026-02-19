# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Design A worker-runtime execution path terminalization through the real worker process.

## Completed in current focus

- Implemented real assignment handling in `services/worker/worker.py`:
  - deterministic runtime simulation for assigned jobs,
  - deterministic output envelope generation,
  - checksum generation (`sha256(output_bytes)`),
  - `ReportWorkOutcome` submission to Coordinator,
  - bounded report retry with exponential backoff (`100ms`, `200ms`, `400ms`, cap `1000ms`, max `4` attempts).
- Preserved worker heartbeat/fetch control loop and integrated execution/reporting into the same deterministic loop.
- Updated `scripts/smoke_integration_terminal_path.py` to validate terminalization through the actual worker process:
  - submit via Gateway only,
  - observe `RUNNING` state at least once,
  - observe terminal state,
  - verify `GetJobResult` readiness and checksum correctness,
  - verify worker signature appears in terminal `output_summary`.
- Retained and re-ran `scripts/smoke_live_stack.py` for baseline API/internal reachability coverage.

## Passing checks

- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`D:\Programming\anaconda3\envs\grpc\python.exe`)
- `docker compose up --build -d`: PASS
- `docker compose ps`: PASS
  - `gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `Up (... healthy)`.
- `conda run -n grpc python -m py_compile services/worker/worker.py scripts/smoke_integration_terminal_path.py`: PASS
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
- `docker compose logs worker | Select-String -Pattern "worker.execute.begin|worker.report.response|worker.execute.complete"`: PASS
  - execution + accepted outcome report observed for live submitted jobs.

## Known gaps/blockers

- Gateway/Coordinator/Worker unary deadlines and retry knobs remain partially hard-coded at call sites and are not yet centralized in shared constants/config.
- No dedicated failure-path smoke for worker-reported `FAILED` outcome yet; current live smoke validates deterministic success path terminalization.

## Timing/race observations

- From `docker compose logs worker | Select-String -Pattern "worker.execute.begin|worker.report.response|worker.execute.complete"`:
  - `job_id=91278825-6b4e-4392-a85f-95e053d52add`: `worker.execute.begin` at `1771512969879`, `worker.report.response accepted=true` at `1771512970004` (~125ms end-to-end simulated execution + report).
  - `job_id=35d97f7a-1dc1-4600-9464-3b17a507a3a4`: same sequence completed on first report attempt.
- In this run, no duplicate terminal outcome reports and no terminal-race rejection were observed in worker log sample.

## Next task (single target)

Centralize internal RPC deadline/retry defaults and apply them consistently across Gateway/Coordinator/Worker call sites.

## Definition of done for next task

- Shared constants/config own default unary deadlines and retry profile values used by Gateway/Coordinator/Worker internal clients.
- Service call sites use shared defaults (with clear override points) instead of scattered literals.
- Live smokes still pass with no behavioral regression.
- Handoff/spec/runtime docs reflect any config-surface changes.
