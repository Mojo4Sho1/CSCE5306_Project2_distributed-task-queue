# Next Task

**Last updated:** 2026-02-24  
**Owner:** Joe + Codex

## Task summary

Define a repository retention/archival policy for loadgen artifacts, then synchronize docs to that policy.

## Why this task is next

- Cleanup of obsolete report-temp/handoff scratch assets is complete.
- The remaining high-impact repo hygiene decision is whether and when to prune raw per-run starter-matrix directories.
- Without an explicit policy, future cleanup may accidentally remove reproducibility-critical artifacts.

## Scope (in)

- Decide retention class for:
  - `results/loadgen/analysis/starter_matrix_2026-02-20/` (canonical evidence package)
  - `results/loadgen/design_a_s_*/` and `results/loadgen/design_b_s_*/` (raw per-run outputs)
  - Related scenario files in `scripts/loadgen/scenarios/` used for reproducibility/demo.
- Record policy and rationale in handoff/spec docs.
- If pruning is approved, produce an explicit target list and verification scan before deletion.

## Scope (out)

- Runtime behavior changes.
- Proto/API contract changes.
- Any benchmark re-runs.

## Dependencies / prerequisites

- Existing reproducibility guidance: `docs/handoff/STARTER_MATRIX_REPRODUCIBILITY.md`
- Existing evidence index: `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md`

## Implementation notes

- Preserve reproducibility first; do not delete artifacts without a written policy decision.
- Keep canonical evidence index and aggregate tables/plots intact.
- If uncertain, defer deletion and document rationale.

## Subtasks

- [ ] Inventory current loadgen artifact classes and sizes.
- [ ] Propose retention tiers (canonical, optional, disposable).
- [ ] Approve/document policy in handoff + spec docs.
- [ ] If approved, execute pruning with explicit verification scans.
- [ ] Re-scan for broken references and update docs.

## Acceptance criteria (definition of done)

- A documented retention policy exists and is linked from handoff docs.
- Canonical evidence artifacts are explicitly protected.
- Any pruned artifacts are listed and validated with post-delete scans.
- No documentation pointers remain to removed artifacts.

## Verification checklist

- [ ] `rg -n "starter_matrix_2026-02-20|design_a_s_|design_b_s_" README.md docs scripts tests results`
- [ ] `find results/loadgen -maxdepth 2 -type d | sort`
- [ ] `git status --short` shows only intentional policy/doc (and optional pruning) changes.

## Risks / rollback notes

- Over-pruning can break reproducibility and make evidence audits harder.
- Under-pruning can keep repository size/noise higher than needed.
- If a deletion decision is later reversed, restore artifacts from VCS history or archived bundle.
