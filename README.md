# Distributed Task Queue (Distributed Systems Project)

This repository implements and evaluates a distributed task queue using gRPC and Protocol Buffers.

The project compares:
- **Design A:** Microservices (6 functional nodes)
- **Design B:** Monolith-per-node (6 nodes)

## Documentation Entry Point

The controlling documentation file is:
- `docs/_INDEX.md`

Read `docs/_INDEX.md` first for:
- authority hierarchy,
- navigation order,
- and update rules.

Benchmark analysis notebook:
- `notebooks/benchmark_analysis.ipynb` (loadgen artifact analysis + plot scaffold)

## Project Scope (v1 Snapshot)

- Communication model: gRPC + protobuf
- Storage model: in-memory
- Processing semantics: at-least-once
- Cancellation semantics:
  - queued cancellation expected,
  - running cancellation best-effort and non-preemptive
- Load generator is evaluation tooling and not counted as a functional node

## Authoritative Specifications

- Architecture and ownership: `docs/spec/architecture.md`
- API contracts and schemas: `docs/spec/api-contracts.md`
- Lifecycle/state machine: `docs/spec/state-machine.md`
- Runtime/env/startup/healthchecks index: `docs/spec/runtime-config.md`
- Design A runtime contract: `docs/spec/runtime-config-design-a.md`
- Design B runtime contract (baseline scaffold): `docs/spec/runtime-config-design-b.md`
- Error/idempotency/retry: `docs/spec/error-idempotency.md`
- Fairness/evaluation protocol: `docs/spec/fairness-evaluation.md`
- Locked constants/defaults: `docs/spec/constants.md`
- Requirements (FR/NFR): `docs/spec/requirements.md`
- Governance and decision locks: `docs/spec/governance.md`

Proto contract authority:
- `proto/taskqueue_public.proto`
- `proto/taskqueue_internal.proto`

## Tech Stack

- Python
- grpcio / protobuf
- Docker / Docker Compose
- Git / GitHub

## Environment Setup (Conda)

Use the checked-in `environment.yml` to create the required runtime environment (`grpc`) on any machine.

```bash
conda env create -f environment.yml
```

If the environment already exists and you pulled updates:

```bash
conda env update -f environment.yml --prune
```

Run repo commands with explicit env selection (recommended for agents and automation):

```bash
conda run -n grpc python -m unittest tests/test_worker_report_retry.py
```

Optional interactive shell:

```bash
conda activate grpc
```

## Docker Compose Helpers

Compose file paths:

- `docker/docker-compose.design-a.yml`
- `docker/docker-compose.design-b.yml`

Helper commands:

```bash
docker compose -f docker/docker-compose.design-a.yml up --build -d
docker compose -f docker/docker-compose.design-a.yml ps
docker compose -f docker/docker-compose.design-a.yml logs --tail=100 worker coordinator gateway job queue result
docker compose -f docker/docker-compose.design-a.yml down --remove-orphans

docker compose -f docker/docker-compose.design-b.yml up --build -d
docker compose -f docker/docker-compose.design-b.yml ps
docker compose -f docker/docker-compose.design-b.yml logs --tail=100 monolith-1 monolith-2 monolith-3 monolith-4 monolith-5 monolith-6
docker compose -f docker/docker-compose.design-b.yml down --remove-orphans
```

Practical note:

- Since there is no root-level default `docker-compose.yml` now, include `-f <compose-file>` on compose commands.
- This is intentional so Design A and Design B can use parallel naming and isolated topology files under `docker/`.

## Design B Baseline Runtime (Scaffold)

- Design B now includes a runnable baseline topology in `docker/docker-compose.design-b.yml`.
- The scaffold starts six identical monolith containers (`monolith-1..monolith-6`), each exposing:
  - public gRPC API: `taskqueue.v1.TaskQueuePublicService`,
  - internal gRPC services in the same process for node-local wiring,
  - one in-process worker loop (`1` execution slot per node baseline).
- Host port mapping for public ingress:
  - `monolith-1 -> localhost:51051`
  - `monolith-2 -> localhost:52051`
  - `monolith-3 -> localhost:53051`
  - `monolith-4 -> localhost:54051`
  - `monolith-5 -> localhost:55051`
  - `monolith-6 -> localhost:56051`

