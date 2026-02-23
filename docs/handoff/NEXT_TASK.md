# Next Task

**Last updated:** 2026-02-23  
**Owner:** Joe + Codex

## Task summary

Complete report drafting phase 8 and final migration workflow: perform LaTeX quality/polish pass, migrate finalized content out of temporary staging, and execute temp-file cleanup once migration is confirmed.

## Why this task is next

- Phases 1-7 are now complete in `docs/temp/report_draft_staging.tex`.
- Remaining work is publication readiness (compile/polish) and transitioning from temporary staging to final report destination.
- Keeping migration and cleanup explicit reduces risk of stale duplicate drafts and handoff ambiguity.

## Scope (in)

- Phase 8 quality pass:
  - Compile draft in final report toolchain (Overleaf/local LaTeX) and fix any syntax/formatting issues.
  - Resolve table width, caption consistency, and section cross-reference polish.
  - Confirm figure imports map to the intended files under `results/loadgen/analysis/starter_matrix_2026-02-20/plots/`.
- Final migration:
  - Migrate finalized report content from `docs/temp/report_draft_staging.tex` to final report destination.
  - Keep traceability references intact during migration.
- Temp cleanup and doc sync:
  - Update `docs/temp/REPORT_DRAFT_CHECKLIST.md` exit criteria.
  - Remove temp draft/checklist files only after migration is verified.
  - Synchronize handoff docs to reflect post-migration state.

## Scope (out)

- New benchmark execution, scenario authoring, or code/runtime behavior changes.
- Changes to locked fairness/proto/runtime semantics.

## Dependencies / prerequisites

- Draft + checklist:
  - `docs/temp/report_draft_staging.tex`
  - `docs/temp/REPORT_DRAFT_CHECKLIST.md`
- Evidence artifacts:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`
  - `results/loadgen/analysis/starter_matrix_2026-02-20/plots/`
- Handoff status docs:
  - `docs/handoff/CURRENT_STATUS.md`
  - `docs/handoff/NEXT_TASK.md`
- Final report destination/toolchain (Overleaf or equivalent LaTeX project).

## Implementation notes

- Preserve source-backed wording and numeric values; do not alter benchmark claims during polish-only edits.
- Treat `docs/temp/` files as staging artifacts until migration completes.
- If compile issues require content changes, keep them minimal and non-semantic.

## Subtasks

- [ ] Run phase-8 compile/polish pass on the staged report (syntax, tables, figures, references).
- [ ] Migrate finalized report content to the final report destination.
- [ ] Mark checklist exit criteria progress in `docs/temp/REPORT_DRAFT_CHECKLIST.md`.
- [ ] Remove `docs/temp` draft/checklist only after migration is verified.
- [ ] Update handoff docs (`CURRENT_STATUS.md`, `NEXT_TASK.md`) to point to post-migration follow-up work.

## Acceptance criteria (definition of done)

- Final report compiles cleanly in the target toolchain (or any known residual issue is explicitly documented).
- Content is migrated from temp staging to the final report destination without losing artifact traceability references.
- Checklist reflects phase 8 completion and migration/cleanup state accurately.
- Handoff docs no longer present phases 6-7 as pending.

## Verification checklist

- [ ] LaTeX compile check in final report environment (Overleaf/local).
- [ ] `rg -n "Phase 8" docs/temp/REPORT_DRAFT_CHECKLIST.md`
- [ ] Migration target contains updated sections:
  - AI-tool lessons
  - reproducibility appendix content
  - artifact pointer references
- [ ] If temp cleanup executed: confirm `docs/temp/` removal status is reflected in docs.

## Risks / rollback notes

- Compile/polish edits can unintentionally alter technical meaning; keep semantic drift at zero.
- Migrating to final destination can introduce copy/paste divergence between repo staging and final source.
- Deleting temp files before migration verification can cause loss of working history; cleanup must be last.
