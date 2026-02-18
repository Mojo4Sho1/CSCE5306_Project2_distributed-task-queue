# Current Status

**Last updated:** 2026-02-18  
**Owner:** Joe + Codex

## Current focus

Gateway service (`TaskQueuePublicService`) v1 orchestration behavior is now implemented on top of the existing Job/Queue/Result/Coordinator baseline.

## Completed in current focus

- Replaced `services/gateway/servicer.py` skeleton handlers with spec-compliant v1 behavior for all public RPCs:
  - `SubmitJob`: Job `CreateJob` + Queue `EnqueueJob` acceptance path with compensation (`DeleteJobIfStatus`) on enqueue failure.
  - `GetJobStatus`: canonical pass-through reads from Job service (`GetJobRecord`).
  - `GetJobResult`: canonical-status-first readiness; terminal envelope fetch from Result service; `UNAVAILABLE` on terminal-envelope missing/mismatch anomalies.
  - `CancelJob`: queued-cancel path (`RemoveJobIfPresent` -> `StoreResult` -> queued CAS), remove-miss fallback (`SetCancelRequested`), running best-effort cancel, deterministic repeated-terminal behavior.
  - `ListJobs`: pass-through filtering/sort/pagination from Job service (`ListJobRecords`) with public response mapping.
- Added `scripts/smoke_gateway_behavior.py` for focused in-process Gateway behavior checks covering submit compensation, status/result readiness, cancel race paths, and list/error propagation.
- Updated `scripts/smoke_live_stack.py` Gateway probe from skeleton `UNIMPLEMENTED` expectation to implemented behavior checks (`SubmitJob` + `GetJobStatus`).
- Fixed a Gateway logging bug discovered during smoke testing (`logging` reserved `message` key collision in `extra` fields).

## Passing checks

- `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`: PASS (`/Applications/MiniConda/miniconda3/envs/grpc/bin/python`)
- `conda run -n grpc python -m py_compile services/gateway/servicer.py scripts/smoke_gateway_behavior.py scripts/smoke_live_stack.py`: PASS
- `conda run -n grpc python scripts/smoke_gateway_behavior.py`: PASS
  - `submit_accept`: PASS
  - `submit_compensate_on_enqueue_fail`: PASS
  - `get_status`: PASS
  - `get_result_not_ready`: PASS
  - `get_result_terminal_missing`: PASS (`UNAVAILABLE`)
  - `get_result_terminal_mismatch`: PASS (`UNAVAILABLE`)
  - `get_result_terminal_ready`: PASS
  - `cancel_terminal_repeat`: PASS
  - `cancel_queued_path`: PASS
  - `cancel_queued_race_fallback`: PASS
  - `cancel_running_advisory`: PASS
  - `list_passthrough_and_error`: PASS

Note: `grpc` emits startup metric-registration warnings in this environment before test output; checks still pass and behavior assertions are deterministic.

## Known gaps/blockers

- Full live-stack verification (`scripts/smoke_live_stack.py`) was updated but not executed in this session because it requires an already-running Design A stack.
- Gateway currently uses fixed internal per-call timeout (`1.0s`) in code; these are aligned with v1 internal default semantics but not yet centralized in shared runtime constants.
- Worker execution-path coverage (real worker loop with coordinator fetch/outcome on a running stack) still needs integrated smoke validation.

## Next task (single target)

End-to-end Design A live-stack validation and hardening for worker/control-plane + public API integration.

## Definition of done for next task

- Bring up full Design A stack and run `scripts/smoke_live_stack.py` successfully with implemented Gateway checks.
- Add a focused integration smoke that drives real submit -> fetch -> outcome -> terminal result retrieval across Gateway + Coordinator + Worker-compatible paths.
- Capture and document any cross-service race/drift findings with concrete reproduction steps and expected remediation.
- Update handoff docs with command evidence and any newly discovered residual risks.
