# Next Task

**Last updated:** 2026-02-17  
**Owner:** Joe + Codex

## Task summary

Validate runtime startup/health behavior in a dependency-complete (conda) environment using the now-normalized runtime-spec env keys.

## Why this task is next

- `common/config.py`, `docker-compose.yml`, and smoke scripts are now aligned to runtime-spec env keys.
- The remaining risk is execution-time validation in an environment where `grpcio` and runtime deps are available.

## Scope (in)

- In conda/runtime environment, bring up services via `docker compose up` and verify startup behavior.
- Validate container healthchecks transition as expected for all six services.
- Run representative smoke checks against running services.
- Record validation outcomes and any runtime issues in handoff docs.

## Scope (out)

- Worker business execution logic and cross-service orchestration behavior.
- Fairness/performance benchmark execution and report updates.
- API/proto schema changes.
- Additional env-key schema changes (normalization is already complete).

## Dependencies / prerequisites

- Conda environment access with project dependencies (`grpcio` and generated stubs importable).
- Docker/Compose runtime available on the target machine.

## Implementation notes

- Keep validation scope focused on runtime bring-up, healthchecks, and observable readiness.
- Capture concrete failure evidence (service name, log snippet, failing healthcheck/smoke step).

## Acceptance criteria (definition of done)

- `docker compose up` completes with all Design A services started.
- Healthchecks pass using shared `scripts.healthcheck` wiring.
- Representative smoke probes confirm expected skeleton behavior under live runtime.
- Handoff docs are updated with pass/fail evidence and any remaining blockers.

## Verification checklist

- [ ] Activate conda/runtime environment with project dependencies.
- [ ] `docker compose up` starts all services without config-key errors.
- [ ] Container healthchecks pass for Gateway/Job/Queue/Coordinator/Result/Worker.
- [ ] Run representative smoke probes and confirm expected outcomes.

## Risks / rollback notes

- Runtime failures may surface only during live dependency-backed execution.
- Service startup fallback behavior may still hide strict config contract violations and may require follow-up hardening.
