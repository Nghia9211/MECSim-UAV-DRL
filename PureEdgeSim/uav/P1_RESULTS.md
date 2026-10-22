# P1 — Estimator và SERVICE_AWARE: kết quả development

Ngày 01/10/2026. Đã triển khai và chạy cục bộ, không train DRL mới.
**Kết luận: cải thiện nhẹ trên synthetic nhưng chưa vượt Oldest Data trên mixed
RescueNet + Alibaba. Chưa có bằng chứng về một cơ chế cải tiến bền vững.**

## 1. Cơ chế đã triển khai

`ServiceEstimator.java` dự báo cho từng điểm đến từ trạng thái hiện tại và
workload trung bình của pool khai báo. Dùng lại radio, FIFO CPU và công thức
năng lượng của simulator. Không đọc seed, ảnh/job sắp sinh hoặc chạy bước mô
phỏng tương lai. RPC `estimate` không thay state/RNG; observation DQN vẫn 24D.

Với điểm đến a, dự báo thời gian slot T(a), cập nhật thành công d_i(a), và
cập nhật local không cần UAV l_i(a), cùng tại thời lượng T(a). Đặt:

```text
u_i = 1 / max(1, 10 - age_i)
G(a) = sum_i u_i * (d_i(a) - l_i(a))
C(a) = E_UAV(a)/B_UAV + sum_{i không có nguồn ngoài} E_i(a)/B_i
score(a) = G(a) - lambda_E*C(a) - lambda_T*T(a)/600
```

Chọn score lớn nhất. Chênh lệch cập nhật có thể âm nếu offloading làm mất một
cập nhật vốn hoàn thành local. Khi mọi G không dương, fallback thiết bị có age
lớn nhất. Tie-break dùng thuộc tính vật lý; đối xứng hoàn toàn dùng RNG có seed.
Đây không phải tie-break cyclic của baseline Oldest Data. Không hard-mask action.

Dự báo là **kết quả tại workload trung bình**, không phải xác suất completion đã
hiệu chuẩn. Synthetic dùng 3 MB; mixed dùng trung bình 5.322 MB, 10012.871 MI/ảnh,
8301.5 MI background/slot, CPU 2000 MIPS và 20 W. Pool mixed có 449 ảnh và 1000
Alibaba tasks, dùng chung nguồn giữa các split; chưa phải source-data holdout.
Thống kê pool được tính một lần, không phải đọc sample kế tiếp.

## 2. Protocol và kiểm tra

- Validation: 5 layout seeds 1100000–1100004 × 2 task seeds 1200000–1200001.
  Lưới lambda_E/lambda_T = {0; 0.1; 1}; chọn mean lifetime lớn nhất,
  hòa thì chọn hệ số energy nhỏ hơn, rồi time nhỏ hơn. Tổng 660 episodes.
- Development: protocol P0, base layout42, 8 scenario modes, 22 fixtures ×
  3 task seeds = 66 case/workload. Hai workload × 10 policy = 1320 episodes.
  Hệ số khóa trước khi đọc development outcomes của từng workload.
- Full và các ablation được tuning riêng trên cùng validation; đây không phải
  phép bỏ thành phần với toàn bộ hệ số còn lại luôn cố định.
- Cả hai workload chọn SERVICE_AWARE: **lambda_E=1, lambda_T=0**.
  Validation mean lần lượt 27.2 và 19.2 slot; không dùng các số này làm test result.
- 46 Java tests và 17 Python tests đạt, gồm raw mixed, estimator không đổi RNG,
  forecast khớp kernel trên workload hằng, coverage chưa chắc completion,
  pin cạn, CPU blocking và relabel policy. 264 episode Oldest/Round Robin khớp
  P0 về actions, slots, reason và seconds (sai số <1e-6).
- Kiểm tra 6 failure replays khớp run chính; không episode nào bị truncation.
  Final-test seed ranges chưa được mở.

## 3. Objective chính: lifetime theo slot

