# Thăm dò và chọn kịch bản v2.1 (H3)

## 1. Đăng ký trước (13/11/2026, trước khi chạy bất kỳ thăm dò nào)

Đòn bẩy: [MODEL_V21.md](MODEL_V21.md). Cổng G1–G6: [CALIBRATION.md](CALIBRATION.md). Chỉ dùng seed **development**
(layout 0–4 × task seed 0–29). Seed validation (layout 50–54 × 500–529) và evaluation v2.1 (layout 200–204 × 2000–2029)
không được mở trong H3.

### 1.1 Điểm gốc

v2.0 tải overload (ρ_UAV = 1,3), quỹ đạo CIRCLE, ước lượng chính xác. Mỗi ô chạy **cả hai** chế độ CPU (không / có preemption).

### 1.2 Heuristic tốt nhất và oracle của một ô

- Bộ heuristic: 6 policy offloading (`ALL_LOCAL`, `ALL_UAV`, `RANDOM`, `THRESHOLD_5`, `SHORTEST_FINISH`, `DEADLINE_ENERGY`) × EDF × NONE,
  ở cả hai chế độ CPU; tổng 12 heuristic. 150 episode mỗi heuristic.
- **Heuristic tốt nhất** của ô = heuristic có DVR thấp nhất trong 12; hòa thì lấy J biên/task thấp hơn.
- **Oracle** của ô = `ORACLE_ITER:<heuristic tốt nhất>` trên 6 episode (layout 0–2 × task seed 0–1).
  Lý do chọn ITER thay BEST: ở H0, BEST chỉ hơn ITER ≤ 0,21 điểm DVR mà tốn gấp 10 lần.

### 1.3 Cổng

| Cổng | Phép đo trong một ô | Ngưỡng |
|---|---|---|
| G6 | Heuristic tốt nhất vs oracle, cùng 6 episode | ≥ 5 điểm % DVR hoặc ≥ 10% J biên/task |
| G7 | Heuristic tốt nhất chạy với 3 quỹ đạo: STATIC tâm, CIRCLE (R = area/3), STATIC tại (area/4, area/4) | Chênh DVR max − min ≥ 3 điểm hoặc J biên ≥ 10% |
| G8 | DVR của heuristic tốt nhất | Trong [2%, 40%] |
| G9 | Chỉ ô bật L7: tỉ lệ episode có ≥ 1 thiết bị hết pin dưới `ALL_LOCAL+EDF+NONE` | Trong [10%, 90%] |

### 1.4 Vòng 1: đổi từng đòn bẩy một (11 ô)

| Ô | Thay đổi so với điểm gốc |
|---|---|
| R1-base | không |
| R1-L1 | kênh PLOS đô thị |
| R1-L2a / R1-L2b | băng thông uplink 5 / 2 MHz |
| R1-L3a / R1-L3b | vùng 1200 / 2000 m |
| R1-L4 | điểm nóng 30% thiết bị / 70% task |
| R1-L5 | đến theo đợt |
| R1-L6a / R1-L6b | ρ_sys = 0,8 / 1,0 (thay ρ_UAV) |
| R1-L7 | pin ban đầu 5% |

### 1.5 Vòng 2: kết hợp

Xếp hạng các đòn bẩy theo hiệu ứng ở vòng 1, theo **khoảng cách oracle** (điểm DVR của G6), hòa thì theo **G7**.
Lấy tối đa 3 đòn bẩy đứng đầu có hiệu ứng dương; với mỗi đòn bẩy dùng **mức nhẹ nhất** đã làm G6 hoặc G7 tăng so với R1-base.
Chạy mọi tổ hợp của chúng (tối đa 4 ô: 3 cặp + 1 bộ ba).

### 1.6 Quy tắc chọn

1. Ứng viên = mọi ô của vòng 1 và vòng 2 qua **G6, G7 và G8** (và G9 nếu bật L7).
2. Chọn ứng viên **ít đòn bẩy nhất**; hòa thì ít đòn bẩy loại G hơn; hòa nữa thì G6 lớn hơn.
3. Ô được chọn tên `v2.1-main`. Một ô phụ cho kiểm tra độ bền: ứng viên kế tiếp theo cùng thứ tự, nếu có.
4. Chạy lại G1–G5 trên `v2.1-main` với ngưỡng cũ; G1 dùng heuristic `ALL_UAV+EDF+NONE` như cũ.
5. Không có vòng 3. Nếu không ô nào qua G6 thì áp bảng kết cục trong plan (mục H3): ô qua G7 + G8 ít đòn bẩy nhất trở thành
   `v2.1-main` cho nhánh quỹ đạo (H6), và bỏ RL offloading.
6. Mọi ô, kể cả không qua, được ghi vào mục 2.

## 2. Kết quả

(điền sau khi chạy)
