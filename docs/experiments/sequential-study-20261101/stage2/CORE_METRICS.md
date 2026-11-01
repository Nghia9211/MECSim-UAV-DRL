# Core offloading + scheduling metrics

Image DVR includes every offered image: drops/rejections/deadline-risk failures remain failures.
Energy efficiency = sum(whole-system J) / sum(on-time images), including background/hover energy. Empty efficiency means no successes.
Latency uses completed images (on-time + late), never dropped tasks. Mean and P95 columns are equal-case means; P95 uses nearest rank per episode, not a pooled percentile.
UAV lifetime is battery-based availability, not network lifetime. Restricted time = min(exhaustion time, horizon); censored survivors have only a lower bound. No extrapolation.
All-case averages mix loads/batteries; consult per-scenario CSV before concluding. These are descriptive results, not significance tests.

| Policy | Image DVR % | J/on-time image | Mean latency s | Mean episode P95 s | Restricted UAV time s | Censored/total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__EDF | 10.686 | 1207.080 | 1.527 | 5.661 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__FIFO | 10.937 | 1210.423 | 1.486 | 5.868 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 10.697 | 1207.232 | 1.523 | 5.652 | 600.000 | 120/120 |
| ROUND_ROBIN__ALL_UAV__SPT | 10.723 | 1207.334 | 1.500 | 5.641 | 600.000 | 120/120 |
| ROUND_ROBIN__DELIVERY_AWARE__EDF | 0.034 | 1099.837 | 0.680 | 0.525 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__EDF | 11.618 | 961.749 | 1.463 | 4.380 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__FIFO | 11.849 | 964.315 | 1.427 | 3.812 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 11.619 | 961.751 | 1.461 | 4.326 | 600.000 | 120/120 |
| STATIC_FIRST__ALL_UAV__SPT | 11.661 | 962.037 | 1.440 | 3.978 | 600.000 | 120/120 |
| STATIC_FIRST__DELIVERY_AWARE__EDF | 0.261 | 852.009 | 1.075 | 1.850 | 600.000 | 120/120 |

## Mobile delivery and propulsion

Local computation on a disconnected source does NOT deliver a result. Primary image DVR above is compute completion; delivered DVR below counts received on-time results. Return/backhaul delay is currently zero when delivery is possible.
Total/UAV energy includes flight + hover + CPU; flight and hover are NOT added again. ALL_UAV uses current or enabled known-flight contact; outside eligible contact the task runs locally. CPU scheduling can run during flight.

| Policy | Delivered DVR % | J/on-time delivered image | Mean covered images | Mean offloaded images | Flight kJ | Hover kJ | Distance m |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__EDF | 39.922 | 1799.232 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__FIFO | 40.173 | 1806.690 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 39.933 | 1799.571 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__ALL_UAV__SPT | 39.959 | 1799.947 | 5.217 | 11.450 | 50.934 | 20.835 | 1697.808 |
| ROUND_ROBIN__DELIVERY_AWARE__EDF | 32.887 | 1643.523 | 6.750 | 0.450 | 54.226 | 19.079 | 1807.548 |
| STATIC_FIRST__ALL_UAV__EDF | 39.441 | 1407.491 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__FIFO | 39.672 | 1413.010 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 39.442 | 1407.493 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__ALL_UAV__SPT | 39.484 | 1408.246 | 8.983 | 11.750 | 14.802 | 40.106 | 493.404 |
| STATIC_FIRST__DELIVERY_AWARE__EDF | 32.494 | 1262.257 | 15.183 | 0.933 | 14.802 | 40.106 | 493.404 |

Delivery latency uses all actually delivered images (including late results); unavailable delivery is not assigned zero latency. Output/backhaul delay remains zero in this model.

| Policy | Mean delivered latency s | Mean delivered episode P95 s | Cases with deliveries |
| --- | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__EDF | 1.996 | 9.965 | 120/120 |
| ROUND_ROBIN__ALL_UAV__FIFO | 1.937 | 9.948 | 120/120 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 1.991 | 9.938 | 120/120 |
| ROUND_ROBIN__ALL_UAV__SPT | 1.957 | 9.818 | 120/120 |
| ROUND_ROBIN__DELIVERY_AWARE__EDF | 0.756 | 0.529 | 120/120 |
| STATIC_FIRST__ALL_UAV__EDF | 1.861 | 8.709 | 120/120 |
| STATIC_FIRST__ALL_UAV__FIFO | 1.810 | 8.201 | 120/120 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 1.859 | 8.708 | 120/120 |
| STATIC_FIRST__ALL_UAV__SPT | 1.830 | 8.096 | 120/120 |
| STATIC_FIRST__DELIVERY_AWARE__EDF | 1.331 | 5.487 | 120/120 |

## Known-flight contact waiting

Waiting capability enabled: True. Eligible contact includes only the flight destination already selected at arrival. Reservation is an irrevocable raw-task offload decision; TX starts at the planned contact, never during the wait. Failed reservations remain failures.

| Policy | Mean eligible images | Mean reservations | Mean reservations uploaded | Mean reserved on-time deliveries | Mean actual wait s/episode |
| --- | ---: | ---: | ---: | ---: | ---: |
| ROUND_ROBIN__ALL_UAV__EDF | 11.450 | 6.233 | 6.233 | 1.925 | 122.718 |
| ROUND_ROBIN__ALL_UAV__FIFO | 11.450 | 6.233 | 6.233 | 1.825 | 122.718 |
| ROUND_ROBIN__ALL_UAV__PRIORITY | 11.450 | 6.233 | 6.233 | 1.917 | 122.718 |
| ROUND_ROBIN__ALL_UAV__SPT | 11.450 | 6.233 | 6.233 | 1.892 | 122.718 |
| ROUND_ROBIN__DELIVERY_AWARE__EDF | 14.483 | 0.158 | 0.158 | 0.158 | 1.453 |
| STATIC_FIRST__ALL_UAV__EDF | 11.750 | 2.767 | 2.767 | 0.683 | 56.599 |
| STATIC_FIRST__ALL_UAV__FIFO | 11.750 | 2.767 | 2.767 | 0.658 | 56.599 |
| STATIC_FIRST__ALL_UAV__PRIORITY | 11.750 | 2.767 | 2.767 | 0.675 | 56.599 |
| STATIC_FIRST__ALL_UAV__SPT | 11.750 | 2.767 | 2.767 | 0.667 | 56.599 |
| STATIC_FIRST__DELIVERY_AWARE__EDF | 17.950 | 0.017 | 0.017 | 0.017 | 0.070 |