Design B v1 parity boundary reminder:
- Public request/response contracts remain frozen.
- Design B owner routing for job-scoped operations remains a client/load-generator responsibility per `docs/spec/fairness-evaluation.md`.
- Shared client-routing helper for Design B parity is available at `common/design_b_routing.py` (`DesignBClientRouter` + `build_ordered_targets`) for empty-key round-robin and key/job deterministic owner routing.
- Monolith job creation enforces owner-affine `job_id` generation so `job_id`-based routing is coherent across submit/status/result/cancel paths.
- `ListJobs` is still available for user/demo flows in both designs, but primary A/B performance comparisons intentionally exclude `ListJobs` traffic (`ListJobs=0%` in starter matrix) because Design B v1 list scope is non-global best-effort.

## User Demo Workflow (Design A)

This is a manual, presentation-friendly flow using the public Gateway API.

Start Design A services:

```bash
docker compose -f docker/docker-compose.design-a.yml up --build -d
docker compose -f docker/docker-compose.design-a.yml ps
```

Submit a job from a JSON spec file:

```bash
conda run -n grpc python scripts/manual/manual_gateway_client.py submit --spec-file examples/jobs/hello_distributed.json
```

The response prints a `job_id`. Use that `job_id` for follow-up calls:

```bash
conda run -n grpc python scripts/manual/manual_gateway_client.py status --job-id <JOB_ID>
conda run -n grpc python scripts/manual/manual_gateway_client.py result --job-id <JOB_ID>
```

Optional operations:

```bash
conda run -n grpc python scripts/manual/manual_gateway_client.py cancel --job-id <JOB_ID> --reason "presentation_cancel"
conda run -n grpc python scripts/manual/manual_gateway_client.py list --page-size 10
```

Manual submit without a spec file:

```bash
conda run -n grpc python scripts/manual/manual_gateway_client.py submit --job-type "manual-demo" --work-duration-ms 250 --payload-size-bytes 24 --label demo=true
```

Expected lifecycle:
- `QUEUED -> RUNNING -> DONE` for normal completion.
- `QUEUED -> CANCELED` for queued cancel wins.
- `RUNNING -> CANCELED` is best-effort/non-preemptive in v1.

## Test Taxonomy

This repo uses two complementary test layers:

- `tests/` (unit tests):
  - deterministic,
  - fast and isolated (no live Docker stack required),
  - focused on local logic contracts (for example retry/backoff math).
- `tests/integration/` (canonical smoke/integration probes):
  - live-system checks against running Design A services,
  - validate wiring and cross-service behavior (submit/status/result/cancel paths),
  - slower and environment-dependent by design.

Indexes:
- Test catalog and validation commands: `tests/_TEST_INDEX.md`
- Script catalog and wrappers: `scripts/_SCRIPT_INDEX.md`

Naming convention (navigation standard):
- `tests/integration/smoke_*`: canonical live probe scripts.
- `scripts/manual/*`: human-driven demo/CLI workflows.
- `scripts/dev/*`: local utility helpers.
- Legacy note: old `scripts/*.py` smoke/manual/dev entrypoints are compatibility wrappers that forward to canonical paths.

## Validation Command Matrix

Use this matrix to choose the right verification level:

| Intent | Command(s) | Requires Docker stack |
|---|---|---|
| Fast logic regression check | `conda run -n grpc python -m unittest tests/test_worker_report_retry.py` | No |
| Coordinator terminal idempotency check | `conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py` | No |
| Owner-routing formula check | `conda run -n grpc python -m unittest tests/test_owner_routing.py` | No |
| Design B client-routing policy check (round-robin + deterministic owner) | `conda run -n grpc python -m unittest tests/test_design_b_client_routing.py` | No |
| Loadgen contract/live-engine checks (scheduler + mocked adapter + serialization) | `conda run -n grpc python -m unittest tests/test_loadgen_contracts.py` | No |
| Short live loadgen execution (rows + summary artifacts) | `conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic` | Yes |
| Live API + service wiring sanity | `conda run -n grpc python tests/integration/smoke_live_stack.py` | Yes |
| Live success lifecycle (`QUEUED -> RUNNING -> DONE`) | `conda run -n grpc python tests/integration/smoke_integration_terminal_path.py` | Yes |
| Live failure lifecycle (`QUEUED -> RUNNING -> FAILED`) | `conda run -n grpc python tests/integration/smoke_integration_failure_path.py` | Yes |
| Design B client-routing parity (`SubmitJob` empty-key round-robin + non-empty key owner routing + job-scoped routing) | `conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py` | Yes (Design B) |

