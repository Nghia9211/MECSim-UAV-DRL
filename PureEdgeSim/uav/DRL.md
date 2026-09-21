# DRL trên môi trường MECSim theo bài báo

Đã có luồng Gymnasium → Stable-Baselines3 → `PaperGymBridge` →
`PaperSimulation.Manager`. Mọi bước bay, pin, task, CPU và data age vẫn do Java
tính. Python chỉ chọn thiết bị tiếp theo và huấn luyện mạng. Đây là implementation
theo mô tả paper và các quy ước trong [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md),
không phải source gốc của tác giả hoặc cam kết tái lập chính xác số liệu báo cáo.

## Cài đặt và build

Chạy tại `uav/MECSim`, Java 17, Maven, Python 3.11:

```powershell
python -m venv .venv-drl
.\.venv-drl\Scripts\python.exe -m pip install -r drl/requirements.txt
.\scripts\build-drl.ps1 -Offline
```

Máy hiện tại đã có `.venv-drl` và thư viện. Môi trường này dùng
`--system-site-packages` để tái sử dụng PyTorch đã có, không sửa Python toàn máy.
Máy mới có thể dùng venv độc lập như lệnh trên. Bỏ `-Offline` nếu chưa có dependency
Maven. Build xuất classpath chính xác vào `target/drl-classpath.txt`, gồm cả JAR
bundled của dự án, và đường dẫn JDK thật ở `target/drl-java.txt` để đóng JVM đúng
trên Windows (tránh launcher Oracle sinh tiến trình con). Build lại sau khi sửa
Java hoặc di chuyển project. Không build
Java/`mvn clean` khi đang huấn luyện vì JVM đọc class từ `target/classes`.

## Huấn luyện DQN

Synthetic, theo workload gốc của paper:

```powershell
.\.venv-drl\Scripts\python.exe -m drl.run train --steps 1000000 --seed 0 --layout-seed 42 --powered 8 --connected 8 --output target/drl-paper-dqn
```

RescueNet + Alibaba, dùng raw dataset đã tải:

```powershell
.\.venv-drl\Scripts\python.exe -m drl.run train --workload datasets --steps 1000000 --seed 0 --layout-seed 42 --powered 8 --connected 8 --output target/drl-mixed-dqn
```

Không cần tải thêm dataset. Đường dẫn mặc định:

- `datasets/raw/rescuenet/validation/val-org-img`
- `datasets/raw/rescuenet/validation/val-label-img`
- `datasets/raw/alibaba2018/batch_task.csv`

Mixed dùng pool 449 ảnh, tối đa 1.000 Alibaba tasks từ tối đa 100.000 dòng đầu;
không đọc toàn bộ trace vào RAM. FIFO CPU 2.000 MIPS, CPU 20 W, workload calibration
và quy tắc drop giữ nguyên [DATASET_EVALUATION.md](DATASET_EVALUATION.md). Đây là
extension dataset, không phải dữ liệu gốc của paper và không chạy neural inference
trên pixel. DQN quan sát pin/tuổi dữ liệu, không trực tiếp đọc ảnh.

Có thể thay đường dẫn/tham số bằng `--property KEY=VALUE`, lặp nhiều lần:

```powershell
.\.venv-drl\Scripts\python.exe -m drl.run train --workload datasets --steps 10000 --property paper.backgroundScale=5
```

`--steps 10000` chỉ là pilot, khác ngân sách 1 triệu bước của paper. Bỏ `--output`
để tạo thư mục timestamp tự động; nếu đặt tên đã tồn tại, chương trình từ chối ghi
đè. Mặc định dùng CPU một thread, phù hợp mạng MLP nhỏ. `--save-replay` lưu thêm
replay buffer DQN, có thể chiếm hàng trăm MB; model ZIP đủ cho inference/evaluation.

## State, action, reward và DQN

| Thành phần | Triển khai |
| --- | --- |
| Observation | `float32[24]`: 12 tỷ lệ pin rồi 12 data age, giữ age nguyên 0…10 |
| Action | `Discrete(12)`, ID 0…11 của thiết bị UAV đến tiếp theo |
| Step | Một slot có độ dài giây biến đổi, Java xử lý event cho đến cuối slot |
| Reset | Layout cố định theo `layout_seed`; pin/age/UAV/clock/queue được khởi tạo lại |
| Terminated | Hỏng hệ thống thật: pin thiết bị/UAV hết hoặc age đạt giới hạn |
| Truncated | Chạm `max_slots` (200 mặc định); được SB3 xử lý khác failure |
| Reward mặc định | `U + ln(max(A,1e-6)/max(O,1e-6))`, khớp reward Java |
| Network | MLP 64–64, ReLU, 12 Q-values |
| Paper hyperparameters | LR 0.0071; gamma 0.98; batch 16; 1.000.000 steps |
| Exploration | Epsilon 1→0.05 trong 35% ngân sách, sau đó giữ 0.05 |
| SB3 DQN | Replay buffer, target network, Bellman/Huber loss, Adam, gradient clipping |

