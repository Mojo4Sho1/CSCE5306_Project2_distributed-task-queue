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

> Internal service RPCs may differ between designs, but client-facing behavior remains equivalent.

### Fairness Controls (Locked)
- **Execution capacity parity:** total worker concurrency budget is fixed and equal across designs (`TOTAL_WORKER_SLOTS = 6` by default).
  - Design A (Microservices): 1 Worker Service container with 6 execution slots.
  - Design B (Monolith-per-node): 6 monolith nodes with 1 execution slot per node.
- **Ingress policy:**  
  - Design A load targets Gateway only.  
  - Design B load is distributed round-robin across six monolith nodes.
- **Measurement parity:** same hardware, workload profiles, warm-up policy, run duration, and aggregation logic.

---

## Communication Model
- **gRPC (RPC)**
- **Protocol Buffers** for interface contracts and message schemas

---

## Proto Layout (Phase 0.7 Lock)

The project uses **two proto files** in v1:

1. `proto/taskqueue_public.proto`
   - `package taskqueue.v1`
   - contains only client-facing RPCs and messages

2. `proto/taskqueue_internal.proto`
   - `package taskqueue.internal.v1`
   - contains internal service-to-service and worker-coordinator RPCs

### v1 Import Rule
`taskqueue_internal.proto` may import public message/types when needed to avoid schema drift.  
No third "common proto" file is introduced in v1.

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
   A clean environment reproduces deployment and benchmark execution using documented Docker Compose and scripts.

5. **NFR-5 (Baseline Fault Handling):**  
   The coordinator tracks worker heartbeats and marks workers unavailable after timeout; queue operations do not silently drop queued jobs.

6. **NFR-6 (Capacity Fairness):**  
   Both designs run with the same total worker-slot budget during comparisons.

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
In v1, Worker Service has no public business API. It primarily acts as an RPC client to Coordinator (`WorkerHeartbeat`, `FetchWork`, `ReportWorkOutcome`).

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
5. Optional worker/container health checks are operational-only and out of public API scope.

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
- **Job Service** is the canonical authority that applies job status values.
- **Coordinator Service** is the execution-path transition orchestrator (`QUEUED->RUNNING`, `RUNNING->DONE|FAILED|CANCELED`).
- **Gateway Service** requests cancellation and may apply guarded queued-cancel transition (`QUEUED->CANCELED`) after queue removal confirmation.
- **Worker Service** never writes canonical status directly; it reports outcomes to Coordinator.
- **Queue Service** owns queue membership only (not canonical status).

### Allowed Transitions (Locked)

| Trigger | From | To | Primary Actor | Notes |
|---|---|---|---|---|
| Successful `SubmitJob` | (none) | `QUEUED` | Gateway -> Job (+ Queue) | Job is accepted only when enqueue succeeds. |
| Work assignment / dequeue | `QUEUED` | `RUNNING` | Coordinator -> Job (CAS) | Coordinator dispatches work only after CAS success. |
| Worker success report | `RUNNING` | `DONE` | Worker -> Coordinator -> Job | Result payload is persisted in Result Service. |
| Worker failure report | `RUNNING` | `FAILED` | Worker -> Coordinator -> Job | Failure reason is stored with metadata. |
| Cancel pending job | `QUEUED` | `CANCELED` | Gateway -> Queue remove -> Job (CAS) | Remove from queue first, then apply guarded transition. |
| Cancel running job (best-effort) | `RUNNING` | `CANCELED` | Gateway sets cancel flag; Coordinator applies if race wins | Applies only if cancellation wins the race. |

### Submit Acceptance Atomicity (Locked)
`SubmitJob` acceptance follows this sequence in Design A:

1. Gateway requests `CreateJob` in Job Service.
2. Gateway requests `EnqueueJob` in Queue Service.
3. Submit is **accepted** only if enqueue succeeds.
4. If enqueue fails after create succeeds, Gateway calls:
   - `DeleteJobIfStatus(job_id, expected_status=QUEUED)`
