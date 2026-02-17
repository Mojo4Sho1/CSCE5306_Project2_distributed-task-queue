# API Contracts (v1)

**Document path:** `docs/spec/api-contracts.md`  
**Status:** Locked for v1 implementation  
**Last updated:** 2026-02-17

---

## 1) Scope and Intent

This document defines the **API surface contracts** for the Distributed Task Queue project, including:

- namespace and proto layout,
- public and internal service/method sets,
- message schema contracts,
- caller-to-method authorization matrix,
- v1 scope boundaries and evolution rules.

Runtime wiring, health checks, and deployment details are documented separately in `docs/spec/runtime-config.md`.  
Error codes, retry policy, and idempotency behavior are documented in `docs/spec/error-idempotency.md`.  
Lifecycle transitions and race handling are documented in `docs/spec/state-machine.md`.

---

## 2) Namespace and Proto Layout (Locked)

### API namespace convention
- **Client-facing namespace:** `taskqueue.v1`
- **Internal namespace (Design A):** `taskqueue.internal.v1`

### Proto file layout (v1)
1. `proto/taskqueue_public.proto`
   - package: `taskqueue.v1`
   - client-facing RPCs and shared client-visible messages
   - service: `TaskQueuePublicService`

2. `proto/taskqueue_internal.proto`
   - package: `taskqueue.internal.v1`
   - internal service-to-service and worker-coordinator RPCs
   - services:
     - `JobInternalService`
     - `QueueInternalService`
     - `CoordinatorInternalService`
     - `ResultInternalService`

### Import rule (v1)
`taskqueue_internal.proto` may import public message/types as needed to avoid schema drift.  
No third "common proto" file is introduced in v1.

### Service naming convention (frozen)
Service names are frozen for v1 and must be used consistently in:
- proto definitions,
- generated stubs,
- documentation,
- implementation.

---

## 3) Architecture Equivalence Constraint (Public API)

Both architecture variants must expose the same client-facing methods and compatible semantics:

- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`
- `ListJobs`

**Parity scope (v1):**
- Strict semantic parity: `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`
- `ListJobs`: same schema and functional availability in both designs; Design B may be non-global best-effort in v1.

---

## 4) Public API Surface (must match in both designs)

## Service: `TaskQueuePublicService`

| Method | Public Endpoint Owner | Purpose |
|---|---|---|
| `SubmitJob` | Gateway Service | Accept a new job and return `job_id`. |
| `GetJobStatus` | Gateway Service | Return canonical status for `job_id`. |
| `GetJobResult` | Gateway Service | Return terminal output envelope when available. |
| `CancelJob` | Gateway Service | Request cancellation for queued/running job. |
| `ListJobs` | Gateway Service | Return recent jobs with filtering and pagination. |

---

## 5) Internal API Surface (Design A)

## Job Service (`JobInternalService`)
- `CreateJob`
- `DeleteJobIfStatus`
- `GetJobRecord`
- `ListJobRecords`
- `TransitionJobStatus`
- `SetCancelRequested`

## Queue Service (`QueueInternalService`)
- `EnqueueJob`
- `DequeueJob`
- `RemoveJobIfPresent`

## Coordinator Service (`CoordinatorInternalService`)
- `WorkerHeartbeat`
- `FetchWork`
- `ReportWorkOutcome`

## Result Service (`ResultInternalService`)
- `StoreResult`
- `GetResult`

## Worker role
Worker is an internal RPC client in v1 and has no client-facing business endpoint.

---

## 6) Caller-to-Method Matrix (Locked)

| Caller | Allowed Calls |
|---|---|
| External Client | Gateway: `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`, `ListJobs` |
| Gateway | Job: `CreateJob`, `DeleteJobIfStatus`, `GetJobRecord`, `ListJobRecords`, `SetCancelRequested`, `TransitionJobStatus` *(queued-cancel CAS only)*; Queue: `EnqueueJob`, `RemoveJobIfPresent`; Result: `GetResult`, `StoreResult` *(queued-cancel terminal envelope only)* |
| Coordinator | Queue: `DequeueJob`, `RemoveJobIfPresent`; Job: `TransitionJobStatus`, `GetJobRecord`; Result: `StoreResult` |
| Worker | Coordinator: `WorkerHeartbeat`, `FetchWork`, `ReportWorkOutcome` |

No other cross-service mutation paths are allowed in v1.

---

## 7) Proto v1 Scope Boundary (Frozen)

### Public RPC set (frozen)
- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`
- `ListJobs`

