# Sensitivity phase: cpu

Đã kiểm tra chỉ thay một yếu tố. Reference dùng trace cũ, không chạy lại. CI exploratory crossed environment/workload bootstrap.
CPU capacity đổi tại CPU watts cố định: không phải DVFS/phần cứng đo được. Không chọn mức tốt nhất làm cấu hình thật.

| Setting | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered | Mean/P95 delivered s | Mean total/UAV kJ | UAV censored/cases |
|---|---|---:|---:|---:|---:|---:|---:|
| reference | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 300/300 |
| reference | ALL_UAV__EDF | 39.57 | 56.31 | 27031.46 | 262.21/890.81 | 286.62/214.01 | 300/300 |
| reference | DEADLINE_ENERGY__EDF | 38.92 | 55.40 | 26737.62 | 252.35/884.45 | 289.75/217.12 | 300/300 |
| cpu-low | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 300/300 |
| cpu-low | ALL_UAV__EDF | 39.59 | 56.33 | 27059.15 | 263.12/890.86 | 286.83/214.22 | 300/300 |
| cpu-low | DEADLINE_ENERGY__EDF | 38.94 | 55.78 | 27023.30 | 254.38/884.47 | 290.32/217.67 | 300/300 |
| cpu-high | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 300/300 |
| cpu-high | ALL_UAV__EDF | 39.57 | 56.31 | 27026.66 | 261.99/890.80 | 286.57/213.96 | 300/300 |
| cpu-high | DEADLINE_ENERGY__EDF | 39.08 | 55.69 | 26838.70 | 256.27/885.81 | 288.87/216.22 | 300/300 |

Không coi policy episodes là mẫu độc lập; latency chỉ trên completions/deliveries, gồm task muộn; P95 là mean episode P95.
J/ảnh là ratio of sums. Không có background: background DVR NA. Lifetime còn pin ở horizon là censored.
summary.csv chứa từng môi trường, compute latency mean/P95, restricted UAV time, energy components và contact/offload counts.
Các contrasts.csv gồm effect tham số (giữ policy) và effect routing (giữ setting). CI là exploratory, không phải multiple-testing-corrected confirmatory tests.
Không thay simulator/radio/battery; synthetic 2–4 MB, chưa phải RescueNet inference.