5. If compensation succeeds, client receives failure (`UNAVAILABLE`) and no accepted job remains.
6. If compensation fails, system logs a **consistency anomaly** (with `job_id`) for debugging/reporting.

### Dequeue/CAS Race Handling (Locked)
Coordinator dispatch follows:
1. Dequeue `job_id` from Queue Service.
2. Attempt CAS transition in Job Service: `QUEUED -> RUNNING`.
3. Only if CAS succeeds does Coordinator assign work to Worker.

If CAS fails (for example, cancellation or a terminal write wins race):
- Coordinator does not assign work.
- Event is logged as expected race behavior.
- No silent drop is permitted.

### Anomaly Handling Rule (Locked)
If a `QUEUED` job is not present in queue due to a partial failure window, the system logs an anomaly.  
v1 focuses on detection and logging (not automatic repair).

### Terminal-State Precedence (Locked)
`DONE`, `FAILED`, and `CANCELED` are terminal states.  
**First valid terminal transition applied by Job Service wins.**  
Later conflicting terminal writes are ignored and logged.

### Cancellation Semantics (Locked)
1. **Queued cancellation:** expected to succeed if job has not started.
2. **Running cancellation:** best-effort only.
3. Repeated cancellation requests are idempotent and deterministic once terminal.

### Invalid Transition Handling (Locked)
Any transition not listed above is rejected and logged as invalid (e.g., `DONE -> RUNNING`).

### Monolith Equivalence Constraint
Monolith-per-node preserves the same externally visible lifecycle and terminal-state semantics.

---

## API Surface Lock (Phase 0.4)

### API Namespace Convention (Locked)
- **Client-facing namespace:** `taskqueue.v1`
- **Internal namespace (Design A):** `taskqueue.internal.v1`

### A) Client-Facing API (must match in both designs)

| Method | Public Endpoint Owner | Purpose |
|---|---|---|
| `SubmitJob` | Gateway Service | Accept new job and return `job_id`. |
| `GetJobStatus` | Gateway Service | Return canonical status for `job_id`. |
| `GetJobResult` | Gateway Service | Return final output when available. |
| `CancelJob` | Gateway Service | Request cancellation. |
| `ListJobs` | Gateway Service | Return recent jobs with filtering/pagination. |

### B) Internal Microservice API (Design A)

#### Job Service
- `CreateJob`
- `DeleteJobIfStatus`
- `GetJobRecord`
- `ListJobRecords`
- `TransitionJobStatus`
- `SetCancelRequested`

#### Queue Service
- `EnqueueJob`
- `DequeueJob`
- `RemoveJobIfPresent`

#### Coordinator Service
- `WorkerHeartbeat`
- `FetchWork`
- `ReportWorkOutcome`

#### Result Service
- `StoreResult`
- `GetResult`

#### Worker Service
- Worker is an internal RPC client in v1.
- Worker has no client-facing business endpoint.

### C) Caller-to-Method Matrix (Locked)

| Caller | Allowed Calls |
|---|---|
| External Client | Gateway: `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`, `ListJobs` |
| Gateway | Job: `CreateJob`, `DeleteJobIfStatus`, `GetJobRecord`, `ListJobRecords`, `SetCancelRequested`, `TransitionJobStatus` *(queued-cancel CAS only)*; Queue: `EnqueueJob`, `RemoveJobIfPresent`; Result: `GetResult` |
| Coordinator | Queue: `DequeueJob`, `RemoveJobIfPresent`; Job: `TransitionJobStatus`, `GetJobRecord`; Result: `StoreResult` |
| Worker | Coordinator: `WorkerHeartbeat`, `FetchWork`, `ReportWorkOutcome` |

No other cross-service mutations are allowed in v1.

---

## Proto v1 Scope Boundary (Locked)

Proto v1 is intentionally minimal and frozen to the current method set.

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

No additional RPC methods are added before v1 implementation and baseline benchmarking complete.

---

