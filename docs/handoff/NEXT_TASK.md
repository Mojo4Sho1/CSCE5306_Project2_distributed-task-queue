# Next Task

**Last updated:** 2026-02-18  
**Owner:** Joe + Codex

## Task summary

Execute full Design A live-stack integration validation for implemented public/internal services and harden remaining cross-service behavior gaps.

## Why this task is next

- Gateway public API orchestration is now implemented and Gateway-focused behavior checks are passing.
- The highest remaining risk is integration drift under real inter-service networking/runtime conditions (not in-process fakes).
- End-to-end validation is required before moving into benchmark/fairness execution work.

## Scope (in)

- Run and validate full Design A stack with implemented Gateway using live probes.
- Validate submit/status/result/cancel/list flows through real service-to-service RPC paths.
- Add one focused integration smoke covering submit -> dispatch/fetch -> report outcome -> terminal result retrieval.
- Investigate and document any observed cross-service anomalies (status/result mismatch, cancel race drift, timeout regressions).
- Update handoff docs with concrete command outputs, pass/fail evidence, and residual risk notes.

## Scope (out)

- Design B implementation work.
- Proto/schema/contract changes.
- Fairness benchmark execution/report generation.
- Production-grade reliability features (durability, lease/ack queue model, etc.).

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests in this repo.
- Prefer explicit command form:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc pytest` (if/when pytest suites are added)
- Live-stack checks require running Design A services with configured upstream addresses:
  - `JOB_SERVICE_ADDR`
  - `QUEUE_SERVICE_ADDR`
  - `RESULT_SERVICE_ADDR`
  - `COORDINATOR_ADDR`

## Implementation notes

- Treat `docs/spec/state-machine.md` and `docs/spec/error-idempotency.md` as primary lock references for integration drift triage.
- Preserve canonical-status-first logic for result readiness in all integration checks.
- Validate queued-cancel remove-miss fallback and terminal-envelope consistency under realistic timing/race windows.
- Keep smoke checks deterministic and reproducible (fixed small workloads, explicit timeouts).

## Acceptance criteria (definition of done)

- `scripts/smoke_live_stack.py` passes against a running Design A stack with implemented Gateway behavior.
- Integration smoke demonstrates end-to-end terminalization path and successful `GetJobResult` retrieval on terminal job.
- Any failures are documented with exact commands, timestamps, and root-cause hypotheses in `CURRENT_STATUS.md`.
- Handoff docs are updated with concrete evidence and clearly stated next technical risk.

## Verification checklist

- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Bring up Design A stack and run `conda run -n grpc python scripts/smoke_live_stack.py`.
- [ ] Add/run one integration smoke covering submit -> execution outcome -> terminal result retrieval.
- [ ] Record concrete command outputs and pass/fail notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Live-stack timing may expose transient races not seen in in-process smoke tests.
- Terminal status/result consistency anomalies can surface under cancellation/execution race windows.
- Short internal RPC deadlines may need tuning if real container startup or network jitter causes false `UNAVAILABLE` paths.
