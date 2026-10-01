# UAV simulation

Chạy từ thư mục `uav/MECSim`, Java 17 và Maven.

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
