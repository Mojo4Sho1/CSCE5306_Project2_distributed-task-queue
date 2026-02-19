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
- `conda run -n grpc python tests/integration/smoke_live_stack.py`
- `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`
- `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`

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

## Naming Standard for New Tests

- New deterministic unit tests: `tests/test_<scope>.py`
- New integration probes: `tests/integration/smoke_<scope>.py`

Avoid adding new test entrypoints under top-level `scripts/`; keep test execution under `tests/`.
