# scenario_mix_questions.md

1) For each starter-matrix request mix (`submit_heavy`, `balanced`, `poll_heavy`), what is the exact per-RPC distribution/weight used by the load generator across:
   - SubmitJob
   - GetJobStatus
   - GetJobResult
   - CancelJob
   - ListJobs (expected disabled in starter matrix)

2) Where in the repo are these mixes defined (exact file paths), and are they shared across all load levels?

3) Does the load generator enforce the mix as:
   - per-request random selection by weight, or
   - a fixed repeating sequence, or
   - per-thread independent selection?

4) Confirm whether poll-heavy intentionally reduces SubmitJob volume relative to polling volume (so terminal jobs/sec is expected to be lower even if the system is healthy).

---

## Answers

1) Starter-matrix per-RPC weights are:

- `submit_heavy`
  - `SubmitJob`: `60`
  - `GetJobStatus`: `20`
  - `GetJobResult`: `15`
  - `CancelJob`: `5`
  - `ListJobs`: `0`
- `balanced`
  - `SubmitJob`: `35`
  - `GetJobStatus`: `30`
  - `GetJobResult`: `25`
  - `CancelJob`: `10`
  - `ListJobs`: `0`
- `poll_heavy`
  - `SubmitJob`: `15`
  - `GetJobStatus`: `45`
  - `GetJobResult`: `35`
  - `CancelJob`: `5`
  - `ListJobs`: `0`

Verified from starter-matrix scenario files under:
- `scripts/loadgen/scenarios/starter_matrix/*.json`

2) Where defined and whether shared across load levels:

- Defined in each scenario JSON under:
  - `request_mix_profile`
  - `request_mix_weights`
- Paths:
  - `scripts/loadgen/scenarios/starter_matrix/design_a_s_*_*.json`
  - `scripts/loadgen/scenarios/starter_matrix/design_b_s_*_*.json`
- They are shared across `low/medium/high` for a given profile and across both designs.
  - Only load-level controls (`concurrency`, `request_rate_rps`) change by low/medium/high.

3) How mix enforcement works:

- It is a deterministic weighted repeating sequence, not per-request random draw.
- Implementation:
  - `common/loadgen_contracts.py` `RequestMixScheduler.__init__`:
    - Builds a method list by repeating each method name `weight` times.
    - Shuffles that list once using phase seed.
  - `common/loadgen_contracts.py` `RequestMixScheduler.next_method`:
    - Returns next item cyclically with wraparound.
- Threading behavior:
  - One shared scheduler is created per phase (`BenchmarkRunner._run_phase`), and worker threads call `next_method()` through a lock.
  - So method selection is globally sequenced across threads (not independently random per thread).

4) Poll-heavy submit-volume intent:

- Yes. `poll_heavy` intentionally lowers `SubmitJob` to `15%` and raises polling (`GetJobStatus` `45%`, `GetJobResult` `35%`).
- Therefore, at the same offered request rate, terminal jobs/sec is expected to be lower than mixes with higher submit share (because fewer new jobs are introduced per unit time).