## Loadgen Execution (Live + Scaffold)

The benchmark contract now supports both scaffold-only and live traffic execution:

- Scenario schema + loader: `common/loadgen_contracts.py` (`BenchmarkScenario`, `load_scenario_config`)
- Runner + phase engine hooks: `common/loadgen_contracts.py` (`BenchmarkRunner`, `LiveTrafficEngine`)
- Row schema + writers: `common/loadgen_contracts.py` (`BenchmarkRow`, JSONL/CSV writers)
- Live RPC adapter with locked retry/deadline semantics: `common/loadgen_contracts.py` (`GrpcPublicApiAdapter`)
- CLI entrypoint: `scripts/loadgen/run_benchmark_scaffold.py`
- Example scenarios:
  - `scripts/loadgen/scenarios/design_a_live_smoke_short.json`
  - `scripts/loadgen/scenarios/design_b_balanced_baseline.json`
  - `scripts/loadgen/scenarios/design_a_balanced_seed5306.json`
  - `scripts/loadgen/scenarios/design_a_balanced_seed5307.json`
  - `scripts/loadgen/scenarios/design_b_balanced_seed5306.json`
  - `scripts/loadgen/scenarios/design_b_balanced_seed5307.json`
  - full starter-matrix set:
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_low_submit_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_low_poll_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_low_balanced.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_medium_submit_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_medium_poll_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_medium_balanced.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_high_submit_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_high_poll_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_a_s_high_balanced.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_low_submit_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_low_poll_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_low_balanced.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_medium_submit_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_medium_poll_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_medium_balanced.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_high_submit_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_high_poll_heavy.json`
    - `scripts/loadgen/scenarios/starter_matrix/design_b_s_high_balanced.json`

Design B ingress in live mode remains wired through the shared routing utility:
- `common/design_b_routing.py` (`DesignBClientRouter`)
- Scenario contract requires explicit `design_b_ordered_targets` list.

Run scaffold-only artifacts (no traffic):

```bash
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_baseline.json --output-dir results/loadgen
```

Run live traffic artifacts:

```bash
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic --precheck-health
```

Balanced multi-seed live example (A/B parity slice):

```bash
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_balanced_seed5306.json --output-dir results/loadgen --live-traffic --precheck-health
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_balanced_seed5307.json --output-dir results/loadgen --live-traffic --precheck-health
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_seed5306.json --output-dir results/loadgen --live-traffic --precheck-health
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_b_balanced_seed5307.json --output-dir results/loadgen --live-traffic --precheck-health
```

Full starter matrix execution example (Design A then Design B, sequential isolation):

```bash
for sid in design_a_s_low_submit_heavy design_a_s_low_poll_heavy design_a_s_low_balanced design_a_s_medium_submit_heavy design_a_s_medium_poll_heavy design_a_s_medium_balanced design_a_s_high_submit_heavy design_a_s_high_poll_heavy design_a_s_high_balanced; do
  conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario "scripts/loadgen/scenarios/starter_matrix/${sid}.json" --output-dir results/loadgen --live-traffic --precheck-health
done

for sid in design_b_s_low_submit_heavy design_b_s_low_poll_heavy design_b_s_low_balanced design_b_s_medium_submit_heavy design_b_s_medium_poll_heavy design_b_s_medium_balanced design_b_s_high_submit_heavy design_b_s_high_poll_heavy design_b_s_high_balanced; do
  conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario "scripts/loadgen/scenarios/starter_matrix/${sid}.json" --output-dir results/loadgen --live-traffic --precheck-health
