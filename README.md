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
   The coordinator tracks worker heartbeats and marks workers unavailable after timeout so queued jobs are not silently lost.

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
| Gateway | Job: `CreateJob`, `GetJobRecord`, `ListJobRecords`, `SetCancelRequested`; Queue: `EnqueueJob`, `RemoveJobIfPresent`; Result: `GetResult` |
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
