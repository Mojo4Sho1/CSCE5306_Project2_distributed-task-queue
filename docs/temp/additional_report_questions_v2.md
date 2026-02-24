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

9. **Worker “slot” terminology (avoid misleading claims)**
   - Given current code, what does “slot” concretely mean in each design?
   - Is there any implementation anywhere that creates true parallel slots in a single worker process/container (threads/async/process pool), or is each loop strictly single-job-at-a-time?

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