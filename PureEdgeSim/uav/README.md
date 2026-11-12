# UAV simulation

Bắt đầu với [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md).

| Nội dung hiện dùng | Tài liệu |
|---|---|
| Việc tiếp theo: offloading có xét thời gian giữ stop (đề xuất) | [NEXT_OFFLOADING_PLAN.md](../../docs/history/v1/NEXT_OFFLOADING_PLAN.md) |
| Mới nhất: sensitivity CPU/deadline/dwell, 5.400 episode mới | [NEAR_PAPER_SENSITIVITY_RESULTS.md](../../docs/history/v1/NEAR_PAPER_SENSITIVITY_RESULTS.md) |
| Mới nhất: offloading qua 10 môi trường, 1.500 episode | [NEAR_PAPER_MULTILAYOUT_RESULTS.md](../../docs/history/v1/NEAR_PAPER_MULTILAYOUT_RESULTS.md) |
| Scenario gần paper: ưu tiên offloading, scheduler tùy leverage | [NEAR_PAPER_SCENARIO.md](NEAR_PAPER_SCENARIO.md), [NEAR_PAPER_RESULTS.md](../../docs/history/v1/NEAR_PAPER_RESULTS.md) |
| Mới nhất: diagnosis, admission, validation/evaluation đã verified | [ADMISSION_STUDY_RESULTS.md](../../docs/history/v1/ADMISSION_STUDY_RESULTS.md) |
| Mới: hai giai đoạn scheduling/mobile đã chạy và audit | [SEQUENTIAL_STUDY_RESULTS.md](../../docs/history/v1/SEQUENTIAL_STUDY_RESULTS.md) |
| Kết quả baseline mixed-v2,4.320episode | [WORKLOAD_V2_BASELINES_RESULTS.md](../../docs/history/v1/WORKLOAD_V2_BASELINES_RESULTS.md) |
| Radio/upload và thiết kế thí nghiệm | [RADIO_UPLOAD_AUDIT.md](../../docs/history/v1/RADIO_UPLOAD_AUDIT.md), [SCHEDULING_EXPERIMENT_DESIGN.md](../../docs/history/v1/SCHEDULING_EXPERIMENT_DESIGN.md) |
| Compute/deadline: số đo và giới hạn | [TASK_CALIBRATION.md](../../docs/history/v1/TASK_CALIBRATION.md) |
| Seed generator, profiling và việc còn thiếu | [WORKLOAD_REPAIR.md](../../docs/history/v1/WORKLOAD_REPAIR.md) |
| Định nghĩa DVR, energy, latency và censoring | [EVALUATION_METRICS.md](EVALUATION_METRICS.md) |
| Kernel local/UAV + scheduling | [OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md) |
| Mobility/contact | [ADAPTED_PAPER_SERVICE.md](../../docs/history/v1/ADAPTED_PAPER_SERVICE.md) |
| Dataset | [DATASET_SETUP.md](../../docs/history/v1/DATASET_SETUP.md) |
| Dashboard | [VISUALIZATION.md](../../docs/history/v1/VISUALIZATION.md) |
| Đối chiếu paper lifetime | [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md), [PAPER_REFERENCE_RESULTS.md](PAPER_REFERENCE_RESULTS.md) |
| Scenario/workload/seed/suite của nhánh paper (`scenarios.json`) | [SCENARIOS.md](SCENARIOS.md) |

Chạy từ gốc MECSim:
```powershell
mvn -o test
.\scripts\build-drl.ps1 -Offline
.\.venv-drl\Scripts\python.exe -u -m drl.workload_baselines --output target/baselines-new --smoke
```

Mỗi output phải mới. Không dùng `mvn clean` nếu cần giữ kết quả trong `target/`.
`mixed-v2` đã sửa seed; compute/deadline chưa được hiệu chuẩn trên phần cứng edge.
Greedy hiện bay một chặng rồi hover; chưa có bằng chứng riêng cho joint scheduling.

Các báo cáo/plan cũ nằm trong [docs/history/](../../docs/history/README.md).
Source prototype đã nghỉ được giữ tại [legacy/](../../legacy/README.md).
Nhánh paper và các verifier đang dùng vẫn được giữ.
