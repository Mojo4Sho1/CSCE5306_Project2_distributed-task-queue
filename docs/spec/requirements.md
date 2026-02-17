# Requirements Specification (v1)

**Status:** Locked for v1  
**Freeze baseline:** 2026-02-10

This document captures functional and non-functional requirements for the Distributed Task Queue project.

---

## 1) Functional Requirements

1. **FR-1 SubmitJob:** Accept a job request and return a unique `job_id`.
2. **FR-2 GetJobStatus:** Return the current state of a job.
3. **FR-3 GetJobResult:** Return job output after completion.
4. **FR-4 CancelJob:** Cancel pending jobs (best-effort for running jobs).
5. **FR-5 ListJobs:** List jobs with filtering/pagination support.
6. **FR-6 WorkerHeartbeat / FetchWork:** Support worker liveness and work retrieval.

### FR-6 scope clarification
FR-6 is an internal functional requirement (worker/coordinator control plane) in Design A.  
FR-6 is not part of the client-facing equivalence surface between Design A and Design B.

---

## 2) Non-Functional Requirements

1. **NFR-1 API Contract Consistency:**  
   Both architectures expose equivalent client-facing gRPC APIs and status semantics.
2. **NFR-2 Scalability Testability:**  
   The system supports controlled load tests across multiple concurrency levels without code changes.
3. **NFR-3 Performance Observability:**  
   Evaluation records throughput (req/s, jobs/s), latency percentiles (p50/p95/p99), and end-to-end completion time.
4. **NFR-4 Reproducibility:**  
   A clean environment reproduces deployment and benchmark execution using documented Compose/runtime scripts.
5. **NFR-5 Baseline Fault Handling:**  
   Coordinator tracks worker heartbeats and marks workers unavailable after timeout; queue operations do not silently drop queued jobs.
6. **NFR-6 Capacity Fairness:**  
   Both designs run with the same total worker-slot budget during comparisons.

---

## 3) Cross-References

- Architecture and ownership: `docs/spec/architecture.md`
- API semantics and schema: `docs/spec/api-contracts.md`
- Lifecycle transitions: `docs/spec/state-machine.md`
- Runtime contract: `docs/spec/runtime-config.md`
- Error/idempotency/retry: `docs/spec/error-idempotency.md`
- Fairness/evaluation protocol: `docs/spec/fairness-evaluation.md`
- Locked constants: `docs/spec/constants.md`
