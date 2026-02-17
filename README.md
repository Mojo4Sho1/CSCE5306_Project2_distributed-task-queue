# Distributed Task Queue (Distributed Systems Project)

This repository implements and evaluates a distributed task queue using gRPC and Protocol Buffers.

The project compares:
- **Design A:** Microservices (6 functional nodes)
- **Design B:** Monolith-per-node (6 nodes)

## Documentation Entry Point

The controlling documentation file is:
- `docs/INDEX.md`

Read `docs/INDEX.md` first for:
- authority hierarchy,
- navigation order,
- and update rules.

## Project Scope (v1 Snapshot)

- Communication model: gRPC + protobuf
- Storage model: in-memory
- Processing semantics: at-least-once
- Cancellation semantics:
  - queued cancellation expected,
  - running cancellation best-effort and non-preemptive
- Load generator is evaluation tooling and not counted as a functional node

## Authoritative Specifications

- Architecture and ownership: `docs/spec/architecture.md`
- API contracts and schemas: `docs/spec/api-contracts.md`
- Lifecycle/state machine: `docs/spec/state-machine.md`
- Runtime/env/startup/healthchecks: `docs/spec/runtime-config.md`
- Error/idempotency/retry: `docs/spec/error-idempotency.md`
- Fairness/evaluation protocol: `docs/spec/fairness-evaluation.md`
- Locked constants/defaults: `docs/spec/constants.md`
- Requirements (FR/NFR): `docs/spec/requirements.md`
- Governance and decision locks: `docs/spec/governance.md`

Proto contract authority:
- `proto/taskqueue_public.proto`
- `proto/taskqueue_internal.proto`

## Tech Stack

- Python
- grpcio / protobuf
- Docker / Docker Compose
- Git / GitHub

## Repository Structure

```text
distributed-task-queue/
|-- README.md
|-- docs/
|   |-- INDEX.md
|   `-- spec/
|-- proto/
|-- generated/
|-- services/
|-- common/
|-- scripts/
`-- results/
```
