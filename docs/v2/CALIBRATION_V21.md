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

## 2. Kết quả (14/11/2026)

Run: `target/mec/h3-r1-heuristics` (59.400 episode), `h3-r1-oracle`, `h3-r2-heuristics` (21.600), `h3-r2-oracle`.
Verifier PASS trên cả bốn run. Bảng gốc: [data/h3-r1-gates.json](data/h3-r1-gates.json), [data/h3-r2-gates.json](data/h3-r2-gates.json).

Cột "G6" và "G7" ghi chênh DVR (điểm %) / chênh J biên. Cột quỹ đạo ghi DVR % của heuristic tốt nhất với
CIRCLE / STATIC tâm / STATIC (area/4, area/4). G9 ghi kèm tỉ lệ episode `ALL_LOCAL` có thiết bị hết pin.
Heuristic tốt nhất của mọi ô đều dùng EDF có preemption.

| Ô | Heuristic tốt nhất | DVR % | G6 | G7 | Quỹ đạo | G6 | G7 | G8 | G9 |
|---|---|---:|---|---|---|---|---|---|---|
| R1-L1 | DEADLINE_ENERGY [pre] | 0.21 | 0.24 / 3.9% | 0.04 / 1.7% | 0.21 / 0.25 / 0.21 | — | — | — |  |
| R1-L2a | DEADLINE_ENERGY [pre] | 1.07 | 0.47 / 7.9% | 0.43 / 1.7% | 1.07 / 0.64 / 0.91 | — | — | — |  |
| R1-L2b | SHORTEST_FINISH [pre] | 5.56 | 4.12 / 18.1% | 0.52 / 0.5% | 5.56 / 5.04 / 5.32 | qua | — | qua |  |
| R1-L3a | DEADLINE_ENERGY [pre] | 0.17 | 0.24 / 5.0% | 0.03 / 1.7% | 0.17 / 0.14 / 0.16 | — | — | — |  |
| R1-L3b | DEADLINE_ENERGY [pre] | 1.70 | 1.02 / 8.4% | 1.41 / 4.3% | 1.70 / 0.29 / 1.20 | — | — | — |  |
| R1-L4 | DEADLINE_ENERGY [pre] | 0.33 | 0.13 / 1.4% | 0.06 / 0.7% | 0.33 / 0.39 / 0.34 | — | — | — |  |
| R1-L5 | DEADLINE_ENERGY [pre] | 5.16 | 0.73 / 4.7% | 0.08 / 1.1% | 5.16 / 5.21 / 5.13 | — | — | qua |  |
| R1-L6a | DEADLINE_ENERGY [pre] | 0.38 | 0.20 / 3.4% | 0.05 / 0.7% | 0.38 / 0.43 / 0.42 | — | — | — |  |
| R1-L6b | DEADLINE_ENERGY [pre] | 4.44 | 1.58 / 3.3% | 0.33 / 0.6% | 4.44 / 4.77 / 4.56 | — | — | qua |  |
| R1-L7 | DEADLINE_ENERGY [pre] | 1.62 | 1.43 / 2.0% | 0.03 / 0.5% | 1.62 / 1.60 / 1.62 | — | — | — | — (100%) |
| R1-base | DEADLINE_ENERGY [pre] | 0.16 | 0.21 / 3.5% | 0.01 / 0.5% | 0.16 / 0.18 / 0.18 | — | — | — |  |
| R2-L2a+L6a | SHORTEST_FINISH [pre] | 5.63 | 4.10 / 11.3% | 0.09 / 0.8% | 5.63 / 5.54 / 5.60 | qua | — | qua |  |
| R2-L2a+L6a+L7 | SHORTEST_FINISH [pre] | 6.26 | 4.49 / 9.2% | 0.14 / 0.8% | 6.26 / 6.12 / 6.23 | — | — | qua | — (100%) |
| R2-L2a+L7 | SHORTEST_FINISH [pre] | 2.64 | 2.11 / 14.8% | 0.08 / 0.6% | 2.64 / 2.56 / 2.62 | qua | — | qua | — (100%) |
| R2-L6a+L7 | DEADLINE_ENERGY [pre] | 3.45 | 2.49 / 1.5% | 0.06 / 0.7% | 3.45 / 3.39 / 3.44 | — | — | qua | — (100%) |

### Vòng 2 được chọn thế nào

