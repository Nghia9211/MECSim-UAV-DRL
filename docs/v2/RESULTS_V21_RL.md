# Kết quả H4–H5: RL trên `v2.1-main`

Ngày 15/11/2026. Kịch bản `v2.1-main` (5 MHz + ρ_sys = 0,8, khóa ở [CALIBRATION_V21.md](CALIBRATION_V21.md) mục 5),
biến thể chính: EDF có preemption, ước lượng chính xác, quỹ đạo CIRCLE.
Seed: huấn luyện layout 1000–1999 × task seed 10⁶–2·10⁶ (rút ngẫu nhiên); validation layout 50–54 × 500–529;
**evaluation v2.1 layout 200–204 × 2000–2029, mở một lần cho mỗi policy cuối**.

## Tóm tắt

1. **RL cho offloading (H5a) vượt heuristic tốt nhất ở cả 5 seed huấn luyện.** Trên evaluation, DVR 3,22–3,85% so với 6,12%
   của `SHORTEST_FINISH+EDF`. Chênh ghép cặp −2,27 đến −2,90 điểm, khoảng tin cậy 95% không chứa 0, mỗi seed thắng 150/150 cặp episode.
   Năng lượng biên/task đúng hạn thấp hơn 1,4–2,0%, latency trung bình và P95 cũng thấp hơn.
   Tiêu chí đóng góp của plan (≥ 4/5 seed có khoảng tin cậy không chứa 0) đạt **5/5**.
2. **Ưu thế của policy H5a giữ nguyên khi đổi điều kiện mà policy chưa từng thấy:** ước lượng sai ±40% (−2,14 đến −2,74 điểm) và UAV đứng yên
   (−1,21 đến −1,84 điểm so với heuristic tốt nhất của chính biến thể đó, kèm −6,6 đến −7,1% năng lượng).
3. **Huấn luyện thêm 2 triệu bước (H5a-long, đăng ký trước) giảm DVR thêm:** 2,59–3,00% trên evaluation, chênh −3,11 đến −3,53 điểm
   so với heuristic (KTC không chứa 0, 5/5 seed); DVR lớp DETECT 1,1–1,7% so với 6,3%. **Đổi lại**, ưu thế năng lượng gần như mất
   (chỉ 2/5 seed còn chênh có ý nghĩa: −1,27% và −0,81%) và latency P95 nhỉnh hơn heuristic ở 3/5 seed. Chọn trên validation
   (H5a-long 2,02–2,54% so với H5a 2,31–2,85%), **H5a-long là policy cuối**; cả hai được báo cáo (mục 2b).
4. **RL lấy được khoảng một nửa đến ba phần tư khoảng trống** (ước lượng thô: oracle chỉ chạy trên 10 episode). Oracle biết trước tương lai đạt DVR 0,06% trên 10 episode evaluation, so với 4,74%
   của `SHORTEST_FINISH` trên cùng 10 episode.
5. **RL chọn task cho CPU UAV (H5b) không vượt EDF.** Lần 1 hỏng do thiết lập (mục 4). Lần 2 sửa thiết lập: chênh DVR trên
   evaluation bằng 0 ở 4/5 seed; seed còn lại +0,005 điểm (khoảng tin cậy chứa 0). Không đạt tiêu chí đóng góp.
   Điều này phù hợp với lý thuyết: trên một CPU có preemption, EDF tối ưu về việc đáp ứng deadline mỗi khi tập task còn khả thi.
   Vì vậy không làm H5c (kết hợp hai policy học được).
6. **Mở rộng offloading (H5d, mục 4b) không cho kết quả dương.** Hành động REJECT không qua gate, vì ngay cả oracle cũng chỉ lợi −0,04% năng lượng.
   Quét trọng số năng lượng 0/16/64 không tạo được trade-off front: policy gần như không đổi so với warm start, dù DVR vẫn thấp hơn heuristic
   ở 9/9 run. Tính trên mỗi task được gửi đến, mọi policy RL tốn năng lượng hơn `SHORTEST_FINISH` 1,7–3,0%, vì chúng hoàn thành đúng hạn nhiều task hơn.

## 1. Mốc so sánh H4 (evaluation v2.1)

