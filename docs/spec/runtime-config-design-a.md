# Runtime Configuration and Startup Contract (Design A, v1)

This document defines the runtime wiring, environment configuration, startup/readiness behavior, and container healthcheck strategy for the distributed task queue system.

## Scope

- This file is the canonical runtime contract for **Design A (Microservices)**.
- It captures and freezes the behavior previously defined in:
  - runtime startup contract lock
  - healthcheck strategy lock
- Design B (monolith-per-node) uses its own deployment topology; this file focuses on the six microservice functional nodes and their runtime behavior.
- Design B runtime wiring is documented separately in `docs/spec/runtime-config-design-b.md`.
- Design A compose file location: `docker/docker-compose.design-a.yml`.

---

## 1) Service Endpoint Map (Design A)

| Service | Compose DNS name | Inbound Proto Service | Bind Host | Port | Inbound Business RPC |
|---|---|---|---|---:|---|
| Gateway | `gateway` | `taskqueue.v1.TaskQueuePublicService` | `0.0.0.0` | `50051` | Yes |
| Job | `job` | `taskqueue.internal.v1.JobInternalService` | `0.0.0.0` | `50052` | Yes |
| Queue | `queue` | `taskqueue.internal.v1.QueueInternalService` | `0.0.0.0` | `50053` | Yes |
| Coordinator | `coordinator` | `taskqueue.internal.v1.CoordinatorInternalService` | `0.0.0.0` | `50054` | Yes |
| Result | `result` | `taskqueue.internal.v1.ResultInternalService` | `0.0.0.0` | `50055` | Yes |
| Worker | `worker` | (none; internal RPC client in v1) | n/a | n/a | No |

---

## 2) Upstream Dependency Addresses (Design A)

| Consumer | Required upstream address env vars (default values) |
|---|---|
| Gateway | `JOB_SERVICE_ADDR=job:50052`, `QUEUE_SERVICE_ADDR=queue:50053`, `RESULT_SERVICE_ADDR=result:50055` |
| Coordinator | `JOB_SERVICE_ADDR=job:50052`, `QUEUE_SERVICE_ADDR=queue:50053`, `RESULT_SERVICE_ADDR=result:50055` |
| Worker | `COORDINATOR_ADDR=coordinator:50054` |
| Job / Queue / Result | none |

---

## 3) Required Environment Variables

## Shared (all containers)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `LOG_LEVEL` | No | `INFO` | Logging verbosity. |
| `PYTHONUNBUFFERED` | Yes | `1` | Ensures unbuffered stdout/stderr for container logs. |

## Gateway

| Variable | Required | Default | Notes |
|---|---|---|---|
| `GATEWAY_PORT` | No | `50051` | gRPC bind port for public API. |
| `JOB_SERVICE_ADDR` | Yes | none | Upstream Job service address. |
| `QUEUE_SERVICE_ADDR` | Yes | none | Upstream Queue service address. |
| `RESULT_SERVICE_ADDR` | Yes | none | Upstream Result service address. |
| `INTERNAL_RPC_TIMEOUT_MS` | No | `1000` | Default unary timeout for Gateway -> Job/Queue/Result internal RPCs. |

## Job

| Variable | Required | Default | Notes |
|---|---|---|---|
| `JOB_PORT` | No | `50052` | gRPC bind port for Job internal API. |
| `MAX_DEDUP_KEYS` | No | `10000` | In-memory bounded submit-idempotency key capacity. |

## Queue

| Variable | Required | Default | Notes |
|---|---|---|---|
| `QUEUE_PORT` | No | `50053` | gRPC bind port for Queue internal API. |

## Coordinator

| Variable | Required | Default | Notes |
|---|---|---|---|
| `COORDINATOR_PORT` | No | `50054` | gRPC bind port for Coordinator internal API. |
| `JOB_SERVICE_ADDR` | Yes | none | Upstream Job service address. |
| `QUEUE_SERVICE_ADDR` | Yes | none | Upstream Queue service address. |
| `RESULT_SERVICE_ADDR` | Yes | none | Upstream Result service address. |
| `HEARTBEAT_INTERVAL_MS` | No | `1000` | Worker heartbeat cadence hint/expectation. |
| `WORKER_TIMEOUT_MS` | No | `4000` | Liveness timeout threshold for worker unavailability. |
| `INTERNAL_RPC_TIMEOUT_MS` | No | `1000` | Default unary timeout for Coordinator -> Job/Queue/Result internal RPCs. |

## Result

| Variable | Required | Default | Notes |
|---|---|---|---|
| `RESULT_PORT` | No | `50055` | gRPC bind port for Result internal API. |
| `MAX_OUTPUT_BYTES` | No | `262144` | Maximum output payload bytes stored for terminal envelopes. |

