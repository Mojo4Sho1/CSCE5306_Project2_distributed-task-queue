# Current Status

**Last updated:** 2026-02-23  
**Owner:** Joe + Codex

## Current focus

Report drafting phases 6-7 are complete in `docs/temp/report_draft_staging.tex` (AI-tool lessons + reproducibility appendix-style content).

## Completed in current focus

- Replaced all TODO placeholders in `Lessons Learned from AI Tool Usage` with concrete project-specific content:
  - how AI assistance was used in code/docs workflow,
  - concrete iteration-speed and boilerplate-reduction benefits,
  - explicit validation safeguards (contract checks, tests, artifact traceability).
- Added `Reproducibility Appendix (Concise)` to `docs/temp/report_draft_staging.tex` with:
  - minimal Design A/Design B rerun command flow,
  - aggregation command,
  - artifact pointers to evidence index/tables/plots/run log,
  - fairness guardrail reminder tied to `docs/spec/fairness-evaluation.md`.
- Updated `docs/temp/REPORT_DRAFT_CHECKLIST.md`:
  - phases 6 and 7 marked complete,
  - placeholder/method-alignment checks synchronized.
- Ran placeholder scan on the draft and confirmed no residual `TODO`/placeholder markers remain.

## Passing checks

- Placeholder scan is clean:
  - `rg -n "TODO|todo|<username>|<repo-name>" docs/temp/report_draft_staging.tex` (no matches)
- Reproducibility references are present:
  - `rg -n "STARTER_MATRIX_REPRODUCIBILITY|EVIDENCE_INDEX|reproduc" docs/temp/report_draft_staging.tex`
- Checklist phase markers are updated:
  - `rg -n "Phase 6|Phase 7" docs/temp/REPORT_DRAFT_CHECKLIST.md`

## Known gaps/blockers

- Phase 8 quality pass remains:
  - compile the draft in final report environment (Overleaf/local LaTeX),
  - resolve any table/figure/reference polish issues.
- Final migration and cleanup remain:
  - move finalized report content to final destination,
  - remove temporary draft/checklist files once migration is confirmed.
- Overleaf image import wiring is intentionally not performed in-repo; only artifact paths and analysis prose are provided.

## Repo cleanup candidates (review only; do not delete yet)

The items below are candidates that may be removable after verification. This section is an audit list only; no deletions have been executed.

### Candidate 1: `scripts/SMOKE_INDEX.md` (high confidence)

- Why it may be removed:
  - File is now only a redirect stub ("Moved: Smoke Index") pointing to `tests/_TEST_INDEX.md` and `scripts/_SCRIPT_INDEX.md`.
  - No in-repo references to `scripts/SMOKE_INDEX.md` were found outside the file itself.
- Safe removal steps:
  1. Verify no references remain:
     - `rg -n "scripts/SMOKE_INDEX.md|SMOKE_INDEX.md" README.md docs scripts tests results`
  2. Delete `scripts/SMOKE_INDEX.md`.
  3. Re-run docs link/reference scan:
     - `rg -n "_TEST_INDEX.md|_SCRIPT_INDEX.md|SMOKE_INDEX.md" README.md docs scripts tests`

### Candidate 2: legacy report-question scratch files in `docs/temp/` (high confidence)

- Files:
  - `docs/temp/report_questions.md`
  - `docs/temp/additional_report_questions.md`
  - `docs/temp/additional_report_questions_v2.md`
- Why they may be removed:
  - They appear to be one-off planning/Q&A scratch artifacts.
  - No in-repo references were found to these paths outside the files themselves.
  - The active handoff/report workflow currently references `report_draft_staging.tex` and `REPORT_DRAFT_CHECKLIST.md`, not these three files.
- Safe removal steps:
  1. Confirm zero inbound references:
     - `rg -n "report_questions.md|additional_report_questions.md|additional_report_questions_v2.md" README.md docs scripts tests results`
  2. Delete the three files.
  3. Re-run docs temp scan to confirm only active temp files remain:
     - `find docs/temp -maxdepth 1 -type f | sort`

### Candidate 3: report staging files after migration is complete (already planned; high confidence)

- Files:
  - `docs/temp/report_draft_staging.tex`
  - `docs/temp/REPORT_DRAFT_CHECKLIST.md`
- Why they may be removed:
  - These are explicitly marked temporary/non-authoritative in docs and handoff.
  - Cleanup is already defined in current handoff criteria and should happen only after migration to final report destination is confirmed.
