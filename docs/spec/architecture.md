# Architecture Specification (`docs/spec/architecture.md`)

## Document Status

- **Status:** Locked for v1
- **Freeze date:** 2026-02-10
- **Scope:** System architecture, service ownership boundaries, and cross-service invariants.
- **Exclusions:** Detailed RPC schemas, state-machine transition rules, runtime env/ports, and benchmark methodology are specified in dedicated docs.

## Purpose

This document defines the architecture for the Distributed Task Queue project and fixes ownership boundaries so implementation remains consistent across work sessions.

---

## 1) System Overview

The system accepts client jobs, schedules and dispatches work, executes tasks, and returns status/results.

The project compares two designs:

1. **Design A: Microservices**
2. **Design B: Monolith-per-node**

Both designs use gRPC + Protocol Buffers and target equivalent client-facing behavior for fair comparison.

---

## 2) Architecture Alternatives

## Design A: Microservices (6 functional nodes)

1. **Gateway Service**
2. **Job Service**
3. **Queue Service**
4. **Coordinator Service**
5. **Worker Service**
6. **Result Service**

> A load generator may run as a separate evaluation client/container, but it is **not** counted as one of the six functional system nodes.

### Design intent
This design separates concerns by service ownership (API routing, canonical state, queueing, orchestration, execution, and results).

---

## Design B: Monolith-per-node (6 nodes)

- Six identical monolith nodes.
- Each node colocates most/core functionality in-process.
- The design exposes equivalent client-facing API behavior for parity with Design A.

### Design intent
This design reduces inter-service RPC hops and operational fragmentation, while preserving external semantics required for A/B comparison.

---

## 3) Communication Model

- **RPC framework:** gRPC
- **Schema format:** Protocol Buffers
- **Public package:** `taskqueue.v1`
- **Internal package (Design A):** `taskqueue.internal.v1`

For full method/message definitions, see:
- `docs/spec/api-contracts.md`
- `proto/taskqueue_public.proto`
- `proto/taskqueue_internal.proto`

---

## 4) Service Ownership Boundaries (Single-Owner Model)

Each data/control domain has one primary owner service.

## Gateway Service
**Owns**
- Client-facing gRPC API surface
- Request routing/orchestration across internal services

**Does not own**
- Canonical job state
- Queue internals
- Worker liveness registry
- Result payload storage

## Job Service
**Owns**
- Canonical job metadata and lifecycle status (`QUEUED`, `RUNNING`, `DONE`, `FAILED`, `CANCELED`)
- Submit idempotency/dedup index keyed by `client_request_id` (v1)

**Does not own**
- Queue ordering/membership
- Worker liveness policy
- Dispatch policy
- Result payload storage

## Queue Service
**Owns**
- Queue primitives only: `enqueue`, `dequeue`, `remove-if-present`

**Does not own**
- Canonical lifecycle status
- Worker selection policy
- Result payloads

## Coordinator Service
**Owns**
- Worker liveness registry
- Heartbeat timeout policy
- Dispatch orchestration flow

**Does not own**
- Canonical job metadata schema
- Result payload persistence

## Worker Service
**Owns**
- Execution of assigned jobs
- Reporting outcomes to Coordinator

**Does not own**
- Global queue policy
- Canonical lifecycle authority
- Client-facing API behavior

**v1 note**
- Worker has no public business API.
- Worker acts as an internal RPC client to Coordinator.

## Result Service
**Owns**
- Completed job output retrieval path
- Terminal result payload records

**Does not own**
- Queueing
- Worker liveness
- Dispatch decisions

---

## 5) Mutation Authority Rules (Locked)

- **Canonical status authority:** Job Service is the source of truth for job status.
- **Queue authority:** Queue Service is the only service that mutates queue contents.
- **Worker liveness authority:** Coordinator Service is the only service that determines worker availability from heartbeats.
- **Result payload authority:** Result Service is the only service that stores/retrieves final output payloads.

---

## 6) Cross-Service Boundary Invariants (Locked)

1. No service writes another service’s internal store directly.
2. All cross-service actions use gRPC contracts.
3. Gateway remains stateless with respect to canonical job state.
4. Worker executes assigned jobs only; Worker does not self-assign via local policy.
5. Optional worker/container health checks are operational-only and out of public API scope.

---

## 7) Functional Requirement Coverage by Service

| Requirement | Primary Services |
|---|---|
| **FR-1 SubmitJob** | Gateway, Job, Queue |
| **FR-2 GetJobStatus** | Gateway, Job, Result |
| **FR-3 GetJobResult** | Gateway, Result (canonical readiness resolved via Job status) |
| **FR-4 CancelJob** | Gateway, Job, Queue, Coordinator |
| **FR-5 ListJobs** | Gateway, Job |
| **FR-6 WorkerHeartbeat / FetchWork** | Coordinator, Worker, Queue |

**Scope clarification:** FR-6 is an internal requirement in Design A and is not part of the client-facing equivalence surface.

---

## 8) Public API Equivalence Constraint (Design A vs Design B)

Both designs expose the same client-facing RPC methods:

- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`
- `ListJobs`

### v1 parity scope
- Strict semantic parity: `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`
- `ListJobs` remains functionally available with schema parity; in Design B, v1 results may be best-effort/non-global unless explicit aggregation is added.

Internal RPC topologies may differ by design, but client-visible behavior remains equivalent within v1 scope.

---

## 9) Capacity and Fairness Architecture Constraints (v1)

- Starter-matrix as-run capacity framing:
  - **Design A:** 1 worker container with 1 sequential worker loop (effective execution concurrency: 1)
  - **Design B:** 6 monolith nodes, each with 1 embedded worker loop (effective execution concurrency: 6)
- Measurement parity requires identical hardware, workload profiles, warm-up policy, run duration, and aggregation logic.

Detailed routing and evaluation constraints are defined in:
- `docs/spec/fairness-evaluation.md`

Determinism clarification for new readers:
- See `docs/spec/fairness-evaluation.md` Section `4.4 Determinism Model (Design A vs Design B)` for why Design A does not require owner routing while Design B does.

---

## 10) Design Assumptions and Out-of-Scope (v1)

### Fixed assumptions
- In-memory storage only (project scope)
- At-least-once execution semantics
- Running cancellation is best-effort and non-preemptive

### Out-of-scope
- Durable persistence guarantees
- Consensus/leader election
- Exactly-once delivery/execution
- Production-grade security hardening
- Multi-region deployment

---

## 11) Related Specifications

- **API contracts:** `docs/spec/api-contracts.md`
- **State machine and transitions:** `docs/spec/state-machine.md`
- **Runtime wiring/env/readiness:**
  - `docs/spec/runtime-config-design-a.md`
  - `docs/spec/runtime-config-design-b.md`
- **Error/idempotency/retry model:** `docs/spec/error-idempotency.md`
- **Fairness and evaluation constraints:** `docs/spec/fairness-evaluation.md`
- **Locked constants:** `docs/spec/constants.md`

---

## 12) Change Control

If architecture-level behavior changes, record in the same change set:

1. What changed
2. Why it changed
3. Scope of impact (services/APIs/evaluation)
4. Any required updates to related spec documents and handoff docs
