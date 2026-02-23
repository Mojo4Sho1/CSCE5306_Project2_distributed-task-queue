# Starter Matrix Reproducibility Runbook

**Last updated:** 2026-02-23  
**Purpose:** rerun a minimal A/B starter pair, regenerate aggregates, and refresh notebook outputs without rerunning the full matrix.

## Preconditions

- Run commands from repo root.
- Use conda env `grpc`.
- Do not run Design A and Design B compose stacks at the same time.

## 1) Rerun One Design A Starter Scenario

Start Design A:

```bash
docker compose -f docker/docker-compose.design-a.yml up --build -d
docker compose -f docker/docker-compose.design-a.yml ps
```

Execute one starter scenario (example: `design_a_s_low_balanced`):

```bash
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py \
  --scenario scripts/loadgen/scenarios/starter_matrix/design_a_s_low_balanced.json \
  --output-dir results/loadgen \
  --live-traffic \
  --precheck-health
```

Stop Design A:

```bash
docker compose -f docker/docker-compose.design-a.yml down --remove-orphans
```

## 2) Rerun One Design B Starter Scenario

Start Design B:

```bash
docker compose -f docker/docker-compose.design-b.yml up --build -d
docker compose -f docker/docker-compose.design-b.yml ps
```

Execute one starter scenario (example: `design_b_s_low_balanced`):

```bash
conda run -n grpc python scripts/loadgen/run_benchmark_scaffold.py \
  --scenario scripts/loadgen/scenarios/starter_matrix/design_b_s_low_balanced.json \
  --output-dir results/loadgen \
  --live-traffic \
  --precheck-health
```

Stop Design B:

```bash
docker compose -f docker/docker-compose.design-b.yml down --remove-orphans
```

## 3) Rerun Aggregation

Regenerate starter-matrix aggregate tables and plots:

```bash
conda run -n grpc python scripts/loadgen/aggregate_starter_matrix.py \
  --results-root results/loadgen \
  --output-dir results/loadgen/analysis/starter_matrix_2026-02-20
```

## 4) Refresh Notebook Workflow

Open and rerun notebook cells against updated artifacts:

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

## 5) Required Interpretation Guardrails

Always carry these constraints into report text:

- Starter matrix is fixed-pacing evidence, not absolute max-throughput proof.
- External validity is bounded to the measured environment unless independently replicated.
- Fairness interpretation assumes locked parity controls from `docs/spec/fairness-evaluation.md`:
  - equal total worker slots,
  - deterministic owner routing in Design B,
  - `ListJobs=0%` for primary parity conclusions,
  - shared timing windows and measurement logic.

## 6) Validation Checks

```bash
test -f results/loadgen/starter_matrix_execution_2026-02-20.log
test -f results/loadgen/analysis/starter_matrix_2026-02-20/EVIDENCE_INDEX.md
test -f results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_summary.md
test -f results/loadgen/analysis/starter_matrix_2026-02-20/starter_matrix_ab_delta_primary.csv
test -f results/loadgen/analysis/starter_matrix_2026-02-20/plots/ab_p95_latency_primary_methods.png
test -f notebooks/benchmark_analysis.ipynb
```

## Notes

- This runbook intentionally avoids full-matrix reruns.
- Use `--overwrite` on the loadgen runner only when intentionally replacing an existing deterministic run directory.
