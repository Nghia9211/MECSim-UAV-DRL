# Scenario gần paper: kết quả baseline

Đây là pilot mở rộng continuous-time, không phải tái hiện kết quả DQN/lifetime của paper.
Đã audit PASS: 720 episode; 32088 task outcomes; 30 workload seed trên một layout cố định.
Task ảnh synthetic 2–4 MB; không phải benchmark inference RescueNet. Alibaba, nếu bật, là tải nền theo proxy CPU, không replay trace nguyên bản.
Các seed chỉ thay workload; chưa chứng minh khả năng tổng quát qua layout. CI dưới đây là exploratory; không dùng kết quả này để tuyên bố SOTA.

| Scenario | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered đúng hạn | Delivered latency mean / P95 s | Total / UAV kJ | Offload/episode |
|---|---|---:|---:|---:|---:|---:|---:|
| background-sensitivity | ALL_LOCAL__EDF | 34.18 | 42.93 | 20685.14 | 89.55 / 227.12 | 290.28 / 218.59 | 0.00 |
| background-sensitivity | ALL_UAV__EDF | 31.71 | 37.89 | 18480.22 | 84.74 / 231.33 | 282.13 / 211.13 | 2.57 |
| background-sensitivity | ALL_UAV__FIFO | 31.71 | 37.89 | 18480.22 | 84.74 / 231.33 | 282.13 / 211.13 | 2.57 |
| background-sensitivity | ALL_UAV__RISK_EDF | 31.71 | 37.89 | 18480.22 | 84.74 / 231.33 | 282.13 / 211.13 | 2.57 |
| background-sensitivity | ALL_UAV__SPT | 31.71 | 37.89 | 18480.22 | 84.74 / 231.33 | 282.13 / 211.13 | 2.57 |
| background-sensitivity | DEADLINE_ENERGY__EDF | 31.71 | 37.89 | 18891.67 | 84.10 / 229.62 | 288.41 / 217.39 | 2.30 |
| background-sensitivity | DELIVERY_AWARE__EDF | 31.71 | 37.89 | 18891.67 | 84.10 / 229.62 | 288.41 / 217.39 | 2.30 |
| background-sensitivity | SHORTEST_FINISH__EDF | 31.71 | 37.89 | 18892.93 | 83.00 / 228.77 | 288.43 / 217.38 | 1.93 |
| deadline-sensitivity | ALL_LOCAL__EDF | 35.09 | 43.84 | 21020.79 | 87.53 / 218.17 | 290.09 / 218.48 | 0.00 |
| deadline-sensitivity | ALL_UAV__EDF | 32.88 | 39.06 | 19152.56 | 80.96 / 210.20 | 286.65 / 215.75 | 2.57 |
| deadline-sensitivity | ALL_UAV__FIFO | 32.88 | 39.06 | 19152.56 | 80.96 / 210.20 | 286.65 / 215.75 | 2.57 |
| deadline-sensitivity | ALL_UAV__RISK_EDF | 32.88 | 39.06 | 19152.56 | 80.96 / 210.20 | 286.65 / 215.75 | 2.57 |
| deadline-sensitivity | ALL_UAV__SPT | 32.88 | 39.06 | 19152.56 | 80.96 / 210.20 | 286.65 / 215.75 | 2.57 |
| deadline-sensitivity | DEADLINE_ENERGY__EDF | 32.88 | 39.06 | 19346.17 | 79.89 / 205.00 | 289.55 / 218.55 | 2.30 |
| deadline-sensitivity | DELIVERY_AWARE__EDF | 32.88 | 39.06 | 19346.17 | 79.89 / 205.00 | 289.55 / 218.55 | 2.30 |
| deadline-sensitivity | SHORTEST_FINISH__EDF | 32.88 | 39.06 | 19347.46 | 78.79 / 204.15 | 289.57 / 218.54 | 1.93 |
| primary | ALL_LOCAL__EDF | 34.18 | 42.93 | 20677.11 | 89.55 / 227.12 | 290.17 / 218.48 | 0.00 |
| primary | ALL_UAV__EDF | 31.71 | 37.89 | 18472.84 | 84.74 / 231.33 | 282.02 / 211.02 | 2.57 |
| primary | ALL_UAV__FIFO | 31.71 | 37.89 | 18472.84 | 84.74 / 231.33 | 282.02 / 211.02 | 2.57 |
| primary | ALL_UAV__RISK_EDF | 31.71 | 37.89 | 18472.84 | 84.74 / 231.33 | 282.02 / 211.02 | 2.57 |
| primary | ALL_UAV__SPT | 31.71 | 37.89 | 18472.84 | 84.74 / 231.33 | 282.02 / 211.02 | 2.57 |
| primary | DEADLINE_ENERGY__EDF | 31.71 | 37.89 | 18884.29 | 84.10 / 229.62 | 288.30 / 217.27 | 2.30 |
| primary | DELIVERY_AWARE__EDF | 31.71 | 37.89 | 18884.29 | 84.10 / 229.62 | 288.30 / 217.27 | 2.30 |
| primary | SHORTEST_FINISH__EDF | 31.71 | 37.89 | 18885.55 | 83.00 / 228.77 | 288.32 / 217.26 | 1.93 |

