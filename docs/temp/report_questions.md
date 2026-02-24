# Report Finalization Questions (for Codex/Repo Agent)

## A) Experiment environment (must be explicit)
1. Were all containers **and** the load generator running on **one machine**, or across **multiple machines**?
2. What are the exact machine specs used for the benchmark runs (CPU model, core/thread count, RAM, OS)?
3. What Docker and docker-compose (or Docker Compose plugin) versions were used?
4. Were any **CPU/memory limits** (or reservations) configured for containers? If yes, what were they?

## B) “Job work” definition (critical for interpreting throughput)
5. What does a worker actually execute for each job (e.g., fixed sleep, CPU loop, payload processing, etc.)?
6. Is job runtime **fixed or variable**? If fixed, what is the approximate duration? If variable, what is the distribution or range?
7. What causes a job to end as **DONE** vs **FAILED**? Are retries implemented anywhere?

## C) Worker-slot fairness (ensure designs are truly comparable)
8. In Design A (microservices): the “1 worker container × 6 slots” — are those slots implemented as threads, async tasks, processes, or something else?
9. In Design B (monolith-per-node): do the 6 monolith containers each run their own worker execution loop with exactly **1 slot**?
10. Do Design A and Design B use the same queueing policy (FIFO/priority), dispatch logic, and backpressure behavior under load?

## D) Routing semantics in Design B (needs one crisp explanation)
11. How is the **owner node** chosen on job submission in Design B (round-robin, hash, key-based routing, etc.)?
12. Does the **job_id** encode/enable deterministic owner routing for status/result/cancel, or does the client maintain a map?
13. What happens in v1 if the owner node is down when a client calls GetJobStatus / GetJobResult / CancelJob?

## E) Results sanity checks (for a tight narrative)
14. When the report says “mean throughput is matched under fixed pacing,” does that refer to **RPC throughput (requests/sec)** rather than **terminal job throughput (jobs/sec)**?
15. For scenarios with large A/B gaps (e.g., `high_submit_heavy`), do logs/metrics capture any corroborating signal (queue depth, worker utilization, time-in-queue, per-service CPU, retries/timeouts)?