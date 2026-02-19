# Runtime Configuration and Startup Contract (Design B Baseline Scaffold, v1)

## Scope and status

- Status: baseline scaffold contract for initial Design B bring-up.
- This document defines only the runnable monolith-node topology and startup/health visibility boundaries.
- Public API/proto contracts remain frozen per:
  - `proto/taskqueue_public.proto`
  - `docs/spec/api-contracts.md`
  - `docs/spec/state-machine.md`

## Topology (baseline scaffold)

- Compose file: `docker/docker-compose.design-b.yml`
- Node count: `6` containers (`monolith-1..monolith-6`)
- Process model: one Python process per node (`python -m services.monolith.main`)
- Execution slot mapping: one in-process worker loop per node (baseline target: total `6` slots)

## Node runtime wiring

Each monolith node hosts in one gRPC server process:

- Public inbound service:
  - `taskqueue.v1.TaskQueuePublicService`
- Internal inbound services:
  - `taskqueue.internal.v1.JobInternalService`
  - `taskqueue.internal.v1.QueueInternalService`
  - `taskqueue.internal.v1.CoordinatorInternalService`
  - `taskqueue.internal.v1.ResultInternalService`

Baseline internal orchestration uses node-local loopback wiring.

## Ports and ingress

- Container bind host: `0.0.0.0`
- Container public port: `50051`
- Host port mapping:
  - `monolith-1`: `51051 -> 50051`
  - `monolith-2`: `52051 -> 50051`
  - `monolith-3`: `53051 -> 50051`
  - `monolith-4`: `54051 -> 50051`
  - `monolith-5`: `55051 -> 50051`
  - `monolith-6`: `56051 -> 50051`

## Environment variables (scaffold defaults)

- Shared:
  - `PYTHONUNBUFFERED=1`
  - `LOG_LEVEL=INFO`
  - `PYTHONPATH=/app:/app/generated`
- Monolith node identity and bind:
  - `MONOLITH_NODE_ID` (per-container unique id)
  - `MONOLITH_NODE_ORDER` (comma-separated fixed ordered node id list; default `monolith-1,monolith-2,monolith-3,monolith-4,monolith-5,monolith-6`)
  - `MONOLITH_BIND_HOST` (default `0.0.0.0`)
  - `MONOLITH_PUBLIC_PORT` (default `50051`)
- Worker enablement:
  - `MONOLITH_ENABLE_WORKER=1` (default enabled)

Runtime defaults remain aligned with locked v1 constants for:
- internal RPC timeout,
- heartbeat timing,
- retry/backoff settings,
- dedup and output byte bounds.

## Deterministic routing coherence (v1)

- The client/load-generator performs locked ingress routing policy:
  - `SubmitJob` with empty `client_request_id`: round-robin over ordered node targets,
  - `SubmitJob` with non-empty `client_request_id`: deterministic owner routing by key,
  - `GetJobStatus`/`GetJobResult`/`CancelJob`: deterministic owner routing by `job_id`.
- Shared client utility module for this policy:
  - `common/design_b_routing.py`
  - `DesignBClientRouter` (policy), `build_ordered_targets` (ordered target config surface).
- Monolith node job creation enforces owner-affine `job_id` generation based on configured node order, so `job_id`-routed follow-up calls map back to the creating owner node without inter-node forwarding.

## Health visibility

Compose healthcheck command shape:

```bash
python -m scripts.healthcheck --mode tcp --target 127.0.0.1:50051 --timeout-ms 1000 --service <monolith-node>
```

Container health timing policy:
- `interval: 5s`
- `timeout: 2s`
- `retries: 12`
- `start_period: 20s`

## Bring-up commands

```bash
docker compose -f docker/docker-compose.design-b.yml up --build -d
docker compose -f docker/docker-compose.design-b.yml ps
docker compose -f docker/docker-compose.design-b.yml logs --tail=100 monolith-1 monolith-2 monolith-3 monolith-4 monolith-5 monolith-6
docker compose -f docker/docker-compose.design-b.yml down --remove-orphans
```

## Boundaries and non-goals (for this baseline)

- No proto/schema changes.
- No Design A contract changes.
- No inter-node forwarding behavior in this scaffold.
- Design B owner routing for job-scoped operations remains a client/load-generator responsibility per `docs/spec/fairness-evaluation.md`.
