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
For v1 equivalence, semantic parity is strict for `SubmitJob`, `GetJobStatus`, `GetJobResult`, and `CancelJob`.  
`ListJobs` preserves functional availability and schema parity in both designs, while Design B may return non-global best-effort results in v1.

> Internal service RPCs may differ between designs, but client-facing behavior remains equivalent within the v1 scope above.

### Fairness Controls (Locked)
- **Execution capacity parity:** total worker concurrency budget is fixed and equal across designs (`TOTAL_WORKER_SLOTS = 6` by default).
  - Design A (Microservices): 1 Worker Service container with 6 execution slots.
  - Design B (Monolith-per-node): 6 monolith nodes with 1 execution slot per node.
- **Ingress policy (locked):**
  - Design A load targets Gateway only.
  - Design B `SubmitJob` load is distributed round-robin across six monolith nodes **when `client_request_id` is empty**.
- **Design B submit-idempotency routing (locked):**
  - If `client_request_id` is non-empty, the client/load generator routes `SubmitJob` to a deterministic owner node derived from `client_request_id`.
  - This preserves submit idempotency semantics with per-node in-memory dedup state.
- **Design B state-coherence routing (locked):**
  - `GetJobStatus`, `GetJobResult`, and `CancelJob` are routed to a deterministic owner node derived from `job_id` (stable partition).
  - **Routing is performed by the client/load generator in v1**.
  - Monolith nodes do not forward job-scoped requests to each other in v1.
- **ListJobs in Design B (locked):**
  - `ListJobs` remains functionally available with the same public schema.
  - In v1, `ListJobs` is best-effort and non-global in Design B unless explicit aggregation is added later.
  - Primary performance parity analysis focuses on `SubmitJob`, `GetJobStatus`, `GetJobResult`, and `CancelJob`.
- **Measurement parity:** same hardware, workload profiles, warm-up policy, run duration, and aggregation logic.

### Deterministic Owner Routing Algorithm (Design B, Locked)
To ensure routing reproducibility across runs and machines, owner mapping is fixed:

- **Hash function:** SHA-256
- **Input bytes:** UTF-8 bytes of the routing key
- **Owner index formula:** `owner_index = uint64_be(first_8_bytes(sha256(key))) % N`
- **N:** number of monolith nodes in the run (v1 default `N=6`)
- **Node order:** fixed ordered node list from configuration (stable for the run)

Routing keys:
- `SubmitJob` with non-empty `client_request_id`: route by `client_request_id`
- `GetJobStatus`, `GetJobResult`, `CancelJob`: route by `job_id`

