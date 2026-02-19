# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Implement and validate real worker execution-path terminalization on Design A live stack.

## Why this task is next

- Live-stack Gateway/control-plane integration smoke coverage now passes.
- The highest remaining correctness gap is that the real worker runtime still does not execute/report outcomes.
- Benchmark/fairness work should not proceed until terminalization is verified through the actual worker process.

## Scope (in)

- Implement worker assignment handling in `services/worker/worker.py` for deterministic simulated execution.
- Report terminal outcomes through Coordinator (`ReportWorkOutcome`) with consistent envelope fields.
- Validate submit -> worker fetch -> worker report -> `GetJobResult` terminal retrieval on running Design A stack.
- Add or update live smoke coverage so the terminalization path is tested through the actual worker process.
- Document timing/race observations and residual risks.

## Scope (out)

- Design B implementation changes.
- Proto/schema/contract changes.
- Fairness benchmark report generation.
- Durability/lease/ack redesigns.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests in this repo.
- Prefer explicit command form:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc pytest` (if/when pytest suites are added)
- Run Design A services via `docker compose up --build -d` before live smokes.

## Implementation notes

- Treat `docs/spec/state-machine.md` and `docs/spec/error-idempotency.md` as primary lock references for integration drift triage.
- Preserve canonical-status-first logic for result readiness in all integration checks.
- Keep worker behavior deterministic/reproducible (fixed runtime simulation and explicit timeouts).
- Preserve at-least-once semantics and first-terminal-wins behavior.

## Acceptance criteria (definition of done)

- Worker service reports outcomes for fetched assignments in live stack.
- Live smoke confirms terminal status and terminal envelope retrieval via public API for worker-processed jobs.
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `CURRENT_STATUS.md`.
- Handoff docs updated with concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Implement worker assignment execution + `ReportWorkOutcome` path.
- [ ] Verify conda execution path using `conda run -n grpc python -c "import grpc,sys; print(sys.executable)"`.
- [ ] Run `docker compose up --build -d` and confirm healthy services with `docker compose ps`.
- [ ] Run live smoke that proves worker-driven terminalization and `GetJobResult` readiness.
- [ ] Record command outputs and residual risk notes in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- Worker/Coordinator race timing can expose duplicate outcome reports; keep idempotent handling explicit.
- Short RPC deadlines may create false-negative `UNAVAILABLE` outcomes under container jitter.
- Skeleton-era assumptions in current worker loop may need cleanup to avoid behavioral regressions.
