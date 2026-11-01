# Core offloading + scheduling metrics

Image DVR includes every offered image: drops/rejections/deadline-risk failures remain failures.
Energy efficiency = sum(whole-system J) / sum(on-time images), including background/hover energy. Empty efficiency means no successes.
Latency uses completed images (on-time + late), never dropped tasks. Mean and P95 columns are equal-case means; P95 uses nearest rank per episode, not a pooled percentile.
UAV lifetime is battery-based availability, not network lifetime. Restricted time = min(exhaustion time, horizon); censored survivors have only a lower bound. No extrapolation.
All-case averages mix loads/batteries; consult per-scenario CSV before concluding. These are descriptive results, not significance tests.

| Policy | Image DVR % | J/on-time image | Mean latency s | Mean episode P95 s | Restricted UAV time s | Censored/total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALL_UAV__EDF | 10.192 | 827.873 | 5.812 | 17.869 | 600.000 | 360/360 |
| ALL_UAV__FIFO | 11.671 | 841.620 | 6.255 | 18.794 | 600.000 | 360/360 |
| ALL_UAV__PRIORITY | 10.073 | 826.699 | 5.446 | 17.439 | 600.000 | 360/360 |
| ALL_UAV__SPT | 10.169 | 827.577 | 5.407 | 17.109 | 600.000 | 360/360 |
