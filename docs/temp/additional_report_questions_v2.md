# additional_report_questions_v2.md

## Purpose
Finalize a report narrative that does **not** require new experiments by:
1) correcting the fairness framing (equal node-count, different effective execution capacity), and  
2) tightening the causal explanation of observed terminal throughput and latency using only repo-grounded behavior.

---

## A) Design A hot-path behavior (why terminal jobs/sec is well below 1/0.12s)
1. **Worker FetchWork polling cadence**
   - When the worker loop calls `FetchWork` and receives “no work available,” does it:
     - immediately retry (tight loop), or
     - sleep for a fixed interval, or
     - apply exponential backoff?
   - Identify the exact code path and default sleep/backoff parameters.

2. **Worker loop minimum delay even when work exists**
   - When work *is* returned, does the worker loop introduce any deliberate delay between iterations (e.g., tick interval)?
   - If yes, what are the defaults and where are they configured?

3. **Coordinator dispatch throttling**
   - Does the coordinator enforce any throttling/lease/heartbeat gating that limits how frequently a worker can obtain new work?
   - Examples: issuing work only on heartbeat cadence, limiting in-flight leases, cooldown intervals, etc.
   - Provide the relevant code path and default values.

4. **Synchronous RPC chain on the Design A worker path**
   - For a single job execution in Design A, list the ordered RPC calls on the critical path from:
     - worker `FetchWork` → (any internal calls) → worker “execute” → worker `ReportWorkOutcome`.
   - Include whether coordinator performs internal RPCs such as JobService lookups, QueueService ops, ResultService writes, etc., and which of these are synchronous vs async.

---

## B) Design B execution and state model (to describe accurately in the report)
5. **Where the queue lives in Design B**
   - On `SubmitJob`, does the job get enqueued into:
     - an owner node’s local in-process queue only, or
     - any shared queue component across nodes?
   - Confirm whether there is **any** cross-node queue/state sharing in v1.

6. **State replication / forwarding behavior (confirm “owner-only”)**
   - Confirm that job records and results are stored only in the owner node’s in-memory state in v1.
   - Confirm there is no inter-node forwarding for `GetJobStatus`, `GetJobResult`, or `CancelJob`.

7. **Design B worker loop cadence**
   - Does the embedded worker loop in each monolith use the same polling/backoff logic as Design A’s standalone worker?
   - If different, identify the differences and defaults.

---

## C) Capacity framing for the report (no new experiments; just describe truth)
8. **Confirm effective execution capacity as-run**
   - For the starter-matrix runs:
     - Design A: number of worker loops actually running (expected: 1).
     - Design B: number of worker loops actually running (expected: 6).
   - Point to the compose defaults and any enabling env vars (e.g., `MONOLITH_ENABLE_WORKER`) that make this true.

9. **Worker-loop terminology (avoid misleading claims)**
   - Given current code, what is the exact worker-loop execution model in each design?
   - Is there any implementation anywhere that creates true parallel execution in a single worker process/container (threads/async/process pool), or is each loop strictly single-job-at-a-time?

---

## D) (Optional, if easy) Any artifact-visible signal for queueing/empty-poll behavior
10. **Evidence of empty polls / no-work responses**
   - Do run logs or per-run artifacts record counts of:
     - `FetchWork` responses with “no work,”
     - worker idle time,
     - coordinator “no dispatch” events,
     - or similar?
   - If yes, identify where these appear (file paths / log lines / counters), since this can support the explanation of low jobs/sec in Design A without adding new instrumentation.

---
## Answers (repo-grounded)

### A) Design A hot-path behavior

1. **Worker `FetchWork` polling cadence**
   - Behavior on no work: **sleep**, not tight-loop and not exponential backoff.
   - Code path: `services/worker/worker.py` (`_run_iteration` -> `_fetch_work`).
   - Mechanics:
     - Worker calls `FetchWork`.
     - If no assignment, coordinator response `retry_after_ms` is honored when `>0`; otherwise worker uses `fetch_idle_sleep_ms`.
     - Sleep floor is `max(..., 50 ms)`.
   - Defaults:
     - `fetch_idle_sleep_ms = 200` ms (`common/config.py`, fallback in `services/worker/worker.py`).
     - Coordinator `retry_after_ms` default = `200` ms, clamped to `[50, 1000]` (`common/rpc_defaults.py`, used by coordinator servicer).

2. **Worker loop minimum delay even when work exists**
   - With assignment present, there is **no deliberate inter-iteration idle sleep/tick**.
   - Loop does: `FetchWork` -> execute (simulated wait) -> `ReportWorkOutcome` -> next iteration.
   - The dominant per-job delay is execution wait (`work_duration_ms` fallback to `120` ms when non-positive).

