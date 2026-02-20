# Next Task

**Last updated:** 2026-02-20  
**Owner:** Joe + Codex

## Task summary

Execute the full starter fairness matrix for Design A and Design B and generate consolidated, report-ready A/B comparison outputs.

## Why this task is next

- A small balanced multi-seed matrix is now complete with validated artifacts and per-design summaries.
- Remaining risk is under-sampling: claims currently rely on a narrow workload slice.
- Final report quality now depends on matrix breadth, aggregation discipline, and visualization from produced artifacts.

## Scope (in)

- Run the full starter matrix from `docs/spec/fairness-evaluation.md` for both designs:
  - load levels: `low`, `medium`, `high`,
  - mixes: `submit_heavy`, `poll_heavy`, `balanced`,
  - repeated seeds per scenario (minimum 3 recommended for this pass).
- Use pre-run connectivity gate and deterministic artifact policy:
  - `--precheck-health` for live runs,
  - avoid `--overwrite` except deliberate reruns with explicit note.
- Build a reproducible aggregation pass across run directories producing:
  - per-method throughput and latency percentile comparison (A vs B),
  - grpc non-OK/error-code rates by method,
  - terminal-job throughput comparison by scenario and design,
  - seed-to-seed variability stats.
- Update notebook and handoff docs with generated tables/plots and run-traceable inputs.

## Scope (out)

- Proto/schema changes.
- Service business-logic rewrites.
- Fairness lock changes.
- New loadgen feature development outside execution/aggregation/reporting.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests.
- Start healthy stacks before live runs:
  - `docker compose -f docker/docker-compose.design-a.yml up --build -d`
  - `docker compose -f docker/docker-compose.design-b.yml up --build -d`
- Keep scenario config and fairness controls aligned with locked specs.

## Implementation notes

- Follow `docs/spec/fairness-evaluation.md` for parity controls and reporting scope.
- Preserve deterministic run naming; do not silently replace artifacts.
- Treat `--overwrite` as an explicit operator decision only.
- Keep Design A and Design B runs isolated in time (no overlapping load runs).
- Record environment-related deviations (for example sandboxed localhost permission constraints) in handoff docs.

## Acceptance criteria (definition of done)

- Full 9-scenario starter matrix runs complete for both designs with repeated seeds.
- Artifact sets are complete and traceable for every executed run.
- Consolidated comparison outputs (tables and at least one plot set) are generated from `summary.json`/`rows.*`.
- Documentation reflects exact execution batches, aggregation commands, and caveats.
- Handoff docs include concrete evidence plus remaining risks to external validity.

## Verification checklist

- [ ] Run deterministic unit baseline:
  - `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`
- [ ] Verify both design stacks are healthy (`docker compose ... ps`) before each batch.
- [ ] Execute all 9 starter scenarios for Design A with repeated seeds.
- [ ] Execute all 9 starter scenarios for Design B with repeated seeds.
- [ ] Confirm artifact completeness for every run directory.
- [ ] Run aggregation step and publish consolidated A/B tables.
- [ ] Update notebook/report visuals from generated artifacts.
- [ ] Update `docs/handoff/CURRENT_STATUS.md` with commands, run IDs, outputs, and caveats.

## Risks / rollback notes

- Live A/B runs are environment-sensitive (stack health, host resources, network stability).
- Full matrix execution is time-consuming; interruption handling and partial-batch labeling must be explicit.
- Compose project-name collision can cause teardown races when A/B compose files are controlled in parallel; prefer sequential `down`.
- Overwrite misuse can replace deterministic evidence; keep command logs and explicit rerun notes in handoff.
