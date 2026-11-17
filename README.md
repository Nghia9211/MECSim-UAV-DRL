# MECSim-UAV-DRL

Môi trường nghiên cứu **energy-aware edge offloading cho UAV disaster analytics**,
mở rộng từ MECSim/PureEdgeSim.

Bắt đầu với [tổng quan dự án](PureEdgeSim/uav/PROJECT_OVERVIEW.md).
Hướng dẫn MECSim/PureEdgeSim trước khi dọn được giữ tại
[docs/upstream/MECSim-original.md](docs/upstream/MECSim-original.md).
Scenario, workload, seed protocol và các bộ thực nghiệm của nhánh paper khai báo một lần
trong [`scenarios.json`](scenarios.json): [hướng dẫn registry](PureEdgeSim/uav/SCENARIOS.md).

## v2: lõi offloading + scheduling mới (đang phát triển)

Từ 12/11/2026 phần offloading/scheduling được làm lại trong package `uav.mec`
(nhánh `feat/mec-v2`). Lý do: [chẩn đoán v1](docs/v1-diagnosis/README.md) cho thấy CPU và hàng đợi
gần như không phải nút thắt trong kernel cũ. Đặc tả, hiệu chuẩn và kết quả v2 nằm ở [docs/v2/](docs/v2/).

Trạng thái 16/11/2026. Kịch bản chính là `v2.1-main` (5 MHz, ρ_sys = 0,8, EDF có preemption):
[CALIBRATION_V21.md](docs/v2/CALIBRATION_V21.md), [MODEL_V21.md](docs/v2/MODEL_V21.md).
**Kết quả chính:** RL quyết định offloading (PPO, khởi tạo bằng bắt chước `SHORTEST_FINISH`, trọng số năng lượng 4) đạt DVR
2,6–3,0% trên evaluation, so với 6,1% của heuristic tốt nhất. Thắng ở 5/5 seed, khoảng tin cậy 95% ghép cặp không chứa 0.
Chi tiết: [RESULTS_V21_RL.md](docs/v2/RESULTS_V21_RL.md). Các mốc trước: [RESULTS_BASELINES.md](docs/v2/RESULTS_BASELINES.md),
[CALIBRATION.md](docs/v2/CALIBRATION.md), [MODEL.md](docs/v2/MODEL.md).

Code v2 trên nhánh chỉ còn những phần dẫn tới kết quả dùng được: kernel `uav.mec`, các heuristic, oracle `ORACLE`,
`ORACLE_ITER` và `ORACLE_BEST`, cầu Gym điều khiển offloading (`drl/mec_env.py`, `drl/mec_rl.py`) và verifier.

### Kết quả âm tính (code đã gỡ khỏi nhánh, giữ tại tag `v2-h5-full`)

Ngày 16/11/2026 code của các thí nghiệm dưới đây đã được gỡ. Kết quả, cấu hình đăng ký trước (`experiments/*.json`) và số liệu
(`docs/v2/data/`) vẫn giữ nguyên. Muốn chạy lại thì dùng `git checkout v2-h5-full`.

| Thí nghiệm | Code đã gỡ | Kết quả |
|---|---|---|
| H5b: RL chọn task cho CPU UAV ([h5b-v2-sched.json](experiments/h5b-v2-sched.json)) | `MecSchedEnv`, `--control schedule`, teacher `edf`, `--bc-smoothing`; bước `schedule` của `MecGymBridge` (K = 5 ứng viên theo thứ tự EDF, có mask); `Policy.uavScheduler`; `scripts/h5b_v2.sh`; bước H5b trong `h5_pipeline.sh` | Không vượt EDF có preemption: chênh DVR bằng 0 ở 4/5 seed, seed còn lại +0,005 điểm (khoảng tin cậy chứa 0). Phù hợp lý thuyết: EDF tối ưu trên một CPU có preemption khi tập task còn khả thi. |
| H5d-1: hành động REJECT lúc task đến ([h5d-gate-reject.json](experiments/h5d-gate-reject.json)) | oracle `ORACLE_ITER_R` | Gate không qua: oracle được phép reject chỉ lợi 0 điểm DVR và −0,04% năng lượng (ngưỡng: 0,5 điểm hoặc 3%). Không huấn luyện agent. |
| H5d-2: quét trọng số năng lượng 0/16/64 để có trade-off front ([h5d-offload-ext.json](experiments/h5d-offload-ext.json)) | `--select-rule objective`, `scripts/h5d2_front.sh`, `scripts/h5d2_server.sh`, `scripts/h5d_front.py` | Không tạo được front: policy gần như không đổi so với warm start (J/task thay đổi < 1%), dù DVR vẫn thắng heuristic ở 9/9 run. Đây là thất bại tối ưu, không chứng minh front không tồn tại. |

