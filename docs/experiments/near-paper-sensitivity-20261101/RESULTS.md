# Sensitivity CPU, deadline và dwell — kết quả đầy đủ

Hoàn tất tuần tự CPU → deadline → dwell. 5400 episode mới; 900 reference episode tái sử dụng; 131760 task outcomes mới, tất cả audit PASS.
10 environments × 30 shared workload seeds × 3 policies. Không rerun reference; không cộng smoke vào full sample.
Physical/radio/battery/arrival model giữ nguyên; CPU watts cố định 20 W khi đổi throughput. RR + EDF cố định.
Các mức là giả định sensitivity, không phải số đo hardware hoặc SLA thực. Task synthetic 2–4 MB; không background/RescueNet inference.

| Setting | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered | Mean/P95 delivered s | Total/UAV kJ | Delivered ontime | UAV censored/cases |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Reference: CPU 2 MB/s, deadline 600s, dwell 60s | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 2800 | 300/300 |
| Reference: CPU 2 MB/s, deadline 600s, dwell 60s | ALL_UAV__EDF | 39.57 | 56.31 | 27031.46 | 262.21/890.81 | 286.62/214.01 | 3181 | 300/300 |
| Reference: CPU 2 MB/s, deadline 600s, dwell 60s | DEADLINE_ENERGY__EDF | 38.92 | 55.40 | 26737.62 | 252.35/884.45 | 289.75/217.12 | 3251 | 300/300 |
| CPU 0.5 MB/s | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 2800 | 300/300 |
| CPU 0.5 MB/s | ALL_UAV__EDF | 39.59 | 56.33 | 27059.15 | 263.12/890.86 | 286.83/214.22 | 3180 | 300/300 |
| CPU 0.5 MB/s | DEADLINE_ENERGY__EDF | 38.94 | 55.78 | 27023.30 | 254.38/884.47 | 290.32/217.67 | 3223 | 300/300 |
| CPU 8 MB/s | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 2800 | 300/300 |
| CPU 8 MB/s | ALL_UAV__EDF | 39.57 | 56.31 | 27026.66 | 261.99/890.80 | 286.57/213.96 | 3181 | 300/300 |
| CPU 8 MB/s | DEADLINE_ENERGY__EDF | 39.08 | 55.69 | 26838.70 | 256.27/885.81 | 288.87/216.22 | 3229 | 300/300 |
| Deadline 300s | ALL_LOCAL__EDF | 54.45 | 69.19 | 38886.40 | 259.00/817.06 | 291.26/218.74 | 2247 | 300/300 |
| Deadline 300s | ALL_UAV__EDF | 50.32 | 63.48 | 32475.36 | 221.28/788.73 | 287.73/216.20 | 2658 | 300/300 |
| Deadline 300s | DEADLINE_ENERGY__EDF | 49.11 | 61.89 | 31317.09 | 212.01/783.47 | 290.00/218.40 | 2778 | 300/300 |
| Deadline 900s | ALL_LOCAL__EDF | 36.03 | 57.13 | 28141.38 | 319.16/976.54 | 293.14/218.74 | 3125 | 300/300 |
| Deadline 900s | ALL_UAV__EDF | 32.61 | 51.83 | 24454.37 | 279.12/942.66 | 286.12/212.88 | 3510 | 300/300 |
| Deadline 900s | DEADLINE_ENERGY__EDF | 32.12 | 51.16 | 24331.39 | 271.45/938.63 | 288.81/215.59 | 3561 | 300/300 |
| Dwell 15s | ALL_LOCAL__EDF | 43.12 | 61.61 | 34818.97 | 300.45/917.84 | 324.98/251.31 | 2800 | 300/300 |
| Dwell 15s | ALL_UAV__EDF | 39.60 | 56.88 | 30055.66 | 271.41/889.40 | 315.08/242.40 | 3145 | 300/300 |
| Dwell 15s | DEADLINE_ENERGY__EDF | 38.84 | 55.85 | 29844.74 | 261.21/886.15 | 320.93/248.25 | 3226 | 300/300 |
| Dwell 180s | ALL_LOCAL__EDF | 43.12 | 61.61 | 27940.15 | 300.45/917.84 | 260.77/187.11 | 2800 | 300/300 |
| Dwell 180s | ALL_UAV__EDF | 39.12 | 55.77 | 23898.88 | 255.80/877.07 | 256.83/184.55 | 3224 | 300/300 |
| Dwell 180s | DEADLINE_ENERGY__EDF | 38.66 | 55.27 | 23782.30 | 246.65/872.82 | 258.59/186.18 | 3262 | 300/300 |

DVR macro mean theo episode; P95 là mean episode P95, gồm task muộn đã giao; không gán drops thành latency.
J/ảnh = ratio tổng energy / tổng successes; pin chưa cạn ở horizon là censored. Background DVR NA.
summary.csv có cả completed mean/P95, restricted UAV time, compute/delivery counts và từng environment.

## Effect của tham số trên DEADLINE_ENERGY

| Factor | Mức | Δ delivered DVR vs reference, điểm % [CI 95%] | J/ảnh delivered |
|---|---|---:|---:|
| cpu | 0.5 | 0.38 [0.00, 0.96] | 27023.30 |
| cpu | 8.0 | 0.29 [0.00, 0.98] | 26838.70 |
| deadline | 300 | 6.49 [3.95, 8.99] | 31317.09 |
| deadline | 900 | -4.23 [-5.59, -2.84] | 24331.39 |
| dwell | 15 | 0.46 [-0.82, 1.81] | 29844.74 |
| dwell | 180 | -0.12 [-2.28, 1.75] | 23782.30 |

CI exploratory crossed bootstrap 5.000 lần trên environments và shared workload seeds. Không coi policy episodes độc lập; không multiple-testing-corrected confirmatory claims.
Các phase/contrasts.csv còn chứa routing effect so với ALL_LOCAL và DEADLINE_ENERGY so với ALL_UAV cùng setting.

## Cách đọc đúng

CPU-high vs reference, DEADLINE_ENERGY: 51 route changes, 17 episode đổi visit trace, 0 task được cứu và 22 task mất delivered ontime. Không diễn giải CPU nhanh hơn là hardware kém đi.

- CPU: thay throughput UAV ở watts cố định; hiệu ứng nhỏ không có nghĩa CPU luôn vô ích ngoài grid/tải đã thử.
- Deadline: nới deadline là thay yêu cầu chấp nhận task, không phải thuật toán chạy nhanh hơn. Latency trên tập completed có thể đổi vì censoring/selection.
- Dwell: không chỉ thay thời gian chờ; nó đổi chu kỳ thăm, contact opportunity, flight/hover và upload pin stop. Không kết luận tiết kiệm compute từ toàn bộ energy change.
- 10 environment seed còn thay hardware/vision task/pin/connectivity. Chưa có fresh holdout hay kết luận ngoài simulator.
- Cơ chế local-result collection, downlink cost và shared bandwidth vẫn chưa được mô hình hóa.
- Giữ baseline DEADLINE_ENERGY, không coi feasibility check có sẵn là novelty mới.

runtime.csv ghi wall time kernel Java trên máy local; không phải thời gian mỗi quyết định hoặc benchmark server. Reference timing tái sử dụng từ process cũ, không dùng để xếp hạng tốc độ giữa settings.
Không thay cấu hình chính theo mức có metric đẹp nhất. Giữ reference làm mốc và dùng sensitivity để chọn giả thuyết cần kiểm chứng tiếp.
