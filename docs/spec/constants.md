# Constants (v1)

**Status:** Locked defaults for v1 implementation and benchmarking  
**Freeze date:** 2026-02-10

This file centralizes frozen constants and default values used across services, load generation, and evaluation.

> If this file and implementation diverge, treat as documentation/code drift and reconcile explicitly in the same change set.

---

## 1) Topology and Fairness Constants

| Constant | Value | Notes |
|---|---:|---|
| `TOTAL_WORKER_SLOTS` | `6` | Fixed total execution capacity across both designs for parity |
| `DESIGN_A_WORKER_CONTAINERS` | `1` | Microservices design |
| `DESIGN_A_SLOTS_PER_WORKER` | `6` | Microservices design |
| `DESIGN_B_MONOLITH_NODES` | `6` | Monolith-per-node design |
| `DESIGN_B_SLOTS_PER_NODE` | `1` | Monolith-per-node design |

---

## 2) Service Ports (Design A)

| Service | Env Var | Default |
|---|---|---:|
| Gateway | `GATEWAY_PORT` | `50051` |
| Job | `JOB_PORT` | `50052` |
| Queue | `QUEUE_PORT` | `50053` |
| Coordinator | `COORDINATOR_PORT` | `50054` |
| Result | `RESULT_PORT` | `50055` |

---

## 3) Upstream Address Defaults (Design A)

| Consumer | Variable | Default |
|---|---|---|
| Gateway | `JOB_SERVICE_ADDR` | `job:50052` |
| Gateway | `QUEUE_SERVICE_ADDR` | `queue:50053` |
| Gateway | `RESULT_SERVICE_ADDR` | `result:50055` |
| Coordinator | `JOB_SERVICE_ADDR` | `job:50052` |
| Coordinator | `QUEUE_SERVICE_ADDR` | `queue:50053` |
| Coordinator | `RESULT_SERVICE_ADDR` | `result:50055` |
| Worker | `COORDINATOR_ADDR` | `coordinator:50054` |

---

## 4) Worker Liveness and Fetch Work Timing

| Constant | Value |
|---|---:|
| `HEARTBEAT_INTERVAL_MS` | `1000` |
| `WORKER_TIMEOUT_MS` | `4000` |
| `FETCHWORK_RETRY_AFTER_DEFAULT_MS` | `200` |
| `FETCHWORK_RETRY_AFTER_MIN_MS` | `50` |
| `FETCHWORK_RETRY_AFTER_MAX_MS` | `1000` |

---

## 5) Request Deadlines

### Client -> Gateway defaults

| Method | Deadline |
|---|---:|
| `SubmitJob` | `3000 ms` |
| `CancelJob` | `3000 ms` |
| `GetJobStatus` | `1000 ms` |
| `GetJobResult` | `1000 ms` |
| `ListJobs` | `1000 ms` |

### Internal RPC defaults

| Call Type / Method | Deadline |
|---|---:|
| Unary service-to-service calls | `1000 ms` |
| `FetchWork` | `1500 ms` |
| `WorkerHeartbeat` | `1000 ms` |

---

## 6) Retry and Backoff Profile (v1)

| Constant | Value |
|---|---|
| `RETRY_BACKOFF_STRATEGY` | Exponential |
| `RETRY_JITTER_MODE` | Full jitter |
| `RETRY_INITIAL_DELAY_MS` | `100` |
| `RETRY_MULTIPLIER` | `2.0` |
| `RETRY_MAX_DELAY_MS` | `1000` |
| `RETRY_MAX_ATTEMPTS` | `4` total (initial + 3 retries) |

### Auto-retry gRPC codes
- `UNAVAILABLE`
- `DEADLINE_EXCEEDED`
- `RESOURCE_EXHAUSTED` (if used)

### Submit retry rule
- Auto-retry `SubmitJob` **only** when `client_request_id` is non-empty.
- If `client_request_id` is empty, do **not** auto-retry.

---

## 7) Pagination and Listing Defaults

| Constant | Value |
|---|---|
| `DEFAULT_PAGE_SIZE` | `50` |
| `MAX_PAGE_SIZE` | `200` |
| `PAGE_TOKEN_FORMAT` | Stringified non-negative integer offset |
| `DEFAULT_SORT` | `CREATED_AT_DESC` |

