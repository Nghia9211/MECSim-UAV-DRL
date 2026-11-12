# Kế hoạch kiểm tra offloading qua nhiều môi trường paper

Khóa trước lượt đầy đủ, ngày 01/11/2026.

## Câu hỏi

Lợi ích offloading ở layout 42 có còn xuất hiện khi lấy mẫu thêm môi trường theo cách của paper?
Offloading có thể cải thiện delivered DVR, nhưng không yêu cầu mọi chỉ số/arm/layout đều cải thiện.

## Bước 1: chỉ đọc trace reference

Reference: target/near-paper-final-20261101, primary, layout 42.
Đã phân loại từng task occurrence theo (seed,id), kiểm tra paired rescues/harms và energy conservation:
421 retained success, 37 rescued, 0 harmed, 274 failed both.
Đây là effect toàn policy, có thể bao gồm thay đổi queue/contact; không phải isolated CPU counterfactual.

Giảm năng lượng chính: flight −16.114 J/episode, hover +8.594 J;
ground compute −720 J, UAV compute +63 J. Không quy toàn bộ energy gain cho CPU.

## Bước 2: campaign cố định

- Environment seeds 100–109; 30 workload seeds 0–29 dùng lại giữa các môi trường.
- Theo PaperSimulation.layout: đổi cùng lúc vị trí, hardware, vision task, pin, connectivity.
  Không gọi đây là chỉ thay geometry.
- Chỉ load primary: deadline 600 s; CPU/radio/pin/dwell/horizon giữ nguyên reference.
- RR + EDF; routing ALL_LOCAL, ALL_UAV, SHORTEST_FINISH, DEADLINE_ENERGY, DELIVERY_AWARE.
- Tổng 1.500 episode; mỗi environment 150 episode.
- Không background Alibaba, không RescueNet inference, không train RL, không thử scheduler mới.
- Seeds 110–119 ghi dự phòng, không chạy ở campaign này. Không tuyên bố toàn dự án chưa dùng chúng.
- Smoke 2 environment × 1 workload seed × 5 policy = 10 episode; không nhập smoke vào full metrics.

## Kiểm chứng

- Lock plan và protocol hashes, source snapshot và live-source hash checks.
- Mỗi run Java exit code 0, manifest COMPLETE, independent near-paper verifier PASS.
- Tự xuất mandatory metrics; ghép cặp workload hash giữa mọi policy và environment.
- Đếm đủ outcomes/cases, recount metrics từ traces, audit input hashes và process logs.
- Không ghi đè folder đã chạy dở; lỗi phải kiểm tra. Resume chỉ nhận child run COMPLETE.
- Không thay kernel, bảng paper hoặc baseline implementation.

## Cách đánh giá đã định

Primary contrast: ALL_UAV vs ALL_LOCAL, delivered DVR.
Giữ cả các baseline routing còn lại và full per-layout tables, không chỉ báo arm thắng.
Đo compute/delivery DVR, J/on-time compute/delivered image, completed/delivered mean/P95 latency,
total/UAV energy, ontime counts, UAV restricted availability+censoring, background DVR NA và kernel runtime.

DVR/latency macro mean theo episode; energy efficiency ratio of sums.
CI exploratory crossed bootstrap 5.000 lượt, resample environments và shared workload seeds độc lập,
giữ ghép cặp policy. Không coi 1.500 episode là 1.500 mẫu độc lập.
Chỉ 10 environments; chưa phải holdout confirmation, chưa suy ra SOTA.

## Điểm dừng và bước tiếp

Sau audit, đọc regression từng môi trường và trade-off P95/energy.
Không tăng tải hoặc đổi radio để bảo đảm baseline thắng.
Nếu offloading ổn định: thiết kế sensitivity CPU/deadline/dwell, rồi chọn một cơ chế cải tiến dựa trên failures.
Nếu hiệu ứng phụ thuộc môi trường/contact: tập trung giải thích phụ thuộc đó trước thuật toán mới.
Pin chưa cạn thì lifetime chỉ censored, không tuyên bố kéo dài lifetime.
