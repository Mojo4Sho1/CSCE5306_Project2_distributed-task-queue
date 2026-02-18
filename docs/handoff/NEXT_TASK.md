# Next Task

**Last updated:** 2026-02-18  
**Owner:** Joe + Codex

## Task summary

Implement `ResultInternalService` from skeleton to spec-compliant v1 behavior for terminal result envelopes in Design A.

## Why this task is next

- Runtime/health validation is complete, and Job/Queue service business semantics are now implemented.
- Result service is required for terminal envelope storage and retrieval contracts used by Gateway and Coordinator terminalization flows.
- Current Result RPC handlers still return `UNIMPLEMENTED`.

## Scope (in)

- Implement Result in-memory data structures and thread-safe mutation paths.
- Implement `StoreResult` and `GetResult` per locked specs.
- Enforce terminal-status-only validation for `StoreResult` (`DONE`, `FAILED`, `CANCELED`) with `INVALID_ARGUMENT` on non-terminal statuses.
- Enforce idempotent conflict semantics for repeated `StoreResult` calls (`stored`, `already_exists`, `current_terminal_status`).
- Enforce output size bounds (`MAX_OUTPUT_BYTES`) and deterministic response fields.
- Add/adjust tests or service-level smoke checks to validate result behavior and edge cases.
- Record outcomes and any unresolved behavior gaps in handoff docs.

## Scope (out)

- Gateway orchestration across downstream services.
- Coordinator dispatch/rescue/business terminalization flow changes.
- Queue/Job business semantics (already implemented in current focus).
- API/proto schema changes.
- Fairness benchmark execution/reporting updates.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests in this repo.
- Prefer explicit command form to avoid shell-activation ambiguity:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc pytest` (if/when pytest suites are added)
- Generated stubs available under `generated/`.

## Implementation notes

- Follow ownership rules: Result Service owns terminal output envelope storage/retrieval (`docs/spec/architecture.md`).
- Respect terminal/result semantics in specs (`docs/spec/api-contracts.md`, `docs/spec/state-machine.md`, `docs/spec/error-idempotency.md`).
- Keep behavior deterministic under local concurrency and test edge cases first (invalid terminal status, duplicate store, oversized output).

## Acceptance criteria (definition of done)

- `ResultInternalService` RPCs return real responses (no `UNIMPLEMENTED`) for core happy paths.
- `StoreResult` accepts terminal statuses only and rejects invalid status with `INVALID_ARGUMENT`.
- Repeated store attempts are idempotent and surface conflict visibility via response fields.
- `GetResult` returns `found=false` for unknown `job_id` and deterministic envelope fields for stored records.
- Focused smoke/tests cover invalid status, duplicate store, get-missing, and output-size bound behavior.
- Handoff docs updated with concrete passing/failing evidence.

## Verification checklist

- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Implement Result service behavior and remove Result-specific `UNIMPLEMENTED` responses.
- [ ] Add/run Result-focused checks covering terminal validation, idempotent store, and retrieval semantics.
- [ ] Capture concrete evidence (command outputs and key pass/fail notes) in `CURRENT_STATUS.md`.

## Risks / rollback notes

- Result consistency semantics can drift from locked terminal-envelope rules if status validation/idempotency handling is not strict.
- Existing skeleton smoke scripts may need selective updates once Result RPCs stop returning `UNIMPLEMENTED`.
