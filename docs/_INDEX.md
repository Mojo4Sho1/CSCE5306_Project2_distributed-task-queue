# Documentation Index

This file is the controlling documentation entry point for this repository.

## Purpose

Use this index to quickly locate:
- authoritative behavior and contract specs,
- implementation handoff status,
- and evaluation/reporting references.

---

## Recommended Reading Order

When starting a new work session, read in this order:

1. **`docs/_INDEX.md`**  
   Documentation governance, authority hierarchy, and navigation.
2. **`README.md`**  
   Project overview, quickstart, and repo map.
3. **`docs/handoff/CURRENT_STATUS.md`**  
   What is implemented now, what is passing, and what is next.
4. **`docs/handoff/NEXT_TASK.md`**  
   Single next target and acceptance criteria.
5. **`docs/spec/*.md`**  
   Locked v1 contracts (architecture, API semantics, lifecycle, runtime, errors, fairness, constants, governance).
6. **`proto/*.proto`**  
   Message and service shape authority.

---

## Documentation Governance

1. This file (`docs/_INDEX.md`) controls documentation navigation and authority interpretation.
2. If behavior/contracts/config change, docs must be updated in the same change set.
3. If docs and code diverge, record and reconcile explicitly as documentation/code drift.
4. Do not silently reinterpret locked semantics.

---

## Documentation Authority Hierarchy

If two sources conflict, use this precedence:

1. **Proto definitions** (`proto/taskqueue_public.proto`, `proto/taskqueue_internal.proto`)  
   Source of truth for RPC/message shape and names.
2. **Spec docs** (`docs/spec/*`)  
   Source of truth for runtime semantics and behavior contracts.
3. **Code + docstrings**  
   Implementation details and local invariants.
4. **README**  
   Orientation and navigation.

---

## Docs Map

## Core
- **`docs/_INDEX.md`** *(this file)*  
  Navigation, governance, and authority model.
- **`README.md`**  
  Project overview, quickstart, and links to authoritative docs (including the practical A/B evaluation execution plan).
- **`notebooks/benchmark_analysis.ipynb`**  
  Starter notebook for loading benchmark artifacts and generating A/B comparison plots.
- **`tests/_TEST_INDEX.md`**  
  Test taxonomy and canonical validation command matrix.
- **`scripts/_SCRIPT_INDEX.md`**  
  Script taxonomy and purpose map for canonical manual/dev/loadgen tooling.

## Handoff
- **`docs/handoff/CURRENT_STATUS.md`**  
  Current implementation snapshot:
  - completed items,
  - passing checks,
  - known gaps/blockers,
  - immediate next target.
- **`docs/handoff/NEXT_TASK.md`**  
  Exact next implementation task and acceptance criteria.
- **`docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md`**  
  Minimal rerun/aggregation/notebook workflow for starter-matrix reproducibility.

## Benchmark Evidence (Completed Starter Matrix)
- **`results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`**  
  Canonical index for starter-matrix artifacts:
  - execution log pointer,
  - per-run artifact locations,
  - aggregate CSV tables,
  - primary plots,
  - interpretation guardrails.

## Temporary Planning
- **`docs/temp/`**  
  Optional non-authoritative planning/checklist artifacts used during active implementation transitions.  
  This directory may be empty between milestones; any files added here should be removed once their trigger conditions are satisfied.
- **`docs/temp/REPORT_DRAFT_CHECKLIST.md`** *(temporary)*  
  Active checklist for staged report-draft completion; use for phase-by-phase execution tracking during handoff.
- **`docs/temp/report_draft_staging.tex`** *(temporary)*  
  Non-authoritative staging draft for report content before migration to final report destination.

## Spec (authoritative v1 semantics)
- **`docs/spec/architecture.md`**  
  Service boundaries, ownership, mutation authority, and invariants.
- **`docs/spec/api-contracts.md`**  
  Public/internal RPC method semantics and caller-to-method matrix.
- **`docs/spec/state-machine.md`**  
  Job lifecycle, allowed transitions, race handling, cancellation behavior.
- **`docs/spec/runtime-config.md`**  
  Runtime configuration entrypoint/index for design-specific runtime contracts.
- **`docs/spec/runtime-config-design-a.md`**  
  Design A ports, env vars, startup/readiness, healthchecks, endpoint map.
- **`docs/spec/runtime-config-design-b.md`**  
  Design B baseline scaffold runtime topology, entrypoint wiring, and health visibility contract.
- **`docs/spec/error-idempotency.md`**  
  gRPC status policy, soft outcomes, idempotency matrix, retry/backoff defaults.
- **`docs/spec/fairness-evaluation.md`**  
  A/B fairness constraints, routing rules, workload controls, starter scenario matrix, and reporting scope.
- **`docs/spec/constants.md`**  
  Locked constants (timeouts, caps, defaults, limits).
- **`docs/spec/requirements.md`**  
  Functional and non-functional requirements.
- **`docs/spec/governance.md`**  
  Phase decisions, freeze gates, ambiguity lock register, and change control.

---

## Current Design Lock Snapshot (v1)

- System: **Distributed Task Queue**
- Communication: **gRPC + Protocol Buffers**
- Architectures:
  - **Design A:** Microservices (6 functional nodes)
  - **Design B:** Monolith-per-node (6 nodes)
- Storage: **in-memory**
- Processing: **at-least-once**
- Cancellation:
  - queued cancel expected,
  - running cancel best-effort, non-preemptive.
- Load generator is evaluation tooling and not counted as a functional node.

---

## Session Continuity Checklist

At the start of each implementation session:

1. Read `docs/handoff/CURRENT_STATUS.md`.
2. Read `docs/handoff/NEXT_TASK.md`.
3. Check relevant spec docs for affected behavior.
4. Implement with spec/doc updates in the same change set when behavior changes.

## Execution Environment Requirement

- Use the conda environment `grpc` for running project code/tests that import runtime dependencies (especially `grpcio`).
- Prefer explicit invocation to avoid shell-activation drift:
  - `conda run -n grpc python <script.py>`
  - `conda run -n grpc python -m unittest <test_path.py>`
- Rationale: default/base Python in local setups may not include required runtime deps, causing false failures.

---

## Update Rules

When changing any of the following, update docs immediately in the same commit:
- RPC behavior or semantics,
- env vars/defaults,
- startup or healthcheck behavior,
- ownership boundaries,
- fairness/evaluation constraints,
- design locks, assumptions, or frozen decisions.

---

## Report / Presentation Traceability

Use these docs as source material for final deliverables:
- **System design:** `docs/spec/architecture.md`
- **Communication model + API:** `docs/spec/api-contracts.md` + `proto/*`
- **Evaluation methodology:** `docs/spec/fairness-evaluation.md`
- **Performance/scalability analysis:** `results/` + report figures
- **Starter matrix evidence package:** `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`
- **Starter matrix reproducibility commands:** `docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md`
- **AI-tool lessons learned:** add notes during implementation and summarize in final report

---

## Status Fields Template for `CURRENT_STATUS.md`

Use this structure for consistent handoffs:

- **Current focus:**  
- **Completed in current focus:**  
- **Passing checks:**  
- **Known gaps/blockers:**  
- **Next task (single target):**  
- **Definition of done for next task:**  

---
