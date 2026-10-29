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
