# Report Finalization Questions (for Codex/Repo Agent)

## A) Experiment environment (must be explicit)
1. Were all containers **and** the load generator running on **one machine**, or across **multiple machines**?
2. What Docker and docker-compose (or Docker Compose plugin) versions were used?
3. Were any **CPU/memory limits** (or reservations) configured for containers? If yes, what were they?

## B) “Job work” definition (critical for interpreting throughput)
4. What does a worker actually execute for each job (e.g., fixed sleep, CPU loop, payload processing, etc.)?
5. Is job runtime **fixed or variable**? If fixed, what is the approximate duration? If variable, what is the distribution or range?
6. What causes a job to end as **DONE** vs **FAILED**? Are retries implemented anywhere?

## C) Worker-loop fairness (ensure designs are truly comparable)
7. In Design A (microservices): is the worker service a single execution loop, or does it implement any real parallel execution model (threads, async tasks, processes)?
8. In Design B (monolith-per-node): do the 6 monolith containers each run their own worker execution loop with exactly **1 slot**?
9. Do Design A and Design B use the same queueing policy (FIFO/priority), dispatch logic, and backpressure behavior under load?

## D) Routing semantics in Design B (needs one crisp explanation)
10. How is the **owner node** chosen on job submission in Design B (round-robin, hash, key-based routing, etc.)?
11. Does the **job_id** encode/enable deterministic owner routing for status/result/cancel, or does the client maintain a map?
12. What happens in v1 if the owner node is down when a client calls GetJobStatus / GetJobResult / CancelJob?

## E) Results sanity checks (for a tight narrative)
13. When the report says “mean throughput is matched under fixed pacing,” does that refer to **RPC throughput (requests/sec)** rather than **terminal job throughput (jobs/sec)**?
14. For scenarios with large A/B gaps (e.g., `high_submit_heavy`), do logs/metrics capture any corroborating signal (queue depth, worker utilization, time-in-queue, per-service CPU, retries/timeouts)?

---

## Answers (repo-grounded)

### A) Experiment environment (must be explicit)
1. All benchmark containers and the load generator were run on one machine (single-host local setup; no multi-host cluster).
2. Docker Engine: `24.0.6` (`linux/arm64`); Docker Compose: `v2.22.0-desktop.2`.
3. No explicit CPU/memory limits or reservations are set in the design compose files (`docker/docker-compose.design-a.yml`, `docker/docker-compose.design-b.yml`).

### B) “Job work” definition (critical for interpreting throughput)
4. Worker execution is simulated deterministic work: it waits (`stop_event.wait`) for planned runtime and then reports outcome with synthetic output bytes/checksum; no real payload compute pipeline is implemented in v1.
5. In current runtime behavior, effective job runtime is fixed at about `120 ms` for normal runs because coordinator `FetchWork` currently returns `spec.work_duration_ms=0`, and worker defaults `<=0` to `120 ms`. (Worker logic can clamp explicit values to `[20, 2000]` if present, but that value is not propagated in current fetch path.)
6. `DONE` vs `FAILED`: worker reports `FAILED` only when `job_type` contains `"force-fail"` (deterministic failure trigger); otherwise it reports success (`DONE`). Retries are implemented for transient RPC failures in worker `ReportWorkOutcome` and client-side RPC adapter retries (retryable codes), with `SubmitJob` retries only when `client_request_id` is non-empty.

### C) Worker-loop fairness (ensure designs are truly comparable)
7. In implemented code, Design A worker execution is a single worker loop (single thread/slot behavior), not a 6-thread/process executor inside one worker process.
8. Yes. In Design B baseline, each of the 6 monolith containers starts one in-process worker loop (`1` slot per node baseline).
9. Queue discipline is FIFO in both designs where queue service logic is used, but global behavior is not identical under load because Design B relies on deterministic owner routing with per-node state and no inter-node forwarding in v1.

### D) Routing semantics in Design B (needs one crisp explanation)
10. `SubmitJob` owner choice: empty `client_request_id` uses round-robin over ordered monolith targets; non-empty `client_request_id` uses deterministic hash-based owner routing.
11. `job_id` is owner-affine in Design B (job IDs are generated so hash(job_id) maps to creator/owner node), so job-scoped calls route deterministically by `job_id`; client-side deterministic routing is used instead of maintaining a mutable owner map.
12. In v1, if the owner node is down, `GetJobStatus`/`GetJobResult`/`CancelJob` to that owner fail (typically transport `UNAVAILABLE`/deadline behavior). There is no inter-node forwarding/failover for job-scoped requests, and per-node in-memory state means data is not recoverable from other nodes in that case.

### E) Results sanity checks (for a tight narrative)
13. Yes. In this dataset, “mean throughput matched under fixed pacing” refers to RPC throughput (successful requests/sec by method), which is equalized by the fixed offered-load/request-mix setup.
14. Partially. Current benchmark artifacts clearly include RPC throughput, latency, non-OK rate, and terminal job throughput. They do not include deep corroborating internals like queue depth, per-service CPU, worker utilization, or time-in-queue in the aggregate outputs, so large-gap root-cause attribution remains inferential unless additional instrumentation is added.
