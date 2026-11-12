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

## 2. Kết quả (12/11/2026)

**Mọi cổng G1–G5 qua ở lần chạy đầu, không chỉnh tham số nào.** G6 đo ở P5.

| Cổng | Kết quả | Qua? |
|---|---|---|
| G1 | DVR `ALL_UAV+EDF`: 37,10% / 6,59% / 0,54% ở CPU 2 / 4 / 8 Gc/s; giảm đơn điệu, chênh 36,6 điểm | ✅ |
| G2a | Chênh DVR giữa 5 scheduler (`ALL_UAV`): light 4,2 / 8,2; medium 21,9 / 28,4; overload 52,7 / 57,3 điểm (không / có preemption) | ✅ |
| G2b | Trên 15 trace `ALL_UAV+EDF` không preemption (11.781 lần dispatch): hàng đợi ≥ 2 ở 75,1%; FIFO/EDF/SRPT chọn khác nhau ở **72,2%** mọi lần dispatch (v1: 3,2–6,4%). Tái dựng khớp lựa chọn EDF thật 11.781/11.781 | ✅ |
| G3 | `DEADLINE_ENERGY` có DVR thấp hơn cả `ALL_LOCAL` và `ALL_UAV` ở cả 3 mức tải. `ALL_LOCAL` tốn ít J biên/task hơn `ALL_UAV` ở light (19,3 vs 21,4 J) và medium; `ALL_UAV` có DVR thấp hơn ở mọi mức | ✅ |
| G4 | J biên max/min giữa 6 policy offloading: 1,48 (light), 1,67 (medium), 1,73 (overload) | ✅ |
| G5 | Sai lệch W_q: M/M/1 ρ=0,5: 0,43%; ρ=0,8: 0,30%; M/D/1 ρ=0,5: 0,42%; ρ=0,8: 1,55% (≈ 210.000 task mỗi ô) | ✅ |

DVR theo episode trung bình trên 150 episode development; J biên/task đúng hạn = tổng / tổng.
Số liệu đầy đủ: `target/mec/{g1-cpu,gates-dev,g5-queue-theory}/gates-*.json` (không commit, tái tạo bằng lệnh ở mục 4).

**Kiểm tra độc lập** (`scripts/verify_mec.py`): PASS trên cả ba run, tổng 12.600 + 900 + 4 episode;
424 episode có trace đầy đủ, ≈ 1,18 triệu kết quả task và ≈ 2,1 triệu đoạn CPU/kênh được tính lại.
`scripts/test_verify_mec.py`: verifier bác bỏ 8/8 kiểu trace bị sửa.

### Điều cần lưu ý trước P5

- **Trần thấp cho heuristic tốt nhất.** `DEADLINE_ENERGY+EDF` đã có DVR 0,49% / 1,40% / 2,52% (không preemption)
  và 0,16% ở overload có preemption. Lý do: 10 CPU thiết bị cộng lại ≈ 4,5 Gc/s, xấp xỉ CPU UAV, nên ρ_UAV = 1,3
  chỉ tương đương ≈ 0,6 công suất toàn hệ thống. Còn rất ít khoảng trống về DVR; G6 nhiều khả năng phải dựa vào năng lượng.
- Ở light có preemption, `ALL_UAV` đạt DVR 0% nhưng tốn 20,6 J/task so với 16,5 J của `DEADLINE_ENERGY`: đánh đổi DVR–năng lượng là thật.
- FIFO cho kết quả y hệt nhau khi bật/tắt preemption (28,46% ở medium): đúng kỳ vọng, vì FIFO không bao giờ ngắt task đang chạy.
- Run P4 ghi `git_dirty = true`: chạy trên commit `8f58369` cộng thay đổi `Json.java` (cho phép `null` xóa khóa),
  thay đổi này được commit ngay sau đó, không đổi gì khác.

## 3. Nhật ký chỉnh tham số

Không có lần chỉnh nào. Cấu hình khóa (SHA-256):

| File | SHA-256 |
|---|---|
| `experiments/base-model.json` | `e8a6e82c7501f6328f06bc4943b80757e4d8d87248b60df785a50448a001ea4d` |
| `docs/v2/data/rescuenet_val_bytes.csv` | `947a59787a5e43855c17de0807e4a06ccfb493a66ce1764a70ca2b5461ae9e8c` |

## 4. Lệnh tái lập

```powershell
foreach ($c in "g5-queue-theory","g1-cpu","gates-dev") {
  mvn -o -q compile exec:java "-Dexec.mainClass=uav.mec.MecRunner" "-Dexec.args=experiments/$c.json"
  .\.venv-drl\Scripts\python.exe scripts\verify_mec.py target\mec\$c
}
.\.venv-drl\Scripts\python.exe scripts\mec_gates.py g5 target\mec\g5-queue-theory
.\.venv-drl\Scripts\python.exe scripts\mec_gates.py g1 target\mec\g1-cpu
.\.venv-drl\Scripts\python.exe scripts\mec_gates.py g234 target\mec\gates-dev
```
