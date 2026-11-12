# Project evaluation requirements

For energy-aware UAV disaster offloading/scheduling experiments, follow
`PureEdgeSim/uav/EVALUATION_METRICS.md`. Every new algorithm evaluation must report
image deadline violation ratio, whole-system joules per on-time image, completed-image
mean/P95 latency, and UAV battery service lifetime with explicit horizon censoring.
Also retain total/UAV energy, on-time image counts and background DVR. Use paired
seeds/workload hashes and unchanged simulation assumptions for comparisons.
Run the independent verifier and `scripts/offloading_metrics.py`; retain per-scenario
tables. Never count dropped tasks as completed, zero successes as zero J/task, or
horizon survivors as observed battery exhaustion. State unavailable metrics explicitly.

# v2 working rules (from 12/11/2026, package `uav.mec`)

v1 (`uav.offloading`, `uav.scheduling`, `Paper*`, `drl/` campaigns) is frozen at tag `v1-final`.
Do not add experiments to it or change its code; fix only what breaks the build.

1. Gates before campaigns. Do not run a v2 campaign above 100 episodes on a configuration whose
   gates G1-G5 in `docs/v2/CALIBRATION.md` have not passed.
2. One experiment = one config file under `experiments/`, run with `uav.mec.MecRunner`.
   Do not add a new Java `main` or campaign script per experiment.
3. At most one result document per phase in `docs/v2/`. Plans and notes go into commit messages.
4. Write the hypothesis and pass threshold at the top of the config before running it.
5. Independent verification (`scripts/verify_mec.py`) recomputes metrics and physics from traces.
   Its PASS means the bookkeeping matches; never present it as evidence that the model is realistic.
6. Do not change the kernel or locked parameters while comparing algorithms. Bump the config
   version and rerun baselines instead.
7. Before merging into `main`: `mvn -o test` and `python -m unittest discover -s drl -t .` pass.
8. Run outputs go to `target/mec/<config-name>/`; smoke runs to `target/smoke/` (safe to delete).

For v2 the metric conventions above still apply with two changes: the primary energy metric is
**marginal** energy (CPU + TX + RX) per on-time task, reported next to total energy; and v2 has
no background workload, so background DVR is reported as unavailable.
