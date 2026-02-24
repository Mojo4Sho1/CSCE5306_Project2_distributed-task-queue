# codex_plot_fix_tasks.md
Goal: Regenerate the two report figures with clean, readable styling for a single-column LaTeX report. Keep the **same output filenames** and update the visuals so we can use **short captions** in the paper (i.e., the plots should not rely on verbose in-figure titles to be understandable).

Target output files (overwrite in-place):
- `ab_p95_latency_primary_methods.png`
- `ab_terminal_throughput_by_scenario.png`

---

## Task 1 — Locate the plot-generation code
1. Find where these two PNGs are generated (likely in `notebooks/benchmark_analysis.ipynb`).
2. Confirm the exact function/cell that writes:
   - `ab_p95_latency_primary_methods.png`
   - `ab_terminal_throughput_by_scenario.png`
3. Ensure the code path used is the one that currently produces the plots included in Overleaf.

---

## Task 2 — Replace long scenario labels with S1–S9
Implement a mapping from the scenario keys currently shown on the x-axis to the report’s scenario IDs:

- `s_low_submit_heavy`     → `S1`
- `s_low_balanced`         → `S2`
- `s_low_poll_heavy`       → `S3`
- `s_medium_submit_heavy`  → `S4`
- `s_medium_balanced`      → `S5`
- `s_medium_poll_heavy`    → `S6`
- `s_high_submit_heavy`    → `S7`
- `s_high_balanced`        → `S8`
- `s_high_poll_heavy`      → `S9`

Requirements:
- Apply this mapping to the **x-tick labels** for both plots.
- Preserve the intended x-order to match the report table (S1..S9 left-to-right). If current order differs, explicitly reorder.
- Ensure tick labels render as just `S1` … `S9` (no prefixes, no long names).

---

## Task 3 — Make plots “report-ready” (readable and compact)
These figures will be included in LaTeX with `\includegraphics[width=\linewidth]{...}`. Update matplotlib styling for readability and to reduce wasted space.

### 3A) Remove/shorten plot titles to reduce vertical space
- **Throughput plot**: remove the overall figure title (e.g., no `suptitle` and no `title`).
- **p95 2×2 plot**:
  - remove any global `suptitle` if present
  - keep **short, simple subplot titles only** (e.g., `SubmitJob`, `GetJobStatus`, `GetJobResult`, `CancelJob`)
  - do **not** include units in subplot titles if axis already conveys them.

### 3B) Use compact axis labeling (avoid repeated text)
- Prefer a single y-axis label per subplot or per figure:
  - For the 2×2 p95 plot, use y-label `p95 latency (ms)` on the left-column subplots only (optional but preferred).
  - For throughput plot, y-label `jobs/s` or `throughput (jobs/s)`.
- x-axis label should be just `Scenario` (or omit if clear and space is tight).

### 3C) Increase readability (fonts, sizes, layout)
Apply to both figures:
- Font sizes (target ranges, adjust if needed for best fit):
  - Axis labels: 12–14
  - Tick labels: 11–12
  - Legend: 11–12
  - Subplot titles (p95 figure): 12–13
- Use a larger figure size **with compact height**:
  - p95 2×2 subplot figure: `figsize` around `(7.0, 5.5)` to `(7.5, 6.0)`
  - throughput bar figure: `figsize` around `(7.0, 3.0)` to `(7.5, 3.5)`
- Use `constrained_layout=True` (preferred) or `tight_layout()` to prevent collisions.
- Set x-tick rotation to **0** (S1–S9 should fit). If overlap occurs, use a small rotation (≤20°).

### 3D) Legend formatting
- Keep legend labels as `A_microservices` and `B_monolith` (or slightly shorter if already present and clear).
- Place legend so it does not cover bars (upper-left is fine if it doesn’t occlude; otherwise outside or best location).
- For the 2×2 plot, keep a single shared legend if it’s currently shared; otherwise ensure per-subplot legends do not clutter.

### 3E) Export quality
- Save at `dpi=300`
- Use `bbox_inches="tight"`

---

## Task 4 — Keep filenames identical and overwrite
- Save outputs using the same filenames:
  - `ab_p95_latency_primary_methods.png`
  - `ab_terminal_throughput_by_scenario.png`
- Overwrite the existing files in the repo results/plots location so Overleaf re-renders without changing LaTeX.

---

## Task 5 — Quick visual sanity check
Before handing back:
- Confirm x-axis shows `S1 S2 ... S9` in order.
- Confirm text is clearly readable in the saved PNGs when viewed at typical PDF zoom.
- Confirm legends still distinguish `A_microservices` vs `B_monolith`.
- Confirm p95 figure retains 2×2 layout and each subplot corresponds to the correct method.
- Confirm no titles are wasting vertical space (throughput plot has no title; p95 plot has short subplot titles only).