`target/mec/h4-baselines-eval21`: 12 biến thể × 15 policy × 150 episode = 27.000 episode. Verifier PASS (180 trace, 262.440 kết quả task).
Bảng đầy đủ: [data/h4-eval21-summary.csv](data/h4-eval21-summary.csv).

Biến thể chính, 4 heuristic tốt nhất:

| Policy | DVR % [KTC 95%] | J biên/task | Latency TB / P95 (s) | Offload |
|---|---|---:|---|---:|
| `SHORTEST_FINISH+EDF+NONE` | 6,12 [5,70; 6,52] | 19,56 | 6,11 / 24,23 | 0,23 |
| `THRESHOLD_5+EDF+NONE` | 6,81 [6,50; 7,13] | 21,26 | 6,55 / 24,76 | 0,50 |
| `DEADLINE_ENERGY+EDF+DROP_INFEASIBLE` | 6,88 [6,54; 7,23] | 21,01 | 8,34 / 39,47 | 0,59 |
| `DEADLINE_ENERGY+EDF+NONE` | 7,12 [6,75; 7,47] | 21,20 | 8,37 / 39,62 | 0,59 |

**G6 trên evaluation** (`h4-oracle-eval21`, `ORACLE_ITER:SHORTEST_FINISH+EDF+NONE`, 10 episode): có preemption,
DVR 4,74% → 0,06% (−4,68 điểm), J biên 19,06 → 16,70 (−12,4%); không preemption, 17,56% → 5,07% (−12,50 điểm).
G6 qua. Dữ liệu: [data/h4-eval21-g6.json](data/h4-eval21-g6.json).

## 2. H5a: RL quyết định offloading

### Thiết lập

| Thành phần | Giá trị |
|---|---|
| Bước quyết định | Mỗi task đến; hành động LOCAL / UAV |
| Quan sát | 19 đặc trưng của `MecGymBridge.features`: đúng thông tin heuristic thấy (khối lượng ước lượng, deadline, hàng đợi, kênh, dự báo) |
| Scheduler | EDF có preemption (Java), không admission |
| Phần thưởng | +1 task đúng hạn, −1 task vi phạm, −λ·(năng lượng biên)/100, cộng dồn giữa hai quyết định |
| Thuật toán | PPO (SB3 2.6), MLP 128×128, lr 1e-4, clip 0,1, γ = 0,99, GAE 0,95, 8 môi trường song song, 2 triệu bước |
| Khởi động | Bắt chước `SHORTEST_FINISH` trên 30 episode huấn luyện (độ chính xác 99,5%; DVR validation 4,97% so với 4,89% của giáo viên) |
| Chọn checkpoint | DVR thấp nhất trên 20 episode validation, đo mỗi 200.000 bước |
| Chọn λ ∈ {1, 4} | Trung bình 5 seed trên toàn bộ 150 episode validation: λ = 4 → 2,61%; λ = 1 → 3,58% (giáo viên: 4,73%) |

Mọi lựa chọn đều chỉ dùng validation. Nhật ký huấn luyện: [data/h5-training-logs.json](data/h5-training-logs.json),
[data/h5a-selection.json](data/h5a-selection.json).

### Kết quả trên evaluation (`target/mec/h5-rl-eval21`)

Verifier PASS: 3.750 episode, 150 nhóm cùng workload (RL và heuristic nhận đúng cùng đầu vào), 10 trace RL được tính lại toàn bộ.

| Policy | DVR % [KTC 95%] | Chênh DVR ghép cặp (điểm) [KTC] | Thắng/thua (cặp) | J biên/task | Chênh J | Latency TB / P95 |
|---|---|---|---|---:|---|---|
| `SHORTEST_FINISH+EDF` | 6,12 [5,71; 6,55] | — | — | 19,56 | — | 6,11 / 24,23 |
| RL λ=4, seed 0 | 3,85 [3,54; 4,16] | −2,27 [−2,41; −2,14] | 150/0 | 19,26 | −1,57% | 5,65 / 21,33 |
| RL λ=4, seed 1 | **3,22** [2,93; 3,50] | −2,90 [−3,05; −2,74] | 150/0 | 19,17 | −2,00% | 5,59 / 21,38 |
| RL λ=4, seed 2 | 3,46 [3,19; 3,73] | −2,66 [−2,83; −2,49] | 150/0 | 19,27 | −1,49% | 5,67 / 21,60 |
| RL λ=4, seed 3 | 3,75 [3,44; 4,06] | −2,37 [−2,51; −2,24] | 150/0 | 19,21 | −1,81% | 5,62 / 21,27 |
| RL λ=4, seed 4 | 3,60 [3,32; 3,91] | −2,52 [−2,67; −2,37] | 150/0 | 19,28 | −1,43% | 5,68 / 21,62 |

