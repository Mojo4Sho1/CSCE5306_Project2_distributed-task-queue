# Next Task

**Last updated:** 2026-02-17  
**Owner:** Joe + Codex

## Task summary

Implement `QueueInternalService` from skeleton to spec-compliant v1 behavior for Design A queue primitives.

## Why this task is next

- Runtime/health validation is complete, and Job Service business semantics are now implemented.
- Queue service is the next foundational dependency for both Gateway (`SubmitJob`/queued-cancel paths) and Coordinator (`FetchWork` dispatch path).
- Current Queue RPC handlers still return `UNIMPLEMENTED`.

## Scope (in)

- Implement Queue in-memory data structures and thread-safe mutation paths.
- Implement `EnqueueJob`, `DequeueJob`, and `RemoveJobIfPresent` per locked specs.
- Enforce idempotent enqueue/remove semantics and destructive dequeue behavior.
- Preserve best-effort FIFO semantics with deterministic behavior under single-process access.
- Add/adjust tests or service-level smoke checks to validate queue behavior and core edge cases.
- Record outcomes and any unresolved behavior gaps in handoff docs.

## Scope (out)

- Gateway orchestration across downstream services.
- Coordinator dispatch/rescue/business terminalization flow changes.
- Result service business semantics.
- Job service business semantics (already implemented in current focus).
- API/proto schema changes.
- Fairness benchmark execution/reporting updates.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests in this repo.
- Prefer explicit command form to avoid shell-activation ambiguity:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc pytest` (if/when pytest suites are added)
- Generated stubs available under `generated/`.

## Implementation notes

- Follow ownership rules: Queue Service owns queue membership only (`docs/spec/architecture.md`).
- Respect queue constraints in specs: best-effort FIFO and destructive dequeue model (`docs/spec/api-contracts.md`, `docs/spec/state-machine.md`).
- Keep behavior deterministic under local concurrency and test edge cases first (duplicate enqueue, remove idempotency, dequeue empty queue).

## Acceptance criteria (definition of done)

- `QueueInternalService` RPCs return real responses (no `UNIMPLEMENTED`) for core happy paths.
- `EnqueueJob` is idempotent by `job_id` and does not create duplicate queue entries.
- `DequeueJob` follows destructive dequeue semantics and returns `found=false` when empty.
- `RemoveJobIfPresent` is repeat-safe and deterministic for existing/missing jobs.
- Focused smoke/tests cover enqueue duplicate, dequeue order, remove-before-dequeue, and dequeue-empty paths.
- Handoff docs updated with concrete passing/failing evidence.

## Verification checklist

- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Implement Queue service behavior and remove Queue-specific `UNIMPLEMENTED` responses.
- [ ] Add/run Queue-focused checks covering idempotent enqueue/remove and dequeue semantics.
- [ ] Capture concrete evidence (command outputs and key pass/fail notes) in `CURRENT_STATUS.md`.

## Risks / rollback notes

- Queue mutation semantics can drift from locked destructive/FIFO assumptions if dedup and removal logic are not carefully synchronized.
- Existing skeleton smoke scripts may need selective updates once Queue RPCs stop returning `UNIMPLEMENTED`.
