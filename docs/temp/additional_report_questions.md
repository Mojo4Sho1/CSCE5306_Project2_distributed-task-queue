# additional_report_questions.md

## Purpose
Resolve the A/B comparison semantics and ensure the reportâ€™s â€œfairnessâ€ claims match what actually executed during the starter-matrix runs. These questions focus on (1) effective worker capacity, (2) Design B routing determinism, (3) retry/deadline behavior, (4) offered-load pacing semantics, and (5) whether we can decompose end-to-end time into queueing vs execution.

---

## A) Effective worker capacity and â€œslotâ€ semantics (highest priority)
1. **Design A worker concurrency actually used in benchmarks**
   - During the starter-matrix runs for Design A, how many *worker execution loops* were active in total?
   - Was there exactly **one worker container** with **one loop**, or were worker containers **scaled/replicated** (e.g., `--scale worker=N`)?
   - If scaled, what was the exact scaling factor and how was it invoked?

2. **Meaning of `TOTAL_WORKER_SLOTS=6` in Design A**
   - Where is `TOTAL_WORKER_SLOTS` defined and enforced?
   - Does it correspond to *real parallel execution capacity* (threads/async tasks/processes), or is it only a *logical budget* (e.g., coordinator permits)?
   - If the worker process is single-loop, how can it realize more than one â€œslotâ€ concurrently (if at all)?

3. **Design B effective worker capacity during benchmarks**
   - During starter-matrix runs for Design B, did **each of the 6 monolith containers** start a worker loop by default?
   - If yes, did each monolith run exactly **one slot** (one concurrent job) or more?
   - If no, which monolith nodes had a worker loop enabled?

4. **Were A and B intentionally matched on total worker capacity?**
   - If the goal was parity, what exact configuration ensured A and B had the same total number of concurrent job executions?
   - If parity was *not* enforced (by design), what is the intended interpretation of the comparison (e.g., â€œ6 distinct microservice nodesâ€ vs â€œ6 full-stack nodesâ€)?

---

## B) Design B routing determinism (owner selection details)
5. **Owner selection mechanisms (precise behavior)**
   - For `SubmitJob` in Design B:
     - What code path implements round-robin when `client_request_id` is empty?
     - What code path implements deterministic hashing when `client_request_id` is non-empty?
   - What is the exact ordered list of monolith targets used for round-robin/hashing, and how is that ordering kept stable?

6. **How deterministic routing by `job_id` works**
   - Is the â€œowner-affinityâ€ achieved by:
     - encoding node identity into `job_id`,
     - generating IDs such that hash(job_id) returns to the same node,
     - or simply reusing the same hash function + same stable node list for routing all job-scoped calls?
   - Please point to the exact functions/files that:
     - generate `job_id`, and
     - compute the node selection from `job_id`.

7. **Behavior when the owner is down (v1 semantics)**
   - Confirm what happens for `GetJobStatus`, `GetJobResult`, and `CancelJob` if the owner node is unavailable:
     - expected gRPC status codes (e.g., `UNAVAILABLE`, `DEADLINE_EXCEEDED`),
     - any retry attempts (client side),
     - any fallback behavior (forwarding/failover) (expected: none in v1).

---

## C) Retry / timeout / deadline policy (affects p95/p99 and load amplification)
8. **Worker `ReportWorkOutcome` retry policy**
   - Max attempts?
   - Backoff strategy (fixed/exponential; min/max delay)?
   - Which gRPC status codes are considered retryable?
   - What is the per-RPC deadline/timeout?

9. **Client RPC adapter retry policy**
   - For each method (`SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`):
     - max attempts,
     - backoff,
     - retryable codes,
     - per-RPC deadlines.
   - Confirm the special-case behavior: `SubmitJob` retries only when `client_request_id` is non-empty (idempotency key behavior).

---

## D) Offered-load pacing semantics (prevents ambiguous â€œthroughput matchedâ€ statements)
10. **Meaning of `request_rate_rps` in the load generator**
   - Is `request_rate_rps` applied:
     - globally across all concurrent clients (shared token bucket),
     - per-client,
     - or per-worker thread/process in the load generator?
   - If global, confirm how concurrency interacts with pacing (e.g., queued client tasks waiting for tokens).