Thông số **không được paper công bố đầy đủ**, chọn tường minh theo SB3 2.6.0:
buffer 1.000.000 transitions; warm-up 100 steps; train mỗi 4 steps; một gradient
update; target update mỗi 10.000 steps; tau 1; max gradient norm 10. Không thêm
Double/Dueling/Prioritized DQN. SB3/Gymnasium được pin ở 2.6.0/1.1.1; phiên bản
Python, Torch, NumPy thực tế lưu vào `config.json`.

Tài liệu API: [SB3 DQN](https://stable-baselines3.readthedocs.io/en/v2.6.0/modules/dqn.html),
[custom Gymnasium environment](https://stable-baselines3.readthedocs.io/en/v2.6.0/guide/custom_env.html).

## Lưu model và đọc kết quả

Mỗi run có:

- `config.json`: seed, workload, tham số, phiên bản, bước thực chạy, optimizer
  updates và `COMPLETE`/`INTERRUPTED`; đọc file này trước khi gọi run là hoàn tất.
- `train.monitor.csv`: reward và số slot của từng training episode.
- `progress.csv`: rollout/optimizer metrics của SB3.
- `validation.csv`: mean/max slot trên validation task seeds, theo training step.
- `best_model.zip`: model có mean lifetime tốt nhất trên validation, giữ model
  trước khi hòa điểm, chỉ chọn sau khi đã có optimizer update;
  `final_model.zip`: sau toàn bộ training; `checkpoint.zip`:
  snapshot định kỳ. Chúng có thể cho kết quả khác nhau.
- `environment/`: layout, cấu hình/pool/hashes dataset khi khởi tạo. CSV slot/task
  ở đây chỉ có header vì chưa thực hiện action; episode trace nằm trong evaluation.
- `source/`: bản chụp source để kiểm tra điều kiện thực nghiệm.
- `evaluation-*/summary.csv`: mean, sample SD, maximum số slot, thời gian vật lý,
  số truncation, CPU energy của DQN và 3 baseline.
- `evaluation-*/episodes.csv`: từng episode, lý do/thiết bị hỏng, pin, CPU/task.
- `evaluation-*/paired.csv`: chênh lệch số slot DRL trừ từng baseline trên cùng
  layout/task seed. Dương nghĩa là DRL kéo dài lifetime hơn trong episode đó.
- `evaluation-*/traces/`: đường bay/pin/data age, CSV giống các lần chạy Java.

Training tự reset với task seed trong `[0,1000000)`. Validation dùng từ 1.000.000;
test sau training dùng từ 2.000.000. Chọn best theo **mean slot validation**, không
chọn bằng test. Mặc định kiểm tra validation mỗi 10.000 bước/5 episode; test 30
episode mỗi policy. Mỗi JVM chỉ chứa một env, tránh registry entity tĩnh bị trộn.

State của paper không chứa layout/hardware hay UAV position. Vì vậy mặc định
train/test cùng layout, khác task seeds. Đây **không phải** đánh giá tổng quát hóa
sang layout mới hoặc 30 independent training seeds. Random baseline dùng NumPy
RNG; hai baseline xác định có cùng tie-breaking với Java.

Đánh giá lại model đã lưu (không huấn luyện lại):

```powershell
.\.venv-drl\Scripts\python.exe -m drl.run evaluate target/drl-mixed-dqn --episodes 30 --traces
.\.venv-drl\Scripts\python.exe -m drl.run evaluate target/drl-mixed-dqn --checkpoint final_model.zip --episodes 30
.\.venv-drl\Scripts\python.exe -m drl.run evaluate target/drl-mixed-dqn --unseen-layouts --episodes 30
```

Lệnh cuối là kiểm tra generalization riêng: mỗi test seed sinh một layout mới.
Không gộp kết quả này với test trên layout đã học. Không dùng kết quả test để
chọn checkpoint/hyperparameter; khi so nhiều lần cần giữ tập test độc lập.

## PPO/A2C, reward ablation và lưới thực nghiệm

`--algorithm PPO` hoặc `--algorithm A2C` dùng cùng env/action/state. Các tham số
PPO/A2C **là lựa chọn triển khai**, không được xác nhận từ paper: MLP64–64 ReLU,
gamma .98; PPO LR .0003, rollout2048, batch64,10epochs,GAE.95,clip.2;
A2C LR .0007,rollout5,GAE1,RMSprop. Chi tiết có trong `model_options()` và config.
PPO có thể chạy quá ngân sách yêu cầu để hoàn thành rollout; đọc `actual_steps`.

`--reward` có 11 lựa chọn của Table 6: `age`, `uptime`, `min_battery`,
`negative_oldest`, `sum`, `log_age`, `log_uptime`, `log_min_battery`,
`negative_log_oldest`, `log_sum`, `paper`. A/O trước step, M sau step, U sau step;
log dùng ln và clamp 1e-6. Các thời điểm/clamp là quy ước, không suy ra chính xác
từ source tác giả. Với reward khác mặc định, `slots.csv` vẫn giữ reward paper
để đối chiếu; Monitor/evaluation ghi reward được chọn.

Lưới Table 5: DQN + reward paper, power/comms `{12,10,8,6,4}`. Lưới Table 6:
DQN/PPO/A2C × 11 reward × scenarios 6/6,8/8,10/8. Xem quy mô trước khi chạy:

```powershell
.\.venv-drl\Scripts\python.exe -m drl.experiments --suite table6 --seeds 3 --output target/table6 --plan-only
.\.venv-drl\Scripts\python.exe -m drl.experiments --suite table5 --seeds 3 --steps 1000000 --output target/table5
```

Table 5 với 3 seed là 75 models; Table 6 là 297 models. Mỗi seed vừa định nghĩa
layout vừa là learning seed; mỗi layout được train riêng vì ID thiết bị mang
nghĩa riêng. `runs.csv` lưu từng run; `summary.csv` tính mean/SD qua **run means**
và maximum quan sát, không coi mọi test episode là independent training runs.
Table 5 báo average, Table 6 báo maximum; không tráo hai metric. Thêm
`--workload datasets` để chạy lưới extension trên mixed workload.

## Kiểm thử và giới hạn còn lại

```powershell
mvn -o test
$env:DRL_TEST_DATASETS='1'
.\.venv-drl\Scripts\python.exe -m unittest drl.test_drl -v
```

Test kiểm tra Gym/SB3 API, reset giữa episode, determinism, terminated/truncated,
trace bằng nhau từng dòng với Java CLI cho synthetic và mixed, lỗi subprocess,
optimizer thực sự đổi trọng số, save/load bảo toàn policy/rollout.

Không tự nhận các pilot là train đủ 1 triệu bước hoặc tái lập Tables 5/6.
SUMO Round Lake/Albany và reward trọng số traffic của case study §5.1 chưa có;
cần road network, flow/density và camera-road mapping trước khi làm phần đó.
Sẽ cần chuẩn bị dữ liệu SUMO khi triển khai case study, chưa cần tải lúc này.
Các mơ hồ vật lý (β0, age10/11, output1kB, cap600s) vẫn giữ nguyên trong
`PAPER_ALIGNMENT.md`; có DRL không tự giải quyết chúng.

## Kết quả kiểm chứng triển khai — 21/09/2026

34/34 JUnit tests và 8/8 Python integration tests đã pass, có bật kiểm tra raw
RescueNet + Alibaba. Trace Gym khớp Java CLI từng dòng cho `slots`, `devices`,
`layout`, và thêm task/CPU/summary của mixed. Test dừng JVM cưỡng bức đã xác nhận
trả lỗi thay vì treo/chừa tiến trình con. PPO đã chạy 2.048 bước/10 optimizer
updates; A2C 1.000 bước/200 updates. Đây là smoke tests, không dùng để xếp hạng.

Hai DQN pilot đều train 10.000 bước, 2.475 optimizer updates, learning seed0,
layout42, powered8/connected8; chọn best checkpoint trên validation. Test
10 task seeds 2.000.000…2.000.009, cùng layout42:

| Workload | DQN mean slots | OLDEST_DATA | ROUND_ROBIN | RANDOM |
| --- | --- | --- | --- | --- |
| Synthetic | 17.00 | 17.00 | 10.00 | 10.20 |
| RescueNet + Alibaba | 17.00 | 17.00 | 10.00 | 10.10 |

Không có truncation ở các test này. Run/model/trace:

- `target/drl-pilot-synthetic-10k/`
- `target/drl-pilot-mixed-10k-v2/`
- `target/drl-verified-ppo/` và `target/drl-smoke-a2c/` là smoke comparison.

Mixed pilot còn được kiểm tra trên **5 layout chưa gặp**, với layout/task seed
2.000.000…2.000.004: DQN 10.0 slot, OLDEST_DATA 18.6 ± 5.13 slot (sample SD),
ROUND_ROBIN/RANDOM đều 10.0. Đây là dấu hiệu pilot chưa tổng quát hóa sang layout
mới, không được chỉ báo cáo bảng cùng layout rồi kết luận DQN tốt hơn baseline.
Các lần evaluate tách riêng bằng trường `unseen_layouts` trong `evaluation.json`.

Chưa chạy đủ 1.000.000 bước/model, nhiều independent training seeds hoặc toàn
lưới Table5/6. Các thông số và kết quả này chỉ xác nhận pipeline thực sự chạy/học,
không chứng minh tái lập kết quả paper hay ưu thế của DRL.