Khoảng tin cậy của chênh năng lượng cũng không chứa 0 ở cả 5 seed.
Theo lớp task (seed 1 / heuristic): DETECT 3,04 / 6,34%; SEGMENT 4,38 / 7,85%; MAP 0,27 / 0,43%.
RL offload nhiều hơn heuristic (36–43% task so với 23%).
Lifetime UAV: 150/150 episode còn pin tới horizon, chỉ có cận dưới (censored).
Dữ liệu: [data/h5-eval21-summary.csv](data/h5-eval21-summary.csv), [data/h5-eval21-paired.csv](data/h5-eval21-paired.csv).

### 2b. H5a-long: huấn luyện tiếp 2 triệu bước ([experiments/h5a-long.json](../../experiments/h5a-long.json))

Mỗi seed tiếp tục từ checkpoint H5a đã chọn, cùng siêu tham số, không bắt chước lại. Checkpoint chọn trên 20 episode validation,
trong đó bước 0 chính là policy H5a. Validation đầy đủ: 2,523 / 2,016 / 2,537 / 2,051 / 2,172% (seed 0–4), tốt hơn H5a ở cả 5 seed.
Evaluation (`target/mec/h5a-long-eval21`, verifier PASS, 150 nhóm cùng workload):

| Seed | Checkpoint | DVR % [KTC] | (H5a) | Chênh DVR vs heuristic [KTC] | Thắng/thua | J biên/task | Chênh J [KTC] | Latency TB / P95 |
|---|---|---|---:|---|---|---:|---|---|
| 0 | 1,6 triệu | 2,97 [2,78; 3,16] | 3,85 | −3,15 [−3,46; −2,82] | 134/15 | 19,62 | +0,28% [−0,17; +0,75] | 6,47 / 27,59 |
| 1 | 1,0 triệu | **2,59** [2,40; 2,77] | 3,22 | −3,53 [−3,80; −3,26] | 150/0 | 19,31 | −1,27% [−1,63; −0,88] | 5,96 / 23,93 |
| 2 | 1,2 triệu | 3,00 [2,83; 3,19] | 3,46 | −3,11 [−3,45; −2,77] | 133/14 | 19,58 | +0,09% [−0,37; +0,57] | 6,50 / 27,91 |
| 3 | 1,0 triệu | 2,67 [2,48; 2,87] | 3,75 | −3,45 [−3,70; −3,19] | 150/0 | 19,40 | −0,81% [−1,19; −0,41] | 6,00 / 24,05 |
| 4 | 1,2 triệu | 2,70 [2,52; 2,88] | 3,60 | −3,42 [−3,73; −3,12] | 145/4 | 19,48 | −0,43% [−0,86; +0,01] | 6,18 / 25,40 |

Heuristic `SHORTEST_FINISH+EDF`: 6,12%, 19,56 J, 6,11 / 24,23 s. Policy học thêm chủ yếu giảm vi phạm của lớp DETECT
(1,09–1,70% so với 6,34%) bằng cách chấp nhận tốn thêm năng lượng và kéo dài latency của task khác.
**Lưu ý minh bạch:** evaluation đã được mở cho cả H5a và H5a-long (mỗi policy một lần); việc chọn H5a-long làm policy cuối dựa trên
validation, không dựa trên evaluation. Dữ liệu: `data/h5a-long-*`.

### Độ bền (không dùng để chọn gì; policy giữ nguyên)

Thực hiện trên policy H5a (trước H5a-long).