Mỗi ô là mean trên 66 paired cases; cap600s, age limit10, tối đa200 slots.

| Policy | Synthetic | RescueNet + Alibaba |
| --- | ---: | ---: |
| OLDEST_DATA | 19.061 | **18.424** |
| ROUND_ROBIN | 10.818 | 10.000 |
| RANDOM | 10.258 | 10.000 |
| SERVICE_AWARE | **19.758** | 17.955 |
| NO_ENERGY | 18.955 | 17.576 |
| NO_TIME | 19.758 | 17.955 |
| NO_COMPLETION | 16.000 | 11.091 |
| NO_URGENCY | 10.000 | 10.000 |
| URGENCY_ONLY | 18.970 | 18.455 |
| NEAREST | 10.000 | 10.000 |

SERVICE_AWARE so với Oldest: synthetic +0.697 slot (+3.66%), 36 thắng/28 hòa/2 thua;
mixed −0.470 slot (−2.55%), 32 thắng/25 hòa/9 thua. Nhiều thắng nhỏ không bù được
một số thua lớn. NO_TIME trùng cả chuỗi action với full vì hệ số time được chọn
bằng0; **chưa chứng minh thành phần phạt thời gian hữu ích**. Completion và urgency
có tín hiệu hữu ích trong pilot, nhưng không suy ra ý nghĩa thống kê/novelty.

| Scenario | Synthetic Oldest / Service | Mixed Oldest / Service |
| --- | ---: | ---: |
| legacy | 17.000 / 18.000 | 17.000 / 17.000 |
| position | 17.000 / 18.000 | 17.000 / 17.000 |
| hardware_task | 20.556 / 21.333 | 17.667 / 17.333 |
| capacity | 17.000 / 17.667 | 16.667 / 17.667 |
| power | 21.667 / 22.000 | 21.444 / 21.667 |
| connectivity | 16.333 / 16.667 | 16.000 / 17.000 |
| outage | 21.667 / 22.000 | 21.000 / 22.000 |
| full | 19.889 / 21.222 | **19.667 / 13.333** |

## 4. Failure traces và giải thích

Trong mixed, Service có 9/66 episode vi phạm age, Oldest có0. Chín episode thuộc
3 fixture, mỗi fixture lặp3 task seeds; không phải9 cấu hình độc lập.

| Fixture (task2000000) | Service / Oldest slots | Thiết bị vượt age dưới Service |
| --- | ---: | --- |
| hardware_task, shift2100000 | 10 / 13 | 6 |
| full, shift2100000 | 10 / 12 | 1 |
| full, shift2100001 | 10 / 27 | 3, 7, 10 |

Case cuối có actions `6 6 6 6 6 6 5 8 11 2`: UAV chọn cùng đích sáu lần đầu,
ba thiết bị bị vi phạm chưa từng nằm trong coverage. Dự báo một bước và tổng
lợi ích/chi phí **không đảm bảo mọi thiết bị được cập nhật trước hạn**.
Bỏ energy khắc phục fixture hardware_task nhưng vẫn thất bại hai fixture full;
không thể quy toàn bộ nguyên nhân cho lambda_E. Urgency-only đạt 13/12/27 slot
trên ba case này, gợi ý cần kiểm tra cơ chế tránh bỏ sót trước khi tăng độ phức tạp.

## 5. Chỉ số phụ, runtime và complexity

| Chỉ số Service / Oldest | Synthetic | Mixed |
| --- | ---: | ---: |
| Mean simulated seconds | 11539.0 / 11093.0 | 10471.6 / 10735.2 |
| Battery J mỗi lần age được reset | 6503.9 / 6600.9 | 9241.6 / 9903.6 |
| Image delivery fraction | Không áp dụng | 0.5346 / 0.5117 |