done
```

If a deterministic run directory already exists, the runner now fails by default.
Use `--overwrite` only for intentional replacement:

```bash
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario scripts/loadgen/scenarios/design_a_live_smoke_short.json --output-dir results/loadgen --live-traffic --precheck-health --overwrite
```

Aggregate starter-matrix artifacts (tables + plots):

```bash
conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py --results-root results/loadgen --output-dir results/loadgen/analysis/starter_matrix_2026-02-20
```

Artifacts are written per run under:
- `results/loadgen/<scenario_id>/<run_id>/rows.jsonl`
- `results/loadgen/<scenario_id>/<run_id>/rows.csv`
- `results/loadgen/<scenario_id>/<run_id>/summary.json`
- `results/loadgen/<scenario_id>/<run_id>/summary.csv`
- `results/loadgen/<scenario_id>/<run_id>/metadata.json`

Live benchmark hardening notes:
- optional fail-fast precheck gate: `--precheck-health` (`--precheck-timeout-ms` override),
- run-directory collision safety: fail-if-exists by default; explicit `--overwrite` for replacement,
- summary now includes job-terminal throughput aggregation (`unique_terminal_jobs`, `throughput_rps`),
- latency percentiles keep sub-millisecond precision with a `0.001 ms` floor for observed calls.

## Live Smoke Workflow (Design A)

After Design A services are healthy, run:

```bash
conda run -n grpc python -m unittest tests/test_worker_report_retry.py
conda run -n grpc python -m unittest tests/test_coordinator_report_outcome_idempotency.py
conda run -n grpc python tests/integration/smoke_live_stack.py
conda run -n grpc python tests/integration/smoke_integration_terminal_path.py
conda run -n grpc python tests/integration/smoke_integration_failure_path.py
```

Design B routing-validation path:

```bash
conda run -n grpc python -m unittest tests/test_owner_routing.py
conda run -n grpc python -m unittest tests/test_design_b_client_routing.py
conda run -n grpc python tests/integration/smoke_design_b_owner_routing.py
```

Retry-coverage note:
- `tests/test_worker_report_retry.py` provides deterministic automated checks for worker `ReportWorkOutcome` retry semantics, including bounded exponential backoff windows, full-jitter bounds, attempt-count behavior, stop-event early exit, and transient `grpc.RpcError` retry flow.

Coordinator idempotency note:
- `tests/test_coordinator_report_outcome_idempotency.py` provides deterministic automated checks for coordinator `ReportWorkOutcome` terminal-write behavior: first terminal write persistence (`DONE`/`FAILED`), duplicate-equivalent idempotency, and conflicting repeated-report non-corruption.

Failure-path note:
- `tests/integration/smoke_integration_failure_path.py` submits a job whose `job_type` contains `force-fail`.
- Worker runtime treats this marker as a deterministic test trigger and reports `JOB_OUTCOME_FAILED`.

Retry semantics note:
- Worker `ReportWorkOutcome` retries use bounded exponential backoff with full jitter (per locked v1 constants/spec).

## Evaluation Execution Plan (A vs B)

Use this runbook after both designs and the load generator are complete.

1. Lock parity before any measurement:
   - same total worker-slot capacity across designs (per locked constants),
   - same workload mix, request pacing model, runtime, and warmup/cooldown windows,
   - same host resource limits and background-load conditions.
2. Keep production retry semantics enabled for benchmark realism:
   - bounded exponential backoff + full jitter stays on for both designs.
3. Define workload matrix:
   - low/medium/high offered load,
   - request-mix profiles (`submit_heavy`, `poll_heavy`, `balanced`) with starter definitions in `docs/spec/fairness-evaluation.md`,
   - at least one sustained run duration per point (not burst-only).
4. Run repeated trials per workload point for each design:
   - execute multiple independent runs (for example, 10),
   - alternate A/B run order when possible to reduce time-of-day and thermal bias.
5. Report distribution-oriented metrics, not single-run snapshots:
   - throughput, success rate, and error-rate breakdown by gRPC code,
   - end-to-end latency p50/p95/p99,
   - fairness metrics defined in `docs/spec/fairness-evaluation.md`,
   - retry observability (retry count and retry-wait behavior) to interpret jitter impact.
6. Add controlled transient-failure scenarios:
   - briefly degrade one internal dependency (for example temporary unavailability),
   - measure recovery profile, tail-latency behavior, and completion stability.
7. Compare A vs B using aggregate statistics:
   - present mean/median plus spread (stddev or confidence intervals),
   - base conclusions on repeated-run distributions, not best-case outliers.

## Demo UX TODO (Post-Core Milestones)

After completing Design A remaining tasks, Design B, and load-generator implementation, add a lightweight alias workflow to reduce manual demo friction:

- Add local alias map file for manual client (for example `.manual_gateway_aliases.json`).
- Support `submit --alias <name>` to bind alias -> returned `job_id`.
- Support `status/result/cancel --alias <name>` so presenters do not need to type/copy UUID job IDs.
- Keep alias mapping client-local only (no proto/backend contract changes required).

## Repository Structure

```text
distributed-task-queue/
|-- .gitignore
|-- README.md
|-- common/
|   |-- __init__.py
|   |-- config.py
|   |-- design_b_routing.py
|   |-- grpc_server.py
|   |-- loadgen_contracts.py
|   |-- logging.py
|   |-- owner_routing.py
|   |-- rpc_defaults.py
|   `-- time_utils.py
|-- docker/
|   |-- .gitkeep
|   |-- docker-compose.design-a.yml
|   `-- docker-compose.design-b.yml
|-- examples/
|   `-- jobs/
|       `-- hello_distributed.json
|-- docs/
|   |-- _INDEX.md
|   |-- handoff/
|   |   |-- CURRENT_STATUS.md
|   |   `-- NEXT_TASK.md
|   `-- spec/
|       |-- api-contracts.md
|       |-- architecture.md
|       |-- constants.md
|       |-- error-idempotency.md
|       |-- fairness-evaluation.md
|       |-- governance.md
|       |-- requirements.md
|       |-- runtime-config-design-a.md
|       |-- runtime-config-design-b.md
|       |-- runtime-config.md
|       `-- state-machine.md
|-- generated/
|   |-- taskqueue_internal_pb2.py
|   |-- taskqueue_internal_pb2_grpc.py
|   |-- taskqueue_public_pb2.py
|   `-- taskqueue_public_pb2_grpc.py
|-- proto/
|   |-- taskqueue_internal.proto
|   `-- taskqueue_public.proto
|-- results/
|   `-- .gitkeep
|-- scripts/
|   |-- _SCRIPT_INDEX.md
|   |-- healthcheck.py                  # compatibility wrapper -> scripts/dev/healthcheck.py
|   |-- manual_gateway_client.py        # compatibility wrapper -> scripts/manual/manual_gateway_client.py
|   |-- smoke_live_stack.py             # compatibility wrapper -> tests/integration/smoke_live_stack.py
|   |-- smoke_integration_terminal_path.py # compatibility wrapper -> tests/integration/smoke_integration_terminal_path.py
|   |-- smoke_integration_failure_path.py  # compatibility wrapper -> tests/integration/smoke_integration_failure_path.py
|   |-- manual/
|   |   `-- manual_gateway_client.py
|   |-- dev/
|   |   `-- healthcheck.py
|   |-- loadgen/
|   |   |-- run_benchmark_scaffold.py
|   |   `-- scenarios/
|   |       |-- design_a_live_smoke_short.json
|   |       |-- design_b_balanced_baseline.json
|   |       |-- design_a_balanced_seed5306.json
|   |       |-- design_a_balanced_seed5307.json
|   |       |-- design_b_balanced_seed5306.json
|   |       `-- design_b_balanced_seed5307.json
|   `-- legacy_smoke/
|       |-- smoke_coordinator_behavior.py
|       |-- smoke_coordinator_skeleton.py
|       |-- smoke_gateway_behavior.py
|       |-- smoke_gateway_skeleton.py
|       |-- smoke_job_behavior.py
|       |-- smoke_job_skeleton.py
|       |-- smoke_queue_behavior.py
|       |-- smoke_queue_skeleton.py
|       |-- smoke_result_behavior.py
|       |-- smoke_result_skeleton.py
|       `-- smoke_worker_skeleton.py
|-- tests/
|   |-- _TEST_INDEX.md
|   |-- test_worker_report_retry.py
|   |-- test_coordinator_report_outcome_idempotency.py
|   |-- test_owner_routing.py
|   |-- test_design_b_client_routing.py
|   |-- test_loadgen_contracts.py
|   `-- integration/
|       |-- smoke_live_stack.py
|       |-- smoke_integration_terminal_path.py
|       |-- smoke_integration_failure_path.py
|       `-- smoke_design_b_owner_routing.py
`-- services/
    |-- monolith/
    |   |-- __init__.py
    |   |-- main.py
    |   `-- node.py
    |-- coordinator/
    |   |-- main.py
    |   |-- server.py
    |   `-- servicer.py
    |-- gateway/
    |   |-- __init__.py
    |   |-- main.py
    |   |-- server.py
    |   `-- servicer.py
    |-- job/
    |   |-- __init__.py
    |   |-- main.py
    |   |-- server.py
    |   `-- servicer.py
    |-- queue/
    |   |-- main.py
    |   |-- server.py
    |   `-- servicer.py
    |-- result/
    |   |-- main.py
    |   |-- server.py
    |   `-- servicer.py
    `-- worker/
        |-- .gitkeep
        |-- main.py
        `-- worker.py
```