| Biến thể | Heuristic tốt nhất của biến thể | Chênh DVR của 5 seed RL (điểm) | Thắng/thua | Chênh J biên |
|---|---|---|---|---|
| Ước lượng sai ±40% | `SHORTEST_FINISH+EDF` 6,13% | −2,14 đến −2,74, KTC không chứa 0 | 150/0 mỗi seed | −1,5 đến −2,1% |
| UAV đứng yên ở tâm | `DEADLINE_ENERGY+EDF+DROP_INFEASIBLE` 4,86% | −1,21 đến −1,84, KTC không chứa 0 | 90–121 / 27–58 | −6,6 đến −7,1% |

Verifier PASS trên cả hai. Dữ liệu: `data/h5-robust-*`.

## 3. Kiểm tra trước khi tin kết quả (plan 7.3)

| Kiểm tra | Kết quả |
|---|---|
| Python cài lại heuristic qua cầu nối cho đúng kết quả Java | `ALL_LOCAL`, `ALL_UAV`, `DEADLINE_ENERGY`, `SHORTEST_FINISH`: khớp chính xác (`drl/test_mec_env.py`) |
| Policy sau bắt chước sát giáo viên (≤ 0,5 điểm) | 4,97% so với 4,89% |
| Báo cáo mọi seed | Có: 10 run H5a và 5 run H5b, kể cả run hỏng |
| Tách seed | Huấn luyện / validation / evaluation không giao nhau; evaluation chỉ mở sau khi chọn checkpoint và λ |
| Chi phí suy luận | MLP 38.531 tham số; mỗi quyết định qua `PPO.predict` (1 luồng, Ryzen 7 5800HS): trung vị 334 µs, P95 495 µs, phần lớn là chi phí của SB3; riêng lan truyền xuôi ≈ 3 µs/mẫu khi chạy theo lô. Đo trong lúc máy đang huấn luyện H5b-v2 |

## 4. H5b: RL chọn task cho CPU UAV

Thiết lập: tại mỗi lần CPU UAV phải chọn và có ≥ 2 ứng viên, policy chọn 1 trong K = 5 ứng viên có deadline sớm nhất
(ứng viên 0 = lựa chọn của EDF; có mask). Offloading = `SHORTEST_FINISH`. MaskablePPO (sb3-contrib 2.6), λ = 4.
Kiểm tra parity: luôn chọn ứng viên 0 cho đúng `SHORTEST_FINISH+EDF` của Java.

**Lần 1 (hỏng do thiết lập).** Bắt chước EDF nghĩa là bắt chước một hành động không đổi (luôn là 0). Sau 40 epoch, xác suất chọn 0
bằng 1,000 ở mọi trạng thái, PPO không còn khám phá. Cả 5 seed cho validation giống hệt EDF ở mọi checkpoint.
Không coi đây là kết quả âm.

**Lần 2** ([experiments/h5b-v2-sched.json](../../experiments/h5b-v2-sched.json), đăng ký trước): label smoothing 0,3 khi bắt chước,
hệ số entropy 0,01. Kết quả (`target/mec/h5b2-rl-eval21`, verifier PASS, 150 nhóm cùng workload):

| Seed | Checkpoint chọn | DVR validation đầy đủ | DVR evaluation | Chênh DVR ghép cặp [KTC] | Chênh J biên [KTC] |
|---|---|---:|---:|---|---|
| 0 | bước 0 (= EDF) | 4,727% | 6,119% | 0 | 0 |
| 1 | bước 0 (= EDF) | 4,727% | 6,119% | 0 | 0 |
| 2 | 1,4 triệu | 4,727% | 6,119% | 0 | −0,00% |
| 3 | 1,2 triệu | 4,727% | 6,119% | 0 | −0,00% |
| 4 | 2 triệu | 4,755% | 6,124% | +0,005 [−0,019; +0,028] | −0,13% [−0,17; −0,10] |

`SHORTEST_FINISH+EDF` trên cùng seed: DVR 6,119%, 19,56 J. Chẩn đoán trên 400 trạng thái validation: sau 400.000 bước, xác suất chọn
ứng viên EDF giảm từ 0,78 xuống 0,63 (policy có thay đổi) nhưng hành động có xác suất cao nhất vẫn luôn là EDF; khi policy bắt đầu
lệch khỏi EDF (sau 1,6–1,8 triệu bước, seed 0, 1, 3) thì DVR validation tăng (4,92–5,02%).