### ListJobs Parity Scope in Evaluation (Locked)
`ListJobs` remains available with schema parity in both designs.  
In v1, Design B may return non-global best-effort listings.  
Therefore, primary throughput/latency parity conclusions are based on:
- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`

`ListJobs` is reported separately as a secondary/qualitative result.

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
   - defines public service: `TaskQueuePublicService`

2. `proto/taskqueue_internal.proto`
   - `package taskqueue.internal.v1`
   - contains internal service-to-service and worker-coordinator RPCs
   - defines internal services:
     - `JobInternalService`
     - `QueueInternalService`
     - `CoordinatorInternalService`
     - `ResultInternalService`

### v1 Import Rule
`taskqueue_internal.proto` may import public message/types when needed to avoid schema drift.  
No third "common proto" file is introduced in v1.

### Service Naming Convention (Locked)
The proto service names above are frozen for v1 and used consistently in generated stubs, docs, and implementation.

---

## Runtime Startup Contract (Step 2.1 Lock)

This section defines the runtime wiring contract for Design A (microservices) so container startup is deterministic and reproducible.

### A) Service Endpoint Map (Design A)

| Service | Compose DNS name | Inbound Proto Service | Bind Host | Port | Inbound Business RPC |
|---|---|---|---|---:|---|
| Gateway | `gateway` | `taskqueue.v1.TaskQueuePublicService` | `0.0.0.0` | `50051` | Yes |
| Job | `job` | `taskqueue.internal.v1.JobInternalService` | `0.0.0.0` | `50052` | Yes |
| Queue | `queue` | `taskqueue.internal.v1.QueueInternalService` | `0.0.0.0` | `50053` | Yes |
| Coordinator | `coordinator` | `taskqueue.internal.v1.CoordinatorInternalService` | `0.0.0.0` | `50054` | Yes |
| Result | `result` | `taskqueue.internal.v1.ResultInternalService` | `0.0.0.0` | `50055` | Yes |
| Worker | `worker` | (none; internal RPC client in v1) | n/a | n/a | No |

### B) Upstream Dependency Addresses (Design A)

| Consumer | Required upstream address env vars (default values) |
|---|---|
| Gateway | `JOB_SERVICE_ADDR=job:50052`, `QUEUE_SERVICE_ADDR=queue:50053`, `RESULT_SERVICE_ADDR=result:50055` |
| Coordinator | `JOB_SERVICE_ADDR=job:50052`, `QUEUE_SERVICE_ADDR=queue:50053`, `RESULT_SERVICE_ADDR=result:50055` |
| Worker | `COORDINATOR_ADDR=coordinator:50054` |
| Job / Queue / Result | none |

### C) Required Env Vars (Step 2 skeleton)

Shared:
- `LOG_LEVEL` (default `INFO`)
- `PYTHONUNBUFFERED=1`

Gateway:
- `GATEWAY_PORT` (default `50051`)
- `JOB_SERVICE_ADDR` (required)
- `QUEUE_SERVICE_ADDR` (required)
- `RESULT_SERVICE_ADDR` (required)

Job:
- `JOB_PORT` (default `50052`)
- `MAX_DEDUP_KEYS` (default `10000`)

Queue:
- `QUEUE_PORT` (default `50053`)

Coordinator:
- `COORDINATOR_PORT` (default `50054`)
- `JOB_SERVICE_ADDR` (required)
- `QUEUE_SERVICE_ADDR` (required)
- `RESULT_SERVICE_ADDR` (required)
- `HEARTBEAT_INTERVAL_MS` (default `1000`)
- `WORKER_TIMEOUT_MS` (default `4000`)

Result:
- `RESULT_PORT` (default `50055`)
- `MAX_OUTPUT_BYTES` (default `262144`)

Worker:
- `COORDINATOR_ADDR` (required)
- `WORKER_ID` (optional; fallback = container hostname)
- `HEARTBEAT_INTERVAL_MS` (default `1000`)

### D) Startup/Readiness Definition (Step 2)

For services with inbound gRPC endpoints (Gateway/Job/Queue/Coordinator/Result), a service is considered **ready** when:
1. configuration is parsed successfully, and
2. gRPC server is bound to configured host/port, and
3. startup log emits a ready event, and
4. corresponding Step 2.4 healthcheck passes.

For Worker, readiness is:
1. configuration parsed, and
2. worker loop started, and
3. first heartbeat attempt emitted in logs, and
4. corresponding Step 2.4 healthcheck passes.

### E) Entrypoint Rule

Each service container must declare exactly one startup command in Docker Compose.  
If an entrypoint changes, README endpoint/env tables must be updated in the same commit.

---

## Healthcheck Strategy (Step 2.4 Lock)

This section locks the container health/readiness strategy for v1.

### A) Common Healthcheck Command Shape (Locked)

All containers use one shared command interface:

`python -m scripts.healthcheck --mode <tcp|worker> --target <host:port> --timeout-ms <ms> --service <name>`

- `--mode`:
  - `tcp`: check TCP connect to target host:port.
  - `worker`: check Worker liveness by verifying coordinator reachability at target.
- `--target`: required `host:port`.
- `--timeout-ms`: optional, default `1000`.
- `--service`: optional label for structured log output.

**Exit semantics (locked):**
- exit `0` = healthy
- exit non-zero = unhealthy

### B) Mode Mapping by Service (Design A)

| Service | Mode | Target |
|---|---|---|
| Gateway | `tcp` | `127.0.0.1:${GATEWAY_PORT}` |
| Job | `tcp` | `127.0.0.1:${JOB_PORT}` |
| Queue | `tcp` | `127.0.0.1:${QUEUE_PORT}` |
| Coordinator | `tcp` | `127.0.0.1:${COORDINATOR_PORT}` |
| Result | `tcp` | `127.0.0.1:${RESULT_PORT}` |
| Worker | `worker` | `${COORDINATOR_ADDR}` |

### C) Docker Healthcheck Policy (Locked)

Default healthcheck timing for all services:

- `interval: 5s`
- `timeout: 2s`
- `retries: 12`
- `start_period: 20s`

These values are chosen to tolerate normal startup jitter while still surfacing failures promptly in local development.

### D) Readiness Interpretation (Locked)

- For Gateway/Job/Queue/Coordinator/Result:
  - ready when service startup succeeds **and** healthcheck (`mode=tcp`) passes.
- For Worker:
  - ready when worker loop starts **and** healthcheck (`mode=worker`) passes coordinator reachability.

This health/readiness model is intentionally minimal for v1 and is sufficient for container orchestration and smoke validation.

---

## Functional Requirements
1. **SubmitJob**: Accept a job request and return a unique job ID.
2. **GetJobStatus**: Return the current state of a job.
3. **GetJobResult**: Return job output after completion.
4. **CancelJob**: Cancel pending jobs (best-effort for running jobs).
5. **ListJobs**: List jobs with filtering/pagination support.
6. **WorkerHeartbeat / FetchWork**: Support worker liveness and job retrieval.

### FR-6 Scope Clarification (Locked)
FR-6 is an **internal functional requirement** (worker/coordinator control plane) in Design A.  
FR-6 is **not** part of the client-facing public API used for architecture equivalence.

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
In v1, Job Service also owns submit-idempotency dedup state keyed by `client_request_id`.

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
- **Gateway Service** requests cancellation and may invoke transition only for the guarded queued-cancel path (`QUEUED->CANCELED`) after queue removal confirmation and terminal-envelope write.
- **Worker Service** never writes canonical status directly; it reports outcomes to Coordinator.
- **Queue Service** owns queue membership only (not canonical status).

### Allowed Transitions (Locked)

| Trigger | From | To | Primary Actor | Notes |
|---|---|---|---|---|
| Successful `SubmitJob` | (none) | `QUEUED` | Gateway -> Job (+ Queue) | Job is accepted only when enqueue succeeds. |
| Work assignment / dequeue | `QUEUED` | `RUNNING` | Coordinator -> Job (CAS) | Coordinator dispatches work only after CAS success. |
| Worker success report | `RUNNING` | `DONE` | Worker -> Coordinator -> Job | Terminal result envelope is written via Result Service in terminalization protocol. |
| Worker failure report | `RUNNING` | `FAILED` | Worker -> Coordinator -> Job | Terminal result envelope is written via Result Service in terminalization protocol. |
| Cancel pending job | `QUEUED` | `CANCELED` | Gateway -> Queue remove -> Job (CAS) | Remove from queue first; terminalization protocol applies. |
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

### Dequeue/CAS Rescue Rule (Locked)
Because v1 dequeue is destructive, Coordinator must apply this rescue behavior:

1. If CAS fails, Coordinator reads authoritative current status from Job Service.
2. If current status is still `QUEUED`, Coordinator performs a single immediate `EnqueueJob(job_id)` rescue attempt.
3. If status is terminal (or no longer queued), Coordinator does not re-enqueue.
4. Rescue attempts are logged with `job_id` for observability.

This rule prevents stranded `QUEUED` jobs and preserves baseline fault-handling guarantees.

### Terminal Result Consistency Protocol (Locked)

For worker/coordinator terminal outcomes (`DONE`, `FAILED`, running `CANCELED` path):
1. Coordinator requests `StoreResult` in Result Service (idempotent write).
2. Coordinator requests CAS terminal transition in Job Service (`RUNNING -> terminal`).
3. If CAS fails because another terminal state already won, Coordinator logs a benign terminal race (result may be orphaned and is ignored by canonical status).

For queued cancellation terminalization:
1. Gateway requests `RemoveJobIfPresent` in Queue Service.
2. Gateway requests `StoreResult` cancellation envelope in Result Service.
3. Gateway requests CAS in Job Service (`QUEUED -> CANCELED`).

**Invariant:** terminal jobs are expected to expose terminal result envelopes via `GetJobResult`.  
If a partial failure breaks this expectation, the system logs an anomaly.

### Anomaly Handling Rule (Locked)
If a `QUEUED` job is not present in queue due to a partial failure window, the system logs an anomaly.  
v1 focuses on detection and logging (not automatic repair).

### Terminal-State Precedence (Locked)
`DONE`, `FAILED`, and `CANCELED` are terminal states.  
**First valid terminal transition applied by Job Service wins.**  
Later conflicting terminal writes are ignored and logged.

### Cancellation Semantics (Locked)
1. **Queued cancellation:** expected to succeed if job has not started.
2. **Running cancellation:** best-effort only and **non-preemptive** in v1.
3. For running jobs, `CancelJob` sets `cancel_requested=true`; completion or failure may still win the race.
4. Repeated cancellation requests are idempotent and deterministic once terminal.
5. **Queued-cancel race fallback (locked):** if queued-cancel path loses the race (for example, `RemoveJobIfPresent=false` because dequeue already happened), Gateway must set `cancel_requested=true` via Job Service and return authoritative `current_status`. This transitions cancellation handling to the running-cancel path.

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

- **Service name:** `TaskQueuePublicService`

| Method | Public Endpoint Owner | Purpose |
|---|---|---|
| `SubmitJob` | Gateway Service | Accept new job and return `job_id`. |
| `GetJobStatus` | Gateway Service | Return canonical status for `job_id`. |
| `GetJobResult` | Gateway Service | Return final output when available. |
| `CancelJob` | Gateway Service | Request cancellation. |
| `ListJobs` | Gateway Service | Return recent jobs with filtering/pagination. |

### B) Internal Microservice API (Design A)

#### Job Service (`JobInternalService`)
- `CreateJob`
- `DeleteJobIfStatus`
- `GetJobRecord`
- `ListJobRecords`
- `TransitionJobStatus`
- `SetCancelRequested`

#### Queue Service (`QueueInternalService`)
- `EnqueueJob`
- `DequeueJob`
- `RemoveJobIfPresent`

#### Coordinator Service (`CoordinatorInternalService`)
- `WorkerHeartbeat`
- `FetchWork`
- `ReportWorkOutcome`

#### Result Service (`ResultInternalService`)
- `StoreResult`
- `GetResult`

#### Worker Service
- Worker is an internal RPC client in v1.
- Worker has no client-facing business endpoint.

### C) Caller-to-Method Matrix (Locked)

| Caller | Allowed Calls |
|---|---|
| External Client | Gateway: `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`, `ListJobs` |
| Gateway | Job: `CreateJob`, `DeleteJobIfStatus`, `GetJobRecord`, `ListJobRecords`, `SetCancelRequested`, `TransitionJobStatus` *(queued-cancel CAS only)*; Queue: `EnqueueJob`, `RemoveJobIfPresent`; Result: `GetResult`, `StoreResult` *(queued-cancel envelope only)* |
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
- `JOB_OUTCOME_SUCCEEDED = 1`
- `JOB_OUTCOME_FAILED = 2`
- `JOB_OUTCOME_CANCELED = 3`

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

**Semantics (Locked):**
- If `client_request_id` is non-empty:
  - same key + same payload returns original `job_id`
  - same key + different payload returns `FAILED_PRECONDITION`
- If `client_request_id` is empty:
  - request is treated as non-idempotent (new submit attempt)
- Deduplication guarantees apply only while key entries remain in the in-memory dedup store (see dedup scope and bound below).

**Dedup payload-equality rule (locked):**
- “Same payload” means canonical-equivalent `JobSpec`:
  - identical `job_type`
  - identical `work_duration_ms`
  - identical `payload_size_bytes`
  - identical `labels` after key-sorted normalization

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
- **Canonical precedence rule (locked):** `GetJobResult` resolves readiness from canonical Job Service status first. If status is non-terminal, return `result_ready=false` even if a stale/orphan result envelope exists.
- **Terminal-mismatch rule (locked):** if canonical status is terminal but no terminal envelope exists in Result Service, API returns gRPC `UNAVAILABLE` and logs a consistency anomaly with `job_id`.

**Terminal envelope minimums (Locked):**
- `DONE`: `runtime_ms`, `checksum`, and optional `output_bytes`/`output_summary`.
- `FAILED`: `runtime_ms` (if known), failure context in `output_summary`, `output_bytes` may be empty.
- `CANCELED`: cancellation context in `output_summary`, `output_bytes` may be empty.

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
- Unknown `job_id` returns gRPC `NOT_FOUND`.

#### `ListJobs`
**Request:**
- `repeated JobStatus status_filter`
- `PageRequest page`
- `JobSort sort` (default `CREATED_AT_DESC`)

**Response:**
- `repeated JobSummary jobs`
- `PageResponse page`

**Semantics (Locked):**
- Deterministic ordering uses requested sort on `created_at_ms` with tie-break `job_id` ascending.
- Empty `status_filter` means **all statuses**.
- v1 pagination is **best-effort non-snapshot**; concurrent writes may shift page boundaries between requests.

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

**Transition guard strictness (locked):**
- `expected_from_status` is mandatory for CAS transitions.
- `expected_from_status = JOB_STATUS_UNSPECIFIED` is invalid and returns `INVALID_ARGUMENT`.

#### Queue Service
- `EnqueueJobRequest { string job_id; int64 enqueued_at_ms; }`
- `EnqueueJobResponse { bool accepted; }`
- `DequeueJobRequest { string worker_id; }`
- `DequeueJobResponse { bool found; string job_id; }`
- `RemoveJobIfPresentRequest { string job_id; }`
- `RemoveJobIfPresentResponse { bool removed; }`

**Queue ordering strength (locked):**
- v1 queue behavior is **best-effort FIFO** for accepted jobs.
- Correctness does not depend on strict global FIFO under races.

**Dequeue acknowledgment model (locked):**
- `DequeueJob` is a destructive pop in v1 (no lease/ack/requeue protocol).
- Crash-recovery requeue and visibility-timeout semantics are out of v1 scope.

#### Coordinator Service
- `WorkerHeartbeatRequest { string worker_id; int64 heartbeat_at_ms; uint32 capacity_hint; }`
- `WorkerHeartbeatResponse { bool accepted; uint32 next_heartbeat_in_ms; }`
- `FetchWorkRequest { string worker_id; }`
- `FetchWorkResponse { bool assigned; string job_id; JobSpec spec; uint32 retry_after_ms; }`
- `ReportWorkOutcomeRequest { string worker_id; string job_id; JobOutcome outcome; uint32 runtime_ms; string failure_reason; string output_summary; bytes output_bytes; string checksum; }`
- `ReportWorkOutcomeResponse { bool accepted; }`

**FetchWork idle semantics (Locked):**
- If no work is available: `assigned=false` and server returns `retry_after_ms`.
- Default hint is 200 ms; server clamps to [50, 1000] ms.

#### Result Service
- `StoreResultRequest { string job_id; JobStatus terminal_status; uint32 runtime_ms; string output_summary; bytes output_bytes; string checksum; }`
- `StoreResultResponse { bool stored; bool already_exists; JobStatus current_terminal_status; }`
- `GetResultRequest { string job_id; }`
- `GetResultResponse { bool found; string job_id; JobStatus terminal_status; uint32 runtime_ms; string output_summary; bytes output_bytes; string checksum; }`

**StoreResult conflict semantics (locked):**
- `stored=true` indicates this call performed/confirmed canonical storage for the terminal envelope.
- `already_exists=true` indicates a prior terminal envelope exists.
- `current_terminal_status` returns authoritative stored terminal status for race/conflict handling.

### C) Field/Type Conventions (Locked)
- IDs: `string` using **UUIDv4** format in v1.
- Time: `int64` epoch milliseconds (UTC), server-generated.
- Durations: `uint32` milliseconds.
- Binary output: `bytes`.
- Optional text fields: empty string when unset in v1.
- Pagination:
  - `page_size` default `50`, max `200`
  - if `page_size == 0`, server uses `50`
  - if `page_size > 200`, server clamps to `200`
  - `page_token` is stringified non-negative integer offset
  - invalid token format returns `INVALID_ARGUMENT`
- `worker_id` source priority:
  1. `WORKER_ID` environment variable
  2. container hostname fallback  
  `worker_id` remains stable for process lifetime.
- Heartbeat policy constants:
  - `HEARTBEAT_INTERVAL_MS = 1000`
  - `WORKER_TIMEOUT_MS = 4000`
- `checksum` format: lowercase hex SHA-256 of `output_bytes` (always populated, including empty payload).
- `MAX_OUTPUT_BYTES = 262144` (256 KiB). Oversized output triggers failed outcome handling (`OUTPUT_TOO_LARGE`) and stores bounded failure metadata without oversized bytes.
- `MAX_DEDUP_KEYS = 10000` for in-memory submit idempotency cache.
- Dedup cache eviction policy in v1: bounded FIFO/LRU-style eviction. If a key is evicted, a later submit with the same key is treated as a new request attempt.
- Timestamp authority mapping (locked):
  - `created_at_ms`: set by Job Service on `CreateJob`.
  - `started_at_ms`: set by Job Service when `QUEUED -> RUNNING` CAS applies.
  - `finished_at_ms`: set by Job Service when terminal transition CAS applies.

### Proto Evolution Hygiene (Locked)
After proto v1 freeze:
1. Do not rename/remove existing fields.
2. Add new fields only additively with new field numbers.
3. Keep enum numeric values stable once published.
4. If a field is retired later, reserve its field number/name (do not reuse).
5. Shared client-visible enums/messages remain single-source in public proto; duplicate definitions are disallowed.

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
| Terminal status present but terminal result missing | `UNAVAILABLE` | Retry with backoff+jitter | Consistency anomaly is logged with `job_id` |
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
| `SubmitJob` | Conditionally | `client_request_id` | Non-empty key: same key + same payload returns original `job_id`; same key + different payload returns `FAILED_PRECONDITION` while key remains in dedup cache. Empty key: treat as non-idempotent new submit. |
| `GetJobStatus` | Yes | `job_id` | Safe repeated reads |
| `GetJobResult` | Yes | `job_id` | Safe repeated reads |
| `CancelJob` | Yes | `job_id` | Deterministic repeated calls |
| `ListJobs` | Yes | filters + page token | Safe repeated reads |

**v1 dedup scope:** in-memory for process lifetime only (not across restarts), bounded by `MAX_DEDUP_KEYS`.

**Design B routing note (locked):**  
To preserve `SubmitJob` idempotency with in-memory per-node dedup state, requests with non-empty `client_request_id` are routed to a deterministic owner node by the locked routing algorithm above.

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
| `StoreResult` | Idempotent by terminal record | Duplicate equivalent writes are safe; conflicts are surfaced via response fields |
| Read methods | Yes | Safe repeats |

### 6) Retry/Backoff Guidance (Locked)
Auto-retry only on:
- `UNAVAILABLE`
- `DEADLINE_EXCEEDED`
- `RESOURCE_EXHAUSTED` (if used)

Retry profile (v1 lock):
- backoff strategy: exponential
- jitter mode: full jitter
- initial delay: `100 ms`
- multiplier: `2.0`
- max delay: `1000 ms`
- max attempts: `4` total attempts (initial + 3 retries)

- `SubmitJob` is auto-retried only when `client_request_id` is non-empty. If `client_request_id` is empty, do not auto-retry.

Do not auto-retry `INVALID_ARGUMENT`, `NOT_FOUND`, or `FAILED_PRECONDITION` without changing assumptions.

### 7) Determinism Rules for Cancellation (Locked)
- `QUEUED`: cancellation moves toward `CANCELED` with queue removal first, then guarded status transition.
- `RUNNING`: best-effort and non-preemptive in v1; completion may win the race.
- terminal state: repeated cancel is deterministic non-error.
- if queued-cancel race is lost, system sets `cancel_requested=true` and follows running-cancel path.

### 8) Observability Requirements for Errors (Locked)
For every non-OK response, log:
- timestamp
- method
- code
- message
- job_id (if present)
- caller/service identity (if available)

### 9) Logging Format (Locked)
Log format for v1 is **JSON Lines** (one JSON object per line).

Minimum required fields:
- `ts_ms`
- `level`
- `service`
- `method`
- `event`
- `job_id` (if present)
- `worker_id` (if present)
- `grpc_code` (for non-OK)
- `message`

Recommended optional fields:
- `request_id`
- `latency_ms`
- `expected_status`
- `current_status`

### 10) Deadline Defaults (Locked)
Client -> Gateway defaults:
- `SubmitJob`: 3000 ms
- `CancelJob`: 3000 ms
- `GetJobStatus`: 1000 ms
- `GetJobResult`: 1000 ms
- `ListJobs`: 1000 ms

Internal defaults:
- unary service-to-service calls: 1000 ms
- `FetchWork`: 1500 ms
- `WorkerHeartbeat`: 1000 ms

### Terminal/Result Mismatch Handling (Locked)
If canonical job status is terminal but Result Service has no terminal envelope:
- API returns `UNAVAILABLE`,
- system logs a consistency anomaly with `job_id`,
- retry policy treats this as transient/retryable per locked backoff rules.

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
13. **FetchWork idle policy:** explicit server backoff hint (`retry_after_ms`) prevents busy-spin.
14. **Submit empty idempotency key:** empty `client_request_id` means non-idempotent submit.
15. **Result consistency protocol:** terminalization uses Result Service envelope + guarded status CAS with anomaly logging on partial failure.
16. **Deterministic pagination tie-break:** `job_id` ascending on equal `created_at_ms`.
17. **Worker identity source:** `WORKER_ID` env var then hostname fallback.
18. **Checksum format and output cap:** lowercase SHA-256 checksum; max output bytes locked.
19. **Cancel unknown ID behavior:** explicit `NOT_FOUND`.
20. **ListJobs snapshot model:** best-effort non-snapshot pagination in v1.
21. **FR-6 scope:** internal requirement only; not public API equivalence surface.
22. **Queued-cancel race fallback:** if queue removal misses due to race, set cancel-request flag and continue best-effort running-cancel semantics.
23. **Terminal-status/result mismatch behavior:** return `UNAVAILABLE` and log anomaly.
24. **Empty status filter behavior:** `ListJobs` with empty filter includes all statuses.
25. **Submit dedup cache bounds:** in-memory dedup map is bounded (`MAX_DEDUP_KEYS`) with eviction; guarantees hold while key is retained.
26. **Proto service naming lock:** public/internal service names are frozen for v1 (`TaskQueuePublicService`, `JobInternalService`, `QueueInternalService`, `CoordinatorInternalService`, `ResultInternalService`).
27. **Design B coherence routing:** job-scoped reads/cancel route by deterministic `job_id` owner mapping.
28. **Design B ListJobs parity scope:** implemented with equivalent schema; excluded from primary throughput/latency parity conclusions.
29. **StoreResult conflict visibility:** response carries `already_exists` and `current_terminal_status` for race introspection.
30. **Transition guard strictness:** CAS requires explicit non-UNSPECIFIED `expected_from_status`.
31. **Queue ordering strength:** best-effort FIFO only; strict global FIFO is out of v1 correctness assumptions.
32. **Heartbeat timing constants:** interval `1000 ms`, timeout `4000 ms`.
33. **Retry constants:** exponential backoff with full jitter (100ms start, x2, 1000ms cap, 4 total attempts).
34. **Logging format:** JSON Lines with required structured fields.
35. **Job ID format:** UUIDv4 for v1.
36. **Submit payload canonical equality:** key-sorted `labels` and exact `JobSpec` field equality define dedup payload match.
37. **Design B routing executor:** client/load generator performs deterministic owner routing for job-scoped reads/cancel; no inter-node forwarding in v1.
38. **Design B submit idempotency routing:** non-empty `client_request_id` routes by deterministic key owner.
39. **Running-cancel execution model:** non-preemptive best-effort; `cancel_requested` is advisory until terminal race resolves.
40. **Dequeue model:** destructive pop in v1; no ack/requeue protocol.
41. **Timestamp authority mapping:** Job Service stamps created/started/finished canonical times.
42. **Dequeue/CAS rescue behavior:** if CAS fails and status remains `QUEUED`, Coordinator performs one immediate re-enqueue rescue.
43. **Deterministic owner algorithm:** SHA-256 + first 8 bytes big-endian modulo N with fixed node ordering.

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
- Cancellation semantics are fixed to: queued cancellation expected; running cancellation best-effort and non-preemptive.
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

### Implementation Stability Rule (Locked)
During active implementation of a task, design changes are allowed only for blocker-level reasons.  
Any change must record:
1. blocker description,
2. why current design fails,
3. exact scope of the change,
4. impact on current task.

---

## Implementation Freeze Gate (Final Phase 0 Lock)

The design is now frozen for v1 implementation.  
No additional design changes are introduced before:
1. both proto files compile,
2. generated stubs are integrated, and
3. microservice smoke tests pass for all five public RPCs.

### Phase 0 Closure Rule (Locked)
**Phase 0 is closed. No new design features are added before proto compilation, stub generation, and end-to-end smoke validation complete.**

### Frozen v1 Clarifications
- Design B client/load-generator routing is mandatory for benchmark/demo correctness:
  - non-empty `client_request_id` submit routing uses deterministic key-owner mapping,
  - job-scoped reads/cancel route by deterministic `job_id` owner mapping.
- `StoreResult` accepts terminal statuses only (`DONE`, `FAILED`, `CANCELED`); otherwise return `INVALID_ARGUMENT`.
- Dequeue is destructive in v1 with no lease/ack/requeue recovery guarantee; crash-recovery semantics are out of scope.
- `ListJobs` page tokens are valid only for the same `(status_filter, sort)` query shape in v1.

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
│  ├─ taskqueue_public.proto
│  └─ taskqueue_internal.proto
├─ generated/
│  ├─ taskqueue_public_pb2.py
│  ├─ taskqueue_public_pb2_grpc.py
│  ├─ taskqueue_internal_pb2.py
│  └─ taskqueue_internal_pb2_grpc.py
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
