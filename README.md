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

Trạng thái 12/11/2026: P0–P5 xong. Cổng G1–G5 qua không cần chỉnh tham số; `DEADLINE_ENERGY` + EDF có preemption là
baseline mạnh nhất; **G6 không qua** (oracle chỉ hơn ≤ 1,6 điểm DVR), nên cần chọn hướng trước khi làm RL.
Đọc [RESULTS_BASELINES.md](docs/v2/RESULTS_BASELINES.md), [CALIBRATION.md](docs/v2/CALIBRATION.md), [MODEL.md](docs/v2/MODEL.md).

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