**Kết luận H5b:** trong `v2.1-main`, chọn thứ tự task trên CPU UAV bằng RL không cải thiện EDF có preemption. Không có bằng chứng
cho việc học scheduling; khoảng trống của bài toán nằm ở quyết định offloading. Dữ liệu: `data/h5b2-*`.

## 4b. H5d: mở rộng agent offloading ([experiments/h5d-offload-ext.json](../../experiments/h5d-offload-ext.json))

Ở phần này năng lượng được đo bằng **J biên trên mỗi task được gửi đến** (marginal J / offered). Không dùng J trên mỗi task đúng hạn, vì một policy
có thể hạ chỉ số đó bằng cách bỏ task tốn kém.

**Lưu ý về H5a-long khi đo theo task được gửi đến.** RL trọng số 4 tốn 18,94 J/task, còn `SHORTEST_FINISH+EDF` tốn 18,39 J/task, tức RL
tốn hơn khoảng 3%. Lý do là RL hoàn thành đúng hạn nhiều task hơn (DVR 2,79% so với 6,12%), và mỗi task hoàn thành đều tiêu năng lượng.
Vì vậy câu "RL tiết kiệm năng lượng" chỉ đúng khi tính trên mỗi task đúng hạn (mục 2b), không đúng khi tính trên mỗi task được gửi đến.

**H5d-1: thêm hành động REJECT lúc task đến. Gate không đạt, không huấn luyện.** Gate dùng oracle biết trước tương lai, trên 6 episode
phát triển. `ORACLE_ITER_R` (được phép reject) đạt 0,011% DVR và 16,689 J/task; `ORACLE_ITER` (không được reject) đạt 0,011% và 16,696 J/task.
Chênh 0 điểm DVR và −0,04% năng lượng, dưới ngưỡng đăng ký trước (0,5 điểm hoặc 3%). Ngay cả khi biết trước tương lai, quyền reject
gần như vô dụng trong kịch bản này, nên không đáng huấn luyện agent có hành động REJECT.

**H5d-2: quét trọng số năng lượng 0 / 16 / 64. Giả thuyết không được ủng hộ.** Mỗi trọng số 3 seed, warm start từ H5a-long, 2 triệu bước.
Checkpoint chọn theo objective của chính trọng số đó trên validation (sửa đổi đã đăng ký trước khi chạy). Chạy trên brev-h100 (CPU),
evaluation `target/mec/h5d2-front-eval21`, verifier PASS (0 lỗi).

| Trọng số | Seed | DVR % | J/task gửi đến | Chênh DVR vs heuristic [KTC] | Thắng/thua | Chênh J/task đúng hạn [KTC] |
|---|---|---:|---:|---|---|---|
| 0 | 0 | 2,67 | 18,82 | −3,45 [−3,75; −3,13] | 142/7 | −1,19% [−1,60; −0,75] |
| 0 | 1 | 2,51 | 18,88 | −3,61 [−3,89; −3,31] | 147/1 | −1,05% [−1,44; −0,60] |
| 0 | 2 | 2,94 | 18,71 | −3,18 [−3,49; −2,85] | 140/10 | −1,47% [−1,93; −1,00] |
| 16 | 0 | 3,28 | 18,85 | −2,84 [−3,16; −2,52] | 127/21 | −0,36% [−0,84; +0,11] |
| 16 | 1 | 2,30 | 18,73 | −3,82 [−4,12; −3,53] | 150/0 | −2,04% [−2,44; −1,62] |
| 16 | 2 | 3,08 | 18,87 | −3,04 [−3,35; −2,73] | 132/17 | −0,48% [−0,96; −0,02] |
| 64 | 0 | 3,10 | 18,93 | −3,02 [−3,33; −2,71] | 137/13 | −0,16% [−0,61; +0,32] |
| 64 | 1 | 2,63 | 18,77 | −3,49 [−3,75; −3,23] | 150/0 | −1,47% [−1,85; −1,07] |
| 64 | 2 | 3,10 | 18,91 | −3,01 [−3,34; −2,68] | 134/14 | −0,27% [−0,71; +0,18] |

