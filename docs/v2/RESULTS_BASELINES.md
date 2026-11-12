# Kết quả P5: baseline, cận trên oracle và cổng G6

Ngày 12/11/2026. Mô hình [MODEL.md](MODEL.md), cấu hình khóa ở [CALIBRATION.md](CALIBRATION.md) (không chỉnh sau P4).
Seed **evaluation** (layout 100–104 × task seed 1000–1029 = 150 episode mỗi ô) mở lần đầu ở đợt này.

## Tóm tắt

1. **`DEADLINE_ENERGY` (chọn local/UAV theo dự báo kịp hạn, rồi theo năng lượng) là heuristic offloading tốt nhất khi không
   preemption**, cả về DVR lẫn J biên/task đúng hạn: DVR 0,34% / 1,07% / 2,23% / 5,70% (light / medium / overload / stress, EDF).
   Có preemption thì có hai ngoại lệ, xem mục 2: `ALL_UAV+EDF` đạt DVR thấp hơn ở light/medium nhưng tốn hơn khoảng 28% năng lượng;
   `ALL_LOCAL` có J/task thấp nhất chỉ vì nó làm hỏng phần lớn task MAP đắt.
2. **Scheduling có tác dụng rõ, nhất là khi có preemption:** cùng `DEADLINE_ENERGY`, EDF có preemption giảm DVR ở overload
   từ 2,23% xuống 0,13%, ở stress từ 5,70% xuống 0,47%. FIFO kém nhất (3,92% ở overload).
3. **G6 không qua.** Oracle biết trước tương lai chỉ hơn heuristic tốt nhất 0,07–1,56 điểm % DVR và 0,7–2,8% năng lượng
   ở các mức tải đã đăng ký (ngưỡng: 5 điểm hoặc 10%). Theo plan, **dừng ở đây để quyết định hướng đi**, không tự chỉnh kịch bản.
4. **Quỹ đạo bay hầu như không ảnh hưởng kết quả** (CIRCLE vs STATIC chênh ≤ 0,25 điểm DVR ở mọi ô): với kênh LoS d⁻² và 20 MHz,
   tốc độ đủ cao ở mọi vị trí trên vòng bay.
5. `DEADLINE_ENERGY` nhạy với sai số ước lượng: ±40% làm DVR tăng từ 0,34% lên 2,84% (light) và từ 2,23% lên 5,24% (overload);
   `ALL_UAV` và `SHORTEST_FINISH` gần như không đổi.

Mức tải **stress** (ρ_UAV = 1,8) và quỹ đạo **STATIC** là thăm dò, không nằm trong đăng ký trước.

## 1. Kiểm tra độc lập

| Run | Episode | Có trace | Kết quả task tính lại | Verifier |
|---|---:|---:|---:|---|
| `p5-baselines-eval` | 72.000 | 480 | 500.760 | PASS |
| `p5-oracle-eval` | 1.280 | 16 | 16.692 | PASS |
| `g6-oracle-dev` | 1.280 | 16 | 16.532 | PASS |

Mọi policy của cùng (biến thể, layout, seed) nhận cùng workload (hash SHA-256 trùng, 4.800 + 1.200 nhóm).
Cả hai run evaluation chạy trên commit sạch (`6052585`, `711e339`, `git_dirty = false`).
PASS nghĩa là sổ sách khớp mô hình, **không** chứng minh mô hình giống thực tế.

## 2. Offloading (EDF, không admission, quỹ đạo CIRCLE, ước lượng chính xác, không preemption)

DVR % [khoảng tin cậy 95%] — J biên / task đúng hạn — latency trung bình / P95 (s) — tỉ lệ offload

