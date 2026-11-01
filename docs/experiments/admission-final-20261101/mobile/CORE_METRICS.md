# Core offloading + scheduling metrics

Image DVR includes every offered image: drops/rejections/deadline-risk failures remain failures.
Energy efficiency = sum(whole-system J) / sum(on-time images), including background/hover energy. Empty efficiency means no successes.
Latency uses completed images (on-time + late), never dropped tasks. Mean and P95 columns are equal-case means; P95 uses nearest rank per episode, not a pooled percentile.
UAV lifetime is battery-based availability, not network lifetime. Restricted time = min(exhaustion time, horizon); censored survivors have only a lower bound. No extrapolation.
All-case averages mix loads/batteries; consult per-scenario CSV before concluding. These are descriptive results, not significance tests.

| Policy | Image DVR % | J/on-time image | Mean latency s | Mean episode P95 s | Restricted UAV time s | Censored/total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 9.492 | 1155.939 | 1.583 | 5.927 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__EDF | 10.686 | 1207.080 | 1.527 | 5.661 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 10.697 | 1207.232 | 1.523 | 5.652 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__RISK_BG_CAP_EDF | 9.492 | 1155.930 | 1.550 | 5.372 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 9.693 | 1172.340 | 1.617 | 6.207 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__RISK_SPT | 9.717 | 1172.631 | 1.601 | 6.184 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 10.786 | 916.666 | 1.548 | 4.658 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__EDF | 11.618 | 961.749 | 1.463 | 4.380 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 11.619 | 961.751 | 1.461 | 4.326 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__RISK_BG_CAP_EDF | 10.786 | 916.662 | 1.530 | 4.620 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 11.076 | 933.710 | 1.531 | 4.603 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__RISK_SPT | 11.130 | 934.297 | 1.489 | 4.209 | 600.000 | 120/120 |

## Mobile delivery and propulsion

Local computation on a disconnected source does NOT deliver a result. Primary image DVR above is compute completion; delivered DVR below counts received on-time results. Return/backhaul delay is currently zero when delivery is possible.
Total/UAV energy includes flight + hover + CPU; flight and hover are NOT added again. ALL_UAV uses current or enabled known-flight contact; outside eligible contact the task runs locally. CPU scheduling can run during flight.

| Policy | Delivered DVR % | J/on-time delivered image | Mean covered images | Mean offloaded images | Flight kJ | Hover kJ | Distance m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 38.728 | 1712.193 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__EDF | 39.922 | 1799.232 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 39.933 | 1799.571 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__RISK_BG_CAP_EDF | 38.728 | 1712.179 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 38.929 | 1738.372 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__RISK_SPT | 38.953 | 1739.014 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 38.609 | 1335.781 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__EDF | 39.441 | 1407.491 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 39.442 | 1407.493 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__RISK_BG_CAP_EDF | 38.609 | 1335.775 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 38.899 | 1362.679 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__RISK_SPT | 38.953 | 1363.935 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |

Delivery latency uses all actually delivered images (including late results); unavailable delivery is not assigned zero latency. Output/backhaul delay remains zero in this model.

| Policy | Mean delivered latency s | Mean delivered episode P95 s | Cases with deliveries |
| --- | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 2.062 | 10.532 | 120/120 |
| ROUND_ROBIN__ALL_UAV__EDF | 1.996 | 9.965 | 120/120 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 1.991 | 9.938 | 120/120 |
| ROUND_ROBIN__ALL_UAV__RISK_BG_CAP_EDF | 2.014 | 10.150 | 120/120 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 2.121 | 10.859 | 120/120 |
| ROUND_ROBIN__ALL_UAV__RISK_SPT | 2.098 | 10.692 | 120/120 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 1.966 | 11.104 | 120/120 |
| STATIC_FIRST__ALL_UAV__EDF | 1.861 | 8.709 | 120/120 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 1.859 | 8.708 | 120/120 |
| STATIC_FIRST__ALL_UAV__RISK_BG_CAP_EDF | 1.939 | 11.073 | 120/120 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 1.950 | 10.402 | 120/120 |
| STATIC_FIRST__ALL_UAV__RISK_SPT | 1.890 | 10.043 | 120/120 |

## Known-flight contact waiting

Waiting capability enabled: True. Eligible contact includes only the flight destination already selected at arrival. Reservation is an irrevocable raw-task offload decision; TX starts at the planned contact, never during the wait. Failed reservations remain failures.

| Policy | Mean eligible images | Mean reservations | Mean reservations uploaded | Mean reserved on-time deliveries | Mean actual wait s/episode |
| --- | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 11.450 | 6.233 | 6.233 | 2.392 | 122.718 |
| ROUND_ROBIN__ALL_UAV__EDF | 11.450 | 6.233 | 6.233 | 1.925 | 122.718 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 11.450 | 6.233 | 6.233 | 1.917 | 122.718 |
| ROUND_ROBIN__ALL_UAV__RISK_BG_CAP_EDF | 11.450 | 6.233 | 6.233 | 2.392 | 122.718 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 11.450 | 6.233 | 6.233 | 2.300 | 122.718 |
| ROUND_ROBIN__ALL_UAV__RISK_SPT | 11.450 | 6.233 | 6.233 | 2.275 | 122.718 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 11.750 | 2.767 | 2.767 | 0.758 | 56.599 |
| STATIC_FIRST__ALL_UAV__EDF | 11.750 | 2.767 | 2.767 | 0.683 | 56.599 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 11.750 | 2.767 | 2.767 | 0.675 | 56.599 |
| STATIC_FIRST__ALL_UAV__RISK_BG_CAP_EDF | 11.750 | 2.767 | 2.767 | 0.758 | 56.599 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 11.750 | 2.767 | 2.767 | 0.733 | 56.599 |
| STATIC_FIRST__ALL_UAV__RISK_SPT | 11.750 | 2.767 | 2.767 | 0.717 | 56.599 |
