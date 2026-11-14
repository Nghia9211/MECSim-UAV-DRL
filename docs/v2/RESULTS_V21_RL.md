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
2. **Ưu thế giữ nguyên khi đổi điều kiện mà policy chưa từng thấy:** ước lượng sai ±40% (−2,14 đến −2,74 điểm) và UAV đứng yên
   (−1,21 đến −1,84 điểm so với heuristic tốt nhất của chính biến thể đó, kèm −6,6 đến −7,1% năng lượng).
3. **RL lấy được khoảng một nửa khoảng trống.** Oracle biết trước tương lai đạt DVR 0,06% trên 10 episode evaluation, so với 4,74%
   của `SHORTEST_FINISH` trên cùng 10 episode.
4. **RL cho scheduling trên CPU UAV (H5b) chưa có kết quả dương.** Lần 1 hỏng do thiết lập (mục 4). Lần 2: (điền sau khi chạy xong).

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

### Độ bền (không dùng để chọn gì; policy giữ nguyên)

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
hệ số entropy 0,01. (điền sau khi chạy xong)

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
bash scripts/h5_pipeline.sh        # H5a + H5b lần 1 + đánh giá + verifier + báo cáo
bash scripts/h5_robustness.sh      # độ bền
bash scripts/h5b_v2.sh             # H5b lần 2
```
