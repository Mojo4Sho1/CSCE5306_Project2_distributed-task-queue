# Distributed Task Queue (Distributed Systems Project)

This repository implements and evaluates a distributed task queue using gRPC and Protocol Buffers.

The project compares:
- **Design A:** Microservices (6 functional nodes)
- **Design B:** Monolith-per-node (6 nodes)

## Documentation Entry Point

The controlling documentation file is:
- `docs/INDEX.md`

Read `docs/INDEX.md` first for:
- authority hierarchy,
- navigation order,
- and update rules.

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
- Runtime/env/startup/healthchecks: `docs/spec/runtime-config.md`
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
conda run -n grpc python scripts/smoke_gateway_skeleton.py
```

Optional interactive shell:

```bash
conda activate grpc
```

## Docker Compose Helpers

Design A compose file path:

- `docker/docker-compose.design-a.yml`

Helper commands:

```bash
docker compose -f docker/docker-compose.design-a.yml up --build -d
docker compose -f docker/docker-compose.design-a.yml ps
docker compose -f docker/docker-compose.design-a.yml logs --tail=100 worker coordinator gateway job queue result
docker compose -f docker/docker-compose.design-a.yml down --remove-orphans
```

Practical note:

- Since there is no root-level default `docker-compose.yml` now, include `-f <compose-file>` on compose commands.
- This is intentional so Design A and Design B can use parallel naming and isolated topology files under `docker/`.

## User Demo Workflow (Design A)

This is a manual, presentation-friendly flow using the public Gateway API.

Start Design A services:

```bash
docker compose -f docker/docker-compose.design-a.yml up --build -d
docker compose -f docker/docker-compose.design-a.yml ps
```

Submit a job from a JSON spec file:

```bash
conda run -n grpc python scripts/manual_gateway_client.py submit --spec-file examples/jobs/hello_distributed.json
```

The response prints a `job_id`. Use that `job_id` for follow-up calls:

```bash
conda run -n grpc python scripts/manual_gateway_client.py status --job-id <JOB_ID>
conda run -n grpc python scripts/manual_gateway_client.py result --job-id <JOB_ID>
```

Optional operations:

```bash
conda run -n grpc python scripts/manual_gateway_client.py cancel --job-id <JOB_ID> --reason "presentation_cancel"
conda run -n grpc python scripts/manual_gateway_client.py list --page-size 10
```

Manual submit without a spec file:

```bash
conda run -n grpc python scripts/manual_gateway_client.py submit --job-type "manual-demo" --work-duration-ms 250 --payload-size-bytes 24 --label demo=true
```

Expected lifecycle:
- `QUEUED -> RUNNING -> DONE` for normal completion.
- `QUEUED -> CANCELED` for queued cancel wins.
- `RUNNING -> CANCELED` is best-effort/non-preemptive in v1.

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
|   |-- grpc_server.py
|   |-- logging.py
|   `-- time_utils.py
|-- docker/
|   |-- .gitkeep
|   `-- docker-compose.design-a.yml
|-- examples/
|   `-- jobs/
|       `-- hello_distributed.json
|-- docs/
|   |-- INDEX.md
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
|   |-- healthcheck.py
|   |-- manual_gateway_client.py
|   |-- smoke_job_behavior.py
|   |-- smoke_queue_behavior.py
|   |-- smoke_coordinator_behavior.py
|   |-- smoke_coordinator_skeleton.py
|   |-- smoke_gateway_behavior.py
|   |-- smoke_gateway_skeleton.py
|   |-- smoke_integration_terminal_path.py
|   |-- smoke_job_skeleton.py
|   |-- smoke_live_stack.py
|   |-- smoke_queue_skeleton.py
|   |-- smoke_result_skeleton.py
|   `-- smoke_worker_skeleton.py
`-- services/
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