Xếp hạng theo G6 (điểm DVR) của mức mạnh nhất ở vòng 1: L2 (4,12), L6 (1,58), L7 (1,43); L3 (1,02) đứng thứ tư.
Mức nhẹ nhất đã làm G6 hoặc G7 tăng so với R1-base (0,21 / 0,01): L2a (5 MHz; G6 0,47), L6a (ρ_sys 0,8; G7 0,05 > 0,01), L7 (chỉ một mức).

### Nhận xét

1. **G7 không qua ở ô nào** (lớn nhất 1,41 điểm ở vùng 2000 m). Trong các đòn bẩy đã đăng ký, vị trí UAV không thay đổi DVR
   hay năng lượng đáng kể. Ở vùng 2000 m, treo ở tâm (0,29%) còn tốt hơn bay vòng (1,70%).
2. **G6 qua ở 3 ô**, đều có băng thông hẹp (L2), và đều qua nhờ **năng lượng** (11–18%). Chênh DVR 2,1–4,1 điểm, dưới ngưỡng 5.
   Ở các ô này heuristic tốt nhất chuyển từ `DEADLINE_ENERGY` sang `SHORTEST_FINISH`: khi kênh hẹp, ước lượng năng lượng của
   `DEADLINE_ENERGY` không còn đủ để quyết định tốt.
3. **L7 (pin 5%) quá nặng:** `ALL_LOCAL` làm 100% episode có thiết bị hết pin, G9 không qua; mọi ô có L7 bị loại.
4. Bùng phát (L5) và tải hệ thống 1,0 (L6b) làm DVR tăng (G8 qua) nhưng không mở khoảng trống: oracle chỉ hơn 0,7–1,6 điểm.

### Áp quy tắc chọn

Không ô nào qua đủ G6 + G7 + G8 → **không có ứng viên theo quy tắc 1.6**. Quy tắc 5 chỉ quy định trường hợp
"không ô nào qua G6". Trường hợp thực tế, G6 qua nhưng G7 không qua ở đâu cả, **không có trong đăng ký trước**.
Dừng ở đây để người dùng quyết định; không tự chọn kịch bản.

Nếu bỏ điều kiện G7, ứng viên theo thứ tự quy tắc 2 (ít đòn bẩy → ít đòn bẩy loại G → G6 lớn hơn):
**R1-L2b** (1 đòn bẩy: băng thông 2 MHz), rồi R2-L2a+L6a (2 đòn bẩy). R2-L2a+L7 bị loại vì G9.

## 3. Quyết định của người dùng (14/11/2026)

Người dùng chọn phương án 1: bỏ điều kiện G7, lấy **R1-L2b** làm `v2.1-main`, làm H4 và H5, **bỏ H6 (RL quỹ đạo)**.
Kết quả "vị trí UAV không ảnh hưởng đáng kể" được giữ như một phát hiện âm. Không có vòng 3.

`v2.1-main` = v2.0 + băng thông uplink 2 MHz (downlink 1 MHz), tải ρ_UAV = 1,3, quỹ đạo CIRCLE R = 200 m:
[experiments/v21-2mhz-model.json](../../experiments/v21-2mhz-model.json) (đổi tên ngày 15/11, xem mục 5).
Không có ô phụ cho kiểm tra độ bền vì không còn ứng viên nào khác thỏa quy tắc 2 khi đã bỏ G7 (R2-L2a+L6a có 2 đòn bẩy,
được dùng làm ô phụ ở H4 theo đúng thứ tự quy tắc 2).

Chạy lại G1–G5 trên `v2.1-main` với ngưỡng cũ (quy tắc 4): G1 ở tải đến cố định của ρ_UAV = 0,9 như cũ;
G2–G4 với ba mức tải light/medium/overload như cũ, cộng băng thông 2 MHz; G5 không phụ thuộc kênh truyền,
chạy lại để kiểm tra lõi sau H2.

## 4. Chạy lại G1–G5 trên `v2.1-main` (2 MHz): G2 và G3 không qua

Verifier PASS trên cả bốn run (`v21-g5-queue-theory`, `v21-g1-cpu`, `v21-gates-dev`, `v21b-gates-dev`).
Số liệu: `data/v21-*-gates-*.json`, `data/v21b-gates-dev-gates-g234.json`.

