# DQN chọn thiết bị trong môi trường offloading + scheduling mở rộng

Ngày 23/10/2026. Đây là **adapter và train development**, tách khỏi
`drl.run` / `PaperGymBridge` của paper. Không dùng checkpoint paper cũ cho state
mới; không gọi kết quả này là tái hiện DQN của Azfar.

## Quyền quyết định và điều kiện thực thi

- DQN chọn **thiết bị UAV phục vụ tiếp theo**, 12 action tương ứng 12 ID.
- Offloading mặc định `ALL_UAV_WHEN_COVERED`, CPU UAV `EDF`, local `FIFO`.
  Các policy này giữ cố định trong một run; DQN chưa học routing hoặc CPU order.
- Gym `step` tiến **kernel Java thật** tới quyết định tiếp theo hoặc hết episode.
  Nhịp quyết định gồm thời gian bay + dwell + upload đang dở; không giả định
  một action = một giây. Mọi task arrival/CPU/energy vẫn chạy theo event.
- ID đã chết được map theo vòng từ ID được yêu cầu tới source còn sống đầu
  tiên. Ghi cả requested/executed action. Nếu tất cả source chết hoặc UAV chết,
  không hỏi action nữa; CPU ground/background còn sống tiếp tục tới horizon.
- Horizon 600 s là **kết thúc bài toán hữu hạn**, trả `terminated=True`, không
  bootstrap Q sau horizon. Task chưa hoàn tất được tính miss tại đây. Không
  kết thúc sớm khi pin UAV cạn để tránh bỏ qua hậu quả và chi phí về sau.
- Không thay quy tắc task ngoài coverage: xử lý local ngay, chưa chờ UAV/retry.

## State: 129 số chuẩn hóa

9 số global, theo thứ tự:

```text
time/horizon, x/area, y/area, UAV battery fraction,
estimated queued compute seconds/horizon, UAV queued jobs/100,
ongoing uploads/100, UAV alive, minimum UAV deadline slack/horizon
```

Mỗi thiết bị có 10 số (12 ×10):

```text
x/area, y/area, battery fraction, age/horizon, connected, alive,
estimated local queued compute seconds/horizon, local jobs/100,
minimum local deadline slack/horizon, previous-target indicator
```

Queue gồm task đã admit còn chờ/đang chạy; queue UAV gồm upload chưa xong.
Work dùng estimated MI trừ work đã thực hiện, không dùng actual remaining MI.
Empty minimum slack =1; work/count/slack được clip vào [0,1]. State được lấy
sau completion/expiry/death và trước arrival/dispatch cùng timestamp.

Không cung cấp task tương lai, danh sách raw ảnh/mask, actual task cost chưa
quan sát hay kết quả chưa xảy ra. Đây là **state tổng hợp, có mất thông tin
hàng đợi**, chưa khẳng định Markov đầy đủ; DQN MLP là baseline phát triển.

## Objective và reward đã khai báo

Với các đại lượng tích lũy tới thời điểm t:

```text
U(t) = delivered_on_time
       − image_misses
       − 0.25 × background_misses
       − 0.05 × image_resolution_latency_seconds / 60
       − 0.1 × total_system_energy_joules / 10000

r(step) = U(t_after) − U(t_before)
```

- `delivered_on_time`: ảnh hoàn tất đúng hạn và kết quả tới trung tâm qua UAV
  hoặc source local connected. Local disconnected không nhận bonus delivery.
- `image_misses`: ảnh late/expired/drop/unfinished; ảnh local hoàn tất đúng hạn
  nhưng disconnected chưa được gọi là deadline miss, đồng thời không có bonus.
- Latency của mọi ảnh đã resolve, kể cả failed/unfinished, là resolve−arrival.
  Đây là **time-to-resolution**, không phải mean latency chỉ trên successful tasks.
- Energy tính tất cả source và UAV: flight, hover, CPU, TX, idle. Không chỉ tính
  marginal CPU energy. Không có bonus cho số lần chọn node hoặc số lần offload.
- Tổng reward episode bằng U(horizon), không chia theo số action. `gamma=1`
  giữ objective hữu hạn này khi các step có duration khác nhau; không dùng gamma
  theo decision để vô tình ưu tiên step dài/ngắn. Chưa có safety constraint học.