| Tải | ALL_LOCAL | ALL_UAV | RANDOM | THRESHOLD_5 | SHORTEST_FINISH | DEADLINE_ENERGY |
|---|---|---|---|---|---|---|
| light | 25,35 [24,71; 26,06] — 18,0 J — 7,6 / 30,1 — 0 | 3,40 [3,24; 3,55] — 20,7 J — 1,8 / 5,0 — 1 | 8,05 — 18,7 J — 3,9 / 17,5 — 0,5 | 6,55 — 16,9 J — 5,2 / 21,9 — 0,20 | 0,61 [0,54; 0,66] — 19,9 J — 1,7 / 4,6 — 0,79 | **0,34** [0,29; 0,39] — **15,7 J** — 5,5 / 22,4 — 0,23 |
| medium | 39,83 — 20,1 J — 9,2 / 35,5 | 6,20 — 21,5 J — 3,6 / 13,8 | 13,19 — 19,5 J | 8,39 — 17,7 J | 2,41 — 19,8 J — 2,4 / 6,6 — 0,58 | **1,07** [0,99; 1,15] — **16,2 J** — 5,7 / 24,8 — 0,37 |
| overload | 51,08 — 21,9 J | 17,03 — 20,8 J — 9,9 / 50,9 | 17,99 — 20,2 J | 10,07 — 18,6 J | 7,66 — 20,0 J — 3,8 / 11,4 — 0,37 | **2,23** [2,09; 2,37] — **16,8 J** — 6,0 / 28,2 — 0,49 |
| stress | 61,04 — 22,9 J | 31,68 — 19,6 J | 23,11 — 21,0 J | 11,77 — 19,4 J | 21,93 — 21,7 J | **5,70** [5,32; 6,09] — **18,0 J** — 6,8 / 33,0 — 0,61 |

So ghép cặp với `DEADLINE_ENERGY` (150 cặp): `SHORTEST_FINISH` có DVR cao hơn 0,26 / 1,34 / 5,43 / 16,23 điểm
và tốn hơn 26,6 / 22,2 / 18,6 / 20,9% năng lượng biên. Khoảng tin cậy của mọi chênh lệch này đều không chứa 0.

**Cách đọc:** `DEADLINE_ENERGY` dùng hết độ chùng deadline để chạy local khi kịp, nên latency trung bình cao hơn
`SHORTEST_FINISH` (5,5 s so với 1,7 s ở light) nhưng tốn ít năng lượng hơn và ít trễ hạn hơn. Đây là đánh đổi
latency–năng lượng; không gọi nó là "tốt hơn về mọi mặt".

### Hai ngoại lệ khi có preemption (offloading, EDF, ước lượng chính xác, CIRCLE)

| Tải | ALL_LOCAL: DVR / J biên/task / DVR lớp MAP | ALL_UAV: DVR / J | DEADLINE_ENERGY: DVR / J |
|---|---|---|---|
| light | 7,89% / 15,34 J / 18,9% | **0,00%** / 20,11 J | 0,05% / 15,65 J |
| medium | 13,84% / 14,77 J / 34,1% | **0,01%** / 20,31 J | 0,08% / 16,05 J |
| overload | 20,87% / 14,14 J / 51,0% | 12,60% / 19,71 J | **0,13%** / 16,52 J |
| stress | 31,25% / 13,25 J / 72,3% | 29,51% / 18,96 J | **0,47%** / 17,14 J |

- Ở tải thấp có preemption, offload hết lên UAV gần như không trễ hạn nhưng tốn hơn khoảng 28% năng lượng biên:
  một đánh đổi DVR–năng lượng thật. `DEADLINE_ENERGY` chấp nhận 0,05–0,08% DVR để tiết kiệm năng lượng đó.
- J biên/task đúng hạn của `ALL_LOCAL` thấp vì task đúng hạn chủ yếu là task rẻ: chỉ số này luôn phải đọc kèm DVR.

## 3. Scheduling và admission (offloading = DEADLINE_ENERGY, CIRCLE, ước lượng chính xác)

DVR %, không preemption / có preemption:

| Tải | FIFO | EDF | SRPT | LLF | PRIORITY_EDF |
|---|---|---|---|---|---|
| light | 0,38 / 0,38 | 0,34 / **0,05** | 0,49 / 0,31 | 0,36 / 0,38 | 0,34 / 0,15 |
| medium | 1,40 / 1,40 | 1,07 / **0,08** | 1,42 / 0,62 | 1,11 / 0,58 | 1,07 / 0,25 |
| overload | 3,92 / 3,92 | 2,23 / **0,13** | 2,97 / 1,02 | 2,28 / 0,71 | 2,23 / 0,34 |
| stress | 13,81 / 13,81 | 5,70 / **0,47** | 6,51 / 1,72 | 5,79 / 1,15 | 5,70 / 0,77 |

