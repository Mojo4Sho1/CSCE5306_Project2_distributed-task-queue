# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Execute a reproducible, small multi-seed benchmark matrix (Design A + Design B) using the current loadgen scaffold and produce report-ready summary evidence.

## Why this task is next

- Loadgen contract hardening is now in place (health precheck, latency precision, terminal-throughput summary, and collision-safe artifact handling).
- Remaining work is controlled execution and evidence capture for A/B analysis quality.
- This closes the loop from tooling readiness to benchmark-result generation.

## Scope (in)

- Run a minimal but representative live benchmark matrix for both designs:
  - at least one balanced profile per design,
  - multiple seeds per selected scenario.
- Use pre-run connectivity gate and deterministic artifact policy:
  - `--precheck-health` for live runs,
  - `--overwrite` only when intentionally replacing a deterministic run directory.
- Capture and validate produced artifacts:
  - `rows.jsonl`, `rows.csv`, `summary.json`, `summary.csv`, `metadata.json`.
- Generate concise report-ready summary snippets from produced artifacts:
  - throughput,
  - latency percentiles (p50/p95/p99),
  - grpc error rates,
  - terminal throughput.
- Update docs/handoff with exact commands, run IDs, and observed caveats.

## Scope (out)

- Proto/schema changes.
- Service business-logic rewrites.
- Fairness lock changes.
- Advanced loadgen feature work beyond execution/reporting of existing scaffold.

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
- Record any environment-related deviations (for example connectivity limits) in handoff docs.

## Acceptance criteria (definition of done)

- Live benchmark runs complete for both designs with multiple seeds.
- Artifacts exist and are traceable by scenario/run ID for each executed run.
- A concise comparison summary is generated from actual produced artifacts.
- Documentation reflects final run commands, locations, and caveats.
- Handoff docs provide concrete pass/fail evidence and residual risks.

## Verification checklist

- [ ] Run deterministic unit baseline:
  - `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`
- [ ] Verify Design A live readiness and execute selected live scenario seeds.
- [ ] Verify Design B live readiness and execute selected live scenario seeds.
- [ ] Confirm artifact set completeness for each run directory.
- [ ] Produce and record summary metrics for report usage.
- [ ] Update `docs/handoff/CURRENT_STATUS.md` with exact command outputs and caveats.

## Risks / rollback notes

- Live A/B runs are environment-sensitive (stack health, host resources, network stability).
- Multi-seed execution can be time-consuming; partial-run artifact interpretation must be explicit.
- Overwrite misuse can still replace evidence if used without intent; keep command logs in handoff.
