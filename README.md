# Distributed Task Queue (Distributed Systems Project)

This repository implements and evaluates a distributed task queue using gRPC and Protocol Buffers.

The project compares:
- **Design A:** Microservices (6 functional nodes)
- **Design B:** Monolith-per-node (6 nodes)

## Quick Start (Choose Your Path)

- **Path A:** Run Design A and use the manual client for user-style submit/status/result/cancel demo flow.
- **Path B:** Run the A/B benchmark experiment (sequential isolation: Design A runs, then Design B runs).

Use this repo-level docs index for deeper spec authority and navigation:
- `docs/_INDEX.md`

## Preflight Checklist

1. Docker Desktop/Engine is running.
2. Conda is installed.
3. Required local ports are free:
   - Design A: `50051-50055`
   - Design B: `51051, 52051, 53051, 54051, 55051, 56051`
4. Create/update the runtime environment:

```bash
conda env create -f environment.yml
# or, if it already exists
conda env update -f environment.yml --prune
```

5. Optional sanity checks:

```bash
conda run -n grpc python -V
docker --version
docker compose version
```

## Setup Notes

- Prefer explicit environment invocation:

```bash
conda run -n grpc python <command>
```

- Optional interactive shell:

```bash
conda activate grpc
```

## Path A: Manual User Flow (Design A Only)

This is the supported manual user/demo flow in the README.

Start Design A:

```bash
docker compose -f docker/docker-compose.design-a.yml up --build -d
docker compose -f docker/docker-compose.design-a.yml ps
```

Submit a job:

```bash
conda run -n grpc python scripts/manual/manual_gateway_client.py submit --spec-file examples/jobs/hello_distributed.json
```

Use the returned `job_id`:

```bash
conda run -n grpc python scripts/manual/manual_gateway_client.py status --job-id <JOB_ID>
conda run -n grpc python scripts/manual/manual_gateway_client.py result --job-id <JOB_ID>
```

Optional operations:

```bash
conda run -n grpc python scripts/manual/manual_gateway_client.py cancel --job-id <JOB_ID> --reason "presentation_cancel"
conda run -n grpc python scripts/manual/manual_gateway_client.py list --page-size 10
```

Stop Design A:

```bash
docker compose -f docker/docker-compose.design-a.yml down --remove-orphans
```

Lifecycle reminder:
- Normal completion: `QUEUED -> RUNNING -> DONE`
- Queued cancel wins: `QUEUED -> CANCELED`
- Running cancel is best-effort/non-preemptive in v1

## Path B: Benchmark Experiment (A vs B, Sequential)

Run this experiment in **sequential isolation** for fairness/reproducibility.
Do not run Design A and Design B benchmark trials concurrently.

### 1) Run Design A starter matrix

Start Design A:

```bash
docker compose -f docker/docker-compose.design-a.yml up --build -d
```

Execute Design A starter scenarios:

```bash
for sid in design_a_s_low_submit_heavy design_a_s_low_poll_heavy design_a_s_low_balanced design_a_s_medium_submit_heavy design_a_s_medium_poll_heavy design_a_s_medium_balanced design_a_s_high_submit_heavy design_a_s_high_poll_heavy design_a_s_high_balanced; do
  conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario "scripts/loadgen/scenarios/starter_matrix/${sid}.json" --output-dir results/loadgen --live-traffic --precheck-health
done
```

Stop Design A:

```bash
docker compose -f docker/docker-compose.design-a.yml down --remove-orphans
```

### 2) Run Design B starter matrix

Start Design B:

```bash
docker compose -f docker/docker-compose.design-b.yml up --build -d
```

Execute Design B starter scenarios:

```bash
for sid in design_b_s_low_submit_heavy design_b_s_low_poll_heavy design_b_s_low_balanced design_b_s_medium_submit_heavy design_b_s_medium_poll_heavy design_b_s_medium_balanced design_b_s_high_submit_heavy design_b_s_high_poll_heavy design_b_s_high_balanced; do
  conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py --scenario "scripts/loadgen/scenarios/starter_matrix/${sid}.json" --output-dir results/loadgen --live-traffic --precheck-health
done
```

Stop Design B:

```bash
docker compose -f docker/docker-compose.design-b.yml down --remove-orphans
```

### 3) Aggregate results

```bash
conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py --results-root results/loadgen --output-dir results/loadgen/analysis/starter_matrix_2026-02-20
```

Results layout:
- Per run: `results/loadgen/<scenario_id>/<run_id>/...`
- Analysis package: `results/loadgen/analysis/starter_matrix_2026-02-20/`

Safety note:
- The loadgen runner fails on deterministic run-directory collisions by default.
- Use `--overwrite` only for intentional replacement.

## Verification and Troubleshooting

Stack health/logs:

```bash
docker compose -f docker/docker-compose.design-a.yml ps
docker compose -f docker/docker-compose.design-a.yml logs --tail=100 gateway job queue result coordinator worker

docker compose -f docker/docker-compose.design-b.yml ps
docker compose -f docker/docker-compose.design-b.yml logs --tail=100 monolith-1 monolith-2 monolith-3 monolith-4 monolith-5 monolith-6
```

Common issues:
- Port already in use: stop conflicting service and rerun compose.
- Missing deps/module errors: rerun `conda env update -f environment.yml --prune`.
- Run-id collision from previous benchmark artifact: keep existing evidence; avoid `--overwrite` unless replacement is intentional.

## Deeper Documentation

- `docs/_INDEX.md` (controlling documentation entry point)
- `docs/spec/fairness-evaluation.md` (A/B fairness and workload controls)
- `docs/handoff/REPRODUCIBILITY_RUNBOOK.md` (reproducibility guardrails + notebook refresh workflow)
- `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md` (artifact package index)
- `tests/_TEST_INDEX.md` and `scripts/_SCRIPT_INDEX.md` (extended command/index details)

## Project Scope (v1 Snapshot)

- Communication model: gRPC + protobuf
- Storage model: in-memory
- Processing semantics: at-least-once
- Cancellation semantics:
  - queued cancellation expected,
  - running cancellation best-effort and non-preemptive
- Load generator is evaluation tooling and not counted as a functional node
