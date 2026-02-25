# Starter Matrix Reproducibility Runbook

**Last updated:** 2026-02-25  
**Purpose:** complement `README.md` benchmark instructions with minimal reproducibility controls, non-destructive rerun guidance, and evidence-validation checks.

## Use This With README

- Primary execution commands live in `README.md` (Path B: benchmark experiment).
- This runbook adds only reproducibility-specific guardrails and validation steps.

## Reproducibility Scope

Use this workflow when you need to:
- rerun a minimal A/B starter pair,
- regenerate aggregate tables/plots,
- refresh notebook outputs,
- and verify evidence integrity.

It is intentionally not a full matrix execution tutorial (README already covers that).

## Guardrails (Required)

- Run commands from repo root.
- Use conda environment `grpc`.
- Do not run Design A and Design B stacks at the same time for benchmark trials.
- Do not overwrite canonical evidence artifacts unless replacement is explicitly intended.
- Avoid `--overwrite` on loadgen runs unless you are intentionally replacing deterministic run directories.

## Minimal Non-Destructive Rerun Pattern

1. Follow README Path B flow, but run only one starter scenario per design (for example `*_s_low_balanced`).
2. Keep outputs under `results/loadgen/` with fresh deterministic run IDs.
3. Regenerate aggregates:

```bash
conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py \
  --results-root results/loadgen \
  --output-dir results/loadgen/analysis/starter_matrix_2026-02-20
```

## Notebook Refresh

```bash
conda run -n grpc jupyter notebook notebooks/benchmark_analysis.ipynb
```

Optional non-interactive execute-in-place flow:

```bash
conda run -n grpc jupyter nbconvert \
  --to notebook \
  --execute \
  --inplace \
  notebooks/benchmark_analysis.ipynb
```

## Required Interpretation Guardrails

Always carry these constraints into report/presentation text:

- Starter matrix is fixed-pacing evidence, not absolute max-throughput proof.
- External validity is bounded to the measured environment unless independently replicated.
- Primary parity interpretation follows locked controls in `docs/spec/fairness-evaluation.md`:
  - equal node count (6 vs 6) with recorded as-run effective worker-loop capacity difference (A=1, B=6),
  - deterministic owner routing in Design B,
  - `ListJobs=0%` for primary parity conclusions,
  - shared timing windows and measurement logic.

## Evidence Validation Checks

```bash
test -f results/loadgen/starter_matrix_execution_2026-02-20.log
test -f results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md
test -f results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_summary.md
test -f results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_ab_delta_primary.csv
test -f results/loadgen/analysis/starter_matrix_2026-02-20/plots/ab_p95_latency_primary_methods.png
test -f notebooks/benchmark_analysis.ipynb
```

## Notes

- If README benchmark commands change, keep this runbook synchronized in the same change set.
- If canonical evidence paths are updated, update this file and `results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md` together.
- Sanity-check outputs from the 2026-02-25 README validation are intentionally non-canonical and live under:
  - `results/loadgen/sanity_readme_2026-02-25/`
  - `results/loadgen/analysis/sanity_readme_2026-02-25/`
