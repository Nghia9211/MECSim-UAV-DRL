# UAV simulation

**Bắt đầu ở đây:** [Tổng quan dự án, những phần đã làm và kế hoạch tiếp theo](PROJECT_OVERVIEW.md).

Chạy từ thư mục `uav/MECSim`, Java 17 và Maven.

## Hướng hiện tại: offloading + task scheduling

Đã có đường local/UAV, CPU/queue/pin từng source và dự báo theo queue/scheduler.
Đọc [OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md) để xem mô hình, policy,
giả định và lệnh benchmark. Đây là extension, không phải reproduce paper/DRL cũ.
Kết quả đã kiểm chứng: [OFFLOADING_RESULTS.md](OFFLOADING_RESULTS.md).

```powershell
.\scripts\run-uav-offloading.ps1 -Seeds 30 -Output target/offloading-new -Offline
python scripts/verify-uav-offloading.py target/offloading-new
```

## Benchmark nền tảng: scheduling với offloading cố định

Đã có queue bền, deadline tính theo giây và baseline FIFO/EDF/Priority trên
RescueNet + Alibaba. Hướng dẫn, phạm vi và kết quả270 episode:
[SCHEDULING.md](SCHEDULING.md).
Scheduler xét deadline/pin/aging, đối chứng SPT và ablation:
[SCHEDULING_AGING_RESULTS.md](SCHEDULING_AGING_RESULTS.md).

```powershell
.\scripts\run-uav-scheduling.ps1 -Seeds 30 -Output target/scheduling-new -Offline
python scripts/verify-uav-scheduling.py target/scheduling-new
```

Đây là luồng task scheduling mới, UAV/offloading cố định; phần DRL bên dưới
thuộc baseline paper chọn thứ tự thiết bị phục vụ.

## DRL: DQN / PPO / A2C

Đã nối Gymnasium với môi trường Java, hỗ trợ synthetic và RescueNet + Alibaba.
Hướng dẫn cài đặt, train/evaluate và đọc model: [DRL.md](DRL.md).

```powershell
.\scripts\build-drl.ps1 -Offline
.\.venv-drl\Scripts\python.exe -m drl.run train --workload datasets --steps 1000000
```

Mặc định DQN theo hyperparameters công bố; các tham số bổ sung được ghi rõ.
Đã có 5 DQN mixed runs × 1 triệu bước. Kết quả, runtime, kiểm tra layout/ID và
độ nhạy: [WEEK1_2_RESULTS.md](WEEK1_2_RESULTS.md). Các run này không đồng nghĩa
tái lập đầy đủ số liệu paper.

Kế hoạch triển khai và thí nghiệm tiếp theo: [NEXT_STEPS.md](NEXT_STEPS.md).
P0 đã có scenario kiểm soát và snapshot trước quyết định:
[FEATURE_CONTRACT.md](FEATURE_CONTRACT.md), [P0_RESULTS.md](P0_RESULTS.md).
P1 đã chạy estimator, SERVICE_AWARE và ablation: [P1_RESULTS.md](P1_RESULTS.md).
Policy mới cải thiện nhẹ synthetic nhưng chưa vượt Oldest Data trên mixed;
chưa train DRL mới hoặc xác nhận lợi ích trên final test.

## RescueNet + Alibaba

```powershell
.\scripts\run-paper-datasets.ps1 -Mode single -Offline
.\scripts\run-paper-datasets.ps1 -Mode evaluate -Seeds 30 -Offline
```

`single`: một episode mixed. `evaluate`: synthetic / RescueNet / mixed,
ba policy chọn thiết bị trên cùng seed. Output: `target/uav-paper-*` hoặc
`target/uav-dataset-evaluation-*`. Mở `run.txt` rồi `REPORT.md`/CSV.
Chi tiết: [DATASET_EVALUATION.md](DATASET_EVALUATION.md).

## Baseline theo bài báo

```powershell
mvn -o compile exec:java "-Dexec.mainClass=uav.PaperSimulation" "-Dexec.classpathScope=compile"
mvn -o compile exec:java "-Dexec.mainClass=uav.PaperBaselines" "-Dexec.classpathScope=compile"
mvn -o test
```

Bỏ `-o`/`-Offline` khi cần tải dependency. Các lệnh baseline này dùng task synthetic
và policy cố định; DRL chạy bằng lệnh Python phía trên.
Đối chiếu: [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md).

## Source chính

| File | Vai trò |
| --- | --- |
| `PaperSimulation.java` | Môi trường và chạy một episode |
| `PaperGymBridge.java`, `drl/environment.py` | Gym reset/step trên event engine Java |
| `drl/run.py`, `drl/experiments.py` (gốc project) | Train, lưu/nạp, evaluate, lưới Table 5/6 |
| `PaperParameters.java` | Tham số bài báo |
| `PaperBaselines.java` | So sánh policy trên synthetic |
| `PaperDatasetWorkload.java` | Trộn task ảnh và tải Alibaba |
| `PaperDatasetEvaluation.java` | Đánh giá nhiều seed |
| `RescueNetWorkload.java`, `AlibabaWorkload.java` | Đọc dataset |
| `Location3D.java`, `UAVMobilityModel.java` | Vị trí, chuyển động |
| `UAVEdgeNode.java`, `UAVEnergyModel.java` | UAV và năng lượng |

Demo milestone cũ và entry point `UAVAlibaba`/`UAVMilestone7` đã được gỡ.
Bản sao source/test trước khi dọn: `archives/legacy-milestones-*.zip`.
Raw dataset và kết quả paper/dataset được giữ nguyên. Không dùng `mvn clean`
nếu còn muốn giữ kết quả trong `target`.
