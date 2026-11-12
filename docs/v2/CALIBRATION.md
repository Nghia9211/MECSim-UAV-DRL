# Hiệu chuẩn và cổng kiểm tra v2 (P4)

## 1. Đăng ký trước (ghi ngày 12/11/2026, trước khi chạy bất kỳ cổng nào)

Mọi cổng chạy trên **development** (layout 0–4 × task seed 0–29 = 150 episode mỗi ô), quỹ đạo `CIRCLE`,
trừ G5. Ba mức tải: light ρ_UAV = 0,5; medium 0,9; overload 1,3. Mô hình khởi điểm: [MODEL.md](MODEL.md),
[experiments/base-model.json](../../experiments/base-model.json). Script tính cổng: `scripts/mec_gates.py`.

| Cổng | Câu hỏi | Phép đo | Ngưỡng qua |
|---|---|---|---|
| G1 | CPU UAV có là nút thắt không? | `ALL_UAV+EDF+NONE`, tải medium với **tốc độ đến cố định** (Λ của ρ = 0,9 ở 4 Gc/s), CPU UAV 2 / 4 / 8 Gc/s | DVR giảm đơn điệu khi CPU tăng và DVR(2) − DVR(8) ≥ 10 điểm % |
| G2 | Scheduler có tạo khác biệt không? | `ALL_UAV` với FIFO, EDF, SRPT, LLF, PRIORITY_EDF; không/có preemption; tải medium và overload | (a) max − min DVR giữa 5 scheduler ≥ 5 điểm % ở ít nhất một ô; (b) trên trace `ALL_UAV+EDF` không preemption, tỉ lệ lần dispatch của UAV mà FIFO/EDF/SRPT chọn khác nhau ≥ 30% **tính trên mọi lần dispatch** (v1: 3,2–6,4%) |
| G3 | Offloading có đánh đổi thật không? | `ALL_LOCAL`, `ALL_UAV`, `RANDOM`, `SHORTEST_FINISH`, `DEADLINE_ENERGY`, `THRESHOLD_5`, scheduler EDF, không preemption | (a) ở ít nhất một mức tải, một policy hỗn hợp có DVR thấp hơn cả `ALL_LOCAL` và `ALL_UAV`; (b) `ALL_LOCAL` thắng `ALL_UAV` ở ít nhất một chỉ số (DVR hoặc J biên/task đúng hạn) ở một mức tải, và ngược lại |
| G4 | Năng lượng có phụ thuộc policy không? | J biên tổng (cộng 150 episode) giữa các policy của G3, cùng tải | max/min ≥ 1,20 ở mọi mức tải |
| G5 | Lõi có khớp lý thuyết hàng đợi không? | 1 CPU UAV, radio `IDEAL`, không bay, `ALL_UAV+FIFO`, đến Poisson, phục vụ mũ (M/M/1) và hằng (M/D/1), ρ = 0,5 và 0,8, ≥ 200 000 task mỗi ô | Thời gian chờ trung bình trong hàng đợi lệch ≤ 3% so với công thức: M/M/1 W_q = ρ/(μ − λ); M/D/1 W_q = ρ/(2μ(1 − ρ)) |
| G6 | Có khoảng trống cho thuật toán mới không? | Heuristic tốt nhất vs rollout oracle `ORACLE:<heuristic tốt nhất>` (P5) | ≥ 5 điểm % DVR hoặc ≥ 10% J biên/task đúng hạn ở ít nhất một mức tải |

Quy tắc khi một cổng không qua (MODEL.md, plan §7.2): chỉnh **một** nhóm tham số mỗi lần, theo thứ tự
tốc độ đến → slack deadline → tỉ lệ lớp task → băng thông; không đưa công suất hay tốc độ CPU ra ngoài khoảng
có nguồn; ghi lại từng lần vào mục 3 bên dưới; chạy lại toàn bộ cổng. Sau khi qua thì khóa cấu hình bằng hash.

## 2. Kết quả

(điền sau khi chạy)

## 3. Nhật ký chỉnh tham số

(điền sau khi chạy)