11. **Definition of â€œfixed pacingâ€ in artifacts**
   - In the summary/aggregation code, when we say â€œthroughput matched under fixed pacing,â€ does that refer to:
     - successful RPCs/sec being constrained by the load generator (offered load),
     - or something else?
   - Which exact metrics/fields are used to compute â€œRPC throughputâ€?

---

## E) Timestamp availability (enables stronger results analysis without deep profiling)
12. **What per-job timestamps exist in artifacts**
   - For each job, do artifacts record:
     - `accepted_at` (submit accepted),
     - `started_at` (work began),
     - `completed_at` (terminal),
     - or only accepted + terminal?
   - If `started_at` exists anywhere, identify the file/schema path.

13. **Can we compute queueing delay vs execution time?**
   - If `started_at` exists:
     - queueing delay = `started_at - accepted_at`
     - execution time = `completed_at - started_at`
   - If it does not exist:
     - confirm that only end-to-end completion time is available in v1 artifacts.

---

## F) Job â€œworkâ€ propagation sanity check (small but clarifying)
14. **Work duration propagation**
   - Confirm why `FetchWork` returns `spec.work_duration_ms=0` in current path.
   - Identify where an explicit duration *would* be set (if supported) and why it is not currently propagated.
   - Confirm worker fallback behavior: `<=0` defaults to ~`120 ms`, and explicit values clamp to `[20, 2000]`.

---
## Answers (repo-grounded)

1. **Design A worker concurrency actually used in benchmarks**
   - Effective active execution loops in starter-matrix runs appear to be **1 total** for Design A.
   - Evidence: Design A compose defines a single `worker` service, and starter-matrix execution logs show only `docker-worker-1` (no `worker-2+`, no `--scale worker=N` in reproducibility commands).
   - I found no repo evidence that worker service was scaled during those runs.

2. **Meaning of `TOTAL_WORKER_SLOTS=6` in Design A**
   - `TOTAL_WORKER_SLOTS` is defined/enforced in benchmark scenario contracts as a locked value (`6`), not in worker runtime concurrency control.
   - It functions as a fairness/control metadata budget in scenarios and artifact rows.
   - Current worker process behavior is single-loop (`run -> _run_iteration -> fetch one -> execute one -> report one`), so runtime does not realize 6 concurrent in-process slots.

3. **Design B effective worker capacity during benchmarks**
   - Yes, the 6 monolith containers are started in starter-matrix runs.
   - Each monolith starts one embedded worker loop by default (`MONOLITH_ENABLE_WORKER` defaults enabled).
   - So effective baseline is 1 worker loop per node, 6 loops total, unless explicitly disabled (not seen in compose/runbook/log evidence).

4. **Were A and B intentionally matched on total worker capacity?**
   - Intent/documentation says yes (A: 1x6, B: 6x1).
   - Executed runtime evidence indicates **effective mismatch** in this code path: Design A behaves as one active loop while Design B has six active loops.
   - Therefore parity is asserted by contract/metadata, but not fully realized by observed Design A runtime behavior.

5. **Owner selection mechanisms (precise behavior)**
   - `SubmitJob` in Design B uses:
     - Empty `client_request_id`: round-robin (`DesignBClientRouter.submit_target -> next_round_robin_target`).
     - Non-empty `client_request_id`: deterministic hash-owner (`submit_target -> owner_target_for_key`).
   - Ordered target list is the scenario-provided `design_b_ordered_targets` array; routing stability depends on this fixed ordering for the run.

6. **How deterministic routing by `job_id` works**
   - It uses both:
     - Job generation in each monolith node is owner-affine: `JobServicer._new_job_id()` keeps generating UUIDs until `owner_index_for_key(job_id)` matches that node index.
     - Client/job-scoped routing applies the same hash function over `job_id` with the same ordered node list.
   - Relevant code:
     - `job_id` generation: `services/job/servicer.py` (`_new_job_id`).
     - Node selection from `job_id`: `common/design_b_routing.py` (`job_target`) and `common/owner_routing.py` (`owner_index_for_key`).

