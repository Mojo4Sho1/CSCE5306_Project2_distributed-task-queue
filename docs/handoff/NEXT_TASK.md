# Next Task

**Last updated:** 2026-02-23  
**Owner:** Joe + Codex

## Task summary

Create a final evidence-and-reproducibility handoff for the completed starter fairness matrix so report writing can proceed from one canonical source of truth.

## Why this task is next

- Starter-matrix execution and aggregation are complete.
- Post-matrix cleanup is complete and canonical paths are now normalized.
- Remaining milestone work is packaging benchmark evidence and rerun instructions for report/presentation use.

## Scope (in)

- Create a benchmark evidence index document under:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/`
- Include explicit links/paths for:
  - execution log,
  - per-run artifacts,
  - aggregate CSV outputs,
  - primary plots,
  - notebook entrypoint.
- Add reproducibility runbook documentation covering:
  - one Design A + one Design B starter scenario rerun,
  - aggregation rerun,
  - notebook refresh workflow.
- Add interpretation guardrails for this dataset:
  - fixed-pacing throughput caveat,
  - environment-bounded external validity,
  - required parity assumptions from fairness spec.
- Update references in:
  - `README.md`
  - `docs/_INDEX.md`
  - `docs/handoff/CURRENT_STATUS.md`
  - `docs/handoff/NEXT_TASK.md`

## Scope (out)

- New benchmark scenario authoring.
- Additional live benchmark execution.
- Service/proto/runtime behavior changes.
- Fairness contract changes.

## Dependencies / prerequisites

- Existing completed outputs in:
  - `results/loadgen/starter_matrix_execution_2026-02-20.log`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/`
- Existing notebook:
  - `notebooks/benchmark_analysis.ipynb`
- Active temporary report workspace (non-authoritative, downstream consumer of this task):
  - `docs/temp/report_draft_staging.tex`
  - `docs/temp/REPORT_DRAFT_CHECKLIST.md`

## Implementation notes

- Keep this task documentation-only unless a broken reference requires a minimal non-behavioral fix.
- Prefer relative repo paths that are copy-paste runnable.
- Keep all benchmark claims traceable to concrete artifact files.
- Sequencing for clean handoff:
  - complete this evidence/reproducibility packaging task first,
  - then execute report-draft checklist phases against `docs/temp/report_draft_staging.tex`.
- Do not rerun full starter matrix for this task.

## Subtasks

- [ ] Draft `EVIDENCE_INDEX.md` in `results/loadgen/analysis/starter_matrix_2026-02-20/`.
- [ ] Add reproducibility runbook doc in `docs/` (or `docs/handoff/` if preferred) with exact commands.
- [ ] Sync README/index/handoff links to these new docs.
- [ ] Validate all referenced artifact paths exist.

## Acceptance criteria (definition of done)

- A single evidence index doc exists and links all primary benchmark artifacts.
- Reproducibility commands execute from documented paths without ambiguity.
- Guardrails/limitations are explicitly documented beside headline benchmark signals.
- README/index/handoff docs point to the new evidence/runbook docs.
- `docs/temp/REPORT_DRAFT_CHECKLIST.md` can reference these outputs directly without path ambiguity.
- Handoff status reflects completion and advances `NEXT_TASK.md` again.

## Verification checklist

- [ ] `test -f results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`
- [ ] `test -f results/loadgen/starter_matrix_execution_2026-02-20.log`
- [ ] `test -f results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_summary.md`
- [ ] `test -f results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_ab_delta_primary.csv`
- [ ] `test -f results/loadgen/analysis/starter_matrix_2026-02-20/plots/ab_p95_latency_primary_methods.png`
- [ ] `test -f notebooks/benchmark_analysis.ipynb`
- [ ] `rg -n "EVIDENCE_INDEX|reproducibility|starter_matrix_2026-02-20" README.md docs`

## Risks / rollback notes

- Missing or stale artifact references can weaken report traceability.
- Overstating benchmark conclusions without caveats can create interpretation errors.
- If any listed artifact is absent, document the gap explicitly before report consumption.
- Do not delete temporary report workspace files until report content is migrated and temp cleanup criteria are satisfied in `docs/temp/REPORT_DRAFT_CHECKLIST.md`.