## Worker

| Variable | Required | Default | Notes |
|---|---|---|---|
| `COORDINATOR_ADDR` | Yes | none | Upstream Coordinator address. |
| `WORKER_ID` | No | container hostname fallback | Stable worker identity for process lifetime. |
| `HEARTBEAT_INTERVAL_MS` | No | `1000` | Worker heartbeat emit interval. |
| `INTERNAL_RPC_TIMEOUT_MS` | No | `1000` | Default unary timeout for worker internal calls (for example `ReportWorkOutcome`). |
| `FETCH_WORK_RPC_TIMEOUT_MS` | No | `1500` | Dedicated timeout for worker `FetchWork` calls. |
| `WORKER_HEARTBEAT_RPC_TIMEOUT_MS` | No | `1000` | Dedicated timeout for worker `WorkerHeartbeat` calls. |
| `REPORT_RETRY_INITIAL_DELAY_MS` | No | `100` | Initial backoff delay for worker outcome report retries. |
| `REPORT_RETRY_MULTIPLIER` | No | `2.0` | Exponential multiplier for worker outcome report retry backoff. |
| `REPORT_RETRY_MAX_DELAY_MS` | No | `1000` | Max backoff delay for worker outcome report retries. |
| `REPORT_RETRY_MAX_ATTEMPTS` | No | `4` | Total attempts (initial + retries) for worker outcome report submission. |

---

## 4) Startup and Readiness Definition

## Services with inbound gRPC endpoints
Applies to: Gateway, Job, Queue, Coordinator, Result

A service is **ready** when all are true:

1. Configuration is parsed successfully.
2. gRPC server is bound to configured host/port.
3. Startup log emits a ready event.
4. Corresponding healthcheck passes.

## Worker (no inbound business RPC in v1)

Worker is **ready** when all are true:

1. Configuration is parsed successfully.
2. Worker loop has started.
3. First heartbeat attempt has been emitted in logs.
4. Corresponding worker healthcheck passes.

---

## 5) Entrypoint Rule

Each service container **must** declare exactly one startup command in Docker Compose.

If an entrypoint changes, this document (and any endpoint/env tables that reference it) must be updated in the same commit.

---

## 6) Healthcheck Strategy (v1)

## 6.1 Common healthcheck command shape

All containers use the shared interface:

```bash
python -m scripts.healthcheck --mode <tcp|worker> --target <host:port> --timeout-ms <ms> --service <name>
```

Parameters:

- `--mode`
  - `tcp`: TCP connect check to target host:port.
  - `worker`: Worker liveness check via coordinator reachability at target.
- `--target`: required `host:port`.
- `--timeout-ms`: optional, default `1000`.
- `--service`: optional label for structured output.

Exit semantics:

- exit `0` = healthy
- exit non-zero = unhealthy

## 6.2 Mode mapping by service (Design A)

| Service | Mode | Target |
|---|---|---|
| Gateway | `tcp` | `127.0.0.1:${GATEWAY_PORT}` |
| Job | `tcp` | `127.0.0.1:${JOB_PORT}` |
| Queue | `tcp` | `127.0.0.1:${QUEUE_PORT}` |
| Coordinator | `tcp` | `127.0.0.1:${COORDINATOR_PORT}` |
| Result | `tcp` | `127.0.0.1:${RESULT_PORT}` |
| Worker | `worker` | `${COORDINATOR_ADDR}` |

## 6.3 Docker healthcheck timing policy

Default policy for all services:

- `interval: 5s`
- `timeout: 2s`
- `retries: 12`
- `start_period: 20s`

These defaults tolerate normal startup jitter while surfacing persistent failure in local development and CI smoke runs.

## 6.4 Readiness interpretation

- Gateway/Job/Queue/Coordinator/Result:
  - ready when startup succeeds **and** `mode=tcp` healthcheck passes.
- Worker:
  - ready when worker loop starts **and** `mode=worker` healthcheck passes coordinator reachability.

This model is intentionally minimal for v1 and sufficient for container orchestration and smoke validation.

---

## 7) Operational Notes

- Worker liveness authority is heartbeat-driven at the Coordinator (`HEARTBEAT_INTERVAL_MS`, `WORKER_TIMEOUT_MS`).
- Optional container-level healthcheck status supports operations; it does not replace canonical control-plane liveness semantics.
- Runtime behavior in this file is designed for deterministic, reproducible local/CI startup using Docker Compose.

---

## 8) Change Control for Runtime Contract

Any change to the following requires updating this file in the same change set:

- service ports or bind behavior,
- required/default env vars,
- dependency addresses,
- startup/readiness rules,
- healthcheck command shape, mode mappings, or timing.

When behavior changes, record what changed and why in the relevant handoff doc.

---