### Internal RPC set (frozen for v1)
- Job: `CreateJob`, `DeleteJobIfStatus`, `GetJobRecord`, `ListJobRecords`, `TransitionJobStatus`, `SetCancelRequested`
- Queue: `EnqueueJob`, `DequeueJob`, `RemoveJobIfPresent`
- Coordinator: `WorkerHeartbeat`, `FetchWork`, `ReportWorkOutcome`
- Result: `StoreResult`, `GetResult`

No additional RPC methods are introduced before:
1. proto compile success,
2. stub integration,
3. baseline microservice smoke tests.

---

## 8) Common Message Types (Locked)

## `JobStatus` enum
- `JOB_STATUS_UNSPECIFIED = 0`
- `QUEUED = 1`
- `RUNNING = 2`
- `DONE = 3`
- `FAILED = 4`
- `CANCELED = 5`

## `JobOutcome` enum
- `JOB_OUTCOME_UNSPECIFIED = 0`
- `JOB_OUTCOME_SUCCEEDED = 1`
- `JOB_OUTCOME_FAILED = 2`
- `JOB_OUTCOME_CANCELED = 3`

## `JobSort` enum
- `JOB_SORT_UNSPECIFIED = 0` (treated as `CREATED_AT_DESC`)
- `CREATED_AT_DESC = 1`
- `CREATED_AT_ASC = 2`

## `JobSpec`
- `string job_type`
- `uint32 work_duration_ms`
- `uint32 payload_size_bytes`
- `map<string, string> labels`

> `priority` is intentionally out of v1 scope.

## `JobSummary`
- `string job_id`
- `JobStatus status`
- `string job_type`
- `int64 created_at_ms`
- `int64 started_at_ms` (0 if not started)
- `int64 finished_at_ms` (0 if not finished)
- `bool cancel_requested`

## `PageRequest`
- `uint32 page_size`
- `string page_token` (stringified non-negative integer offset)

## `PageResponse`
- `string next_page_token` (stringified offset; empty means end)

---

## 9) Public Message Contracts and Semantics

## `SubmitJob`
### Request
- `JobSpec spec`
- `string client_request_id` (optional idempotency key)

### Response
- `string job_id`
- `JobStatus initial_status` (expected `QUEUED`)
- `int64 accepted_at_ms`

### Semantics (locked)
- If `client_request_id` is non-empty:
  - same key + same payload returns original `job_id`
  - same key + different payload returns `FAILED_PRECONDITION`
- If `client_request_id` is empty:
  - request is treated as non-idempotent (new submit attempt)
- Dedup guarantee holds only while key is retained in in-memory dedup store.

### Payload equivalence for dedup (locked)
“Same payload” requires canonical-equivalent `JobSpec`:
- identical `job_type`,
- identical `work_duration_ms`,
- identical `payload_size_bytes`,
- identical `labels` after key-sorted normalization.

---

## `GetJobStatus`
### Request
- `string job_id`

### Response
- `string job_id`
- `JobStatus status`
- `bool cancel_requested`
- `int64 created_at_ms`
- `int64 started_at_ms`
- `int64 finished_at_ms`
- `string failure_reason` (empty unless `FAILED`)

---

## `GetJobResult`
### Request
- `string job_id`