- Safe removal steps:
  1. Complete phase 8 compile/polish and migration to final report location.
  2. Update references in:
     - `docs/_INDEX.md`
     - `docs/handoff/CURRENT_STATUS.md`
     - `docs/handoff/NEXT_TASK.md`
  3. Confirm no lingering references:
     - `rg -n "docs/temp/report_draft_staging.tex|docs/temp/REPORT_DRAFT_CHECKLIST.md" README.md docs scripts tests`
  4. Delete the two files (and remove `docs/temp/` only if empty and intended).

### Candidate 4: non-canonical one-off loadgen scenario/result sets (conditional; medium confidence)

- Potential files/directories:
  - Scenario JSONs:
    - `scripts/loadgen/scenarios/design_a_live_smoke_short.json`
    - `scripts/loadgen/scenarios/design_b_balanced_baseline.json`
    - `scripts/loadgen/scenarios/design_a_balanced_seed5306.json`
    - `scripts/loadgen/scenarios/design_a_balanced_seed5307.json`
    - `scripts/loadgen/scenarios/design_b_balanced_seed5306.json`
    - `scripts/loadgen/scenarios/design_b_balanced_seed5307.json`
  - Matching result roots:
    - `results/loadgen/design_a_live_smoke_short/`
    - `results/loadgen/design_a_balanced_seed5306/`
    - `results/loadgen/design_a_balanced_seed5307/`
    - `results/loadgen/design_b_balanced_seed5306/`
    - `results/loadgen/design_b_balanced_seed5307/`
- Why they may be removable:
  - Starter-matrix reproducibility/runbook and evidence package focus on `scripts/loadgen/scenarios/starter_matrix/*` and `results/loadgen/analysis/starter_matrix_2026-02-20/`.
  - These one-off scenarios are convenience/demo assets rather than required starter-matrix artifacts.
- Why removal is conditional:
  - README and `scripts/_SCRIPT_INDEX.md` currently document these scenario commands, so deleting them requires documentation pruning.
  - They may still be useful for quick demo/smoke verification and should be removed only if that workflow is intentionally retired.
- Safe removal steps:
  1. Decide whether quick demo/smoke scenarios are being retired or kept.
  2. If retiring, update docs first:
     - `README.md`
     - `scripts/_SCRIPT_INDEX.md`
  3. Confirm references before delete:
     - `rg -n "design_a_live_smoke_short|design_[ab]_balanced_seed5306|design_[ab]_balanced_seed5307|design_b_balanced_baseline" README.md docs scripts tests results`
  4. Delete scenario JSONs and matching result directories only after docs are clean.
  5. Re-run reference scan to ensure no broken pointers remain.

### Candidate 5: pruning raw per-run starter-matrix directories after archival (conditional; medium confidence, high risk)

- Potential directories:
  - `results/loadgen/design_a_s_*/`
  - `results/loadgen/design_b_s_*/`
- Why they may be removable:
  - If repository size must be reduced, primary reporting outputs already exist in:
    - `results/loadgen/analysis/starter_matrix_2026-02-20/`
    - `results/loadgen/starter_matrix_execution_2026-02-20.log`
- Why removal is high risk:
  - `EVIDENCE_INDEX.md` defines per-run raw artifacts as part of canonical evidence.
  - Removing raw per-run artifacts weakens traceability and prevents re-aggregation/re-audit from committed raw rows.
- Safe removal steps (only if an explicit archive policy is approved):
  1. Archive `results/loadgen/design_a_s_*/` and `results/loadgen/design_b_s_*/` outside repo (or to release artifact storage).
  2. Update `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md` to point to the archive location and explain retention policy.
  3. Update `docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md` to reflect archived raw-data location.
  4. Only then remove local raw directories from repo.

## Active coordination notes

- The report draft now covers phases 1-7 with evidence-backed narrative and reproducibility guidance.
- Remaining work is now primarily publication polish and migration mechanics.
- Temporary drafting workspace remains non-authoritative:
  - `docs/temp/report_draft_staging.tex`
  - `docs/temp/REPORT_DRAFT_CHECKLIST.md`

## Next task (single target)

Complete phase 8 and migration: run LaTeX quality pass, migrate finalized content to the final report destination, and retire temporary staging files.

## Definition of done for next task

- Draft compiles cleanly in the final report toolchain (or any compile issues are resolved and documented).
- Figure/table references and formatting are publication-ready.
- Final report destination contains migrated content from `docs/temp/report_draft_staging.tex`.
- Temporary checklist/draft files are removed only after migration confirmation.
