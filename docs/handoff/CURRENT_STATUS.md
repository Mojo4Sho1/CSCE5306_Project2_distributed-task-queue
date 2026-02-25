# Current Status

**Last updated:** 2026-02-25  
**Owner:** Joe + Codex

## Current focus

README onboarding simplification and post-cleanup documentation alignment.

## Completed in current focus

- Reorganized `README.md` for first-time usability with a top-level "choose your path" flow.
- Added a preflight checklist (env, Docker, ports) and concise setup instructions.
- Split execution guidance into:
  - Path A: manual user/demo flow on Design A,
  - Path B: benchmark experiment for A vs B in sequential isolation.
- Explicitly documented that README manual user flow is Design A-only.
- Removed the full repository file tree from README to reduce onboarding noise.
- Renamed and slimmed reproducibility documentation to reduce redundancy:
  - `docs/handoff/REPRODUCIBILITY_RUNBOOK.md` now complements README instead of duplicating command walkthroughs.
- Executed README runtime sanity checks on 2026-02-25:
  - Path A live flow validated (`submit/status/result`) on Design A stack.
  - Path B startup/loop wiring validated in sequential isolation for both designs using non-canonical smoke outputs.
  - Aggregation wiring validated using non-canonical sanity output roots.

## Passing checks

- README command references map to existing scripts/compose files:
  - `docker/docker-compose.design-a.yml`
  - `docker/docker-compose.design-b.yml`
  - `scripts/manual/manual_gateway_client.py`
  - `scripts/loadgen/run_benchmark_scaffold.py`
  - `scripts/loadgen/aggregate_starter_matrix.py`

## Known gaps/blockers

- Retention policy for raw starter-matrix per-run directories is still undecided.

## Active coordination notes

- Overleaf remains the canonical final report source.
- Existing benchmark evidence artifacts should not be overwritten during sanity checks.
- For any sanity-run validation, prefer read-only checks and/or fresh non-colliding run IDs; avoid `--overwrite` unless explicitly intended.

## Next task (single target)

Define and document a retention policy for raw starter-matrix per-run directories, including pruning criteria and what remains canonical evidence.

## Definition of done for next task

- Retention decisions are explicit for:
  - canonical evidence directories,
  - non-canonical sanity outputs,
  - intermediate per-run folders under `results/loadgen/<scenario_id>/`.
- A documented prune/archive workflow exists and is safe by default.
- Handoff docs and README references are synchronized with the policy.
