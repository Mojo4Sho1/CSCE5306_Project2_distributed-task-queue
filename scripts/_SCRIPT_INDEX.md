# Script Index

This file maps canonical script locations and usage.

Test commands and test taxonomy live in:
- `tests/_TEST_INDEX.md`

## Canonical Locations

- Manual CLI tools: `scripts/manual/`
- Developer utilities: `scripts/dev/`
- Load generator scaffolding: `scripts/loadgen/`

## Canonical Commands

- `conda run -n grpc python scripts/manual/manual_gateway_client.py --help`
- `conda run -n grpc python scripts/manual/manual_gateway_client.py submit --spec-file examples/jobs/hello_distributed.json`
- `conda run -n grpc python scripts/dev/healthcheck.py --mode tcp --target gateway:50051 --service gateway`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_baseline.json --output-dir results/loadgen`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic --precheck-health`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_balanced_seed5306.json --output-dir results/loadgen --live-traffic --precheck-health`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_balanced_seed5307.json --output-dir results/loadgen --live-traffic --precheck-health`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_seed5306.json --output-dir results/loadgen --live-traffic --precheck-health`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_seed5307.json --output-dir results/loadgen --live-traffic --precheck-health`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic --precheck-health --overwrite`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/starter_matrix/design_a_s_low_submit_heavy.json --output-dir results/loadgen --live-traffic --precheck-health`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/starter_matrix/design_b_s_low_submit_heavy.json --output-dir results/loadgen --live-traffic --precheck-health`
- `conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py --results-root results/loadgen --output-dir results/loadgen/analysis/starter_matrix_2026-02-20`

Loadgen runner safety:
- deterministic `run_id` path collisions fail by default;
- pass `--overwrite` only when intentional artifact replacement is desired.

## Naming Standard for New Additions

- New integration probes: `tests/integration/smoke_<scope>.py`
- New manual tools: `scripts/manual/manual_<scope>.py`
- New developer utilities: `scripts/dev/dev_<scope>.py`

Avoid creating new top-level `scripts/smoke_*` files; use canonical locations instead.
