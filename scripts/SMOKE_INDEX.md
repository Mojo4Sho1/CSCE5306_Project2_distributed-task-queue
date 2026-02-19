# Smoke Index

This file maps canonical and compatibility script paths after the repo navigation migration.

## Canonical Locations

- Unit tests: `tests/`
- Integration/smoke probes: `tests/integration/`
- Manual CLI tools: `scripts/manual/`
- Developer utilities: `scripts/dev/`
- Legacy retained helpers: `scripts/legacy_smoke/`

## Canonical Commands

- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`
- `conda run -n grpc python tests/integration/smoke_live_stack.py`
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`
- `conda run -n grpc python scripts/manual/manual_gateway_client.py --help`

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
