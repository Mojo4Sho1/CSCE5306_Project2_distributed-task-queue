# Next Task

**Last updated:** 2026-02-23  
**Owner:** Joe + Codex

## Task summary

Populate `docs/temp/report_draft_staging.tex` with authoritative, traceable technical content (architecture, methodology, and benchmark results) using the completed starter-matrix evidence package.

## Why this task is next

- Benchmark evidence packaging and reproducibility documentation are complete.
- Remaining high-value milestone work is turning existing validated artifacts into a near-final report draft.
- No additional benchmark execution is required to complete the core report narrative.

## Scope (in)

- Replace report placeholders for:
  - repository metadata and artifact references,
  - system architecture + communication model summary,
  - functional/non-functional requirement tables (aligned to spec wording),
  - evaluation methodology and fairness controls.
- Insert benchmark-backed results content from:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_summary.md`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_method_agg.csv`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_terminal_agg.csv`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_ab_delta_primary.csv`
- Add explicit interpretation guardrails in report prose:
  - fixed-pacing throughput caveat,
  - environment-bounded external validity,
  - locked parity assumptions from fairness spec.
- Keep `docs/temp/REPORT_DRAFT_CHECKLIST.md` synchronized as progress is made.

## Scope (out)

- New benchmark scenario authoring or full starter-matrix reruns.
- Service/proto/runtime behavior changes.
- Final temp-file deletion/cleanup (defer until report migration is complete).

## Dependencies / prerequisites

- Evidence index:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`
- Reproducibility runbook:
  - `docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md`
- Report draft workspace:
  - `docs/temp/report_draft_staging.tex`
  - `docs/temp/REPORT_DRAFT_CHECKLIST.md`
- Authoritative specs/proto:
  - `docs/spec/*.md`
  - `proto/*.proto`

## Implementation notes

- Keep claims traceable to concrete artifact files/paths.
- Preserve temporary-draft status of `docs/temp/` files.
- Prefer incremental checklist-driven completion (phases 1-5 first, then remaining phases).

## Subtasks

- [ ] Phase 1-2: replace placeholders + fill architecture/API/requirements sections in `report_draft_staging.tex`.
- [ ] Phase 3: fill methodology/fairness controls with locked wording from `docs/spec/fairness-evaluation.md`.
- [ ] Phase 4-5: insert real results figures/tables and interpretation guardrails using evidence index artifacts.
- [ ] Update `docs/temp/REPORT_DRAFT_CHECKLIST.md` progress markers as each phase completes.
- [ ] Run placeholder/traceability checks and document any intentionally deferred sections.

## Acceptance criteria (definition of done)

- Report draft includes concrete repository metadata and no `<username>/<repo-name>` placeholders.
- Core technical sections (system design, communication model, requirements, methodology, results) are populated with authoritative content.
- All numeric claims and figures in populated sections are traceable to `results/loadgen/analysis/starter_matrix_2026-02-20/` artifacts.
- Guardrails and parity assumptions are explicit in methodology/results interpretation.
- Checklist reflects completed phases and remaining deferred work clearly.

## Verification checklist

- [ ] `rg -n "<username>|<repo-name>" docs/temp/report_draft_staging.tex` returns no matches.
- [ ] `rg -n "TODO|todo" docs/temp/report_draft_staging.tex` returns only intentionally deferred sections.
- [ ] `rg -n "EVIDENCE_INDEX|starter_matrix_2026-02-20|STARTER_MATRIX_REPRODUCIBILITY" docs/temp/report_draft_staging.tex docs/temp/REPORT_DRAFT_CHECKLIST.md`
- [ ] `rg -n "fixed-pacing|external validity|ListJobs|owner routing" docs/temp/report_draft_staging.tex`

## Risks / rollback notes

- Untraceable numeric claims can weaken report credibility and should be removed or explicitly marked provisional.
- Overstating external generalization beyond this environment can misrepresent evidence strength.
- If conflicts appear between draft prose and authoritative specs/proto, update draft prose (not specs) and document the correction.
