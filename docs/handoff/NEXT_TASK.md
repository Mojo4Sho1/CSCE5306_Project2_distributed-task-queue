# Next Task

**Last updated:** 2026-02-24  
**Owner:** Joe + Codex

## Task summary

Run a non-destructive sanity-check pass for the README "choose your path" workflows (Path A and Path B), then document results and any command corrections.

## Why this task is next

- README was reorganized to be first-time-user friendly and now serves as the primary execution runbook.
- We need to confirm the exact documented command paths still execute as intended.
- Validation must avoid rewriting existing benchmark artifacts used by notebook/reporting outputs.

## Scope (in)

- Validate README Path A (Design A manual user/demo flow).
- Validate README Path B (A/B benchmark workflow wiring and command correctness).
- Record any command drift and update docs in the same change set.
- Preserve existing canonical evidence artifacts during validation.

## Scope (out)

- Runtime behavior changes.
- Proto/API contract changes.
- Full benchmark regeneration intended to replace canonical evidence.

## Dependencies / prerequisites

- `README.md` (new choose-your-path structure)
- `docs/handoff/REPRODUCIBILITY_RUNBOOK.md`
- `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`

## Implementation notes

- Prefer non-destructive checks:
  - stack boot/health checks,
  - manual submit/status/result smoke,
  - loadgen command wiring verification.
- Do not use `--overwrite` unless explicit artifact replacement is intentionally approved.
- If live loadgen emits new artifacts during sanity checks, use fresh, clearly non-canonical paths/IDs.

## Subtasks

- [ ] Validate Path A startup commands (`design-a` compose up/ps) and manual client commands (`submit/status/result`).
- [ ] Validate Path B startup commands for both designs (`design-a` then `design-b`) and starter-matrix invocation loops.
- [ ] Validate aggregation command wiring (`aggregate_starter_matrix.py`) against current paths.
- [ ] Confirm no canonical artifact replacement occurred (especially under `results/loadgen/analysis/starter_matrix_2026-02-20/`).
- [ ] Patch README/docs immediately if any command/path drift is discovered.
- [ ] Keep retention-policy follow-up explicitly tracked after sanity pass.

## Acceptance criteria (definition of done)

- README Path A commands are executable as documented.
- README Path B commands are executable as documented (at minimum as smoke-level wiring checks).
- No existing canonical reporting/notebook artifacts are overwritten.
- Any discovered command drift is fixed in-repo and documented.
- Follow-on retention-policy work remains visible in handoff docs.

## Verification checklist

- [ ] `docker compose -f docker/docker-compose.design-a.yml ps`
- [ ] `docker compose -f docker/docker-compose.design-b.yml ps`
- [ ] `conda run -n grpc python scripts/manual/manual_gateway_client.py --help`
- [ ] `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --help`
- [ ] `conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py --help`
- [ ] `find results/loadgen/analysis/starter_matrix_2026-02-20 -maxdepth 2 -type f | sort`
- [ ] `git status --short` shows only intentional docs (and optional sanity-log) changes.

## Risks / rollback notes

- Running heavy live benchmarks during sanity checks can accidentally create or replace artifacts.
- Use explicit non-canonical run targets and avoid overwrite flags to reduce risk.
- If accidental changes occur, restore canonical artifact state from VCS history before closing the task.
