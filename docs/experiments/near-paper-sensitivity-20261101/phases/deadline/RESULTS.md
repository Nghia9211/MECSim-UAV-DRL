# Sensitivity phase: deadline

Đã kiểm tra chỉ thay một yếu tố. Reference dùng trace cũ, không chạy lại. CI exploratory crossed environment/workload bootstrap.
CPU capacity đổi tại CPU watts cố định: không phải DVFS/phần cứng đo được. Không chọn mức tốt nhất làm cấu hình thật.

| Setting | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered | Mean/P95 delivered s | Mean total/UAV kJ | UAV censored/cases |
|---|---|---:|---:|---:|---:|---:|---:|
| reference | ALL_LOCAL__EDF | 43.12 | 61.61 | 31329.19 | 300.45/917.84 | 292.41/218.74 | 300/300 |
| reference | ALL_UAV__EDF | 39.57 | 56.31 | 27031.46 | 262.21/890.81 | 286.62/214.01 | 300/300 |
| reference | DEADLINE_ENERGY__EDF | 38.92 | 55.40 | 26737.62 | 252.35/884.45 | 289.75/217.12 | 300/300 |
| deadline-low | ALL_LOCAL__EDF | 54.45 | 69.19 | 38886.40 | 259.00/817.06 | 291.26/218.74 | 300/300 |
| deadline-low | ALL_UAV__EDF | 50.32 | 63.48 | 32475.36 | 221.28/788.73 | 287.73/216.20 | 300/300 |
| deadline-low | DEADLINE_ENERGY__EDF | 49.11 | 61.89 | 31317.09 | 212.01/783.47 | 290.00/218.40 | 300/300 |
| deadline-high | ALL_LOCAL__EDF | 36.03 | 57.13 | 28141.38 | 319.16/976.54 | 293.14/218.74 | 300/300 |
| deadline-high | ALL_UAV__EDF | 32.61 | 51.83 | 24454.37 | 279.12/942.66 | 286.12/212.88 | 300/300 |
| deadline-high | DEADLINE_ENERGY__EDF | 32.12 | 51.16 | 24331.39 | 271.45/938.63 | 288.81/215.59 | 300/300 |

Không coi policy episodes là mẫu độc lập; latency chỉ trên completions/deliveries, gồm task muộn; P95 là mean episode P95.
J/ảnh là ratio of sums. Không có background: background DVR NA. Lifetime còn pin ở horizon là censored.
summary.csv chứa từng môi trường, compute latency mean/P95, restricted UAV time, energy components và contact/offload counts.
Các contrasts.csv gồm effect tham số (giữ policy) và effect routing (giữ setting). CI là exploratory, không phải multiple-testing-corrected confirmatory tests.
Không thay simulator/radio/battery; synthetic 2–4 MB, chưa phải RescueNet inference.
