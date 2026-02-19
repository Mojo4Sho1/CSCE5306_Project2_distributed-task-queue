# Fairness and Evaluation Specification (v1)

**Document path:** `docs/spec/fairness-evaluation.md`  
**Status:** Locked for v1 benchmarking and report analysis  
**Last updated:** 2026-02-17

---

## 1) Purpose

This document defines how Design A (microservices) and Design B (monolith-per-node) are compared fairly.  
It locks the evaluation scope, workload controls, routing policy, and measurement procedure so throughput and latency conclusions are reproducible and defensible.

---

## 2) Compared Designs

## Design A: Microservices (6 functional nodes)
1. Gateway
2. Job
3. Queue
4. Coordinator
5. Worker
6. Result

- Load generator may run separately and is **not** a functional node.
- Public client traffic enters through Gateway only.

## Design B: Monolith-per-node (6 nodes)
- Six identical nodes.
- Each node colocates most/all core functionality in-process.
- Exposes the same client-facing API surface as Design A within v1 parity scope.

---

## 3) API Equivalence Scope

Both designs must expose equivalent client-facing request/response schemas and status semantics for:

- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`
- `ListJobs`

### v1 parity emphasis
Primary parity and performance conclusions are based on:
- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`

`ListJobs` remains available with schema parity in both designs, but in Design B v1 it may be non-global best-effort unless explicit aggregation is added. `ListJobs` is reported as secondary/qualitative.

---

## 4) Fairness Controls (Locked)

## 4.1 Capacity parity
- `TOTAL_WORKER_SLOTS = 6` by default for both designs.
- Design A mapping: 1 Worker container with 6 execution slots.
- Design B mapping: 6 monolith containers with 1 execution slot each.

No benchmark run is valid if total execution capacity differs across designs.

## 4.2 Ingress parity
- Design A: all client load targets Gateway only.
- Design B:
  - `SubmitJob` with empty `client_request_id` uses round-robin across 6 monolith nodes.
  - `SubmitJob` with non-empty `client_request_id` uses deterministic owner routing (see Section 5).

## 4.3 State-coherence routing in Design B
In v1, the client/load generator performs deterministic owner routing for job-scoped reads/writes:
- `GetJobStatus` routed by `job_id`
- `GetJobResult` routed by `job_id`
- `CancelJob` routed by `job_id`

Monolith nodes do not forward job-scoped requests to each other in v1.

## 4.4 Determinism Model (Design A vs Design B)

- Design A does not require owner routing:
  - client traffic enters through Gateway,
  - canonical mutation authorities are centralized by service role (`job`, `queue`, `result`, `coordinator`),
  - determinism comes from single-owner state + locked CAS/idempotency rules.
- Design B requires owner routing:
  - state is distributed across six monolith nodes with per-node in-memory stores,
  - deterministic routing by key is required to preserve submit idempotency and job-scoped read/cancel coherence,
  - this is why Section 5 is correctness-critical in Design B, not just a load-balancing choice.

Operational interpretation for new users/agents:
- If comparing fairness/performance only, follow capacity and workload parity rules.
- If validating semantic parity in Design B, routing correctness is a first-order prerequisite.

## 4.5 Measurement parity
Both designs must use:
- same hardware
- same workload matrix
- same warm-up policy
- same run duration
- same sampling/aggregation logic
- same client measurement implementation

---

## 5) Deterministic Owner Routing (Design B, Locked)

To make routing reproducible across runs/machines:

- Hash function: `SHA-256`
- Input bytes: UTF-8 bytes of routing key
- Owner formula: `owner_index = uint64_be(first_8_bytes(sha256(key))) % N`
- `N`: number of monolith nodes (v1 default `N=6`)
- Node order: fixed, configured ordered list for the run

## Routing keys
- `SubmitJob` with non-empty `client_request_id`: key = `client_request_id`
- `GetJobStatus`, `GetJobResult`, `CancelJob`: key = `job_id`

This routing is mandatory for correctness and idempotency semantics in Design B with per-node in-memory state.

---

## 6) Workload Model

Workloads vary along three axes:

1. **Concurrency** (simultaneous clients/streams)
2. **Job duration** (`work_duration_ms`)
3. **Request mix** (submit/status/result/cancel proportions)

### Example request-mix profiles
- **Submit-heavy:** submit dominant, light polling
- **Poll-heavy:** high status/result polling pressure
- **Balanced:** mixed submit + status + result + occasional cancel

A run is valid only if the same workload profile is executed against both designs.

---

## 7) Run Protocol (Locked)

Each benchmark scenario must follow this sequence:

1. **Environment setup**
   - Deploy selected design (A or B)
   - Verify all required services are healthy
   - Confirm slot budget equals `TOTAL_WORKER_SLOTS`

2. **Warm-up**
   - Run non-recorded traffic for fixed warm-up duration

3. **Measurement window**
   - Record metrics during fixed steady-state duration

