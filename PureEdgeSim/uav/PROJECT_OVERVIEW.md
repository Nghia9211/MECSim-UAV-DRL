# Tổng quan dự án UAV

Cập nhật sau đợt dọn30/10/2026. Tài liệu này là điểm bắt đầu; các báo cáo cũ nằm ở
[lịch sử nghiên cứu](../../docs/history/README.md).

## Bài toán đang phát triển

Thiết bị mặt đất phát sinh task phân tích ảnh, một số thiết bị mất kết nối.
UAV di chuyển để cung cấp contact và CPU. Hệ thống có ba tầng quyết định:
chọn điểm phục vụ, chọn local/UAV và thứ tự task trên CPU UAV.

RescueNet cung cấp metadata ảnh cho cost model; Alibaba cung cấp workload CPU nền.
Chưa chạy segmentation thực trong simulator. Không bắt buộc có cache hoặc tối ưu
đồng thời mọi thành phần để phát triển đề tài.

## Hai luồng cần phân biệt

| Luồng | Quyết định/chỉ số | Source |
|---|---|---|
| Đối chiếu paper Azfar | Chọn thiết bị phục vụ; lifetime và tuổi dữ liệu | `PaperSimulation.java`, `drl/run.py` |
| Môi trường mở rộng | Chọn điểm phục vụ + offloading/scheduler; DVR, J/ảnh, latency, lifetime UAV | `offloading/`, `scheduling/`, `drl/mobile_environment.py` |

Luồng paper được giữ để đối chiếu. Nó không phải CPU task scheduler và chưa tái hiện
đầy đủ mọi bảng/cấu hình của paper. Đọc [PAPER_REFERENCE_RESULTS.md](PAPER_REFERENCE_RESULTS.md)
và [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md).

## Bằng chứng mới nhất

**Sensitivity đã hoàn tất tuần tự:** [NEAR_PAPER_SENSITIVITY_RESULTS.md](NEAR_PAPER_SENSITIVITY_RESULTS.md):
5.400 episode mới audit PASS, 900 reference cases reused. CPU UAV ít ảnh hưởng trong dải đã thử;
deadline ảnh hưởng DVR, dwell ảnh hưởng energy. Giữ reference, chưa chọn cấu hình/thuật toán mới hay train DQN.


**Đã kiểm tra nhiều môi trường:** [NEAR_PAPER_MULTILAYOUT_RESULTS.md](NEAR_PAPER_MULTILAYOUT_RESULTS.md):
1.500 episode, 10 môi trường × 30 workload seed × 5 routing policy, 36.600 task outcomes audit PASS.
ALL_UAV giảm delivered DVR trên 10/10 môi trường; DEADLINE_ENERGY/DELIVERY_AWARE là baseline mạnh hơn
trong tổng hợp này. Chưa có thuật toán mới hoặc xác nhận lifetime.


**Scenario gần paper theo hướng mới:** [NEAR_PAPER_RESULTS.md](NEAR_PAPER_RESULTS.md) và
[NEAR_PAPER_SCENARIO.md](NEAR_PAPER_SCENARIO.md): 720 episode / 30 workload seed audit PASS.
Offloading có tác dụng trong pilot; scheduler ít cơ hội tác động. Task synthetic 2–4 MB,
throughput local theo bảng paper; không trộn kết luận với benchmark RescueNet/DeepLab trước.


**Cập nhật tiếp01/11:** [Admission study](ADMISSION_STUDY_RESULTS.md) đã chạy6480episode mới,
bao gồm30seed validation và30seed evaluation trên geometry mới theo source/protocol lock.
Cap bảo vệ ảnh nhưng làm background DVR xấu hơn RISK_EDF; chưa chọn làm thuật toán cuối.
Các partition này đã được dùng đánh giá, không còn chỉ là input diagnostics.

**Cập nhật01/11:** [Hai giai đoạn scheduling/mobile](SEQUENTIAL_STUDY_RESULTS.md) đã chạy tuần tự,
2.640full episode audit PASS; scheduler cải thiện hover control, hiệu ứng nhỏ hơn khi mobile.
Compute vẫn provisional; radio/default kernel giữ nguyên; chưa train RL hoặc chứng minh lifetime tăng.
Các số mixed-v2 bên dưới thuộc benchmark trước hiệu chuẩn và không so trực tiếp như cải tiến thuật toán.

