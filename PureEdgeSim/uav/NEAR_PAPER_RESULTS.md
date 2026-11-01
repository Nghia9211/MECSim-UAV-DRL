# Kết quả scenario gần paper — 01/11/2026

Đã chạy **720 episode, 30 workload seed × 3 scenario × 8 baseline**, audit độc lập PASS trên **32.088 task outcomes**.
Đây là pilot continuous-time mở rộng từ paper, **không phải tái hiện kết quả DQN của paper**.

## Kết quả cấu hình chính

| Chỉ số | ALL_LOCAL + EDF | Cho phép UAV offload + EDF |
|---|---:|---:|
| Ảnh không giao đúng hạn (%) | 42.93 | 37.89 |
| Compute DVR (%) | 34.18 | 31.71 |
| J / ảnh giao đúng hạn | 20677.11 | 18472.84 |
| Mean delivered latency (s) | 89.55 | 84.74 |
| Mean episode P95 delivered latency (s) | 227.12 | 231.33 |
| Năng lượng toàn hệ thống (kJ) | 290.17 | 282.02 |
| Năng lượng UAV (kJ) | 218.48 | 211.02 |
| Tổng ảnh giao đúng hạn / 30 episode | 421.00 | 458.00 |

Giữ ROUND_ROBIN và EDF ở cả hai nhánh. ALL_UAV chỉ offload khi có current/known-flight contact;
ngoài contact vẫn local. Workload/hash được ghép cặp giữa các baseline.

- Delivered DVR giảm **5,05 điểm %**; paired workload-seed bootstrap CI 95% **[−6,74; −3,44] điểm %**.
- J/ảnh giao đúng hạn giảm khoảng **10,66%**. Đây là efficiency toàn hệ thống, không phải chỉ điện compute.
- Mean delivered latency giảm nhưng **P95 delivered latency hơi tăng**; không kết luận cải thiện mọi mặt.
- Một phần giảm năng lượng do upload giữ UAV dừng lâu hơn: quãng đường trung bình giảm từ
  **5.319,90 m xuống 4.782,76 m**, flight energy giảm còn hover energy tăng.
  Không diễn giải thành thuật toán offloading đã tối ưu riêng năng lượng bay.
- Chỉ offload trung bình **2,57 ảnh/episode**; contact vẫn là giới hạn lớn.

## Scheduler có ý nghĩa chưa?

Trong primary, ALL_UAV+EDF chỉ có **1/65 dispatch** với ≥2 task ready.
FIFO/EDF/SPT/RISK_EDF có cùng kết quả core metrics ở pilot này.
Trong background-sensitivity là **4/1.880 dispatch** và các core metrics vẫn giống nhau.

Tải nền Alibaba tùy chọn hiện nhẹ: thời gian CPU cô lập trung bình từ source pool là **0,083015 s/task**,
tốc độ đến 0,1 task/s ⇒ offered background CPU load khoảng **0,83%**.
Không gọi đó là stress test scheduler. Không tăng tải chỉ để tạo scheduler thắng.

**Hướng phù hợp hiện tại: phát triển quyết định offloading trước**.
Scheduler được cấu hình và kiểm chứng, nhưng chưa có bằng chứng nó là nút thắt của scenario gần paper này.
Nếu nghiên cứu scheduler về sau, phải khai báo thí nghiệm tải/CPU riêng và so sánh trade-off cả background.

## Độ tin cậy và giới hạn

- 143 Java tests: PASS; 21 scripts tests: PASS; 72 DRL Python tests: OK, 3 skipped.
- Smoke: 48 episode / 2.000 outcomes PASS trước lượt đầy đủ.
- Independent verifier kiểm tra RNG/task/layout, bảng hardware, routing/queue, mobility/contact/upload,
  energy conservation và delivered updates. Negative tests phát hiện sửa sai compute hoặc energy.
- 30 workload seed dùng **một layout 42**; chưa đánh giá generalization qua layout hay xác nhận bằng holdout.
- Tất cả 30 UAV trong mỗi arm/scenario sống đến horizon **1.800 s**: censored, **chưa chứng minh lifetime tăng**.
- Workload ảnh synthetic **2–4 MB**; **không phải RescueNet inference benchmark**.
  Các bảng throughput local là của nhánh paper; UAV CPU/deadline/arrival/dwell là giả định mở rộng.
- Bật/tắt background giữ nguyên mọi trường của task ảnh, kể cả estimated MI; đã verify độc lập theo seed.
- Không train model hoặc công bố novel algorithm từ kết quả này.
- Không so trực tiếp với benchmark DeepLab/RescueNet mixed-v2 trước đây vì đã đổi mô hình task và compute.

## Cấu hình, lệnh và bằng chứng

- [Mô hình và lệnh chạy](NEAR_PAPER_SCENARIO.md).
- [Cấu hình mặc định, không cần dataset](offloading/near-paper-protocol.json).
- [Kết quả đủ 3 scenario và 8 baseline](../../docs/experiments/near-paper-20261101/RESULTS.md).
- Run đầy đủ: target/near-paper-final-20261101/; smoke: target/near-paper-check-20261101/.
- Bộ đối chiếu paper gốc và kết quả cũ vẫn giữ nguyên để kiểm tra riêng.

**Bước tiếp:** giữ scenario này làm reference; đánh giá policy offloading trên nhiều layout và sensitivity CPU UAV,
deadline, contact/dwell đã khai báo trước. Chưa cần train DQN hoặc thêm cache/scheduler phức tạp.

## Đã thực hiện bước tiếp

[Xem campaign 10 môi trường mới](NEAR_PAPER_MULTILAYOUT_RESULTS.md): 1.500 episode audit PASS.
Đọc trace reference trước khi chạy campaign; không rerun baseline layout 42.
