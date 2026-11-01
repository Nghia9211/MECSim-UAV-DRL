# Sequential study: mobile

Completed and independently verified 1200 episodes, development seeds only.
Provisional architecture timing/random weights. Synthetic deadlines and power; Alibaba CPU proxy. No RL training.
Completed-only latency must be read with DVR; horizon survivors are censored, not observed lifetime exhaustion.

| Policy | Image DVR % | J/on-time image | Mean/P95 s | Background DVR % | Censored/cases |
|---|---:|---:|---:|---:|---|
| ROUND_ROBIN__ALL_UAV__EDF | 10.686 | 1207.080 | 1.527/5.661 | 10.650 | 120/120 |
| ROUND_ROBIN__ALL_UAV__FIFO | 10.937 | 1210.423 | 1.486/5.868 | 10.650 | 120/120 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 10.697 | 1207.232 | 1.523/5.652 | 10.673 | 120/120 |
| ROUND_ROBIN__ALL_UAV__SPT | 10.723 | 1207.334 | 1.500/5.641 | 10.196 | 120/120 |
| ROUND_ROBIN__DELIVERY_AWARE__EDF | 0.034 | 1099.837 | 0.680/0.525 | 10.650 | 120/120 |
| STATIC_FIRST__ALL_UAV__EDF | 11.618 | 961.749 | 1.463/4.380 | 10.650 | 120/120 |
| STATIC_FIRST__ALL_UAV__FIFO | 11.849 | 964.315 | 1.427/3.812 | 10.650 | 120/120 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 11.619 | 961.751 | 1.461/4.326 | 10.650 | 120/120 |
| STATIC_FIRST__ALL_UAV__SPT | 11.661 | 962.037 | 1.440/3.978 | 10.196 | 120/120 |
| STATIC_FIRST__DELIVERY_AWARE__EDF | 0.261 | 852.009 | 1.075/1.850 | 10.650 | 120/120 |

Per-scenario core-metrics-summary.csv and paired-statistics.csv retain load/deadline effects.
Intervals are exploratory, paired by seed; no multiple-testing-adjusted confirmatory significance claim.
queue-diagnostics.csv reports CPU busy fraction over the arrival window and actual multi-ready dispatch opportunities.
Scheduling runtime records measured selection calls, not entire episode time; pure host timings, no deployment claim.

ALL_UAV still falls back to local outside contact. Only its within-selector scheduler comparison has audited identical service trajectories.
DELIVERY_AWARE+EDF changes routing: treat it as a separate arm. STATIC_FIRST chooses ID0 before seeing tasks and is not an optimized placement.
Read delivered DVR/energy separately from compute DVR in CORE_METRICS.md. Layout42 at two scales is not unseen-layout evaluation.