Additional rule:
- In v1, `ListJobs` page tokens are valid only for the same `(status_filter, sort)` query shape.

---

## 8) Data and Storage Bounds

| Constant | Value | Notes |
|---|---:|---|
| `MAX_OUTPUT_BYTES` | `262144` | 256 KiB output cap |
| `MAX_DEDUP_KEYS` | `10000` | In-memory dedup bound |
| `DEDUP_SCOPE` | Process lifetime | Not preserved across restarts |

---

## 9) Job Identity, Time, and Checksums

| Constant | Value |
|---|---|
| `JOB_ID_FORMAT` | UUIDv4 |
| `TIME_FORMAT` | UTC epoch milliseconds (`int64`) |
| `CHECKSUM_ALGORITHM` | SHA-256 |
| `CHECKSUM_FORMAT` | Lowercase hex of `output_bytes` |

Timestamp authority mapping:
- `created_at_ms`: set by Job Service on create
- `started_at_ms`: set by Job Service on `QUEUED -> RUNNING` CAS
- `finished_at_ms`: set by Job Service on terminal CAS

---

## 10) Routing Constants (Design B)

| Constant | Value |
|---|---|
| `OWNER_HASH_FUNCTION` | SHA-256 |
| `OWNER_HASH_PREFIX_BYTES` | `8` (first 8 bytes) |
| `OWNER_UINT_ENDIAN` | Big-endian unsigned 64-bit |
| `OWNER_INDEX_FORMULA` | `uint64_be(first_8_bytes(sha256(key))) % N` |
| `OWNER_NODE_COUNT_DEFAULT` | `6` |
| `OWNER_NODE_ORDER_SOURCE` | Fixed ordered node list from config |

Routing keys:
- `SubmitJob` with non-empty `client_request_id`: route by `client_request_id`
- `GetJobStatus`, `GetJobResult`, `CancelJob`: route by `job_id`

---

## 11) Healthcheck Defaults

Shared healthcheck command:
- `python -m scripts.healthcheck --mode <tcp|worker> --target <host:port> --timeout-ms <ms> --service <name>`

| Constant | Value |
|---|---|
| `HEALTHCHECK_DEFAULT_TIMEOUT_MS` | `1000` |
| `DOCKER_HEALTHCHECK_INTERVAL` | `5s` |
| `DOCKER_HEALTHCHECK_TIMEOUT` | `2s` |
| `DOCKER_HEALTHCHECK_RETRIES` | `12` |
| `DOCKER_HEALTHCHECK_START_PERIOD` | `20s` |

Exit semantics:
- `0` healthy
- non-zero unhealthy

---

## 12) Lifecycle and Queue Behavior Constants

| Constant | Value |
|---|---|
| `CANONICAL_JOB_STATES` | `QUEUED`, `RUNNING`, `DONE`, `FAILED`, `CANCELED` |
| `TERMINAL_JOB_STATES` | `DONE`, `FAILED`, `CANCELED` |
| `QUEUE_ORDERING_STRENGTH` | Best-effort FIFO |
| `DEQUEUE_MODEL` | Destructive pop (no lease/ack/requeue in v1) |
| `EXECUTION_SEMANTICS` | At-least-once |

---

## 13) Logging Contract Constants

| Constant | Value |
|---|---|
| `LOG_FORMAT` | JSON Lines |

Required fields:
- `ts_ms`
- `level`
- `service`
- `method`
- `event`
- `job_id` (if present)
- `worker_id` (if present)
- `grpc_code` (for non-OK)
- `message`

Recommended fields:
- `request_id`
- `latency_ms`
- `expected_status`
- `current_status`

---

## 14) Common Environment Defaults

| Variable | Default |
|---|---|
| `LOG_LEVEL` | `INFO` |
| `PYTHONUNBUFFERED` | `1` |
| `WORKER_ID` | Container hostname fallback when unset |

---

## 15) Public API Surface (Frozen for v1)

- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`
- `ListJobs`

Internal API additions are out of scope until v1 baseline implementation and smoke validation are complete.