Mean/P95 chỉ tính ảnh đã hoàn thành/giao được, có cả ảnh muộn. P95 là trung bình P95 từng episode, không phải pooled P95.
J/ảnh là tổng năng lượng toàn hệ thống chia tổng ảnh giao đúng hạn. Drops vẫn tính là thất bại.

| Scenario | So sánh | Δ delivered DVR, điểm % [CI 95%] |
|---|---|---:|
| background-sensitivity | ALL_UAV__EDF − ALL_LOCAL__EDF | -5.05 [-6.74, -3.44] |
| background-sensitivity | ALL_UAV__EDF − ALL_UAV__FIFO | 0.00 [0.00, 0.00] |
| background-sensitivity | ALL_UAV__RISK_EDF − ALL_UAV__FIFO | 0.00 [0.00, 0.00] |
| deadline-sensitivity | ALL_UAV__EDF − ALL_LOCAL__EDF | -4.78 [-6.29, -3.29] |
| deadline-sensitivity | ALL_UAV__EDF − ALL_UAV__FIFO | 0.00 [0.00, 0.00] |
| deadline-sensitivity | ALL_UAV__RISK_EDF − ALL_UAV__FIFO | 0.00 [0.00, 0.00] |
| primary | ALL_UAV__EDF − ALL_LOCAL__EDF | -5.05 [-6.74, -3.44] |
| primary | ALL_UAV__EDF − ALL_UAV__FIFO | 0.00 [0.00, 0.00] |
| primary | ALL_UAV__RISK_EDF − ALL_UAV__FIFO | 0.00 [0.00, 0.00] |

Δ âm là giảm lỗi. So sánh offloading giữ EDF; so sánh scheduler giữ ALL_UAV. Cùng workload hash trong từng cặp.

| Scenario, ALL_UAV+EDF | Dispatch có ≥2 task ready / tất cả dispatch | Background DVR | UAV censored / tổng |
|---|---:|---:|---:|
| background-sensitivity | 4 / 1880 | 0.00% | 30 / 30 |
| deadline-sensitivity | 1 / 63 | NA% | 30 / 30 |
| primary | 1 / 65 | NA% | 30 / 30 |

Không suy ra tăng lifetime khi pin chưa cạn trước horizon. UAV time bị censor là cận dưới, không phải thời điểm hết pin.
Giới hạn: một layout; các tham số deadline/CPU UAV là giả định; radio beta0 còn mơ hồ; chưa chia sẻ bandwidth; chưa có downlink cost hay thu gom kết quả local khi nguồn mất kết nối.

Xem cấu hình và ranh giới paper/phần mở rộng tại PureEdgeSim/uav/NEAR_PAPER_SCENARIO.md.
Nguồn: manifest.json, verification.json, core-metrics-episodes.csv, core-metrics-summary.csv, paired-contrasts.csv và queue-opportunities.csv.
