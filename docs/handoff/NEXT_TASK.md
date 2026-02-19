# Next Task

**Last updated:** 2026-02-19  
**Owner:** Joe + Codex

## Task summary

Implement live benchmark traffic execution on top of the new scaffold contracts, including request scheduling, RPC execution, and summary aggregation artifacts.

## Why this task is next

- The scaffold contract is now implemented and verified:
  - machine-readable scenario schema/loader,
  - warm-up/measure/cool-down/repeat runner skeleton,
  - fairness-aligned row schema and artifact writers,
  - Design B routing wired through shared `DesignBClientRouter`.
- Remaining gap before full A/B benchmarking is actual traffic generation and recorded measurement rows during the measure window.

## Scope (in)

- Add request scheduler that uses scenario request-mix weights and concurrency controls.
- Add RPC client adapter layer for `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob` execution.
- Enforce locked retry/deadline policy on benchmark client calls per spec constants/error model.
- Record real measurement rows during measure window and write scaffold artifacts.
- Add summary tables/artifacts:
  - per-method throughput,
  - latency p50/p95/p99,
  - grpc-code error rates.
- Add deterministic tests for scheduler/mix behavior and row production with mocked RPC adapter.
- Update docs/handoff with commands/evidence and residual risks.

## Scope (out)

- Proto/schema changes.
- Service-side state model changes.
- Fairness lock modifications (`TOTAL_WORKER_SLOTS`, routing formula, parity method scope).
- Plotting/report visualization layer.

## Dependencies / prerequisites

- Use conda environment `grpc` for all code/tests:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc python -m unittest <test_path.py>`
- Keep Design A and Design B stacks healthy for live smoke/non-regression checks:
  - `docker compose -f docker/docker-compose.design-a.yml ps`
  - `docker compose -f docker/docker-compose.design-b.yml ps`

## Implementation notes

- Treat these as lock references:
  - `docs/spec/fairness-evaluation.md`
  - `docs/spec/constants.md`
  - `docs/spec/error-idempotency.md`
  - `docs/spec/state-machine.md`
- Build on existing scaffold contract paths:
  - `common/loadgen_contracts.py`
  - `scripts/loadgen/run_benchmark_scaffold.py`
  - `scripts/loadgen/scenarios/design_b_balanced_baseline.json`
- Use starter matrix/policy from:
  - `docs/spec/fairness-evaluation.md` (Section 7 starter matrix; primary runs keep `ListJobs=0%`)
- Keep Design B ingress/routing delegated to shared utility:
  - `common/design_b_routing.py`
- Keep changes additive and separable from core service runtime.

## Acceptance criteria (definition of done)

- Live request scheduler executes operations according to scenario mix/concurrency.
- Measure window rows are populated with real outcomes and written via existing schema writers.
- Summary artifacts are generated and parseable for fairness reporting fields.
- Design B paths continue using shared router utility for submit/job-scoped target resolution.
- Deterministic scheduler/serialization tests pass.
- Existing baseline checks remain green:
  - `conda run -n grpc python -m unittest tests/test_worker_report_retry.py`
  - `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py`
  - `conda run -n grpc python tests/integration/smoke_live_stack.py`
  - `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py`
  - `conda run -n grpc python tests/integration/smoke_integration_failure_path.py`
  - `conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py`
- Any failures are documented with exact commands, timestamps, and root-cause hypothesis in `docs/handoff/CURRENT_STATUS.md`.

## Verification checklist

- [ ] Implement live request scheduler using scenario mix/concurrency.
- [ ] Add RPC adapter execution path for parity methods.
- [ ] Enforce locked retry/deadline controls in benchmark client path.
- [ ] Write measure-window rows from real RPC outcomes.
- [ ] Add summary artifact generation (throughput/latency/error rates).
- [ ] Add deterministic tests for scheduler + mocked row production.
- [ ] Re-run `tests/test_worker_report_retry.py`.
- [ ] Re-run `tests/test_coordinator_report_outcome_idempotency.py`.
- [ ] Re-run `tests/integration/smoke_live_stack.py`.
- [ ] Re-run `tests/integration/smoke_integration_terminal_path.py`.
- [ ] Re-run `tests/integration/smoke_integration_failure_path.py`.
- [ ] Re-run `tests/integration/smoke_design_b_owner_routing.py`.
- [ ] Record command outputs/timestamps/residual risks in `docs/handoff/CURRENT_STATUS.md`.

## Risks / rollback notes

- If scheduler pacing/mix semantics drift from scenario contract, benchmark reproducibility degrades.
- If retry/deadline behavior diverges from locked constants, A/B comparability is weakened.
- Rollback path remains low risk: current scaffold is additive and isolated from runtime services.
