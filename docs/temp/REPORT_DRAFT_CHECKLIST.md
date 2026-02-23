# Report Draft Checklist (Temporary)

Purpose: drive completion of `docs/temp/report_draft_staging.tex` using repository-backed sources only.

## Ground Rules

- Treat repo specs/proto/results as source of truth.
- Do not rerun the full starter matrix unless explicitly requested.
- Prefer citing concrete artifact files and exact numeric outputs already generated.
- Keep this checklist temporary; delete it after final migration.

## Section-to-Source Map

| Report section | Primary repo sources | What to add |
|---|---|---|
| Introduction | `README.md`, `docs/spec/requirements.md` | project scope, two-design comparison objective, constraints |
| System Design | `docs/spec/architecture.md`, `docs/spec/runtime-config-design-a.md`, `docs/spec/runtime-config-design-b.md` | exact Design A/Design B topology and ownership boundaries |
| Communication Model | `proto/taskqueue_public.proto`, `proto/taskqueue_internal.proto`, `docs/spec/api-contracts.md` | API contract summary with method-level semantics |
| Functional + NFR tables | `docs/spec/requirements.md`, `docs/spec/constants.md` | lock wording to current FR/NFR language |
| Requirement-to-Service mapping | `docs/spec/architecture.md`, `docs/spec/api-contracts.md` | verify each FR maps to authoritative service ownership |
| Evaluation Methodology | `docs/spec/fairness-evaluation.md`, `docs/spec/constants.md` | fairness controls, workload matrix, fixed assumptions |
| Experimental setup values | `results/loadgen/starter_matrix_execution_2026-02-20.log`, local host notes | CPU/RAM/OS/docker versions if captured; else clearly mark as limited/observed |
| Results + figures | `results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_summary.md`, `starter_matrix_method_agg.csv`, `starter_matrix_terminal_agg.csv`, `starter_matrix_ab_delta_primary.csv`, `plots/*.png` | populate findings, tables, and figure captions with actual numbers |
| Trade-off analysis | `docs/spec/architecture.md`, aggregated results files | interpret latency/throughput/operational complexity differences |
| AI tool usage | commit/history notes + your workflow notes | concrete usage, benefits, validation safeguards |
| Conclusion | all above | concise claim set with limitations |

## Execution Plan

- [ ] Phase 1: Replace all `<username>/<repo-name>` and placeholder metadata.
- [ ] Phase 2: Fill architecture/API/requirements sections from spec + proto docs.
- [ ] Phase 3: Fill methodology and fairness controls with locked language from fairness spec.
- [ ] Phase 4: Insert real benchmark results and convert placeholders to real figures/tables.
- [ ] Phase 5: Add interpretation guardrails (fixed pacing, environment bounds, external validity).
- [ ] Phase 6: Fill AI-tool lessons with concrete examples and verification methods.
- [ ] Phase 7: Add reproducibility appendix commands (env, compose, selected checks, artifact paths).
- [ ] Phase 8: LaTeX quality pass (compile cleanly, table widths, figure references, cross-refs).

## Data/Plot Completion Checklist

- [ ] Confirm which existing plots are sufficient for report.
- [ ] If adding plots, generate only from existing CSV artifacts (no new live runs).
- [ ] Ensure every headline metric in prose points to a concrete artifact file.
- [ ] Include at least one latency figure and one terminal-throughput figure.

## Final Quality Checks

- [ ] `rg -n "TODO|todo|<username>|<repo-name>" docs/temp/report_draft_staging.tex` returns no unresolved placeholders.
- [ ] All numeric claims in report are traceable to `results/loadgen/analysis/starter_matrix_2026-02-20/` artifacts.
- [ ] Methods text aligns with `docs/spec/fairness-evaluation.md` and does not imply rerunning full matrix.
- [ ] No statements conflict with proto/service contracts.
- [ ] LaTeX compiles in Overleaf without missing package or reference errors.

## Exit Criteria and Temp Cleanup

Use this when report content is finalized and migrated to your authoritative destination (Overleaf/final report location).

- [ ] Copy finalized report content out of `docs/temp/report_draft_staging.tex` to the final report source.
- [ ] Confirm no active work still depends on temporary files in `docs/temp/`.
- [ ] Delete temporary files:
  - `docs/temp/report_draft_staging.tex`
  - `docs/temp/REPORT_DRAFT_CHECKLIST.md`
- [ ] Remove the temp directory if empty:
  - `rmdir docs/temp`
- [ ] Optional doc hygiene check: ensure no docs still reference temp draft paths unless intentionally retained.

