# Multi-layout near-paper offloading baseline

Audit PASS: 1500 episode; 10 môi trường paper × 30 workload seed × 5 policy.
Không train, không thay tham số vật lý/radio/deadline/CPU/dwell so với primary. Không có background Alibaba trong đợt này.
Mỗi layout seed đổi tọa độ, hardware, loại vision task, pin và connectivity cùng lúc theo PaperSimulation.layout.
Đây là exploratory baseline robustness, không phải xác nhận thuật toán mới hay tái hiện paper. Các seed dự phòng không được chạy.

| Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered đúng hạn | Mean/P95 delivered s | Total/UAV kJ | Delivered đúng hạn | UAV censored/cases |
|---|---:|---:|---:|---:|---:|---:|---:|
| ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 2800 | 300/300 |
| ALL_UAV__EDF | 39.57 | 56.31 | 27031.46 | 262.21/890.81 | 286.62/214.01 | 3181 | 300/300 |
| SHORTEST_FINISH__EDF | 38.91 | 55.80 | 27020.21 | 252.00/884.45 | 290.20/217.53 | 3222 | 300/300 |
| DEADLINE_ENERGY__EDF | 38.92 | 55.40 | 26737.62 | 252.35/884.45 | 289.75/217.12 | 3251 | 300/300 |
| DELIVERY_AWARE__EDF | 38.92 | 55.40 | 26737.62 | 252.35/884.45 | 289.75/217.12 | 3251 | 300/300 |

DVR/latency là macro average theo episode; P95 là mean episode P95, không phải pooled P95. Latency chỉ dùng completions/deliveries, gồm cả muộn.
J/ảnh là ratio tổng năng lượng / tổng ảnh đúng hạn; zero-success không gán efficiency = 0.
Compute latency mean/P95, J/compute, lifetime restricted và background DVR (NA vì không có background) có đầy đủ trong summary.csv.

| Policy vs ALL_LOCAL | Δ delivered DVR, điểm % [CI 95%] | Δ J/ảnh delivered [CI 95%] |
|---|---:|---:|
| ALL_UAV__EDF | -5.30 [-7.55, -3.25] | -4297.73 [-6720.25, -2595.32] |
| SHORTEST_FINISH__EDF | -5.81 [-7.69, -4.15] | -4308.98 [-6692.63, -2612.75] |
| DEADLINE_ENERGY__EDF | -6.21 [-8.18, -4.42] | -4591.57 [-7115.64, -2769.67] |
| DELIVERY_AWARE__EDF | -6.21 [-8.18, -4.42] | -4591.57 [-7115.64, -2769.67] |

CI dùng crossed bootstrap: resample layout và shared workload seed độc lập, giữ ghép cặp policy. Không coi 1.500 episode là 1.500 mẫu độc lập.
Chỉ 10 môi trường; CI exploratory, chưa có xác nhận holdout. Mỗi layout phải đọc riêng để thấy regression.

| Layout seed | ALL_LOCAL delivered DVR % | ALL_UAV delivered DVR % | Δ điểm % |
|---|---:|---:|---:|
| 100 | 57.27 | 49.15 | -8.12 |
| 101 | 75.12 | 69.31 | -5.80 |
| 102 | 48.72 | 43.03 | -5.69 |
| 103 | 48.29 | 46.79 | -1.50 |
| 104 | 65.37 | 60.80 | -4.57 |
| 105 | 52.11 | 49.42 | -2.70 |
| 106 | 74.35 | 68.42 | -5.93 |
| 107 | 57.10 | 50.98 | -6.12 |
| 108 | 66.83 | 55.09 | -11.74 |
| 109 | 70.94 | 70.13 | -0.81 |

ALL_UAV+EDF: 8/691 dispatch có ≥2 task ready.
Paired task changes ALL_UAV vs ALL_LOCAL: {"retained_success": 2766, "rescued": 415, "failed_both": 4105, "harmed": 34}.
Các chênh lệch task/năng lượng bao gồm thay đổi contact do upload pin stop; không phải isolated compute effect.
Pin còn sống đến horizon là censored. Chưa thể khẳng định lifetime dài hơn. Synthetic 2–4 MB không phải inference RescueNet.
Radio ambiguity, full independent bandwidth, zero output delay và thiếu thu gom kết quả local vẫn là giới hạn.

runtime.csv: wall time kernel Java trên máy local, không phải runtime mỗi quyết định hoặc server benchmark.
Nguồn: plan.json, source snapshots, từng run/manifest.json, verification.json, episode traces, summary.csv và contrasts.csv.