- EDF có preemption tốt nhất ở mọi mức tải; ghép cặp với EDF, LLF/SRPT/PRIORITY_EDF đều kém hơn và khoảng tin cậy không chứa 0
  (ví dụ overload có preemption: SRPT +0,89 [0,85; 0,94] điểm, thua 150/150 cặp).
- Không preemption: PRIORITY_EDF = EDF, vì ưu tiên trùng thứ tự deadline của ba lớp task.
- FIFO giống hệt khi bật/tắt preemption, đúng như kỳ vọng.
- **Admission `DROP_INFEASIBLE` gần như không có tác dụng:** giảm 0–0,09 điểm DVR, khoảng tin cậy hẹp nhưng hiệu ứng rất nhỏ.

Vi phạm deadline tập trung ở lớp DETECT (deadline 1–3 s). Với `DEADLINE_ENERGY+EDF`, không preemption, ở overload:
DETECT 5,61%, SEGMENT 0,01%, MAP 0%.

## 4. Sai số ước lượng và quỹ đạo

| Tải | DVR % ước lượng chính xác → sai số ±40% (không preemption) |||
|---|---|---|---|
| | ALL_UAV | SHORTEST_FINISH | DEADLINE_ENERGY |
| light | 3,40 → 3,40 | 0,61 → 0,69 | 0,34 → 2,84 |
| medium | 6,20 → 6,20 | 2,41 → 2,63 | 1,07 → 4,02 |
| overload | 17,03 → 17,03 | 7,66 → 7,91 | 2,23 → 5,24 |
| stress | 31,68 → 31,68 | 21,93 → 22,07 | 5,70 → 8,10 |

`DEADLINE_ENERGY` chọn local khi dự báo "vừa kịp", nên dễ trễ hạn nhất khi khối lượng thật lớn hơn ước lượng.
Với ±40%, `SHORTEST_FINISH` có DVR thấp hơn ở light (0,69% so với 2,84%) và medium (2,63% so với 4,02%);
`DEADLINE_ENERGY` vẫn tốt hơn ở overload và stress.

Quỹ đạo CIRCLE và STATIC (DVR %, không preemption): `ALL_UAV` 17,03 / 16,90; `DEADLINE_ENERGY` 2,23 / 2,38 ở overload.
Trên toàn bộ 15 policy × 16 cặp ô, chênh lệch lớn nhất là 0,25 điểm (stress, ±40%, preemption, FIFO).

## 5. G6: khoảng trống so với oracle

Oracle = rollout một bước với `DEADLINE_ENERGY+EDF+NONE`: với mỗi task, mô phỏng lại toàn bộ episode cho cả hai lựa chọn,
**biết trước mọi task tương lai và khối lượng thật**; scheduler giữ EDF. Mỗi ô 10 episode (5 layout × 2 seed).
Oracle không phải tối ưu chứng minh được; nó là mốc tham chiếu mạnh hơn mọi policy trực tuyến.

| Ô (evaluation) | DVR % heuristic → oracle | Chênh (điểm) | J biên/task heuristic → oracle | Chênh |
|---|---|---:|---|---:|
| light, không / có preemption | 0,21 → 0,08 / 0,11 → 0,02 | 0,13 / 0,08 | 15,51 → 15,41 / 15,50 → 15,25 | 0,7% / 1,6% |
| medium | 1,02 → 0,22 / 0,07 → 0,00 | 0,80 / 0,07 | 16,24 → 16,03 / 16,10 → 15,71 | 1,3% / 2,5% |
| overload | 2,09 → 0,53 / 0,16 → 0,01 | 1,56 / 0,15 | 16,62 → 16,15 / 16,34 → 15,88 | 2,8% / 2,8% |
| stress (thăm dò) | 4,95 → 1,85 / 0,29 → 0,04 | 3,11 / 0,25 | 17,34 → 16,58 / 16,62 → 16,18 | 4,3% / 2,7% |

