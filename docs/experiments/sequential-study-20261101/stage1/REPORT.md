# Sequential study: hover

Completed and independently verified 1440 episodes, development seeds only.
Provisional architecture timing/random weights. Synthetic deadlines and power; Alibaba CPU proxy. No RL training.
Completed-only latency must be read with DVR; horizon survivors are censored, not observed lifetime exhaustion.

| Policy | Image DVR % | J/on-time image | Mean/P95 s | Background DVR % | Censored/cases |
|---|---:|---:|---:|---:|---|
| ALL_UAV__EDF | 10.192 | 827.873 | 5.812/17.869 | 6.914 | 360/360 |
| ALL_UAV__FIFO | 11.671 | 841.620 | 6.255/18.794 | 6.908 | 360/360 |
| ALL_UAV__PRIORITY | 10.073 | 826.699 | 5.446/17.439 | 7.025 | 360/360 |
| ALL_UAV__SPT | 10.169 | 827.577 | 5.407/17.109 | 6.662 | 360/360 |

Per-scenario core-metrics-summary.csv and paired-statistics.csv retain load/deadline effects.
Intervals are exploratory, paired by seed; no multiple-testing-adjusted confirmatory significance claim.
queue-diagnostics.csv reports CPU busy fraction over the arrival window and actual multi-ready dispatch opportunities.
Scheduling runtime records measured selection calls, not entire episode time; pure host timings, no deployment claim.
