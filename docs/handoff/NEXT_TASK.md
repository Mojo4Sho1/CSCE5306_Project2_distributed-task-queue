# Next Task

**Last updated:** 2026-02-25  
**Owner:** Joe + Codex
**Status:** Completed on 2026-02-25

## Task summary

Completed a non-destructive sanity-check pass for README Path A and Path B workflows, verified command wiring, and documented outcomes.

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

- [x] Validate Path A startup commands (`design-a` compose up/ps) and manual client commands (`submit/status/result`).
- [x] Validate Path B startup commands for both designs (`design-a` then `design-b`) and starter-matrix invocation loops.
- [x] Validate aggregation command wiring (`aggregate_starter_matrix.py`) against current paths.
- [x] Confirm no canonical artifact replacement occurred (especially under `results/loadgen/analysis/starter_matrix_2026-02-20/`).
- [x] Patch README/docs immediately if any command/path drift is discovered.
- [x] Keep retention-policy follow-up explicitly tracked after sanity pass.

## Execution results (2026-02-25)

- Path A live validation passed:
  - `docker compose -f docker/docker-compose.design-a.yml up --build -d`
  - `docker compose -f docker/docker-compose.design-a.yml ps`
  - `conda run -n grpc python scripts/manual/manual_gateway_client.py submit --spec-file examples/jobs/hello_distributed.json`
  - `conda run -n grpc python scripts/manual/manual_gateway_client.py status --job-id a89e08d0-a323-4acd-838b-9f66d6610414`
  - `conda run -n grpc python scripts/manual/manual_gateway_client.py result --job-id a89e08d0-a323-4acd-838b-9f66d6610414`
  - Job reached `DONE` and returned a ready result payload.
- Path B sequential validation passed:
  - Design A stack startup/shutdown commands worked as documented.
  - Design B stack startup/shutdown commands worked as documented.
  - Starter-matrix loop wiring validated via one-scenario smoke per design using non-canonical output root:
    - `design_a_s_low_balanced`
    - `design_b_s_low_balanced`
  - Both scenario smoke runs emitted deterministic run artifacts under `results/loadgen/sanity_readme_2026-02-25/`.
- Aggregation wiring passed with non-canonical input/output roots:
  - `conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py --results-root results/loadgen/sanity_readme_2026-02-25 --output-dir results/loadgen/analysis/sanity_readme_2026-02-25`
- Command/path drift findings:
  - No README command drift discovered; no README command changes required.
- Canonical artifact protection:
  - Verified `results/loadgen/analysis/starter_matrix_2026-02-20/` file inventory remained unchanged.

## Follow-on task (still open)

- Define and document retention policy for raw starter-matrix per-run directories (what to keep, what can be pruned, and when).

## Acceptance criteria (definition of done)

- [x] README Path A commands are executable as documented.
- [x] README Path B commands are executable as documented (at minimum as smoke-level wiring checks).
- [x] No existing canonical reporting/notebook artifacts are overwritten.
- [x] Any discovered command drift is fixed in-repo and documented.
- [x] Follow-on retention-policy work remains visible in handoff docs.

## Verification checklist

- [x] `docker compose -f docker/docker-compose.design-a.yml ps`
- [x] `docker compose -f docker/docker-compose.design-b.yml ps`
- [x] `conda run -n grpc python scripts/manual/manual_gateway_client.py --help`
- [x] `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --help`
- [x] `conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py --help`
- [x] `find results/loadgen/analysis/starter_matrix_2026-02-20 -maxdepth 2 -type f | sort`
- [x] `git status --short` shows only intentional docs (and optional sanity-log) changes.

## Risks / rollback notes

- Running heavy live benchmarks during sanity checks can accidentally create or replace artifacts.
- Use explicit non-canonical run targets and avoid overwrite flags to reduce risk.
- If accidental changes occur, restore canonical artifact state from VCS history before closing the task.
