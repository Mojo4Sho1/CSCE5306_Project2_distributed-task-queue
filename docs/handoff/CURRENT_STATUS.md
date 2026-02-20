# Current Status

**Last updated:** 2026-02-20  
**Owner:** Joe + Codex

## Current focus

Small live multi-seed benchmark matrix execution (Design A + Design B) is completed with artifact validation and summary extraction.

## Completed in current focus

- Added balanced live scenario files for explicit two-seed execution per design:
  - `scripts/loadgen/scenarios/design_a_balanced_seed5306.json`
  - `scripts/loadgen/scenarios/design_a_balanced_seed5307.json`
  - `scripts/loadgen/scenarios/design_b_balanced_seed5306.json`
  - `scripts/loadgen/scenarios/design_b_balanced_seed5307.json`
- Executed live benchmark runs with precheck enabled:
  - `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_balanced_seed5306.json --output-dir results/loadgen --live-traffic --precheck-health`
  - `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_balanced_seed5307.json --output-dir results/loadgen --live-traffic --precheck-health`
  - `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_seed5306.json --output-dir results/loadgen --live-traffic --precheck-health`
  - `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_seed5307.json --output-dir results/loadgen --live-traffic --precheck-health`
- Run IDs generated:
  - `design_a_balanced_seed5306-r00-88c6b30ac8`
  - `design_a_balanced_seed5307-r00-3c78888ca7`
  - `design_b_balanced_seed5306-r00-19271f3523`
  - `design_b_balanced_seed5307-r00-976e24e878`
- Artifact completeness verified for each run directory:
  - `rows.jsonl`, `rows.csv`, `summary.json`, `summary.csv`, `metadata.json` all present.
- Produced and recorded report-ready metrics from `summary.json` for throughput, p50/p95/p99 latencies, grpc non-OK rates, and terminal throughput.

## Passing checks

- Run timestamp anchor: `2026-02-20` local session.
- `TMPDIR=/tmp/codex-loadgen-tests conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`: PASS
  - `Ran 9 tests ... OK`
- Docker stack health confirmed before run execution:
  - `docker compose -f docker/docker-compose.design-a.yml ps`
  - `docker compose -f docker/docker-compose.design-b.yml ps`
  - all services reported `healthy`.
- Live run outputs:
  - each run returned `row_count: 240` with non-empty run artifact paths.
- Design-level summary averages (2 seeds each, `measure_seconds=20`):
  - `A_microservices`:
    - avg terminal throughput: `3.55 rps`
    - avg p95 latency: `SubmitJob=20.626 ms`, `GetJobStatus=19.596 ms`, `GetJobResult=19.648 ms`, `CancelJob=16.441 ms`
    - avg grpc non-OK rate: `0.0` for Submit/Status/Result/Cancel
  - `B_monolith`:
    - avg terminal throughput: `3.575 rps`
    - avg p95 latency: `SubmitJob=26.095 ms`, `GetJobStatus=22.46 ms`, `GetJobResult=26.4 ms`, `CancelJob=26.09 ms`
    - avg grpc non-OK rate: `0.0` for Submit/Status/Result/Cancel

## Known gaps/blockers

- Local sandboxed command execution path on the current remote MacBook session blocks localhost socket probes by default (`Operation not permitted`), so live precheck/loadgen commands required elevated execution in this environment.
- This appears environment-specific (remote MacBook workflow); user noted this does not reproduce on their desktop Docker environment.
- The two compose files share the same default project name (`docker`). Running `down` in parallel produced benign race errors (`No such container`) during teardown; sequential teardown is preferred for future runs.
- Current matrix is balanced-only and short-window; broader fairness analysis still needs full low/medium/high matrix with repeated replications.

## Next task (single target)

Expand benchmark coverage to the full starter matrix (`low/medium/high` x `submit_heavy/poll_heavy/balanced`) for both designs, then produce consolidated report artifacts/plots suitable for final A/B claims.

## Definition of done for next task

- Full 9-scenario starter matrix is executed for both designs with repeated seeds.
- Aggregated comparison tables are generated directly from produced artifacts.
- Notebook/report figures are updated from real run data with explicit caveat labels.
- Handoff docs include exact command batches, artifact root paths, and residual validity risks.
