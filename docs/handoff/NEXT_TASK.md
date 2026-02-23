# Next Task

**Last updated:** 2026-02-23  
**Owner:** Joe + Codex

## Task summary

Complete report drafting phases 6-7 in `docs/temp/report_draft_staging.tex`: fill AI-tool usage lessons and add concise reproducibility appendix-style content for final report migration.

## Why this task is next

- Phases 1-5 are complete (metadata, architecture/API/requirements, methodology/fairness, results, and trade-off analysis).
- Remaining substantive content gaps are in AI-tool reflection and reproducibility appendix coverage.
- These sections can be completed entirely from existing repo workflow/history and handoff docs.

## Scope (in)

- Phase 6:
  - Replace all TODOs under `Lessons Learned from AI Tool Usage` with concrete, project-specific content:
    - how AI tooling was used,
    - concrete benefits,
    - limitations and validation safeguards.
- Phase 7:
  - Add concise reproducibility appendix-style content in the draft using:
    - `docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md`
    - `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`
  - Include minimal command flow and artifact-location references suitable for report readers.
- Keep `docs/temp/REPORT_DRAFT_CHECKLIST.md` synchronized.

## Scope (out)

- Phase 8 LaTeX compile/polish pass (unless needed for quick syntax sanity checks only).
- New benchmark execution, scenario authoring, or code/runtime behavior changes.
- Temp-file cleanup/deletion.

## Dependencies / prerequisites

- Draft and checklist:
  - `docs/temp/report_draft_staging.tex`
  - `docs/temp/REPORT_DRAFT_CHECKLIST.md`
- Reproducibility authority:
  - `docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md`
- Evidence authority:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`
- Methodology/fairness authority:
  - `docs/spec/fairness-evaluation.md`

## Implementation notes

- Keep claims concrete and auditably tied to repository workflows/artifacts.
- Avoid generic AI-tool commentary; use actual project examples.
- Keep appendix commands concise and copy-paste runnable.

## Subtasks

- [ ] Phase 6: replace AI-tool section TODOs with project-specific narrative and validation safeguards.
- [ ] Phase 7: add reproducibility appendix-style content with key command flow and artifact pointers.
- [ ] Update `docs/temp/REPORT_DRAFT_CHECKLIST.md` phases 6-7 markers.
- [ ] Run residual TODO scan and ensure only intentionally deferred phase-8 polish items remain.

## Acceptance criteria (definition of done)

- No TODO placeholders remain in the AI-tool section.
- Draft includes clear reproducibility command/artifact pointers aligned with existing runbook/evidence docs.
- Checklist reflects completion of phases 6-7.
- Remaining deferred work is limited to final compile/polish and migration mechanics.

## Verification checklist

- [ ] `rg -n "TODO|todo" docs/temp/report_draft_staging.tex` shows no unresolved TODOs in phases 6-7 sections.
- [ ] `rg -n "STARTER_MATRIX_REPRODUCIBILITY|EVIDENCE_INDEX|reproduc" docs/temp/report_draft_staging.tex`
- [ ] `rg -n "Phase 6|Phase 7" docs/temp/REPORT_DRAFT_CHECKLIST.md`

## Risks / rollback notes

- Generic AI prose without concrete project examples weakens report credibility.
- Reproducibility text that diverges from runbook commands can create operator confusion.
- If section length grows too much, keep concise in main body and move extra detail to appendix later.
