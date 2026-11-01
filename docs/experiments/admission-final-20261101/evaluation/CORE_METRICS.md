# Core offloading + scheduling metrics

Image DVR includes every offered image: drops/rejections/deadline-risk failures remain failures.
Energy efficiency = sum(whole-system J) / sum(on-time images), including background/hover energy. Empty efficiency means no successes.
Latency uses completed images (on-time + late), never dropped tasks. Mean and P95 columns are equal-case means; P95 uses nearest rank per episode, not a pooled percentile.
UAV lifetime is battery-based availability, not network lifetime. Restricted time = min(exhaustion time, horizon); censored survivors have only a lower bound. No extrapolation.
All-case averages mix loads/batteries; consult per-scenario CSV before concluding. These are descriptive results, not significance tests.

| Policy | Image DVR % | J/on-time image | Mean latency s | Mean episode P95 s | Restricted UAV time s | Censored/total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 6.757 | 1165.547 | 1.768 | 8.432 | 600.000 | 240/240 |
| ROUND_ROBIN__ALL_UAV__EDF | 7.832 | 1215.821 | 1.683 | 7.295 | 600.000 | 240/240 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 7.183 | 1187.851 | 1.772 | 7.949 | 600.000 | 240/240 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 7.413 | 932.125 | 1.559 | 6.899 | 600.000 | 240/240 |
| STATIC_FIRST__ALL_UAV__EDF | 8.498 | 979.912 | 1.607 | 7.757 | 600.000 | 240/240 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 7.881 | 953.836 | 1.620 | 7.478 | 600.000 | 240/240 |

## Mobile delivery and propulsion

Local computation on a disconnected source does NOT deliver a result. Primary image DVR above is compute completion; delivered DVR below counts received on-time results. Return/backhaul delay is currently zero when delivery is possible.
Total/UAV energy includes flight + hover + CPU; flight and hover are NOT added again. ALL_UAV uses current or enabled known-flight contact; outside eligible contact the task runs locally. CPU scheduling can run during flight.

| Policy | Delivered DVR % | J/on-time delivered image | Mean covered images | Mean offloaded images | Flight kJ | Hover kJ | Distance m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 34.163 | 1652.990 | 4.308 | 9.183 | 50.375 | 21.133 | 1679.171 |
| ROUND_ROBIN__ALL_UAV__EDF | 35.238 | 1732.703 | 4.308 | 9.183 | 50.375 | 21.133 | 1679.171 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 34.589 | 1687.616 | 4.308 | 9.183 | 50.375 | 21.133 | 1679.171 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 34.282 | 1316.448 | 7.233 | 9.775 | 16.369 | 39.270 | 545.621 |
| STATIC_FIRST__ALL_UAV__EDF | 35.367 | 1390.570 | 7.233 | 9.775 | 16.369 | 39.270 | 545.621 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 34.750 | 1349.631 | 7.233 | 9.775 | 16.369 | 39.270 | 545.621 |

Delivery latency uses all actually delivered images (including late results); unavailable delivery is not assigned zero latency. Output/backhaul delay remains zero in this model.

| Policy | Mean delivered latency s | Mean delivered episode P95 s | Cases with deliveries |
| --- | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 2.291 | 12.456 | 240/240 |
| ROUND_ROBIN__ALL_UAV__EDF | 2.179 | 11.369 | 240/240 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 2.300 | 12.786 | 240/240 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 1.964 | 10.853 | 240/240 |
| STATIC_FIRST__ALL_UAV__EDF | 2.039 | 11.758 | 240/240 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 2.054 | 11.711 | 240/240 |

## Known-flight contact waiting

Waiting capability enabled: True. Eligible contact includes only the flight destination already selected at arrival. Reservation is an irrevocable raw-task offload decision; TX starts at the planned contact, never during the wait. Failed reservations remain failures.

| Policy | Mean eligible images | Mean reservations | Mean reservations uploaded | Mean reserved on-time deliveries | Mean actual wait s/episode |
| --- | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__BG_CAP_EDF | 9.183 | 4.875 | 4.875 | 2.237 | 103.898 |
| ROUND_ROBIN__ALL_UAV__EDF | 9.183 | 4.875 | 4.875 | 1.779 | 103.898 |
| ROUND_ROBIN__ALL_UAV__RISK_EDF | 9.183 | 4.875 | 4.875 | 2.038 | 103.898 |
| STATIC_FIRST__ALL_UAV__BG_CAP_EDF | 9.775 | 2.542 | 2.542 | 1.017 | 66.115 |
| STATIC_FIRST__ALL_UAV__EDF | 9.775 | 2.542 | 2.542 | 0.833 | 66.115 |
| STATIC_FIRST__ALL_UAV__RISK_EDF | 9.775 | 2.542 | 2.542 | 0.892 | 66.115 |
