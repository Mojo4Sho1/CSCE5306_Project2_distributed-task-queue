# Script Index

This file maps script-only locations and usage after the repo navigation migration.

Test commands and test taxonomy live in:
- `tests/_TEST_INDEX.md`

## Canonical Locations

- Manual CLI tools: `scripts/manual/`
- Developer utilities: `scripts/dev/`
- Load generator scaffolding: `scripts/loadgen/`
- Legacy retained helpers: `scripts/legacy_smoke/`

## Canonical Commands

- `conda run -n grpc python scripts/manual/manual_gateway_client.py --help`
- `conda run -n grpc python scripts/manual/manual_gateway_client.py submit --spec-file examples/jobs/hello_distributed.json`
- `conda run -n grpc python scripts/dev/healthcheck.py --mode tcp --target gateway:50051 --service gateway`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_baseline.json --output-dir results/loadgen`
- `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic --precheck-health`

## Compatibility Wrappers (Deprecated)

These old paths still run, but now forward to canonical paths:

| Legacy path | Forwards to |
|---|---|
| `scripts/smoke_live_stack.py` | `tests/integration/smoke_live_stack.py` |
| `scripts/smoke_integration_terminal_path.py` | `tests/integration/smoke_integration_terminal_path.py` |
| `scripts/smoke_integration_failure_path.py` | `tests/integration/smoke_integration_failure_path.py` |
| `scripts/manual_gateway_client.py` | `scripts/manual/manual_gateway_client.py` |
| `scripts/healthcheck.py` | `scripts/dev/healthcheck.py` |
| `scripts/smoke_*_behavior.py` | `scripts/legacy_smoke/smoke_*_behavior.py` |
| `scripts/smoke_*_skeleton.py` | `scripts/legacy_smoke/smoke_*_skeleton.py` |

## Legacy Helper Inventory

Retained for Design B and load-generator bring-up diagnostics:

- `scripts/legacy_smoke/smoke_gateway_behavior.py`
- `scripts/legacy_smoke/smoke_gateway_skeleton.py`
- `scripts/legacy_smoke/smoke_job_behavior.py`
- `scripts/legacy_smoke/smoke_job_skeleton.py`
- `scripts/legacy_smoke/smoke_queue_behavior.py`
- `scripts/legacy_smoke/smoke_queue_skeleton.py`
- `scripts/legacy_smoke/smoke_coordinator_behavior.py`
- `scripts/legacy_smoke/smoke_coordinator_skeleton.py`
- `scripts/legacy_smoke/smoke_result_behavior.py`
- `scripts/legacy_smoke/smoke_result_skeleton.py`
- `scripts/legacy_smoke/smoke_worker_skeleton.py`

## Naming Standard for New Additions

- New integration probes: `tests/integration/smoke_<scope>.py`
- New manual tools: `scripts/manual/manual_<scope>.py`
- New developer utilities: `scripts/dev/dev_<scope>.py`

Avoid creating new top-level `scripts/smoke_*` files; use canonical locations instead.
