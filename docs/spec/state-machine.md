# State Machine Specification

This document defines the canonical job lifecycle for the Distributed Task Queue v1 implementation.

## Scope

This specification applies to both architectures:

- **Design A:** Microservices
- **Design B:** Monolith-per-node

Both designs must preserve the same externally visible lifecycle and terminal-state semantics.

---

## Canonical States

The system uses exactly five canonical job states:

- `QUEUED`
- `RUNNING`
- `DONE`
- `FAILED`
- `CANCELED`

No additional canonical states are introduced in v1.

---

## Lifecycle Graph

~~~text
QUEUED -> RUNNING -> DONE
QUEUED -> RUNNING -> FAILED
QUEUED -> CANCELED
RUNNING -> CANCELED   (best-effort, non-preemptive)
~~~

---

## State Authority and Ownership

### Canonical status authority
- **Job Service** is the only authority that applies canonical status values.

### Transition orchestration
- **Coordinator Service** orchestrates execution-path transitions:
  - `QUEUED -> RUNNING`
  - `RUNNING -> DONE | FAILED | CANCELED`
- **Gateway Service** may execute the guarded queued-cancel transition path:
  - `QUEUED -> CANCELED`
  - only after queue-removal confirmation and terminal-envelope write.

### Non-authoritative participants
- **Worker Service** never writes canonical status directly; it reports outcomes to Coordinator.
- **Queue Service** owns queue membership only, not canonical status.
- **Result Service** owns terminal result envelopes, not canonical status.

---

## Allowed Transitions

| Trigger | From | To | Primary actor | Notes |
|---|---|---|---|---|
| Successful `SubmitJob` | (none) | `QUEUED` | Gateway -> Job (+ Queue) | Acceptance requires enqueue success |
| Work assignment / dequeue | `QUEUED` | `RUNNING` | Coordinator -> Job (CAS) | Assignment only after CAS success |
| Worker success report | `RUNNING` | `DONE` | Worker -> Coordinator -> Job | Uses terminalization protocol |
| Worker failure report | `RUNNING` | `FAILED` | Worker -> Coordinator -> Job | Uses terminalization protocol |
| Cancel pending job | `QUEUED` | `CANCELED` | Gateway -> Queue remove -> Job (CAS) | Remove from queue first |
| Cancel running job (best-effort) | `RUNNING` | `CANCELED` | Gateway sets cancel flag; Coordinator applies if race wins | Non-preemptive in v1 |

Any transition not listed above is invalid and must be rejected and logged.

---

## Submit Acceptance Atomicity

`SubmitJob` acceptance in Design A:

1. Gateway calls `CreateJob` in Job Service.
2. Gateway calls `EnqueueJob` in Queue Service.
3. Submit is accepted only if enqueue succeeds.
4. If enqueue fails after create succeeds, Gateway calls:
   - `DeleteJobIfStatus(job_id, expected_status=QUEUED)`
5. If compensation succeeds, return failure (`UNAVAILABLE`) and no accepted job remains.
6. If compensation fails, log a consistency anomaly with `job_id`.

---

## Dequeue/CAS Dispatch Protocol

Coordinator dispatch flow:

1. Dequeue `job_id` from Queue Service.
2. Attempt CAS transition in Job Service: `QUEUED -> RUNNING`.
3. Assign work to Worker only if CAS succeeds.

If CAS fails:

- do not assign work,
- log expected race behavior,
- do not silently drop work.

### Dequeue/CAS Rescue Rule

Because v1 dequeue is destructive:

1. On CAS failure, read authoritative status from Job Service.
2. If status is still `QUEUED`, perform one immediate `EnqueueJob(job_id)` rescue attempt.
3. If status is terminal (or no longer queued), do not re-enqueue.
4. Log rescue attempt with `job_id`.

---

## Terminal Result Consistency Protocol

### Execution-path terminalization (`DONE`, `FAILED`, running `CANCELED`)
1. Coordinator calls `StoreResult` in Result Service (idempotent write).
2. Coordinator attempts CAS terminal transition in Job Service (`RUNNING -> terminal`).
3. If CAS fails because another terminal state already won, log benign terminal race.

### Queued cancellation terminalization
1. Gateway calls `RemoveJobIfPresent` in Queue Service.
2. Gateway calls `StoreResult` cancellation envelope in Result Service.
3. Gateway attempts CAS in Job Service (`QUEUED -> CANCELED`).

### Invariant
Terminal jobs are expected to expose terminal result envelopes via `GetJobResult`.

If canonical status is terminal but a terminal envelope is missing, log a consistency anomaly.

---

## Terminal-State Precedence

`DONE`, `FAILED`, and `CANCELED` are terminal states.

**First valid terminal transition applied by Job Service wins.**  
Later conflicting terminal writes are ignored and logged.

---

## Cancellation Semantics

1. **Queued cancellation:** expected to succeed if job has not started.
2. **Running cancellation:** best-effort and non-preemptive in v1.
3. For running jobs, `CancelJob` sets `cancel_requested=true`; completion/failure may still win the race.
4. Repeated cancellation requests are idempotent and deterministic once terminal.
5. **Queued-cancel race fallback:** if queued-cancel loses the race (e.g., `RemoveJobIfPresent=false` because dequeue already happened), Gateway must:
   - set `cancel_requested=true` via Job Service,
   - return authoritative `current_status`,
   - continue under running-cancel semantics.

---

## Invalid Transition Handling

Any transition not listed in **Allowed Transitions** is rejected and logged (for example, `DONE -> RUNNING`).

---

## Mutation Invariants

1. No service writes another service’s internal store directly.
2. All cross-service actions occur through gRPC contracts.
3. Gateway remains stateless with respect to canonical job state.
4. Worker executes only assigned jobs; it does not self-assign via local policy.
5. Queue mutations occur only in Queue Service.
6. Canonical status mutations occur only in Job Service.

---

## Lifecycle Observability Requirements

Lifecycle-critical logs must use JSON Lines and include, at minimum:

- `ts_ms`
- `level`
- `service`
- `method`
- `event`
- `job_id` (if present)
- `worker_id` (if present)
- `expected_status` (for CAS paths, when applicable)
- `current_status` (when known)
- `grpc_code` (for non-OK outcomes)
- `message`

Anomalies that must be logged:

- submit compensation failure,
- dequeue/CAS race outcome,
- dequeue rescue attempt,
- terminal race conflict,
- invalid transition attempt,
- terminal-status/result mismatch.

---

## Monolith Equivalence Constraint

Design B may differ internally (routing/storage implementation details), but it must preserve the same externally visible lifecycle and terminal-state semantics defined in this document.