### Response
- `string job_id`
- `bool result_ready`
- `JobStatus terminal_status`
- `bytes output_bytes`
- `string output_summary`
- `uint32 runtime_ms`
- `string checksum`

### Semantics (locked)
- Non-terminal job: `result_ready=false`, `terminal_status=JOB_STATUS_UNSPECIFIED`
- Terminal `DONE`: `result_ready=true`; output bytes may be present
- Terminal `FAILED`: `result_ready=true`; bytes may be empty; failure details in summary
- Terminal `CANCELED`: `result_ready=true`; bytes may be empty; cancellation context in summary

### Canonical precedence (locked)
Readiness is derived from canonical Job Service status first.  
If status is non-terminal, return `result_ready=false` even if stale/orphan envelope exists in Result Service.

### Terminal mismatch rule (locked)
If canonical status is terminal but terminal envelope is missing:
- return gRPC `UNAVAILABLE`,
- log consistency anomaly with `job_id`.

### Terminal envelope minimums (locked)
- `DONE`: runtime + checksum + optional output bytes/summary
- `FAILED`: runtime (if known) + failure summary; bytes optional
- `CANCELED`: cancellation summary; bytes optional

---

## `CancelJob`
### Request
- `string job_id`
- `string reason`

### Response
- `string job_id`
- `bool accepted`
- `JobStatus current_status`
- `bool already_terminal`

### Semantics (locked)
- `accepted=true`: request processed through API path
- `already_terminal=true`: job was terminal before request
- `current_status` is authoritative at response time
- for `RUNNING`, `accepted=true` does not guarantee cancellation wins race
- unknown `job_id` returns `NOT_FOUND`

---

## `ListJobs`
### Request
- `repeated JobStatus status_filter`
- `PageRequest page`
- `JobSort sort` (default `CREATED_AT_DESC`)

### Response
- `repeated JobSummary jobs`
- `PageResponse page`

### Semantics (locked)
- Deterministic ordering: requested `created_at_ms` sort + tie-break `job_id` ascending
- empty `status_filter` means all statuses
- pagination is best-effort non-snapshot in v1

---

## 10) Internal Message Contracts (Design A)

## Job Service
- `CreateJobRequest { JobSpec spec; string client_request_id; }`
- `CreateJobResponse { string job_id; JobStatus status; }`
- `DeleteJobIfStatusRequest { string job_id; JobStatus expected_status; }`
- `DeleteJobIfStatusResponse { bool deleted; JobStatus current_status; }`
- `GetJobRecordRequest { string job_id; }`
- `GetJobRecordResponse { JobSummary summary; string failure_reason; }`
- `ListJobRecordsRequest { repeated JobStatus status_filter; PageRequest page; JobSort sort; }`
- `ListJobRecordsResponse { repeated JobSummary jobs; PageResponse page; }`
- `TransitionJobStatusRequest { string job_id; JobStatus expected_from_status; JobStatus to_status; string actor; string reason; }`
- `TransitionJobStatusResponse { bool applied; JobStatus current_status; }`
- `SetCancelRequestedRequest { string job_id; bool cancel_requested; string reason; }`
- `SetCancelRequestedResponse { bool applied; JobStatus current_status; }`

### Transition guard strictness (locked)
- `expected_from_status` is mandatory for CAS transitions
- `JOB_STATUS_UNSPECIFIED` for `expected_from_status` is invalid (`INVALID_ARGUMENT`)

---

## Queue Service
- `EnqueueJobRequest { string job_id; int64 enqueued_at_ms; }`
- `EnqueueJobResponse { bool accepted; }`
- `DequeueJobRequest { string worker_id; }`
- `DequeueJobResponse { bool found; string job_id; }`
- `RemoveJobIfPresentRequest { string job_id; }`
- `RemoveJobIfPresentResponse { bool removed; }`

### Queue ordering strength (locked)
- best-effort FIFO in v1
- strict global FIFO is not a correctness assumption

