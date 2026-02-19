# Test Index

This file is the canonical index for tests and validation commands.

For script-only utilities and wrappers, see:
- `scripts/_SCRIPT_INDEX.md`

## Test Locations

- Unit tests: `tests/`
- Integration/smoke probes: `tests/integration/`

## Canonical Test Commands

- `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`
- `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`
- `conda run -n grpc python -m unittest tests/test_owner_routing.py`
- `conda run -n grpc python -m unittest tests/test_design_b_client_routing.py`
- `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`
- `conda run -n grpc python tests/integration/smoke_live_stack.py`
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`
- `conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py`

## Validation Workflow (Design A)

1. Start services:
   - `docker compose -f docker/docker-compose.design-a.yml up --build -d`
   - `docker compose -f docker/docker-compose.design-a.yml ps`
2. Run deterministic unit tests:
   - `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`
   - `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`
3. Run integration smokes:
   - `conda run -n grpc python tests/integration/smoke_live_stack.py`
   - `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`
   - `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`

## Validation Workflow (Design B Client Routing)

1. Start Design B services:
   - `docker compose -f docker/docker-compose.design-b.yml up --build -d`
   - `docker compose -f docker/docker-compose.design-b.yml ps`
2. Run routing-focused checks:
   - `conda run -n grpc python -m unittest tests/test_owner_routing.py`
   - `conda run -n grpc python -m unittest tests/test_design_b_client_routing.py`
   - `conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py`

## Loadgen Validation Workflow

1. Run deterministic contract/scheduler tests:
   - `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py`
2. Run short live smoke to produce measurement + summary artifacts:
   - `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic --precheck-health`

## Naming Standard for New Tests

- New deterministic unit tests: `tests/test_<scope>.py`
- New integration probes: `tests/integration/smoke_<scope>.py`

Avoid adding new test entrypoints under top-level `scripts/`; keep test execution under `tests/`.