7. **Behavior when the owner is down (v1 semantics)**
   - No forwarding/failover in v1.
   - Client retry logic can retry retryable transport codes (`UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`) up to configured attempts, but against the same owner target.
   - Final surfaced code depends on failure mode/timing; repo policy supports `UNAVAILABLE` and `DEADLINE_EXCEEDED` as retryable outcomes.

8. **Worker `ReportWorkOutcome` retry policy**
   - Max attempts: default 4.
   - Backoff: exponential with full jitter; initial 100 ms, multiplier 2.0, max 1000 ms.
   - Retryable codes: **not code-filtered in worker loop**; worker retries on non-accepted response or exceptions until attempts exhausted.
   - Per-RPC timeout: internal unary timeout default 1000 ms for `ReportWorkOutcome` call.

9. **Client RPC adapter retry policy**
   - Deadlines:
     - `SubmitJob`: 3.0 s
     - `CancelJob`: 3.0 s
     - `GetJobStatus`: 1.0 s
     - `GetJobResult`: 1.0 s
     - `ListJobs`: 1.0 s
   - Max attempts: 4 when retry enabled; otherwise 1.
   - Backoff: exponential full-jitter, 100 ms initial, 2.0 multiplier, 1000 ms cap.
   - Retryable codes: `UNAVAILABLE`, `DEADLINE_EXCEEDED`, `RESOURCE_EXHAUSTED`.
   - Special case confirmed: `SubmitJob` retries only when `client_request_id` is non-empty (`allow_retry=bool(client_request_id)`).

10. **Meaning of `request_rate_rps` in the load generator**
   - It is not implemented as a single global token bucket.
   - Each loadgen worker thread self-paces with interval `concurrency / request_rate_rps`; aggregate effect targets global offered rate.
   - Concurrency affects number of threads while interval scales proportionally.

11. **Definition of "fixed pacing" in artifacts**
   - In current aggregation, "throughput" is successful RPC calls per second (`ok_calls / measure_seconds`) by method.
   - So "throughput matched under fixed pacing" refers to method-level successful RPC throughput under controlled offered load, not terminal jobs/sec.

12. **What per-job timestamps exist in artifacts**
   - API/schema support exists for `accepted_at_ms`, `started_at_ms`, `finished_at_ms`.
   - Job service tracks `created_at_ms`, `started_at_ms`, `finished_at_ms`.
   - But benchmark row artifacts (`rows.jsonl`/`rows.csv`) do not include those per-job lifecycle timestamps; they include RPC `start_ts_ms` and response-derived flags/ids.

13. **Can we compute queueing delay vs execution time?**
   - From current persisted benchmark artifacts alone: **not reliably**.
   - Reason: needed per-job lifecycle timestamps (`accepted_at`, `started_at`, `finished/completed`) are not written into row artifacts, so decomposition into queueing vs execution is unavailable from saved loadgen tables.

14. **Work duration propagation**
   - `FetchWork` returns `spec.work_duration_ms=0` because coordinator reads `GetJobRecordResponse` (which currently returns `JobSummary` + `failure_reason`, not full stored `JobSpec`) and populates placeholder spec fields.
   - Explicit duration is set at submit and stored in Job service (`CreateJobRequest.spec.work_duration_ms` -> job record), but not propagated through current `FetchWork` path.
   - Worker behavior confirmed: `work_duration_ms <= 0` defaults to ~120 ms; explicit values clamp to `[20, 2000]`.

## Notes on uncertainty
- I could not find evidence of runtime scaling commands for Design A worker in the recorded starter-matrix workflow/logs; if scaling happened outside these tracked commands/logs, that evidence is not present in this repository.
- For owner-down behavior, exact final gRPC code (`UNAVAILABLE` vs `DEADLINE_EXCEEDED`) is environment/failure-mode dependent; repository code specifies retry classification and no failover, but not one universal terminal code in every outage case.