## Message Schema Draft (Phase 0.5 Lock)

### Schema Design Principles (Locked)
1. Keep v1 minimal and implementation-friendly.
2. Prefer explicit fields over deeply nested payloads.
3. Use stable IDs and server-generated UTC timestamps in epoch ms.
4. Keep client-facing messages architecture-agnostic for fair comparison.
5. Use enums for lifecycle and sorting semantics.

### Common Types (Locked)

#### `JobStatus` (enum)
- `JOB_STATUS_UNSPECIFIED = 0`
- `QUEUED = 1`
- `RUNNING = 2`
- `DONE = 3`
- `FAILED = 4`
- `CANCELED = 5`

#### `JobOutcome` (enum)
- `JOB_OUTCOME_UNSPECIFIED = 0`
- `SUCCEEDED = 1`
- `FAILED = 2`
- `CANCELED = 3`

#### `JobSort` (enum)
- `JOB_SORT_UNSPECIFIED = 0` (treated as `CREATED_AT_DESC`)
- `CREATED_AT_DESC = 1`
- `CREATED_AT_ASC = 2`

#### `JobSpec`
- `string job_type`
- `uint32 work_duration_ms`
- `uint32 payload_size_bytes`
- `map<string, string> labels`

> `priority` is intentionally **out of v1 scope** to avoid dormant semantics and implementation overhead.

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
- `string page_token` (stringified non-negative integer offset)

#### `PageResponse`
- `string next_page_token` (stringified offset; empty means end)

### A) Client-Facing API Message Draft (Locked)

#### `SubmitJob`
**Request:**
- `JobSpec spec`
- `string client_request_id` (optional idempotency key)

**Response:**
- `string job_id`
- `JobStatus initial_status` (expected `QUEUED`)
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
- `bytes output_bytes`
- `string output_summary`
- `uint32 runtime_ms`
- `string checksum`

**Semantics (Locked):**
- Non-terminal: `result_ready=false`, `terminal_status=JOB_STATUS_UNSPECIFIED`.
- Terminal `DONE`: `result_ready=true`; `output_bytes` may contain payload.
- Terminal `FAILED`: `result_ready=true`; `output_bytes` may be empty; failure details appear in `output_summary` (and `GetJobStatus.failure_reason`).
- Terminal `CANCELED`: `result_ready=true`; `output_bytes` may be empty; cancellation context appears in `output_summary`.

#### `CancelJob`
**Request:**
- `string job_id`
- `string reason`

**Response:**
- `string job_id`
- `bool accepted`
- `JobStatus current_status`
- `bool already_terminal`

**Semantics (Locked):**
- `accepted=true` means the cancel request was successfully processed by the API path.
- `already_terminal=true` means the job was terminal before this request.
- `current_status` is always authoritative at response time.
- For `RUNNING` jobs, `accepted=true` does not guarantee cancellation wins the race.

#### `ListJobs`
**Request:**
- `repeated JobStatus status_filter`
- `PageRequest page`
- `JobSort sort` (default `CREATED_AT_DESC`)

**Response:**
- `repeated JobSummary jobs`
- `PageResponse page`

### B) Internal Microservice Message Draft (Design A)

#### Job Service
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

#### Queue Service
- `EnqueueJobRequest { string job_id; int64 enqueued_at_ms; }`
- `EnqueueJobResponse { bool accepted; }`
- `DequeueJobRequest { string worker_id; }`
- `DequeueJobResponse { bool found; string job_id; }`
- `RemoveJobIfPresentRequest { string job_id; }`
- `RemoveJobIfPresentResponse { bool removed; }`

#### Coordinator Service
- `WorkerHeartbeatRequest { string worker_id; int64 heartbeat_at_ms; uint32 capacity_hint; }`
- `WorkerHeartbeatResponse { bool accepted; uint32 next_heartbeat_in_ms; }`
- `FetchWorkRequest { string worker_id; }`
- `FetchWorkResponse { bool assigned; string job_id; JobSpec spec; }`
- `ReportWorkOutcomeRequest { string worker_id; string job_id; JobOutcome outcome; uint32 runtime_ms; string failure_reason; string output_summary; bytes output_bytes; string checksum; }`
- `ReportWorkOutcomeResponse { bool accepted; }`