- Generator task có version: `legacy-v1` để replay và `mixed-v2` để sửa tương quan seed.
- Ba partition task seed tách biệt: development/validation/evaluation.
- Baseline mixed-v2:9policy x16scenario x30seed development = **4.320episode**, audit/recount PASS.
- `CONTACT_GREEDY`: delivered DVR30,709%,1471,26J/ảnh giao đúng hạn;
  RR+DELIVERY_AWARE/RISK_EDF:37,352%,1961,64J.
- Đây là development trên một layout, hai scale và cùng source pools; chưa hiệu chuẩn inference.
- Trace cho thấy Greedy chỉ bay một chặng rồi hover trong480/480episode.
  Cần static-hover control và ablation trước khi kết luận về scheduling/joint optimization.

Chi tiết: [WORKLOAD_V2_BASELINES_RESULTS.md](WORKLOAD_V2_BASELINES_RESULTS.md),
[WORKLOAD_REPAIR.md](WORKLOAD_REPAIR.md).
Review thiết kế được giữ cùng [artifact review](../../target/workload-v2-design-review-20261030/REPORT.md);
link artifact chỉ có trên máy đã lưu kết quả.

## Việc tiếp theo theo thứ tự

1. Hoàn thiện [compute/deadline calibration](TASK_CALIBRATION.md): đã đo runtime kiến trúc workstation,
   có config opt-in; còn thiếu checkpoint/power/SLA. Kiểm tra radio/delivery trước campaign mới.
2. Cải thiện sampling Alibaba và báo task bất khả thi; giữ benchmark cũ để đối chiếu.
3. Bổ sung scenario ứng dụng, nhiều layout/connectivity và đối chứng static-hover.
4. Ablation giữ selection/route cố định khi thay scheduler; các policy cần cùng quyền điều khiển.
5. Khóa thiết kế trước validation/evaluation; sau đó mới quyết định train policy học mới.

Mô hình profiling: DeepLabV3–MobileNetV3-Large, đo CPU workstation theo phần cứng hiện có.
Hai vai trò dùng cùng tốc độ khi chưa có hai profile độc lập; Pi4B/Jetson Nano chỉ là tham chiếu chưa đo.

## Source và lệnh hiện dùng

| Thành phần | File |
|---|---|
| Task/arrival/cost/seed | [SchedulingWorkload.java](scheduling/SchedulingWorkload.java), [WorkloadSeeds.java](scheduling/WorkloadSeeds.java) |
| Gán nguồn và compute ước lượng | [OffloadingJob.java](offloading/OffloadingJob.java) |
| Event/queue/deadline/energy kernel | [OffloadingSimulation.java](offloading/OffloadingSimulation.java) |
| Mobility/controller | [MobileService.java](offloading/MobileService.java), [MobileGymBridge.java](offloading/MobileGymBridge.java) |
| Baseline mixed-v2 | [drl/workload_baselines.py](../../drl/workload_baselines.py) |
| Independent verification/metrics | [workload_rng.py](../../scripts/workload_rng.py), [trace verifier](../../scripts/verify-uav-mobile-trace.py), [offloading_metrics.py](../../scripts/offloading_metrics.py) |
| Profiling | [profile-image-inference.py](../../scripts/profile-image-inference.py) |

```powershell
mvn -o test
.\scripts\build-drl.ps1 -Offline
.\.venv-drl\Scripts\python.exe -u -m drl.workload_baselines --output target/baselines-new --smoke
```

Chạy từ gốc MECSim. Output mới không được tồn tại.
[Metric bắt buộc](EVALUATION_METRICS.md), [dataset setup](DATASET_SETUP.md),
[dashboard](VISUALIZATION.md).

## Phần lịch sử

Các plan/negative results cũ đã chuyển sang [docs/history/](../../docs/history/README.md),
không bị bỏ khỏi bằng chứng nghiên cứu.
Một số prototype/script dùng một lần được lưu dạng text tại
[legacy/](../../legacy/README.md); không được compile/discover như code đang chạy.
Các class cũ còn dependency trong kernel/verifier vẫn được giữ, bao gồm QIOS projection;
tuổi file không đủ để kết luận nó không còn dùng.
