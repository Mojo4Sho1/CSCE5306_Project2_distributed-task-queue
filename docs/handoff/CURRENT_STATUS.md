# Current Status

**Last updated:** 2026-02-24  
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

## Passing checks

- README command references map to existing scripts/compose files:
  - `docker/docker-compose.design-a.yml`
  - `docker/docker-compose.design-b.yml`
  - `scripts/manual/manual_gateway_client.py`
  - `scripts/loadgen/run_benchmark_scaffold.py`
  - `scripts/loadgen/aggregate_starter_matrix.py`

## Known gaps/blockers

- Path-command runtime sanity checks (README Path A and Path B) are not yet executed after the reorganization.
- Retention policy for raw starter-matrix per-run directories is still undecided.

## Active coordination notes

- Overleaf remains the canonical final report source.
- Existing benchmark evidence artifacts should not be overwritten during sanity checks.
- For any sanity-run validation, prefer read-only checks and/or fresh non-colliding run IDs; avoid `--overwrite` unless explicitly intended.

## Next task (single target)

Execute a non-destructive README path sanity check pass for Path A and Path B command flows, then capture outcomes and follow-on retention-policy actions.

## Definition of done for next task

- README Path A commands are validated end-to-end on a live Design A stack.
- README Path B workflow is validated at least through stack startup, scenario invocation smoke, and aggregation command wiring.
- Validation steps do not overwrite canonical notebook/reporting artifacts.
- Any command drift discovered is fixed in docs immediately.
- Retention-policy follow-up items remain explicitly tracked.
