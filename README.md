# Distributed Task Queue (Distributed Systems Project)

## Project Goal
Design, implement, and evaluate a distributed task queue system using gRPC and Dockerized nodes.  
The project compares two distributed designs and analyzes performance/scalability trade-offs.

---

## System Summary

This project implements a toy distributed task queue that supports:
- job submission
- queueing and dispatch
- worker execution
- status/result retrieval
- cancellation and job listing

The system uses **gRPC + Protocol Buffers** for service-to-service and client-to-service communication.

---

## Architectures Compared

### Design A: Microservices (6 functional nodes)
1. **Gateway Service**
2. **Job Service**
3. **Queue Service**
4. **Coordinator Service**
5. **Worker Service**
6. **Result Service**

> Note: A load generator may run as a separate evaluation client/container, but it is **not** counted as one of the six functional system nodes.

### Design B: Monolith-per-node (6 nodes)
- Six identical nodes
- Each node runs most/all core functionality in-process
- Exposes equivalent external API for fair comparison

---

## Fair-Comparison Constraint (API Equivalence)

To ensure a fair comparison, both designs expose the same **client-facing** gRPC API:

- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`
- `ListJobs`

Both designs use equivalent request/response schemas and status semantics for these methods.  
The experiments also use the same load-generation and measurement logic across both designs.

> Internal service RPCs (e.g., worker heartbeat/fetch-work) may differ between designs, but client-facing behavior remains equivalent.

---

## Communication Model
- **gRPC (RPC)**
- **Protocol Buffers** for interface contracts and message schemas

---

## Functional Requirements
1. **SubmitJob**: Accept a job request and return a unique job ID.
2. **GetJobStatus**: Return the current state of a job.
3. **GetJobResult**: Return job output after completion.
4. **CancelJob**: Cancel pending jobs (best-effort for running jobs).
5. **ListJobs**: List jobs with filtering/pagination support.
6. **WorkerHeartbeat / FetchWork**: Support worker liveness and job retrieval.

---

## Non-Functional Requirements (NFRs)

1. **NFR-1 (API Contract Consistency):**  
   Both architectures expose equivalent client-facing gRPC APIs and status semantics.

2. **NFR-2 (Scalability Testability):**  
   The system supports controlled load tests across multiple concurrency levels without code changes.

3. **NFR-3 (Performance Observability):**  
   The evaluation records throughput (req/s, jobs/s), latency percentiles (p50/p95/p99), and end-to-end completion time.

4. **NFR-4 (Reproducibility):**  
   A clean environment can reproduce deployment and benchmark execution using documented Docker Compose and scripts.

5. **NFR-5 (Baseline Fault Handling):**  
   The coordinator tracks worker heartbeats and marks workers unavailable after timeout; queue operations do not silently drop queued jobs.

---

## Service Ownership Boundaries (Phase 0 Lock)

This project uses a single-owner model: each data domain has one primary owner service.

### Gateway Service
**Owns:** client-facing gRPC API surface and request routing/orchestration.  
**Does not own:** canonical job state, queue internals, worker registry, or result payload storage.

### Job Service
**Owns:** canonical job metadata and lifecycle status for each job ID (job spec, creation time, current state, cancellation flags).  
**Does not own:** queue ordering, worker liveness, dispatch policy, or result payload storage.

### Queue Service
**Owns:** queue primitives only (`enqueue`, `dequeue`, `remove-if-present`).  
**Does not own:** canonical lifecycle status, worker selection policy, or result payloads.

### Coordinator Service
**Owns:** worker liveness registry, heartbeat timeout policy, and dispatch orchestration flow.  
**Does not own:** canonical job metadata schema or result payload persistence.

### Worker Service
**Owns:** execution of assigned jobs and reporting outcomes.  
**Does not own:** global queue policy, canonical lifecycle authority, or client-facing API behavior.  
In v1, Worker Service may run no public server endpoints; it primarily acts as an RPC client to Coordinator (`WorkerHeartbeat`, `FetchWork`, `ReportWorkOutcome`). Any local health endpoint is optional and out of public API scope.

### Result Service
**Owns:** completed job output retrieval path and result payload records.  
**Does not own:** queueing, worker liveness, or dispatch decisions.

### Mutation Authority Rules (Locked)
- **Canonical status authority:** Job Service is the source of truth for job status.
- **Queue authority:** Queue Service is the only service that mutates queue contents.
- **Worker liveness authority:** Coordinator Service is the only service that determines worker availability from heartbeats.
- **Result payload authority:** Result Service is the only service that stores/retrieves final output payloads.

### Boundary Invariants (Locked)
1. No service writes another service’s internal store directly.
2. All cross-service actions use gRPC contracts.
3. Gateway remains stateless with respect to canonical job state.
4. Worker executes assigned jobs only; it does not self-assign via local policy.

---

## Job Lifecycle and State Machine (Phase 0 Lock)

### Canonical Job States
The system uses exactly five canonical states:

- `QUEUED`
- `RUNNING`
- `DONE`
- `FAILED`
- `CANCELED`

No additional canonical states are introduced in v1.

### Lifecycle Graph
`QUEUED -> RUNNING -> DONE | FAILED`  
`QUEUED -> CANCELED`  
`RUNNING -> CANCELED` (best-effort; see cancellation semantics)

### Transition Ownership
- **Job Service** is the canonical authority for job status values.
- **Coordinator Service** orchestrates execution-related transitions (dispatch/worker outcomes).
- **Gateway Service** can request cancellation, but does not directly mutate status stores.
- **Queue Service** owns queue membership only (not canonical status).

### Allowed Transitions (Locked)

| Trigger | From | To | Primary Actor | Notes |
|---|---|---|---|---|
| Successful `SubmitJob` | (none) | `QUEUED` | Gateway -> Job (+ Queue) | Job is considered accepted only when enqueue succeeds. |
| Work assignment / dequeue | `QUEUED` | `RUNNING` | Coordinator | Coordinator dispatches work to worker. |
| Worker success report | `RUNNING` | `DONE` | Worker -> Coordinator -> Job | Result payload is persisted in Result Service. |
| Worker failure report | `RUNNING` | `FAILED` | Worker -> Coordinator -> Job | Failure reason is stored with metadata. |
| Cancel pending job | `QUEUED` | `CANCELED` | Gateway/Coordinator -> Job (+ Queue remove) | Must remove from queue if still present. |
| Cancel running job (best-effort) | `RUNNING` | `CANCELED` | Gateway/Coordinator/Worker | If cancellation reaches worker in time, final state is `CANCELED`. |

### Submit Acceptance Atomicity (Locked)
`SubmitJob` acceptance follows this sequence in Design A:

1. Gateway requests `CreateJob` (initial status `QUEUED`) in Job Service.
2. Gateway requests `EnqueueJob` in Queue Service.
3. The submit is **accepted** only if enqueue succeeds.
4. If enqueue fails after create succeeds, Gateway performs compensating action:
   - `DeleteJobIfStatus(job_id, expected_status=QUEUED)` in Job Service.
5. If compensation succeeds, client receives failure (typically `UNAVAILABLE`) and no accepted job remains.
6. If compensation fails, event is logged as consistency anomaly for manual/debug follow-up.

### Cancellation Semantics (Locked)

1. **Queued cancellation:** expected to succeed if the job has not started.
2. **Running cancellation:** best-effort only.
   - If worker receives cancellation before finishing, final state is `CANCELED`.
   - If worker finishes first, final state is `DONE` or `FAILED`.
3. Repeated cancellation requests are idempotent no-ops once job is terminal.

### Terminal-State Rule (Locked)

`DONE`, `FAILED`, and `CANCELED` are terminal states.  
Once a job reaches a terminal state, it cannot transition to another state.

### Invalid Transition Handling (Locked)

Any transition not explicitly listed in the allowed table is rejected and logged as invalid.  
Examples:
- `DONE -> RUNNING`
- `FAILED -> DONE`
- `CANCELED -> RUNNING`

### Consistency / Retry Note (v1 Scope)

This v1 implementation uses **at-least-once execution semantics** and in-memory state.  
If duplicate completion reports occur, canonical status follows first valid terminal write; later conflicting writes are ignored and logged.

### Monolith Equivalence Constraint

The monolith-per-node design must preserve the same externally visible lifecycle semantics and terminal-state behavior for fair comparison.

---

## API Surface Lock (Phase 0.4)

This section freezes the method-level API surface and service ownership for v1.

### API Namespace Convention (Locked)
- **Client-facing API namespace:** `taskqueue.v1`
- **Internal microservice API namespace (Design A):** `taskqueue.internal.v1`

This separation prevents accidental coupling between public and internal contracts.

### A) Client-Facing API (Design A and Design B must match)

These methods define the externally visible system contract and must remain equivalent across both architectures.

| Method | Public Endpoint Owner | Purpose |
|---|---|---|
| `SubmitJob` | Gateway Service | Accept a new job and return `job_id`. |
| `GetJobStatus` | Gateway Service | Return canonical status for a `job_id`. |
| `GetJobResult` | Gateway Service | Return final output when available. |
| `CancelJob` | Gateway Service | Request cancellation (queued expected, running best-effort). |
| `ListJobs` | Gateway Service | Return recent jobs with filtering/pagination. |

**Fairness lock:** request/response semantics for these five methods are equivalent in both designs.

### B) Internal Microservice API (Design A)

These methods are internal implementation RPCs for the microservices design.

#### Job Service (canonical metadata/status authority)
- `CreateJob`
- `DeleteJobIfStatus`
- `GetJobRecord`
- `ListJobRecords`
- `TransitionJobStatus`
- `SetCancelRequested`

#### Queue Service (queue primitives only)
- `EnqueueJob`
- `DequeueJob`
- `RemoveJobIfPresent`

#### Coordinator Service (liveness + dispatch orchestration)
- `WorkerHeartbeat`
- `FetchWork`
- `ReportWorkOutcome`

#### Result Service (result payload authority)
- `StoreResult`
- `GetResult`

#### Worker Service
- Worker is primarily an RPC **client** in v1 (calls coordinator for heartbeat/fetch/report).
- Worker does not own client-facing endpoints.
- A local health endpoint may exist but is out of public API scope.

### C) Caller-to-Method Matrix (Locked)

| Caller | Allowed Calls |
|---|---|
| External Client | Gateway: `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`, `ListJobs` |
| Gateway | Job: `CreateJob`, `DeleteJobIfStatus`, `GetJobRecord`, `ListJobRecords`, `SetCancelRequested`; Queue: `EnqueueJob`, `RemoveJobIfPresent`; Result: `GetResult` |
| Coordinator | Queue: `DequeueJob`, `RemoveJobIfPresent`; Job: `TransitionJobStatus`, `GetJobRecord`; Result: `StoreResult` |
| Worker | Coordinator: `WorkerHeartbeat`, `FetchWork`, `ReportWorkOutcome` |

No other cross-service mutations are allowed in v1.

### D) Status/Result Authority Lock

- Canonical status returned to clients is sourced from **Job Service**.
- Final output payload returned to clients is sourced from **Result Service**.
- Gateway composes responses; it does not own canonical state.

### E) Monolith Equivalence Constraint

In Design B (monolith-per-node), internal method calls may become in-process function calls, but client-facing behavior for the five public API methods must remain equivalent.

### F) Change Control for API Surface

Any method addition/removal/rename after this lock must record:
1. what changed,
2. why it changed,
3. expected impact on fairness, implementation, and evaluation.

---

## Message Schema Draft (Phase 0.5 Lock)

This section freezes the v1 message shapes (fields + types + semantics) before `.proto` implementation.

### Schema Design Principles (Locked)

1. Keep v1 minimal and implementation-friendly.
2. Prefer explicit fields over deeply nested payloads.
3. Use stable IDs and timestamps in milliseconds since epoch.
4. Keep client-facing messages architecture-agnostic for fair comparison.
5. Use enums for lifecycle-critical states (no free-text status strings).

### Common Types (Locked)

#### `JobStatus` (enum)
- `JOB_STATUS_UNSPECIFIED = 0`
- `QUEUED = 1`
- `RUNNING = 2`
- `DONE = 3`
- `FAILED = 4`
- `CANCELED = 5`

#### `JobOutcome` (enum; worker/coordinator internal outcome)
- `JOB_OUTCOME_UNSPECIFIED = 0`
- `SUCCEEDED = 1`
- `FAILED = 2`
- `CANCELED = 3`

#### `JobSpec`
- `string job_type`
- `uint32 work_duration_ms`
- `uint32 payload_size_bytes`
- `uint32 priority`
- `map<string, string> labels`

> `work_duration_ms` and `payload_size_bytes` are workload knobs for repeatable benchmarking.  
> `priority` is accepted in the v1 schema for forward compatibility, but dispatch ignores priority and uses FIFO order in v1. Priority-aware scheduling is out of scope for v1.

#### `JobSummary`
- `string job_id`
- `JobStatus status`
- `string job_type`
- `int64 created_at_ms`
- `int64 started_at_ms` (0 if not started)
- `int64 finished_at_ms` (0 if not finished)
- `bool cancel_requested`

#### `PageRequest`
- `uint32 page_size`
- `string page_token`

#### `PageResponse`
- `string next_page_token`

#### `ErrorInfo` (in-band structured detail; does not replace gRPC status codes)
- `string code`
- `string message`
- `string details`

### A) Client-Facing API Message Draft (Locked)

#### `SubmitJob`
**Request:**
- `JobSpec spec`
- `string client_request_id` (optional idempotency key)

**Response:**
- `string job_id`
- `JobStatus initial_status` (expected: `QUEUED`)
- `int64 accepted_at_ms`

#### `GetJobStatus`
**Request:**
- `string job_id`

**Response:**
- `string job_id`
- `JobStatus status`
- `bool cancel_requested`
- `int64 created_at_ms`
- `int64 started_at_ms`
- `int64 finished_at_ms`
- `string failure_reason` (empty unless `FAILED`)

#### `GetJobResult`
**Request:**
- `string job_id`

**Response:**
- `string job_id`
- `bool result_ready`
- `JobStatus terminal_status`
- `bytes output_bytes` (optional; may be empty in v1)
- `string output_summary`
- `uint32 runtime_ms`
- `string checksum`

**Locked semantics:**
- If the job is **not terminal**: `result_ready = false`, `terminal_status = JOB_STATUS_UNSPECIFIED`.
- If the job is **terminal**: `result_ready = true`, `terminal_status ∈ {DONE, FAILED, CANCELED}`.

#### `CancelJob`
**Request:**
- `string job_id`
- `string reason`

**Response:**
- `string job_id`
- `bool accepted`
- `JobStatus current_status`
- `bool already_terminal`

#### `ListJobs`
**Request:**
- `repeated JobStatus status_filter`
- `PageRequest page`
- `string sort_by` (default: `created_at_desc`)

**Response:**
- `repeated JobSummary jobs`
- `PageResponse page`

Pagination behavior follows Section C field conventions (`page_size` default `50`, max `200`).

### B) Internal Microservice Message Draft (Design A)

#### Job Service
**`CreateJobRequest`**
- `JobSpec spec`
- `string client_request_id`
- `int64 created_at_ms`

**`CreateJobResponse`**
- `string job_id`
- `JobStatus status` (expected `QUEUED`)

**`DeleteJobIfStatusRequest`**
- `string job_id`
- `JobStatus expected_status` (for v1 compensation path this is `QUEUED`)

**`DeleteJobIfStatusResponse`**
- `bool deleted`
- `JobStatus current_status`

**`GetJobRecordRequest`**
- `string job_id`

**`GetJobRecordResponse`**
- `JobSummary summary`
- `string failure_reason`

**`ListJobRecordsRequest`**
- `repeated JobStatus status_filter`
- `PageRequest page`

**`ListJobRecordsResponse`**
- `repeated JobSummary jobs`
- `PageResponse page`

**`TransitionJobStatusRequest`**
- `string job_id`
- `JobStatus expected_from_status`
- `JobStatus to_status`
- `string actor` (e.g., `coordinator`, `worker`)
- `string reason`

**`TransitionJobStatusResponse`**
- `bool applied`
- `JobStatus current_status`

**`SetCancelRequestedRequest`**
- `string job_id`
- `bool cancel_requested`
- `string reason`

**`SetCancelRequestedResponse`**
- `bool applied`
- `JobStatus current_status`

#### Queue Service
**`EnqueueJobRequest`**
- `string job_id`
- `int64 enqueued_at_ms`

**`EnqueueJobResponse`**
- `bool accepted`

**`DequeueJobRequest`**
- `string worker_id`

**`DequeueJobResponse`**
- `bool found`
- `string job_id`

**`RemoveJobIfPresentRequest`**
- `string job_id`

**`RemoveJobIfPresentResponse`**
- `bool removed`

#### Coordinator Service
**`WorkerHeartbeatRequest`**
- `string worker_id`
- `int64 heartbeat_at_ms`
- `uint32 capacity_hint`

**`WorkerHeartbeatResponse`**
- `bool accepted`
- `uint32 next_heartbeat_in_ms`

**`FetchWorkRequest`**
- `string worker_id`

**`FetchWorkResponse`**
- `bool assigned`
- `string job_id`
- `JobSpec spec`

**`ReportWorkOutcomeRequest`**
- `string worker_id`
- `string job_id`
- `JobOutcome outcome`
- `uint32 runtime_ms`
- `string failure_reason`
- `string output_summary`
- `bytes output_bytes`
- `string checksum`

**`ReportWorkOutcomeResponse`**
- `bool accepted`

#### Result Service
**`StoreResultRequest`**
- `string job_id`
- `JobStatus terminal_status` (`DONE`, `FAILED`, or `CANCELED`)
- `uint32 runtime_ms`
- `string output_summary`
- `bytes output_bytes`
- `string checksum`

**`StoreResultResponse`**
- `bool stored`

**`GetResultRequest`**
- `string job_id`

**`GetResultResponse`**
- `bool found`
- `string job_id`
- `JobStatus terminal_status`
- `uint32 runtime_ms`
- `string output_summary`
- `bytes output_bytes`
- `string checksum`

### C) Field/Type Conventions (Locked)

- IDs: `string` (UUID/ULID format decided at implementation time)
- Time: `int64` milliseconds since epoch (UTC)
- Durations: `uint32` milliseconds
- Binary output: `bytes`
- Optional text fields use empty string when not set in v1
- `ListJobs` pagination defaults: `page_size` default is `50`; maximum is `200`.
- If `page_size == 0`, the server uses default `50`.
- If `page_size > 200`, the server clamps to `200`.

### D) Backward-Compatibility Note (v1)

- Do not rename or remove fields after proto v1 freeze.
- New fields must be additive and use new field numbers.
- Enum numeric values remain stable once published.

---

## Error Model and Idempotency Behavior (Phase 0.6 Lock)

This section freezes error semantics and idempotency behavior for v1.

### 1) Error Handling Model (Locked)

The system uses a two-layer model:

1. **Hard errors** use gRPC status codes (non-OK RPC response).
2. **Soft outcomes** return `OK` with explicit response fields (e.g., `accepted`, `result_ready`, `already_terminal`, `applied`).

This prevents overloading gRPC errors for normal control flow.

### 2) gRPC Status Code Policy (Locked)

| Condition | gRPC Code | Retry Guidance | Notes |
|---|---|---|---|
| Invalid/malformed request fields | `INVALID_ARGUMENT` | Do not retry until request is fixed | Example: empty `job_id`, invalid page token format |
| Unknown `job_id` | `NOT_FOUND` | Do not retry (unless eventual creation is expected) | Applies to status/result/cancel lookups |
| Idempotency key reused with different payload | `FAILED_PRECONDITION` | Do not retry with same conflicting key | Client must use a new key |
| Temporary capacity pressure / rate limiting | `RESOURCE_EXHAUSTED` | Retry with backoff | Optional in v1, if rate limits are enabled |
| Downstream service unavailable | `UNAVAILABLE` | Retry with backoff + jitter | Transient service/network conditions |
| Request deadline exceeded | `DEADLINE_EXCEEDED` | Retry with backoff (idempotent methods only) | Caller should use sane deadlines |
| Unexpected server failure | `INTERNAL` | Retry cautiously | Also log with correlation metadata |

### 3) Soft Outcome Policy (Locked)

Use normal (`OK`) responses for these non-exception outcomes:
- `GetJobResult` when job is not terminal yet (`result_ready = false`).
- `CancelJob` when job is already terminal (`already_terminal = true`).
- Duplicate cancellation requests after cancellation is already requested (deterministic non-error response).
- `TransitionJobStatus` CAS mismatch (`applied = false`, return current status).
- `DeleteJobIfStatus` condition mismatch (`deleted = false`, return current status).

### 4) Client-Facing Idempotency Matrix (Locked)

| Method | Idempotent? | Key / Identity | Required Behavior |
|---|---|---|---|
| `SubmitJob` | **Conditionally** | `client_request_id` (if provided) | Same key + same effective payload returns original `job_id` (no duplicate job creation). Same key + different payload returns `FAILED_PRECONDITION`. Missing key is treated as non-idempotent submission. |
| `GetJobStatus` | Yes | `job_id` | Safe repeated calls; no side effects. |
| `GetJobResult` | Yes | `job_id` | Safe repeated calls; no side effects. |
| `CancelJob` | Yes | `job_id` | Repeated calls must be deterministic and side-effect stable. |
| `ListJobs` | Yes (read-only) | filter + page token | Repeated call with same inputs is safe; ordering consistency is best-effort under concurrent updates. |

**v1 dedup scope lock:** idempotency-key deduplication is enforced in-memory for process lifetime only (not across service restarts).

### 5) Internal API Idempotency Matrix (Design A, Locked)

| Internal Method | Idempotent? | Required Behavior |
|---|---|---|
| `CreateJob` | Conditionally | Deduplicate by `client_request_id` when present. |
| `DeleteJobIfStatus` | Conditional | Deletes only if current status matches expected status; otherwise no-op. |
| `EnqueueJob` | Yes-by-key | Same `job_id` must not appear twice in queue. |
| `RemoveJobIfPresent` | Yes | Repeated remove calls are safe. |
| `TransitionJobStatus` | Conditional (CAS style) | Apply only when `expected_from_status` matches current; otherwise `OK` + `applied=false`. |
| `SetCancelRequested` | Yes | Repeated set-to-true remains true; no duplicate side effects. |
| `WorkerHeartbeat` | Yes | Latest heartbeat refreshes liveness timestamp. |
| `FetchWork` | No (assignment side effects) | May return different work per call; worker must treat delivery as at-least-once. |
| `ReportWorkOutcome` | Effectively idempotent per job terminal rule | First valid terminal write wins; later conflicting terminal reports are ignored and logged. |
| `StoreResult` | Idempotent by `job_id` terminal record | Duplicate equivalent writes are safe; conflicting second terminal write is ignored and logged. |
| `GetResult` / `GetJobRecord` / `ListJobRecords` | Yes | Read-only; safe repeats. |

### 6) Retry/Backoff Guidance (Locked)

Clients and services should only auto-retry on transient failures:
- `UNAVAILABLE`
- `DEADLINE_EXCEEDED`
- `RESOURCE_EXHAUSTED` (if applicable)

Use exponential backoff with jitter.  
Do **not** auto-retry on `INVALID_ARGUMENT`, `NOT_FOUND`, or `FAILED_PRECONDITION` without changing request/state assumptions.

### 7) Determinism Rules for Cancellation (Locked)

- If job is `QUEUED`, cancellation transitions toward `CANCELED` and queue entry is removed.
- If job is `RUNNING`, cancellation remains best-effort.
- Once terminal (`DONE`, `FAILED`, `CANCELED`), repeated `CancelJob` is non-error and deterministic (`already_terminal = true`).

### 8) Observability Requirements for Errors (Locked)

For every non-OK response, log:
- timestamp
- method name
- code
- message
- job_id (if present)
- caller/service identity (if available)

This is required for debugging and report reproducibility.

---

## Phase 0 Decision Lock (Frozen)

**Freeze date:** 2026-02-10

- System choice is fixed to **Distributed Task Queue**.
- Architecture comparison is fixed to:
  - **Design A:** Microservices (6 functional nodes)
  - **Design B:** Monolith-per-node (6 nodes)
- Node-count rule is fixed: load generator is not a functional node.
- Communication model is fixed to gRPC + protobuf.
- Storage assumption is fixed to **in-memory state** for this project.
- Processing semantics are fixed to **at-least-once** execution.
- Cancellation semantics are fixed to: queued cancellation expected; running cancellation best-effort.
- Evaluation fairness controls are fixed to: same hardware, workload profiles, warm-up, run duration, and measurement method for both designs.

### Out of Scope (Scope Control)
- Durable persistence guarantees
- Consensus/leader-election protocols
- Exactly-once processing guarantees
- Production-grade security hardening
- Multi-region deployment

### Change Control
If any frozen decision changes, record:
1. what changed,
2. why it changed,
3. expected impact on implementation/evaluation.

---

## Evaluation Plan (High Level)

The project evaluates both architectures under varying workloads by measuring:
- **Throughput** (requests/sec, jobs/sec)
- **Latency** (p50/p95/p99)
- **End-to-end completion time** (submit → done)

Workload factors include:
- client concurrency
- job duration
- request mix (submit/status/result)

---

## Tech Stack
- Python
- grpcio / protobuf
- Docker / Docker Compose
- Git / GitHub

---

## Repository Structure

```text
distributed-task-queue/
├─ README.md
├─ proto/
├─ services/
│  ├─ gateway/
│  ├─ job/
│  ├─ queue/
│  ├─ coordinator/
│  ├─ worker/
│  └─ result/
├─ docker/
├─ scripts/
└─ results/