#### Result Service
- `StoreResultRequest { string job_id; JobStatus terminal_status; uint32 runtime_ms; string output_summary; bytes output_bytes; string checksum; }`
- `StoreResultResponse { bool stored; }`
- `GetResultRequest { string job_id; }`
- `GetResultResponse { bool found; string job_id; JobStatus terminal_status; uint32 runtime_ms; string output_summary; bytes output_bytes; string checksum; }`

### C) Field/Type Conventions (Locked)
- IDs: `string` (UUID/ULID format decided at implementation time)
- Time: `int64` epoch milliseconds (UTC), server-generated
- Durations: `uint32` milliseconds
- Binary output: `bytes`
- Optional text fields: empty string when unset in v1
- Pagination:
  - `page_size` default `50`, max `200`
  - if `page_size == 0`, server uses `50`
  - if `page_size > 200`, server clamps to `200`
  - `page_token` is stringified non-negative integer offset
  - invalid token format returns `INVALID_ARGUMENT`

### D) Backward-Compatibility Note (v1)
- Do not rename/remove fields after proto v1 freeze.
- Add new fields only additively with new field numbers.
- Keep enum numeric values stable once published.

---

## Error Model and Idempotency Behavior (Phase 0.6 Lock)

### 1) Error Handling Model (Locked)
The system uses a two-layer model:
1. **Hard errors:** gRPC status codes (non-OK RPC response)
2. **Soft outcomes:** `OK` with explicit response fields (`accepted`, `result_ready`, `already_terminal`, `applied`)

### 2) gRPC Status Code Policy (Locked)

| Condition | gRPC Code | Retry Guidance | Notes |
|---|---|---|---|
| Invalid/malformed request fields | `INVALID_ARGUMENT` | Do not retry until fixed | Includes invalid page token format |
| Unknown `job_id` | `NOT_FOUND` | Do not retry | Applies to status/result/cancel lookups |
| Idempotency key reused with different payload | `FAILED_PRECONDITION` | Do not retry with same key | Use a new key |
| Temporary capacity pressure | `RESOURCE_EXHAUSTED` | Retry with backoff | Optional in v1 |
| Downstream service unavailable | `UNAVAILABLE` | Retry with backoff+jitter | Transient failure |
| Request deadline exceeded | `DEADLINE_EXCEEDED` | Retry idempotent methods | Use sane deadlines |
| Unexpected server failure | `INTERNAL` | Retry cautiously | Log with correlation data |

### 3) Soft Outcome Policy (Locked)
Use `OK` responses for:
- `GetJobResult` when result is not ready
- `CancelJob` when job is already terminal
- duplicate cancellation requests
- CAS mismatch on `TransitionJobStatus`
- condition mismatch on `DeleteJobIfStatus`

### 4) Client-Facing Idempotency Matrix (Locked)

| Method | Idempotent? | Key / Identity | Required Behavior |
|---|---|---|---|
| `SubmitJob` | Conditionally | `client_request_id` | Same key + same payload returns original `job_id`; same key + different payload returns `FAILED_PRECONDITION` |
| `GetJobStatus` | Yes | `job_id` | Safe repeated reads |
| `GetJobResult` | Yes | `job_id` | Safe repeated reads |
| `CancelJob` | Yes | `job_id` | Deterministic repeated calls |
| `ListJobs` | Yes | filters + page token | Safe repeated reads |

**v1 dedup scope:** in-memory for process lifetime only (not across restarts).

### 5) Internal API Idempotency Matrix (Design A, Locked)

