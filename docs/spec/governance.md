# Governance and Decision Locks (v1)

**Status:** Locked for v1  
**Freeze baseline:** 2026-02-10

This document records project-level governance rules, frozen decisions, and ambiguity lock resolutions.

---

## 1) Phase 0 Decision Lock

- System choice is fixed to **Distributed Task Queue**.
- Architecture comparison is fixed to:
  - **Design A:** Microservices (6 functional nodes)
  - **Design B:** Monolith-per-node (6 nodes)
- Node-count rule is fixed: load generator is not a functional node.
- Communication model is fixed to gRPC + protobuf.
- Proto packaging is fixed to two files (public + internal).
- Storage assumption is fixed to in-memory.
- Processing semantics are fixed to at-least-once execution.
- Cancellation semantics are fixed to:
  - queued cancellation expected,
  - running cancellation best-effort and non-preemptive.
- Fairness controls are fixed as documented in `docs/spec/fairness-evaluation.md`.

### Out of scope

- Durable persistence guarantees
- Consensus/leader election
- Exactly-once guarantees
- Production-grade security hardening
- Multi-region deployment

---

## 2) Implementation Freeze Gate

No new design features are introduced before:
1. both proto files compile,
2. generated stubs are integrated, and
3. microservice smoke tests pass for all five public RPCs.

Phase-closure rule:
- No new design features are added before proto compilation, stub generation, and end-to-end smoke validation complete.

Frozen clarifications:
- Design B client/load-generator routing is mandatory:
  - non-empty `client_request_id` submit routing uses deterministic key-owner mapping,
  - job-scoped reads/cancel route by deterministic `job_id` owner mapping.
- `StoreResult` accepts terminal statuses only (`DONE`, `FAILED`, `CANCELED`); otherwise `INVALID_ARGUMENT`.
- Dequeue is destructive in v1 with no lease/ack/requeue recovery guarantee.
- `ListJobs` page tokens are valid only for the same `(status_filter, sort)` query shape in v1.

---

## 3) Ambiguity Lock Register (Resolved)

1. Submit anomaly handling: compensation + anomaly logging on create/enqueue partial failure.
2. Fairness framing for starter-matrix evidence: equal node count across designs, but documented as-run effective worker-loop capacity may differ and must be disclosed explicitly.
3. Ingress policy: fixed request routing policy per design.
4. Terminal race precedence: first valid terminal write wins.
5. Sort behavior: enum-based sort (`CREATED_AT_DESC` / `CREATED_AT_ASC`), no free-text sort.
6. ErrorInfo treatment: no generic `ErrorInfo` message in v1 schema.
7. Pagination semantics: offset-based string page tokens.
8. Timestamp authority: server-generated UTC epoch ms is authoritative.
9. Worker health scope: heartbeat is canonical; optional health checks are operational only.
10. Priority treatment: `priority` is removed from v1 `JobSpec`.
11. Proto packaging: two files (`taskqueue_public.proto`, `taskqueue_internal.proto`), no common proto in v1.
12. Dequeue/CAS race policy: CAS gate required before assignment; failed CAS is logged expected race behavior.
13. FetchWork idle policy: explicit server backoff hint (`retry_after_ms`) prevents busy-spin.
14. Submit empty idempotency key: empty `client_request_id` means non-idempotent submit.
15. Result consistency protocol: terminalization uses Result Service envelope + guarded status CAS with anomaly logging on partial failure.
16. Deterministic pagination tie-break: `job_id` ascending on equal `created_at_ms`.
17. Worker identity source: `WORKER_ID` env var then hostname fallback.
18. Checksum format and output cap: lowercase SHA-256 checksum; max output bytes locked.
19. Cancel unknown ID behavior: explicit `NOT_FOUND`.
20. ListJobs snapshot model: best-effort non-snapshot pagination in v1.
21. FR-6 scope: internal requirement only; not public API equivalence surface.
22. Queued-cancel race fallback: if queue removal misses due to race, set cancel-request flag and continue best-effort running-cancel semantics.
23. Terminal-status/result mismatch behavior: return `UNAVAILABLE` and log anomaly.
24. Empty status filter behavior: `ListJobs` with empty filter includes all statuses.
25. Submit dedup cache bounds: in-memory dedup map is bounded (`MAX_DEDUP_KEYS`) with eviction; guarantees hold while key is retained.
26. Proto service naming lock: public/internal service names are frozen for v1 (`TaskQueuePublicService`, `JobInternalService`, `QueueInternalService`, `CoordinatorInternalService`, `ResultInternalService`).
27. Design B coherence routing: job-scoped reads/cancel route by deterministic `job_id` owner mapping.
28. Design B ListJobs parity scope: implemented with equivalent schema; excluded from primary throughput/latency parity conclusions.
29. StoreResult conflict visibility: response carries `already_exists` and `current_terminal_status` for race introspection.
30. Transition guard strictness: CAS requires explicit non-UNSPECIFIED `expected_from_status`.
31. Queue ordering strength: best-effort FIFO only; strict global FIFO is out of v1 correctness assumptions.
32. Heartbeat timing constants: interval 1000 ms, timeout 4000 ms.
33. Retry constants: exponential backoff with full jitter (100 ms start, x2, 1000 ms cap, 4 total attempts).
34. Logging format: JSON Lines with required structured fields.
35. Job ID format: UUIDv4 for v1.
36. Submit payload canonical equality: key-sorted `labels` and exact `JobSpec` field equality define dedup payload match.
37. Design B routing executor: client/load generator performs deterministic owner routing for job-scoped reads/cancel; no inter-node forwarding in v1.
38. Design B submit idempotency routing: non-empty `client_request_id` routes by deterministic key owner.
39. Running-cancel execution model: non-preemptive best-effort; `cancel_requested` is advisory until terminal race resolves.
40. Dequeue model: destructive pop in v1; no ack/requeue protocol.
41. Timestamp authority mapping: Job Service stamps created/started/finished canonical times.
42. Dequeue/CAS rescue behavior: if CAS fails and status remains `QUEUED`, Coordinator performs one immediate re-enqueue rescue.
43. Deterministic owner algorithm: SHA-256 + first 8 bytes big-endian modulo N with fixed node ordering.

---

## 4) Change Control

If governance- or decision-level behavior changes, record in the same change set:
1. what changed,
2. why it changed,
3. expected implementation/evaluation impact.

During active implementation work, design changes are allowed only for blocker-level reasons and must record:
1. blocker description,
2. why the current design fails,
3. exact change scope,
4. task impact.

---

## 5) Related Specs

- `docs/spec/architecture.md`
- `docs/spec/api-contracts.md`
- `docs/spec/state-machine.md`
- `docs/spec/runtime-config-design-a.md`
- `docs/spec/runtime-config-design-b.md`
- `docs/spec/error-idempotency.md`
- `docs/spec/fairness-evaluation.md`
- `docs/spec/constants.md`
- `docs/spec/requirements.md`
