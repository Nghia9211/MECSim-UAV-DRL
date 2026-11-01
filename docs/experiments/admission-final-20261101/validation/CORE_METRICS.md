# Core offloading + scheduling metrics

Image DVR includes every offered image: drops/rejections/deadline-risk failures remain failures.
Energy efficiency = sum(whole-system J) / sum(on-time images), including background/hover energy. Empty efficiency means no successes.
Latency uses completed images (on-time + late), never dropped tasks. Mean and P95 columns are equal-case means; P95 uses nearest rank per episode, not a pooled percentile.
UAV lifetime is battery-based availability, not network lifetime. Restricted time = min(exhaustion time, horizon); censored survivors have only a lower bound. No extrapolation.
All-case averages mix loads/batteries; consult per-scenario CSV before concluding. These are descriptive results, not significance tests.

| Policy | Image DVR % | J/on-time image | Mean latency s | Mean episode P95 s | Restricted UAV time s | Censored/total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 5.653 | 1127.808 | 1.459 | 5.156 | 600.000 | 240/240 |
| ROUND_ROBIN__ALL_UAV__EDF | 7.213 | 1195.252 | 1.397 | 4.161 | 600.000 | 240/240 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 6.052 | 1152.396 | 1.553 | 5.492 | 600.000 | 240/240 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 6.460 | 858.319 | 0.962 | 2.277 | 600.000 | 240/240 |
| STATIC_FIRST__ALL_UAV__EDF | 8.329 | 924.739 | 1.096 | 2.703 | 600.000 | 240/240 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 6.857 | 882.017 | 1.184 | 3.854 | 600.000 | 240/240 |

## Mobile delivery and propulsion

Local computation on a disconnected source does NOT deliver a result. Primary image DVR above is compute completion; delivered DVR below counts received on-time results. Return/backhaul delay is currently zero when delivery is possible.
Total/UAV energy includes flight + hover + CPU; flight and hover are NOT added again. ALL_UAV uses current or enabled known-flight contact; outside eligible contact the task runs locally. CPU scheduling can run during flight.

| Policy | Delivered DVR % | J/on-time delivered image | Mean covered images | Mean offloaded images | Flight kJ | Hover kJ | Distance m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 34.242 | 1617.681 | 4.633 | 8.575 | 47.925 | 22.440 | 1597.497 |
| ROUND_ROBIN__ALL_UAV__EDF | 35.803 | 1727.467 | 4.633 | 8.575 | 47.925 | 22.440 | 1597.497 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 34.641 | 1655.945 | 4.633 | 8.575 | 47.925 | 22.440 | 1597.497 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 37.435 | 1282.594 | 7.825 | 9.250 | 8.050 | 43.706 | 268.347 |
| STATIC_FIRST__ALL_UAV__EDF | 39.303 | 1396.366 | 7.825 | 9.250 | 8.050 | 43.706 | 268.347 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 37.831 | 1320.666 | 7.825 | 9.250 | 8.050 | 43.706 | 268.347 |

Delivery latency uses all actually delivered images (including late results); unavailable delivery is not assigned zero latency. Output/backhaul delay remains zero in this model.

| Policy | Mean delivered latency s | Mean delivered episode P95 s | Cases with deliveries |
| --- | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 1.864 | 9.895 | 240/240 |
| ROUND_ROBIN__ALL_UAV__EDF | 1.796 | 8.674 | 240/240 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 2.008 | 11.102 | 240/240 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 1.179 | 3.922 | 240/240 |
| STATIC_FIRST__ALL_UAV__EDF | 1.398 | 5.600 | 240/240 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 1.515 | 6.987 | 240/240 |

## Known-flight contact waiting

Waiting capability enabled: True. Eligible contact includes only the flight destination already selected at arrival. Reservation is an irrevocable raw-task offload decision; TX starts at the planned contact, never during the wait. Failed reservations remain failures.

| Policy | Mean eligible images | Mean reservations | Mean reservations uploaded | Mean reserved on-time deliveries | Mean actual wait s/episode |
| --- | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 8.575 | 3.942 | 3.942 | 2.217 | 66.356 |
| ROUND_ROBIN__ALL_UAV__EDF | 8.575 | 3.942 | 3.942 | 1.613 | 66.356 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 8.575 | 3.942 | 3.942 | 2.029 | 66.356 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 9.250 | 1.425 | 1.425 | 0.700 | 25.284 |
| STATIC_FIRST__ALL_UAV__EDF | 9.250 | 1.425 | 1.425 | 0.600 | 25.284 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 9.250 | 1.425 | 1.425 | 0.642 | 25.284 |
