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

## Phase 0 Decision Lock (Frozen)

**Freeze date:** 2026-02-10

- System choice is fixed to **Distributed Task Queue**.
- Architecture comparison is fixed to:
  - **Design A:** Microservices (6 functional nodes)
  - **Design B:** Monolith-per-node (6 nodes)
- Node-count rule is fixed: load generator is not a functional node.
- Communication model is fixed to gRPC + protobuf.
- Storage assumption is fixed to **in-memory state** for this project.
- Processing semantics: **at-least-once** execution.
- Cancellation semantics: queued cancellation is expected; running cancellation is best-effort.
- Evaluation fairness controls are fixed: same hardware, workload profiles, warm-up, run duration, and measurement method for both designs.

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