Các hệ số là **lựa chọn development**, chưa là đóng góp khoa học hoặc trọng số
được hiệu chuẩn. Reward kết hợp nhiều tiêu chí thành scalar, chưa là thuật toán
Pareto đa mục tiêu. DVR và delivery rate phải báo cáo riêng để thấy mất kết nối.

## Dữ liệu, seed và train

Dùng pool RescueNet449 + Alibaba1000 sẵn có và mapping cũ. Workload vẫn resample
kích thước/cost, arrival Poisson và deadline synthetic; không phải replay trace
nguyên bản hoặc đo inference. Source pool chung cho train/validation/test, nên
holdout task seed **không phải holdout ảnh/job gốc**.

Mặc định giữ local500 MI/s, vùng250 m, layout42, 12 thiết bị và8 connected,
pin UAV1.600.000 J, tải image0,24/background0,10 task/s, horizon600 s. Không
âm thầm hạ CPU local để làm DQN có lợi. Lệnh diagnose đo riêng grid local
500/125/50 MI/s × ALL_UAV/DEADLINE_ENERGY/ALL_LOCAL × RR/Oldest/Random.

Training task seeds [0,1.000.000), validation từ1.000.000, test từ2.000.000.
Chọn checkpoint theo **mean validation reward**, không theo test. Mặc định
layout training cố định; đánh giá unseen layout là một thí nghiệm riêng.

DQN development: MLP64/64 ReLU, learning rate0,0003, gamma1, batch64,
buffer100.000, warm-up128, train mỗi4step/1gradient, target update500step,
epsilon1→0,05 trong50% bước. Các thông số này **không phải config paper**.
Một Torch thread, CPU. Chưa cần GPU cho mạng nhỏ này.

Từ thư mục repo, dùng đúng Python đã cài requirements:

```powershell
.\scripts\build-drl.ps1 -Offline
.\.venv-drl\Scripts\python.exe -m unittest drl.test_mobile -v
.\.venv-drl\Scripts\python.exe -m drl.mobile_run diagnose --seeds 10 --output target/mobile-signal-new
.\.venv-drl\Scripts\python.exe -m drl.mobile_run train --steps 2000 --seed 0 --output target/mobile-dqn-new
```

Linux tương đương:

```bash
mvn compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath
.venv-drl/bin/python -m unittest drl.test_mobile -v
.venv-drl/bin/python -u -m drl.mobile_run train --steps 2000 --seed 0 --output target/mobile-dqn-new
.venv-drl/bin/python -u -m drl.mobile_run evaluate target/mobile-dqn-new --episodes 30 --unseen-layouts
```

Có thể dùng runner Linux (dùng venv/dataset đã có, tự build và chạy test trước):

```bash
STEPS=2000 SEED=0 bash scripts/train-mobile-server.sh --dry-run
STEPS=2000 SEED=0 bash scripts/train-mobile-server.sh
```

Runner này chưa được chạy trên server trong lần triển khai local này.

`PaperGymBridge --classpath` ở lệnh build chỉ xuất classpath/runtime Java,
không chọn environment dùng để train. Adapter mới khởi chạy `MobileGymBridge`.

## Artifact và tiêu chí cho phép chạy dài

- `config.json`: state/reward/config/hyperparameters, source hashes, status,
  số gradient updates và runtime. `source/` lưu snapshot dùng cho run.
- `validation.csv`, `progress.csv`, `train.monitor.csv`, `best_model.zip`,
  `final_model.zip`, `checkpoint.zip`: checkpoint được train trên adapter mới.
- `evaluation-*/episodes.csv`, `summary.csv`: DQN/RR/Oldest/Random dùng cùng
  task/layout seed. `trace-*` của seed đầu lưu physical trace + transitions.
- `scripts/verify-uav-mobile-trace.py TRACE_DIR`: replay CPU/energy/flight/
  coverage, đối chiếu requested/executed action, toàn bộ129feature và reward.
  Không chạy lại Java và không chỉ đọc summary để tuyên bố pass.

Trước khi chạy dài: phải có gradient updates, reward finite/không hằng theo
action, trace audit đạt, terminal drain đúng và checkpoint load/evaluate được.
Một run ngắn đạt các điều kiện này chỉ chứng minh **pipeline train hoạt động**.
Chưa chứng minh hội tụ hay vượt heuristic; cần nhiều training seed, layout,
ablation reward và kiểm định paired trước khi có kết luận nghiên cứu.