Lưu ý khi viết về năng lượng: tính trên mỗi task được gửi đến, RL tốn hơn `SHORTEST_FINISH` 1,7–3,0%, vì nó hoàn thành
đúng hạn nhiều task hơn. RL chỉ tiết kiệm năng lượng khi tính trên mỗi task đúng hạn
([RESULTS_V21_RL.md](docs/v2/RESULTS_V21_RL.md) mục 4b).

```powershell
mvn -o -q compile exec:java "-Dexec.mainClass=uav.mec.MecRunner" "-Dexec.args=experiments/smoke.json --smoke"
.\.venv-drl\Scripts\python.exe scripts/verify_mec.py target/smoke/smoke
```

v1 (kernel `uav.offloading`/`uav.scheduling`, luồng paper Azfar, các campaign DRL) đóng băng tại tag `v1-final`:
không thêm thí nghiệm, không xóa. Tài liệu kết quả v1 chuyển sang [docs/history/v1/](docs/history/v1/).

## Trạng thái v1 (đóng băng)

- Baseline mobile/offloading/scheduling với generator `mixed-v2`: **4.320 episode đã audit và recount PASS**.
- `CONTACT_GREEDY` tốt nhất trung bình về delivered DVR và J/delivered trong đợt development.
  Nó bay tới một điểm rồi hover trong cả480episode; chưa chứng minh đóng góp riêng của scheduling/joint control.
- Một layout42,30task seed development, cùng source pools RescueNet+Alibaba.
  Compute/deadline vẫn là giả định; chưa có kết luận tổng quát hoặc RL vượt heuristic.
- Nhánh tái hiện paper về lifetime được giữ riêng; không dùng lifetime paper làm kết quả task scheduling.

Đọc [kết quả mixed-v2](docs/history/v1/WORKLOAD_V2_BASELINES_RESULTS.md),
[trạng thái sửa workload](docs/history/v1/WORKLOAD_REPAIR.md) và
[quy ước metric](PureEdgeSim/uav/EVALUATION_METRICS.md).

## Chạy từ thư mục gốc repository

Yêu cầu: JDK17, Maven, Python3.11 với dependencies trong
[drl/requirements.txt](drl/requirements.txt).
Raw dữ liệu và artifact không đi kèm Git:
[DATASET_SETUP.md](docs/history/v1/DATASET_SETUP.md).

```powershell
mvn -o test
.\scripts\build-drl.ps1 -Offline
.\.venv-drl\Scripts\python.exe -u -m drl.workload_baselines --output target/baselines-new --smoke
.\.venv-drl\Scripts\python.exe -u -m drl.workload_baselines --output target/baselines-full-new
```

Output phải mới. Bỏ `-o`/`-Offline` nếu cần Maven tải dependency.
Không chạy `mvn clean` khi cần giữ artifact trong `target/`.
Runner baseline dùng development partition, không train lại DQN/PPO.
Các entrypoint train lịch sử vẫn dùng protocol riêng; không gọi chúng là mixed-v2 nếu chưa đổi protocol.

## Xem đường bay và so sánh

Double-click [Open-UAV-Dashboard.cmd](Open-UAV-Dashboard.cmd).
[VISUALIZATION.md](docs/history/v1/VISUALIZATION.md) ghi rõ bộ kết quả dashboard đang nạp;
không mặc định mọi campaign mới đã xuất hiện trong UI.

## Tìm đúng phần

| Phần | Nơi đọc |
|---|---|
| Tổng quan, phạm vi và việc còn thiếu | [PROJECT_OVERVIEW.md](PureEdgeSim/uav/PROJECT_OVERVIEW.md) |
| Kernel offloading + scheduling | [OFFLOADING_SCHEDULING.md](PureEdgeSim/uav/OFFLOADING_SCHEDULING.md) |
| UAV di chuyển và chọn điểm phục vụ | [ADAPTED_PAPER_SERVICE.md](docs/history/v1/ADAPTED_PAPER_SERVICE.md) |
| Contact PPO đã chạy trên workload cũ | [CONTACT_PPO_RESULTS.md](docs/history/v1/CONTACT_PPO_RESULTS.md) |
| Đối chiếu paper | [PAPER_ALIGNMENT.md](PureEdgeSim/uav/PAPER_ALIGNMENT.md) |
| Tài liệu các giai đoạn trước | [docs/history/README.md](docs/history/README.md) |
| Source prototype đã nghỉ | [legacy/README.md](legacy/README.md) |

Dataset, kết quả server và source snapshot thí nghiệm được giữ nguyên.

Chi tiết đợt dọn và cách khôi phục: [CLEANUP_20261030.md](docs/CLEANUP_20261030.md).