3. **Coordinator dispatch throttling**
   - No lease-credit or in-flight slot throttling exists in coordinator dispatch logic in this repo.
   - Gating that *does* exist:
     - Worker must be heartbeat-live (`worker_timeout_ms`, default `4000` ms).
     - `FetchWork` requires successful queue dequeue and `QUEUED -> RUNNING` CAS.
     - If no job found (or gating fails), coordinator returns `assigned=false` and `retry_after_ms` hint.
   - Defaults:
     - `heartbeat_interval_ms = 1000`, `worker_timeout_ms = 4000`, `retry_after_ms` default `200` (clamped `[50,1000]`).

4. **Synchronous RPC chain on Design A worker path**
   - Ordered critical path for one job:
     1. Worker -> Coordinator: `FetchWork` (sync unary RPC).
     2. Coordinator -> Queue: `DequeueJob` (sync unary RPC).
     3. Coordinator -> Job: `TransitionJobStatus(QUEUED->RUNNING)` (sync unary RPC).
     4. Coordinator -> Job: `GetJobRecord` (sync unary RPC).
     5. Coordinator -> Worker: `FetchWorkResponse(assigned=true, job_id, spec)`.
     6. Worker local execute (simulated wait, no RPC).
     7. Worker -> Coordinator: `ReportWorkOutcome` (sync unary RPC; worker may retry with bounded jittered backoff).
     8. Coordinator -> Result: `StoreResult` (sync unary RPC).
     9. Coordinator -> Job: `TransitionJobStatus(RUNNING->terminal)` (sync unary RPC).
   - Notes:
     - Coordinator rescue path may re-enqueue job when transition race fails.
     - In this path, internal coordinator downstream calls are synchronous; no async background pipeline is implemented.

### B) Design B execution and state model

5. **Where the queue lives in Design B**
   - Queue is **owner node local in-process state** (per monolith node), not shared across nodes.
   - Each monolith process hosts its own `QueueServicer` with in-memory `OrderedDict` queue.
   - No shared cross-node queue component is implemented in v1.

6. **State replication / forwarding behavior (owner-only)**
   - Confirmed in v1:
     - Job records are per-node in-memory state (`JobServicer._jobs`).
     - Results are per-node in-memory state (`ResultServicer._results`).
     - No built-in inter-node forwarding for `GetJobStatus`, `GetJobResult`, `CancelJob`.
   - Routing correctness is delegated to client/loadgen deterministic owner routing (`docs/spec/fairness-evaluation.md`, `common/design_b_routing.py`).

7. **Design B worker loop cadence**
   - Embedded monolith worker uses the **same `WorkerRuntime` class** as Design A standalone worker.
   - So polling/backoff/sleep behavior is the same defaults (`HEARTBEAT_INTERVAL_MS=1000`, `FETCH_IDLE_SLEEP_MS=200`, coordinator retry hint behavior).
   - Difference is topology/placement (in-thread inside each monolith) rather than worker-loop logic.

### C) Capacity framing for report

8. **Confirm effective execution capacity as-run (starter matrix)**
   - Design A:
     - Compose has one `worker` service (`docker/docker-compose.design-a.yml`).
     - Execution log shows only `docker-worker-1` for Design A stack (`results/loadgen/starter_matrix_execution_2026-02-20.log`).
     - Effective running worker loops from recorded run: **1**.
   - Design B:
     - Compose defines `monolith-1..monolith-6`.
     - Monolith runtime default is `MONOLITH_ENABLE_WORKER` enabled when env var unset.
     - Execution log shows six healthy monolith containers.
     - Effective running worker loops from recorded run: **6** (one per monolith).

9. **Worker-loop terminology**
   - In current code, one active worker loop executes one job at a time.
   - No implementation in this repo creates true parallel execution *within a single worker process/container* (no worker thread pool/process pool/async multi-exec loop).
   - Therefore:
     - Design A runtime: one worker loop in one worker container (as-run evidence).
     - Design B runtime: six worker loops total (one per monolith node).

### D) Optional artifact-visible signal for empty-poll behavior

10. **Evidence of empty polls / no-work responses**
   - Code emits explicit structured events for this behavior:
     - Worker: `worker.fetch.response` (`assigned`, `retry_after_ms`) and `worker.loop.idle_sleep`.
     - Coordinator semantics: returns `assigned=false` + `retry_after_ms` on no dispatch.
   - In the checked benchmark artifacts under `results/loadgen/`, there are per-run RPC rows/summaries and execution chronology log, but **no persisted counters/log extract of worker empty-fetch counts**.
   - Reason unable to provide direct count from current repo artifacts:
     - Starter matrix evidence package does not include captured worker/coordinator structured logs with those event counts; only loadgen RPC artifacts are indexed.