### Dequeue model (locked)
- destructive pop (no lease/ack/requeue protocol in v1)

---

## Coordinator Service
- `WorkerHeartbeatRequest { string worker_id; int64 heartbeat_at_ms; uint32 capacity_hint; }`
- `WorkerHeartbeatResponse { bool accepted; uint32 next_heartbeat_in_ms; }`
- `FetchWorkRequest { string worker_id; }`
- `FetchWorkResponse { bool assigned; string job_id; JobSpec spec; uint32 retry_after_ms; }`
- `ReportWorkOutcomeRequest { string worker_id; string job_id; JobOutcome outcome; uint32 runtime_ms; string failure_reason; string output_summary; bytes output_bytes; string checksum; }`
- `ReportWorkOutcomeResponse { bool accepted; }`

### FetchWork idle semantics (locked)
If no work is available:
- `assigned=false`
- server returns `retry_after_ms` (default hint 200 ms, clamped to [50, 1000])

---

## Result Service
- `StoreResultRequest { string job_id; JobStatus terminal_status; uint32 runtime_ms; string output_summary; bytes output_bytes; string checksum; }`
- `StoreResultResponse { bool stored; bool already_exists; JobStatus current_terminal_status; }`
- `GetResultRequest { string job_id; }`
- `GetResultResponse { bool found; string job_id; JobStatus terminal_status; uint32 runtime_ms; string output_summary; bytes output_bytes; string checksum; }`

### StoreResult conflict semantics (locked)
- `stored=true`: this call performed/confirmed canonical terminal envelope storage
- `already_exists=true`: prior terminal envelope exists
- `current_terminal_status`: authoritative stored terminal status

---

## 11) Field and Type Conventions (Locked)

- IDs: `string` UUIDv4 (v1)
- Time: `int64` epoch ms UTC (server-generated)
- Durations: `uint32` milliseconds
- Binary output: `bytes`
- Optional text: empty string when unset

### Pagination rules
- default `page_size = 50`
- max `page_size = 200` (clamp above max)
- `page_size=0` uses default
- `page_token` is stringified non-negative integer offset
- invalid token format returns `INVALID_ARGUMENT`

### Worker identity
`worker_id` source priority:
1. `WORKER_ID` env var
2. container hostname fallback

### Constants referenced by API behavior
- `HEARTBEAT_INTERVAL_MS = 1000`
- `WORKER_TIMEOUT_MS = 4000`
- `MAX_OUTPUT_BYTES = 262144` (256 KiB)
- `MAX_DEDUP_KEYS = 10000`

### Checksum format
Lowercase hex SHA-256 over `output_bytes` (including empty payload).

### Timestamp authority mapping
- `created_at_ms`: set by Job Service on `CreateJob`
- `started_at_ms`: set by Job Service when `QUEUED -> RUNNING` CAS applies
- `finished_at_ms`: set by Job Service when terminal CAS applies

---

## 12) Proto Evolution Hygiene (Locked)

After v1 freeze:
1. Do not rename/remove existing fields.
2. Add fields only additively with new field numbers.
3. Keep enum numeric values stable.
4. Reserve retired field numbers/names; do not reuse.
5. Shared client-visible enums/messages remain single-source in public proto.

---

## 13) Cross-References

- Lifecycle/transition ownership and race rules: `docs/spec/state-machine.md`
- gRPC status codes, idempotency matrix, retry/backoff: `docs/spec/error-idempotency.md`
- Runtime addresses, ports, env vars, readiness: `docs/spec/runtime-config.md`
- Fairness constraints and Design B routing policy: `docs/spec/fairness-evaluation.md`

---

## 14) Change Control for API Contract Updates

Any API contract change must update, in the same change set:
1. this file (`docs/spec/api-contracts.md`),
2. proto definitions under `proto/`,
3. generated stubs under `generated/` (if committed),
4. relevant implementation handlers,
5. tests and smoke checks impacted by the change.
