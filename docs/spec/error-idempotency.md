# Error Model and Idempotency Behavior (Phase 0.6 Lock)

## Scope

This document defines the v1 error model, idempotency behavior, retry policy, and error-observability requirements for the distributed task queue system.

## Lock Status

- **Status:** Locked for v1
- **Freeze baseline:** 2026-02-10
- Changes require explicit change-control notes (what changed, why, impact).

---

## 1) Error Handling Model (Locked)

The system uses a two-layer model:

1. **Hard errors:** gRPC status codes (non-OK RPC response)
2. **Soft outcomes:** `OK` with explicit response fields (`accepted`, `result_ready`, `already_terminal`, `applied`)

---

## 2) gRPC Status Code Policy (Locked)

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

---

## 3) Soft Outcome Policy (Locked)

Use `OK` responses for:

- `GetJobResult` when result is not ready
- `CancelJob` when job is already terminal
- duplicate cancellation requests
- CAS mismatch on `TransitionJobStatus`
- condition mismatch on `DeleteJobIfStatus`

---

## 4) Client-Facing Idempotency Matrix (Locked)

| Method | Idempotent? | Key / Identity | Required Behavior |
|---|---|---|---|
| `SubmitJob` | Conditionally | `client_request_id` | Non-empty key: same key + same payload returns original `job_id`; same key + different payload returns `FAILED_PRECONDITION` while key remains in dedup cache. Empty key: treat as non-idempotent new submit. |
| `GetJobStatus` | Yes | `job_id` | Safe repeated reads |
| `GetJobResult` | Yes | `job_id` | Safe repeated reads |
| `CancelJob` | Yes | `job_id` | Deterministic repeated calls |
| `ListJobs` | Yes | filters + page token | Safe repeated reads |

**v1 dedup scope:** in-memory for process lifetime only (not across restarts), bounded by `MAX_DEDUP_KEYS`.

**Design B routing note (locked):**  
To preserve `SubmitJob` idempotency with in-memory per-node dedup state, requests with non-empty `client_request_id` are routed to a deterministic owner node by the locked routing algorithm in the fairness spec.

---

## 5) Internal API Idempotency Matrix (Design A, Locked)

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

---

## 6) Retry/Backoff Guidance (Locked)

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

`SubmitJob` is auto-retried only when `client_request_id` is non-empty.  
If `client_request_id` is empty, do not auto-retry.

Do not auto-retry `INVALID_ARGUMENT`, `NOT_FOUND`, or `FAILED_PRECONDITION` without changing assumptions.

---

## 7) Determinism Rules for Cancellation (Locked)

- `QUEUED`: cancellation moves toward `CANCELED` with queue removal first, then guarded status transition.
- `RUNNING`: best-effort and non-preemptive in v1; completion may win the race.
- Terminal state: repeated cancel is deterministic non-error.
- If queued-cancel race is lost, system sets `cancel_requested=true` and follows running-cancel path.

---

## 8) Observability Requirements for Errors (Locked)

For every non-OK response, log:

- timestamp
- method
- code
- message
- `job_id` (if present)
- caller/service identity (if available)

---

## 9) Logging Format (Locked)

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

---

## 10) Deadline Defaults (Locked)

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

---

## 11) Terminal/Result Mismatch Handling (Locked)

If canonical job status is terminal but Result Service has no terminal envelope:

- API returns `UNAVAILABLE`,
- system logs a consistency anomaly with `job_id`,
- retry policy treats this as transient/retryable per locked backoff rules.

---

## Related Specs

- `docs/spec/api-contracts.md`
- `docs/spec/state-machine.md`
- `docs/spec/fairness-evaluation.md`
- `docs/spec/constants.md`
