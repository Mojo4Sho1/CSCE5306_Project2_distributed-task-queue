# Next Task

**Last updated:** 2026-02-18  
**Owner:** Joe + Codex

## Task summary

Implement `TaskQueuePublicService` (Gateway) from skeleton to spec-compliant v1 orchestration behavior for submit/status/result/cancel/list in Design A.

## Why this task is next

- Runtime/health validation is complete, and Job/Queue/Result/Coordinator internal services now implement core v1 behavior.
- Gateway is now the remaining major service with client-facing RPC handlers still at skeleton-level `UNIMPLEMENTED`.
- Public API completion is required for end-to-end behavior validation and Design A parity scope.

## Scope (in)

- Implement Gateway orchestration logic for:
  - `SubmitJob` create + enqueue + compensation (`DeleteJobIfStatus`) on partial failure,
  - `GetJobStatus` canonical reads from Job service,
  - `GetJobResult` canonical-status-first behavior with terminal-envelope retrieval from Result service,
  - `CancelJob` queued-cancel and running-cancel semantics per locked contracts,
  - `ListJobs` pass-through filtering/sort/pagination semantics from Job service.
- Enforce locked gRPC status/error/idempotency behavior for public methods.
- Add/adjust smoke checks for Gateway behavior and key edge cases.
- Record outcomes and unresolved behavior gaps in handoff docs.

## Scope (out)

- Worker execution-loop behavior changes beyond current control-plane compatibility.
- Job/Queue/Result/Coordinator internal semantics already implemented.
- API/proto schema changes.
- Fairness benchmark execution/reporting updates.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests in this repo.
- Prefer explicit command form to avoid shell-activation ambiguity:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc pytest` (if/when pytest suites are added)
- Gateway requires configured upstream addresses:
  - `JOB_SERVICE_ADDR`
  - `QUEUE_SERVICE_ADDR`
  - `RESULT_SERVICE_ADDR`

## Implementation notes

- Follow ownership rules in `docs/spec/architecture.md`:
  - Gateway owns public API routing/orchestration,
  - Job owns canonical status,
  - Queue owns queue membership,
  - Result owns terminal envelopes.
- Respect submit/cancel/result consistency contracts in:
  - `docs/spec/state-machine.md`
  - `docs/spec/api-contracts.md`
  - `docs/spec/error-idempotency.md`
- Keep behavior deterministic under local concurrency and validate race/edge paths first.

## Acceptance criteria (definition of done)

- `TaskQueuePublicService` RPCs return real responses (no `UNIMPLEMENTED`) for core paths.
- `SubmitJob` follows create+enqueue acceptance rules with compensation on partial failure.
- `GetJobStatus` and `ListJobs` return canonical/deterministic data per locked contracts.
- `GetJobResult` enforces canonical-status-first readiness and terminal-envelope mismatch handling.
- `CancelJob` follows queued/running terminalization semantics and deterministic repeated-call behavior.
- Focused smoke/tests cover submit/status/result/cancel/list core paths and edge cases.
- Handoff docs updated with concrete passing/failing evidence.

## Verification checklist

- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Implement Gateway service behavior and remove Gateway-specific `UNIMPLEMENTED` responses.
- [ ] Add/run Gateway-focused checks covering submit acceptance/compensation, status/result readiness, cancel behavior, and list semantics.
- [ ] Capture concrete evidence (command outputs and key pass/fail notes) in `CURRENT_STATUS.md`.

## Risks / rollback notes

- Submit compensation failure can leave create/enqueue partial-state anomalies.
- Cancel-path ordering drift (`RemoveJobIfPresent` / `StoreResult` / Job CAS) can create status/result mismatch anomalies.
- Terminal status/result consistency handling must preserve locked `UNAVAILABLE` behavior for missing envelopes.