| Internal Method | Idempotent? | Required Behavior |
|---|---|---|
| `CreateJob` | Conditionally | Deduplicate by `client_request_id` when present |
| `DeleteJobIfStatus` | Conditional | Delete only if status matches expected |
| `EnqueueJob` | Yes-by-key | Same `job_id` not enqueued twice |
| `RemoveJobIfPresent` | Yes | Repeats are safe |
| `TransitionJobStatus` | Conditional (CAS) | Apply only on expected current status |
| `SetCancelRequested` | Yes | Repeated true-setting is stable |
| `WorkerHeartbeat` | Yes | Refreshes liveness timestamp |
| `FetchWork` | No | Assignment side effects; at-least-once delivery model |
| `ReportWorkOutcome` | Effectively idempotent | First valid terminal write wins |
| `StoreResult` | Idempotent by terminal record | Duplicate equivalent writes are safe |
| Read methods | Yes | Safe repeats |

### 6) Retry/Backoff Guidance (Locked)
Auto-retry only on:
- `UNAVAILABLE`
- `DEADLINE_EXCEEDED`
- `RESOURCE_EXHAUSTED` (if used)

Use exponential backoff with jitter.  
Do not auto-retry `INVALID_ARGUMENT`, `NOT_FOUND`, or `FAILED_PRECONDITION` without changing assumptions.

### 7) Determinism Rules for Cancellation (Locked)
- `QUEUED`: cancellation moves toward `CANCELED` with queue removal first, then guarded status transition.
- `RUNNING`: best-effort; completion may win the race.
- terminal state: repeated cancel is deterministic non-error.

### 8) Observability Requirements for Errors (Locked)
For every non-OK response, log:
- timestamp
- method
- code
- message
- job_id (if present)
- caller/service identity (if available)

---

## Ambiguity Locks (Finalized Phase 0 Clarifications)

The following design ambiguities are now explicitly locked:

1. **Submit anomaly handling:** compensation + anomaly logging on create/enqueue partial failure.
2. **Worker-slot fairness:** equal total worker slots across designs with fixed per-design mapping.
3. **Ingress policy:** fixed request routing policy per design.
4. **Terminal race precedence:** first valid terminal write wins.
5. **Sort behavior:** enum-based sort (`CREATED_AT_DESC` / `CREATED_AT_ASC`), no free-text sort.
6. **ErrorInfo treatment:** no generic `ErrorInfo` message in v1 schema.
7. **Pagination semantics:** offset-based string page tokens.
8. **Timestamp authority:** server-generated UTC epoch ms is authoritative.
9. **Worker health scope:** heartbeat is canonical; optional health checks are operational only.
10. **Priority treatment:** `priority` is removed from v1 `JobSpec`.
11. **Proto packaging:** two files (`taskqueue_public.proto`, `taskqueue_internal.proto`), no common proto in v1.
12. **Dequeue/CAS race policy:** CAS gate required before assignment; failed CAS is logged expected race behavior.

---

## Phase 0 Decision Lock (Frozen)

**Freeze date:** 2026-02-10

- System choice is fixed to **Distributed Task Queue**.
- Architecture comparison is fixed to:
  - **Design A:** Microservices (6 functional nodes)
  - **Design B:** Monolith-per-node (6 nodes)
- Node-count rule is fixed: load generator is not a functional node.
- Communication model is fixed to gRPC + protobuf.
- Proto packaging is fixed to two files (public + internal).
- Storage assumption is fixed to **in-memory** for this project.
- Processing semantics are fixed to **at-least-once** execution.
- Cancellation semantics are fixed to: queued cancellation expected; running cancellation best-effort.
- Fairness controls are fixed and documented above.

### Out of Scope
- Durable persistence guarantees
- Consensus/leader election
- Exactly-once guarantees
- Production-grade security hardening
- Multi-region deployment

### Change Control
If any frozen decision changes, record:
1. what changed,
2. why it changed,
3. expected implementation/evaluation impact.

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

    distributed-task-queue/
    ├─ README.md
    ├─ proto/
    │  ├─ taskqueue_public.proto
    │  └─ taskqueue_internal.proto
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