Xem mô hình gốc của extension tại [ADAPTED_PAPER_SERVICE.md](ADAPTED_PAPER_SERVICE.md).

## Kết quả local đã kiểm chứng ngày 23/10/2026

- **100 Java tests đạt** (gồm5 test controller mới), **8 test Gym mới đạt**,
  **17 regression tests Python cũ đạt** với dataset. Gym check, deterministic
  reset, causal state, terminal accounting và corruption tests đều đạt.
- Diagnostic: [270 episode trên10 task seed](../../target/mobile-signal-20261023/summary.csv),
  9 cấu hình local/routing ×3 selector. Có **27 trace seed đầu** được audit độc
  lập toàn bộ physics/queue/observation/reward; không gọi mọi270 episode đã audit.
  [Biên bản kiểm tra](../../target/mobile-signal-20261023/verification.json).
- Train: [mobile-dqn-smoke-20261023](../../target/mobile-dqn-smoke-20261023/),
  seed0, **2.000 decision steps / 468 gradient updates**, learning+validation
  khoảng16,16 s trên local CPU (không gồm build, audit và final evaluation).
  Checkpoint best theo validation nằm tại bước1.000; final ở bước2.000.
  [Kiểm tra trọng số và checkpoint](../../target/mobile-dqn-smoke-20261023/training-verification.json):
  13.260 Q-network parameters, trọng số finite và thực sự thay đổi so với
  khởi tạo cùng seed; source snapshot69file khớp lúc kiểm tra.
- Final evaluation: **10 task seeds mới ×4 policy =40 episode**, layout42,
  offloading ALL_UAV_WHEN_COVERED và CPU EDF cố định.
  [Bảng đầy đủ](../../target/mobile-dqn-smoke-20261023/evaluation-20261023-093026-193569/summary.csv).
  Cả4 trace của seed test đầu đều audit đạt; **không gọi cả40 episode đã audit**.

| Policy | Mean reward ↑ | Image DVR ↓ | Total energy (kJ) ↓ | Images delivered on time ↑ |
| --- | ---: | ---: | ---: | ---: |
| DQN, best validation checkpoint | 22,74 | 19,78% | 62,82 | 39,3 |
| Round Robin | 23,39 | 18,60% | 73,26 | 39,1 |
| Oldest Data | 21,39 | 20,34% | 70,40 | 38,4 |
| Random | 22,78 | 19,25% | 71,17 | 39,0 |

Các số là mean theo10 paired task seeds, cùng pool source; bảng CSV có SD.
DQN chưa vượt Round Robin về reward/DVR; năng lượng thấp hơn không tự chứng
minh thuật toán tốt hơn. Đây là một training seed và lượt ngắn, chưa kiểm định
thống kê, chưa thể kết luận hội tụ, superiority hoặc robustness.

Diagnostic xác nhận nguy cơ của cấu hình:

- Local500 + DEADLINE_ENERGY chỉ offload khoảng0,4–0,8 ảnh/episode. ALL_LOCAL
  cũng đạt DVR khoảng9,15%, nên có ít cơ hội cải thiện routing bằng UAV.
- Local125/50 khiến ALL_LOCAL miss100% deadline ảnh trong grid này. Chỉ hạ CPU
  để tạo ưu thế cho UAV sẽ thành một benchmark quá cực đoan nếu không hiệu chuẩn.
- ALL_UAV có reward khác nhau giữa selector, action thay đổi trajectory/coverage/
  pin/outcome: tín hiệu không hằng. Tuy nhiên support rate thấp và forced upload
  có thể làm deadline tệ hơn xử lý local.

**Bước tiếp theo:** hiệu chuẩn chi phí ảnh/CPU/deadline và chọn các mức tải có
trade-off thực sự; xác định có cho task chờ UAV hay không (đây là thay đổi model,
chưa implement); đóng băng reward/protocol trước khi train dài nhiều training
seed và kiểm tra layout chưa gặp. Với trọng tâm scheduling, cần tiếp tục ablation
giữ selector/routing giống nhau và chỉ thay CPU scheduler để đo đúng đóng góp.
Code mới chưa push GitHub hoặc chạy trên aiotlab92 trong lượt này.