| Cổng | 2 MHz (`v2.1-main`) | 5 MHz (chẩn đoán, cùng cấu trúc cổng) |
|---|---|---|
| G1 | qua: DVR `ALL_UAV` 82,4 / 71,5 / 65,7% ở CPU 2 / 4 / 8 Gc/s | chưa chạy |
| G2a | qua (medium có preemption: chênh 9,0 điểm) | qua (tới 32,9 điểm) |
| G2b | **không qua:** FIFO/EDF/SRPT chọn khác nhau ở 15,9% lần dispatch (ngưỡng 30%) | qua: 60,0%; hàng đợi ≥ 2 ở 64,2% |
| G3 | **không qua:** `ALL_UAV` (DVR 40–84%) không thắng `ALL_LOCAL` ở chỉ số nào | qua: `ALL_UAV` thắng ở light/medium/overload |
| G4 | qua (1,92–2,64×) | qua (1,66–2,77×) |
| G5 | qua (0,30–1,55%), lõi không đổi sau H2 | (không phụ thuộc kênh) |

**Đọc:** ở 2 MHz đường truyền lên UAV thành nút thắt, task kẹt ở upload, CPU UAV ít khi có hàng đợi. Đây chính là bệnh của v1
(chẩn đoán D2–D5). Khoảng trống G6 của ô này chủ yếu đến từ dự báo kém khi kênh nghẽn, không phải từ bài toán offloading + scheduling.
Ở 5 MHz, CPU và hàng đợi vẫn là nút thắt, scheduler có tác dụng, offloading có đánh đổi.

Theo thứ tự quy tắc 2 (khi đã bỏ G7), ứng viên kế tiếp sau R1-L2b là **R2-L2a+L6a** (5 MHz + ρ_sys = 0,8):
G6 qua (4,10 điểm DVR / 11,3% năng lượng), G8 qua (DVR 5,63%). Chờ người dùng quyết định có đổi `v2.1-main` hay không.

## 5. `v2.1-main` mới: 5 MHz + ρ_sys = 0,8 (15/11/2026)

Người dùng đồng ý phương án đề xuất: thay R1-L2b bằng ứng viên kế tiếp theo quy tắc 2, **R2-L2a+L6a**.
File cấu hình 2 MHz cũ đổi tên thành `experiments/v21-2mhz-model.json`; các run 2 MHz giữ nguyên.

`v2.1-main` = v2.0 + uplink 5 MHz (downlink 2,5 MHz) + tải ρ_sys = 0,8, quỹ đạo CIRCLE R = 200 m:
[experiments/v21-main-model.json](../../experiments/v21-main-model.json), SHA-256
`9c1da31ecae0699ba86330476beba68061303251ea606915a6bf8e2d5f408f08`. **Khóa từ đây.**

| Cổng | Kết quả | Run |
|---|---|---|
| G1 | qua: DVR `ALL_UAV+EDF` 47,85 / 20,81 / 10,67% ở CPU 2 / 4 / 8 Gc/s (tải đến cố định), giảm đơn điệu, chênh 37,2 điểm | `v21main-g1-cpu` |
| G2 | qua: chênh DVR giữa scheduler tới 32,9 điểm; FIFO/EDF/SRPT khác nhau ở 60,0% lần dispatch (tái dựng 11.716/11.716) | `v21b-gates-dev` (5 MHz) |
| G3 | qua: `DEADLINE_ENERGY` thắng cả hai cực ở mọi mức tải; `ALL_UAV` thắng `ALL_LOCAL` ở light/medium/overload | `v21b-gates-dev` |
| G4 | qua: J biên max/min 1,66–2,77× | `v21b-gates-dev` |
| G5 | qua: 0,30–1,55% | `v21-g5-queue-theory` |
| G6 | qua: 4,10 điểm DVR / **11,3%** J biên (qua nhờ năng lượng) | `h3-r2-oracle` |
| G8 | qua: DVR heuristic tốt nhất (`SHORTEST_FINISH+EDF`, có preemption) = 5,63% | `h3-r2-heuristics` |
| G7 | không qua (0,09 điểm): vị trí UAV không ảnh hưởng, đã chấp nhận bỏ H6 | `h3-r2-heuristics` |

G2–G4 lấy từ run chẩn đoán `v21b-gates-dev`: cùng cấu trúc cổng với băng thông 5 MHz, có thêm mức tải ρ_sys = 0,8.
Mọi run trên đều được verifier PASS.