Battery energy gồm UAV và thiết bị không có nguồn ngoài, **không gồm grid energy**.
Energy/refresh là tỷ số tổng năng lượng/tổng cập nhật. Exposure và mẫu số khác
giữa policy; giảm chỉ số này không có nghĩa lifetime tốt hơn hay tổng energy giảm.
Age reset bao gồm local và UAV. Failure reasons có thể đồng thời pin và age.

Forecast của Service: tỷ lệ dự báo sai completion 0.096% synthetic, 0.541% mixed;
MAE duration 0.0228/0.0248s, MAE UAV energy 1.82/72.49J. Tính trên các action đã
chọn, chưa đánh giá mọi action; accuracy cao không đảm bảo lịch phục vụ tốt.

Windows, Python3.11.9, Torch1 thread: Service median **384.2 microseconds**, p95
**608.7 microseconds** mỗi quyết định, gồm RPC tạo/serialize forecast và chọn action.
Bỏ hai quyết định đầu mỗi episode; pooled2225 quyết định. Oldest selection-only
median8.8/p9514.4 microseconds. Không tính reset/step, trace I/O hoặc chi phí
thu thập telemetry thực địa. Baseline không chịu diagnostic-only estimator RPC;
do khác phạm vi timing, không diễn giải tỷ số thành slowdown end-to-end.

Với N thiết bị: synthetic estimator O(N²). Mixed hiện có O(N³) worst-case:
N candidate, mỗi candidate sort tối đa N+1 jobs và gọi `deviceFinish` quét O(N)
cho tối đa N devices. Bisection pin80 vòng là hằng số. Có thể cache finish theo
device để giảm thành O(N² log N), nhưng chưa tối ưu hay benchmark scaling.
Packet chứa O(N²) dữ liệu; Python scoring O(N). Oldest/urgency/nearest O(N),
Round Robin O(1). Code hiện đánh giá N=12; Big-O không thay cho scalability test.

## 6. Giới hạn và bước tiếp theo

Các fixtures là can thiệp ghép cặp quanh layout42; task repeats có tương quan.
Không coi1320 episodes là1320 mẫu độc lập, chưa báo p-value confirmatory.
Full dùng metadata/forecast phong phú hơn observation24D của baseline; chưa
tách sạch lợi ích do thông tin khỏi thuật toán. Không chạy DQN trong suite P1.
Chưa thay đổi paper objective, chưa triển khai joint optimization hay Pareto.

**P1.1 đề xuất:** thêm quy tắc xét thời gian còn lại trước giới hạn age và khả
năng phục vụ các thiết bị chưa cập nhật trong vài quyết định tới. So với full
hiện tại, urgency-only và Oldest, ablation riêng quy tắc này. Khóa thiết kế và
tuning trên validation; giữ các failure case trên là regression/development,
không dùng chúng làm final test. Không chỉnh trọng số theo bảng development này.
Chưa có lý do đủ mạnh để train thêm hàng loạt DRL seeds; P2 chưa bắt đầu.

## 7. Artifact và tái chạy

Output cục bộ: `target/p1-20261001/`. `manifest.json` là trạng thái hoàn tất;
`protocol.json` lưu snapshot lúc bắt đầu nên vẫn có status RUNNING. Protocol P0
lồng bên trong mô tả fixture gốc; policy P1 dùng thêm thông tin như mục1, không
chỉ24D. Các file chính: `selected.json`, `validation-grid.csv`, `episodes.csv`,
`summary.csv`, `by-mode.csv`, `decisions.csv`, `timing.csv`, `priors.json`,
`validation-checks.json`, `traces/` và `failure-replays/`.

```powershell
# Từ uav/MECSim; dùng output mới, dữ liệu raw hiện có.
.\scripts\build-drl.ps1 -Offline
.\.venv-drl\Scripts\python.exe -u -m drl.service_experiment --output target/p1-new
```

Linux dùng `.venv-drl/bin/python` sau khi build bridge trên server. Runner không
ghi đè output, không sửa checkpoint và không tải dataset. Failure replays bổ sung
trong run này là phân tích sau development; runner tự lưu các sample traces.
