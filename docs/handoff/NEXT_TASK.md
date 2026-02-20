# Next Task

**Last updated:** 2026-02-20  
**Owner:** Joe + Codex

## Task summary

Perform strict post-matrix cleanup by removing legacy/deprecated script entrypoints and the temporary pre-loadgen planning doc, then sync all affected documentation in the same change set.

## Why this task is next

- Full starter fairness matrix execution and aggregation are complete as of 2026-02-20.
- Remaining work is repository hygiene and documentation normalization before final report packaging.
- Decision lock from prior handoff explicitly required cleanup as a separate follow-on task.

## Scope (in)

- Remove legacy script directory:
  - `scripts/legacy_smoke/`
- Remove deprecated top-level compatibility wrappers:
  - `scripts/smoke_*_behavior.py`
  - `scripts/smoke_*_skeleton.py`
  - `scripts/smoke_live_stack.py`
  - `scripts/smoke_integration_terminal_path.py`
  - `scripts/smoke_integration_failure_path.py`
  - `scripts/manual_gateway_client.py`
  - `scripts/healthcheck.py`
- Remove temporary planning artifact:
  - `docs/temp/TEMP_PRE_LOADGEN_READINESS.md`
- Update documentation/index references to canonical paths:
  - `README.md`
  - `docs/_INDEX.md`
  - `scripts/_SCRIPT_INDEX.md`
  - `docs/handoff/CURRENT_STATUS.md`
  - `docs/handoff/NEXT_TASK.md` (refresh to next target after cleanup completion)

## Scope (out)

- Any new loadgen features.
- Additional benchmark execution.
- Proto/service behavior changes.
- Fairness/control-lock changes.

## Dependencies / prerequisites

- Confirm no required current workflow still depends on removed wrappers.
- Ensure canonical paths remain:
  - integration probes under `tests/integration/`
  - manual tools under `scripts/manual/`
  - dev utilities under `scripts/dev/`

## Implementation notes

- Execute cleanup in one focused change set to avoid transitional drift.
- Do not remove canonical integration tests in `tests/integration/`.
- If any README or script index examples still point to removed wrappers, replace with canonical paths in the same edit.
- Keep this task strictly cleanup/docs-sync only.

## Acceptance criteria (definition of done)

- All listed legacy/deprecated script paths are removed.
- `docs/temp/TEMP_PRE_LOADGEN_READINESS.md` is removed.
- No authoritative doc/index references removed paths.
- Canonical command examples resolve to retained paths only.
- `docs/handoff/CURRENT_STATUS.md` records cleanup evidence.
- `docs/handoff/NEXT_TASK.md` advances to the next single target after cleanup.

## Verification checklist

- [ ] `rg "scripts/legacy_smoke|scripts/smoke_.*(behavior|skeleton)|scripts/smoke_live_stack.py|scripts/smoke_integration_terminal_path.py|scripts/smoke_integration_failure_path.py|scripts/manual_gateway_client.py|scripts/healthcheck.py" README.md docs scripts tests`
- [ ] `rg --files scripts | sort`
- [ ] `rg --files docs/temp` (should be empty or not include readiness file)
- [ ] Validate canonical smoke/test commands still run from `tests/_TEST_INDEX.md`.
- [ ] Update handoff docs and indexes in same cleanup change set.

## Risks / rollback notes

- Removing wrappers without updating references can break user/demo workflows.
- Cleanup must preserve canonical paths used by current tests and docs.
- If a removed wrapper is still operationally required, restore only with explicit justification and doc note.
