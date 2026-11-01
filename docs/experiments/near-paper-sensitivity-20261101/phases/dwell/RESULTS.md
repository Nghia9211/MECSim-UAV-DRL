# Sensitivity phase: dwell

Đã kiểm tra chỉ thay một yếu tố. Reference dùng trace cũ, không chạy lại. CI exploratory crossed environment/workload bootstrap.
CPU capacity đổi tại CPU watts cố định: không phải DVFS/phần cứng đo được. Không chọn mức tốt nhất làm cấu hình thật.

| Setting | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered | Mean/P95 delivered s | Mean total/UAV kJ | UAV censored/cases |
|---|---|---:|---:|---:|---:|---:|---:|
| reference | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 300/300 |
| reference | ALL_UAV__EDF | 39.57 | 56.31 | 27031.46 | 262.21/890.81 | 286.62/214.01 | 300/300 |
| reference | DEADLINE_ENERGY__EDF | 38.92 | 55.40 | 26737.62 | 252.35/884.45 | 289.75/217.12 | 300/300 |
| dwell-low | ALL_LOCAL__EDF | 43.12 | 61.61 | 34818.97 | 300.45/917.84 | 324.98/251.31 | 300/300 |
| dwell-low | ALL_UAV__EDF | 39.60 | 56.88 | 30055.66 | 271.41/889.40 | 315.08/242.40 | 300/300 |
| dwell-low | DEADLINE_ENERGY__EDF | 38.84 | 55.85 | 29844.74 | 261.21/886.15 | 320.93/248.25 | 300/300 |
| dwell-high | ALL_LOCAL__EDF | 43.12 | 61.61 | 27940.15 | 300.45/917.84 | 260.77/187.11 | 300/300 |
| dwell-high | ALL_UAV__EDF | 39.12 | 55.77 | 23898.88 | 255.80/877.07 | 256.83/184.55 | 300/300 |
| dwell-high | DEADLINE_ENERGY__EDF | 38.66 | 55.27 | 23782.30 | 246.65/872.82 | 258.59/186.18 | 300/300 |

Không coi policy episodes là mẫu độc lập; latency chỉ trên completions/deliveries, gồm task muộn; P95 là mean episode P95.
J/ảnh là ratio of sums. Không có background: background DVR NA. Lifetime còn pin ở horizon là censored.
summary.csv chứa từng môi trường, compute latency mean/P95, restricted UAV time, energy components và contact/offload counts.
Các contrasts.csv gồm effect tham số (giữ policy) và effect routing (giữ setting). CI là exploratory, không phải multiple-testing-corrected confirmatory tests.
Không thay simulator/radio/battery; synthetic 2–4 MB, chưa phải RescueNet inference.