Development cho cùng kết luận (chênh tối đa 1,56 điểm ở overload; stress 3,06 điểm; năng lượng ≤ 4,9%).
**G6 không qua** ở cả hai phân vùng. Oracle giảm DVR khoảng 2/3 theo tương đối, nhưng mức tuyệt đối còn lại đã rất nhỏ.

## 6. Chỉ số bắt buộc khác

- **Lifetime UAV:** 150/150 episode ở mọi ô đều còn pin tới horizon 690 s → chỉ có cận dưới ≥ 690 s (censored).
  Pin 1,6 MJ với công suất bay ≈ 1108 W cho khoảng 1440 s nếu bay liên tục.
- **J tổng / task đúng hạn** bị năng lượng bay chi phối: 1716 J (light) đến 512 J (stress) với `DEADLINE_ENERGY`,
  so với 16–18 J năng lượng biên. Vì vậy so sánh policy dùng J biên (AGENTS.md, quy tắc v2).
- Không có episode nào có 0 task đúng hạn; background DVR: không có (v2 không có tải nền).
- Bảng đầy đủ 480 ô × policy: [data/p5-eval-summary.csv](data/p5-eval-summary.csv);
  so sánh ghép cặp: [data/p5-eval-paired.csv](data/p5-eval-paired.csv); cổng: `data/g*.json`; verifier: `data/verification-*.json`.

## 7. Giới hạn

- Tham số loại G trong MODEL.md (tốc độ CPU thiết bị, công suất UAV, deadline, lớp DETECT/MAP) chưa đo thực tế.
- Oracle chỉ tối ưu offloading; không tối ưu scheduling hay admission.
- Một UAV, một CPU UAV, không nhiễu giữa liên kết, không chi phí chuyển ngữ cảnh khi preemption.
- Quỹ đạo không ảnh hưởng vì kênh mạnh; kết luận này phụ thuộc β₀, α, băng thông đã chọn.
- Không có kiểm định giả thuyết chính thức; khoảng tin cậy bootstrap theo cặp (layout, seed) mang tính mô tả.

## 8. Quyết định cần bàn (điều kiện dừng của P5)

G6 không qua nghĩa là, **trong mô hình này**, một thuật toán offloading mới, kể cả RL, chỉ có thể cải thiện rất ít
so với `DEADLINE_ENERGY+EDF`. Các hướng có thể chọn:

1. **Giữ mô hình, đổi đóng góp:** phân tích heuristic. Kết quả đã đủ cho một chương có số liệu:
   offloading theo deadline + năng lượng, vai trò của preemption EDF, độ nhạy với sai số ước lượng.
2. **Làm bài toán khó hơn một cách có lý do:** ví dụ kênh yếu hơn (α > 2 hoặc vùng rộng hơn) để quỹ đạo có ý nghĩa,
   hay deadline DETECT chặt hơn, hay sai số ước lượng lớn. Phải đăng ký trước, giữ phân vùng evaluation mới, chạy lại G1–G6.
3. **Mở rộng không gian quyết định:** đưa scheduling hoặc admission vào oracle/RL, hoặc cho UAV chọn quỹ đạo
   (đã nằm ngoài phạm vi "offloading + scheduling" hiện tại).

## 9. Lệnh tái lập

```powershell
foreach ($c in "g6-oracle-dev","p5-baselines-eval","p5-oracle-eval") {
  mvn -o -q compile exec:java "-Dexec.mainClass=uav.mec.MecRunner" "-Dexec.args=experiments/$c.json"
  .\.venv-drl\Scripts\python.exe scripts/verify_mec.py target/mec/$c
  .\.venv-drl\Scripts\python.exe scripts/mec_report.py target/mec/$c
}
.\.venv-drl\Scripts\python.exe scripts/mec_gates.py g6 target/mec/g6-oracle-dev
.\.venv-drl\Scripts\python.exe scripts/mec_gates.py g6 target/mec/p5-oracle-eval
```
