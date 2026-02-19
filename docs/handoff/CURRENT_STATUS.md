# Current Status

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Current focus

Deterministic coordinator terminal-write idempotency coverage for `ReportWorkOutcome` (first-write-wins, duplicate stability, and conflicting-repeat non-corruption) with live non-regression validation.

## Completed in current focus

- Added deterministic coordinator coverage in `tests/test_coordinator_report_outcome_idempotency.py` for:
  - first terminal write acceptance/persistence for both `DONE` and `FAILED`,
  - duplicate-equivalent repeated reports remaining idempotent/stable,
  - conflicting repeated reports after terminalization not corrupting terminal status/result envelope.
- Implemented test adapters around in-process `JobServicer` and `ResultServicer` to validate behavior contracts without changing runtime semantics.
- Kept coordinator runtime behavior unchanged (`services/coordinator/servicer.py` untouched).
- Updated command/docs references for the new unit module:
  - `README.md`,
  - `scripts/_SCRIPT_INDEX.md`,
  - `tests/_TEST_INDEX.md`.

## Passing checks

- Run timestamp anchor: `2026-02-19 12:23:00 -06:00` (local host clock).
- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`D:\Programming\anaconda3\envs\grpc\python.exe`)
- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`: PASS
  - `Ran 6 tests ... OK`
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`: PASS
  - `Ran 3 tests ... OK`
- `docker compose -f docker/docker-compose.design-a.yml up --build -d`: PASS
- `docker compose -f docker/docker-compose.design-a.yml ps`: PASS
  - `gateway`, `job`, `queue`, `coordinator`, `result`, `worker` all `Up (... healthy)`.
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

## Known gaps/blockers

- No functional blockers identified for this coverage milestone.
- Residual risk: coordinator idempotency unit tests run in-process adapters and deterministic state transitions; they do not capture all live multi-worker concurrency interleavings under heavy churn.

## Timing/race observations

- All three live smokes passed with no observed regressions in terminal/result consistency after adding coordinator idempotency coverage.
- Success path still showed `RUNNING` before terminal `DONE`; failure path still showed `RUNNING` before terminal `FAILED`.
- Repeated/late outcome-report semantics remained first-write-wins per locked state-machine/error-idempotency contracts in deterministic unit coverage.

## Next task (single target)

Kick off Design B implementation baseline by adding runnable Design B skeleton runtime topology (compose + monolith node entrypoint wiring) that preserves frozen v1 external contracts and does not regress Design A.

## Definition of done for next task

- Add Design B runtime scaffold files (compose + node process entrypoint/module structure) with no proto/schema changes.
- Keep Design A command matrix operational and non-regressed.
- Add/update docs for Design B bring-up commands and boundaries.
- Record command evidence and residual risk notes in handoff docs.