4. **Cool-down / flush**
   - Allow in-flight operations to settle if needed

5. **Repeat**
   - Execute multiple repetitions per scenario with identical settings

### Recommended minimum run hygiene
- fixed random seed per scenario
- fixed deadlines/timeouts
- no code/config changes between A/B for same scenario
- separate output files per run

---

## 8) Metrics and Definitions

## 8.1 Throughput
- **RPC throughput:** completed successful RPCs per second, per method
- **Job throughput:** terminal jobs per second (`DONE|FAILED|CANCELED`)

## 8.2 Latency
Compute per-method latency percentiles:
- p50
- p95
- p99

Latency is measured client-side from request send to response receipt (including retries if retrying is part of configured client behavior).

## 8.3 End-to-end completion time
For each accepted job:
- `submit_to_done_ms = terminal_timestamp_ms - accepted_at_ms`

Report distribution (p50/p95/p99) for submit-to-terminal completion time.

## 8.4 Error accounting
Track:
- non-OK gRPC rates by code
- soft outcome frequencies (`result_ready=false`, `already_terminal=true`, etc.)
- anomaly counters (e.g., terminal status without terminal envelope)

---

## 9) Primary vs Secondary Analysis Scope

## Primary (strict parity conclusions)
- `SubmitJob`
- `GetJobStatus`
- `GetJobResult`
- `CancelJob`

Use these for main throughput/latency claims and architecture trade-off conclusions.

## Secondary (qualitative or separately qualified)
- `ListJobs`
- Any scenario relying on non-global `ListJobs` behavior in Design B v1

When reporting `ListJobs`, clearly state non-global best-effort scope in Design B v1.

---

## 10) Data Recording Requirements

Each recorded row should include at least:

- `design` (`A_microservices` or `B_monolith`)
- `scenario_id`
- `run_id`
- `method`
- `start_ts_ms`
- `latency_ms`
- `grpc_code`
- `accepted` (if applicable)
- `result_ready` (if applicable)
- `already_terminal` (if applicable)
- `job_id` (when available and safe to log)
- `concurrency`
- `work_duration_ms`
- `request_mix_profile`
- `total_worker_slots`

Summary artifacts should include:
- percentile tables by method/design/scenario
- throughput tables by method/design/scenario
- error-rate tables by code/design/scenario

---

## 11) Validity Checks and Exclusion Rules

A run is **invalid** and must be rerun if any of the following occur:

1. Capacity mismatch across designs (slot budget differs)
2. Different workload parameters between A/B in same scenario
3. Health/readiness failures during measurement window
4. Incomplete logs or corrupted results file
5. Client routing policy not matching Section 4/5 rules
6. Unintended config drift (timeouts, retries, node count, or deadlines changed)

---

## 12) Reporting Requirements

For each workload axis and profile, report:

1. Throughput vs concurrency
2. Latency (p50/p95/p99) vs concurrency
3. End-to-end completion time distribution
4. Error-rate comparison by gRPC code
5. Brief bottleneck interpretation tied to architecture

Required clarity statements in report/slides:
- `TOTAL_WORKER_SLOTS` equality across designs
- Design B routing policy used by load generator
- `ListJobs` parity scope limitations in v1

---

## 13) Threats to Fairness and Mitigations

## Threat: Different execution capacity
- **Mitigation:** fixed `TOTAL_WORKER_SLOTS`

## Threat: Routing-induced semantic drift in Design B
- **Mitigation:** deterministic owner routing by `client_request_id`/`job_id`

## Threat: Unequal load generation behavior
- **Mitigation:** same load generator binary/config path for both designs

## Threat: Startup transients contaminating measurements
- **Mitigation:** fixed warm-up; only steady-state window recorded

## Threat: Measurement implementation differences
- **Mitigation:** single shared metric collection path and aggregation code

---

## 14) Non-Goals for v1 Evaluation

The fairness comparison does **not** claim:
- durable persistence behavior
- exactly-once guarantees
- consensus behavior
- multi-region performance
- production security overhead comparison

Conclusions are bounded to the defined v1 in-memory, single-environment evaluation model.

---

## 15) Change Control

Any fairness-affecting change requires explicit entry in project change notes:

1. What changed
2. Why change was necessary
3. Expected impact on comparability
4. Whether previous benchmark data remains valid

Examples of fairness-affecting changes:
- worker-slot mapping
- routing algorithm or node order
- retry/deadline defaults
- workload mix definition
- warm-up/measurement duration

---

## 16) Quick Compliance Checklist (Per Scenario)

- [ ] Same hardware/environment
- [ ] Same `TOTAL_WORKER_SLOTS`
- [ ] Same workload profile and duration
- [ ] Correct ingress/routing policy by design
- [ ] Warm-up applied before recording
- [ ] Measurement files complete and parseable
- [ ] Primary parity conclusions limited to locked method set
- [ ] `ListJobs` reported with v1 scope caveat

---

This document is authoritative for benchmark fairness and parity interpretation in v1.