Trung bình theo trọng số: w0 2,71% / 18,80 J; w4 (H5a-long) 2,79% / 18,94 J; w16 2,88% / 18,82 J; w64 2,94% / 18,87 J.
Heuristic `SHORTEST_FINISH+EDF`: 6,12% / 18,39 J. Có 12/15 heuristic (80%) bị ít nhất một trọng số RL trội. Ba heuristic không bị trội:
`SHORTEST_FINISH+EDF+NONE` (18,39 J), `DEADLINE_ENERGY+SRPT+DROP_INFEASIBLE` (7,22%, 18,68 J) và `ALL_LOCAL+EDF+NONE` (32,2%, 9,38 J).
Cả ba đều tốn ít năng lượng hơn mọi điểm RL. Dữ liệu: `data/h5d2-front.json`.

**Vì sao không có front:** trọng số gần như không làm thay đổi policy. Trên validation, J/task gửi đến của w64 chỉ đi từ 18,65 xuống 18,54
sau 2 triệu bước (<1%), và DVR chỉ dao động trong khoảng 1,8–2,3%. Nếu tối ưu đúng objective của w64 thì policy phải chuyển nhiều task về xử lý
local (ALL_LOCAL chỉ tốn 9,4 J/task): phạt năng lượng khoảng 12 đơn vị/task, lớn hơn nhiều so với thưởng ±1 cho mỗi task đúng hạn.
Vì vậy đây là **thất bại tối ưu**, không phải bằng chứng rằng front không tồn tại. Các nguyên nhân khả dĩ (chưa kiểm chứng): warm start từ
policy w4 (critic khớp với thang thưởng cũ), PPO clipping làm policy chỉ nhích từng bước nhỏ, và 2 triệu bước là ít so với mức thay đổi
hành vi cần có. Muốn có front thật thì phải chạy một thí nghiệm mới, đăng ký trước, không warm start, hoặc warm start nhưng có giai đoạn
huấn luyện lại critic.
**Kết luận dùng được:** ở mọi trọng số đã thử, RL vẫn giữ ưu thế DVR so với heuristic (9/9 run, KTC không chứa 0). Tuy nhiên luận văn
không thể khẳng định RL tạo ra một trade-off front giữa deadline và năng lượng.

## 5. Giới hạn

- Một kịch bản chính (`v2.1-main`), tham số loại G chưa đo thực tế; xem [MODEL_V21.md](MODEL_V21.md).
- RL chỉ học offloading; scheduler EDF có preemption và heuristic giữ nguyên.
- Phần thưởng gán toàn cục (task kết thúc giữa hai quyết định), không gán cho đúng quyết định gây ra.
- 2 triệu bước mỗi seed; ở hầu hết seed checkpoint tốt nhất là bước cuối, nên có thể còn cải thiện với ngân sách lớn hơn.
- Không có kiểm định thống kê chính thức ngoài khoảng tin cậy bootstrap ghép cặp.
- Kết quả trong mô phỏng; không chứng minh hành vi trên phần cứng thật.

## 6. Lệnh tái lập

```powershell
mvn -o -q compile exec:java "-Dexec.mainClass=uav.mec.MecRunner" "-Dexec.args=experiments/h4-baselines-eval21.json"
mvn -o -q exec:java "-Dexec.mainClass=uav.mec.MecRunner" "-Dexec.args=experiments/h4-oracle-eval21.json"
bash scripts/h5_pipeline.sh        # H5a + đánh giá + verifier + báo cáo
bash scripts/h5_robustness.sh      # độ bền
bash scripts/h5a_long.sh           # H5a-long
```

Code của các kết quả âm tính (H5b, H5d-1, H5d-2) đã được gỡ khỏi nhánh ngày 16/11/2026 (xem README). Để chạy lại:
`git checkout v2-h5-full`, rồi `bash scripts/h5_pipeline.sh` (bản có H5b lần 1), `bash scripts/h5b_v2.sh`,
`MecRunner experiments/h5d-gate-reject.json`, `PY=python bash scripts/h5d2_server.sh` và `scripts/h5d_front.py`.
