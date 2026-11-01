# Baseline sau sửa seed: mixed-v2

Ngày30/10/2026. Đã chạy local trên Windows CPU, không train model mới.
Output: [workload-v2-baselines-development-20261030](../../target/workload-v2-baselines-development-20261030).

## Thiết kế

-9 policy x16 scenario x30 task seed development = **4.320 episode**.
-16 scenario: area250/800m xlight/overload xpin30kJ/1,6MJ xestimate error0/40%.
-Generator mixed-v2; compute, deadline, CPU/power, radio, source pools và layout giữ nguyên.
-Các policy dùng cùng workload/hash trong từng case. Case zero-error khớp preflight.
-30 seed validation và30 seed evaluation chưa dùng để lấy kết quả thuật toán.
-Đây là development benchmark sau sửa RNG, chưa phải workload inference được hiệu chuẩn,
  source holdout, unseen-layout hay kết luận thống kê xác nhận.
-Nhánh PaperSimulation/DQN lifetime không thay đổi, không cần chạy lại do sửa RNG này.

## Kết quả tổng hợp

DVR dưới đây là macro-average theo480case/policy. J/ảnh là tỷ số tổng năng lượng toàn
hệ thống trên tổng số ảnh giao đúng hạn. Thời gian mean/P95 tính trên ảnh đã compute
xong, gồm on-time+late; P95 là trung bình P95 mỗi episode, không phải pooled percentile.

| Policy | Compute DVR % | Delivered DVR % | J/ảnh giao đúng hạn | Completed mean/P95 s | Restricted UAV s |
|---|---:|---:|---:|---:|---:|
|CONTACT_GREEDY|6.862|30.709|1471.26|22.367/37.128|448.664|
|DISCONNECTED_RR|7.267|32.780|1781.93|22.807/37.700|419.450|
|RR + DELIVERY_AWARE/EDF|7.481|37.400|1969.09|23.162/37.174|415.394|
|RR + DELIVERY_AWARE/RISK_EDF|7.441|37.352|1961.64|23.148/37.132|415.888|
|RR + DEADLINE_ENERGY/RISK_EDF|7.383|37.690|1973.20|23.160/36.993|415.741|
|RR + DELIVERY_AWARE/RISK_SPT|7.444|37.355|1961.77|23.148/37.116|415.888|
|RR + DELIVERY_AWARE/FEASIBLE_AGING|7.481|37.400|1968.45|23.162/37.174|415.394|
|RR + ALL_LOCAL/EDF|7.632|37.941|1990.88|23.243/37.151|415.314|
|RR + ALL_UAV/FIFO|15.712|42.250|2105.46|23.001/38.284|418.894|

RR, DISCONNECTED_RR, CONTACT_GREEDY ở ba dòng đầu cùng dùng DELIVERY_AWARE+EDF,
nên ba dòng này so sánh lựa chọn điểm phục vụ với cùng route/scheduler.
RISK có quyền risk-drop, khác EDF thông thường; không coi toàn bảng là ablation
cùng quyền scheduler. ALL_LOCAL vẫn trả chi phí UAV bay/hover theo mô hình chung;
ALL_UAV dùng UAV khi có contact hợp lệ, ngoài contact vẫn theo luật local.

Mỗi policy có240/480case sống tới horizon600s. Do đó restricted time không phải
lifetime thật không giới hạn. Chỉ nhóm pin30kJ có exhaustion được quan sát trong
setting này; không gọi600s của nhóm pin lớn là thời điểm hết pin.

## Diễn giải

- CONTACT_GREEDY có delivered DVR và J/delivered thấp nhất trong9baseline của đợt này.
  Chênh với RR+DELIVERY_AWARE/RISK_EDF là khoảng6,643điểm phần trăm DVR.
- Không gọi nó tốt hơn mọi metric: ví dụ completed P95 của DEADLINE_ENERGY/RISK_EDF thấp hơn.
- RISK_EDF/RISK_SPT/AGING vẫn cho delivered DVR gần nhau trong setting đang có.
  Đây chưa chứng minh scheduling luôn ít quan trọng; compute/deadline/pool vẫn là giả định cũ.
- Không dùng chênh số giữa bảng cũ và bảng mới để tuyên bố cải tiến thuật toán:
  generator và tập task seed đã đổi.
- DQN/PPO không có trong bảng. Chưa retrain trên mixed-v2 hoặc kết luận RL vượt heuristic.

## Kiểm chứng và lỗi hậu xử lý đã xử lý

-4.320 trace PASS,284.616 task outcomes,480paired scenario/seed cases.
-Source snapshot giữ nguyên trong đợt mô phỏng; có đầy đủ phiên bản source trong output.
-Standalone scripts/offloading_metrics.py đếm lại từ raw traces;153summary rows được
  đối chiếu lại độc lập từ4.320episode rows.
-Post-run review xác nhận chỉ dùng development partition, đúng9policy/case, không mất episode.
-Worker ban đầu exit1 sau khi toàn bộ simulation/audit đã xong: phép so chuỗi số
  quá chặt bị lệch tối đa5,69e-14s ở tổng actual_contact_wait_s của48row.
  Finalizer kiểm tra lại tất cả rows với float rtol1e-12/atol1e-9; counts và identities
  phải khớp tuyệt đối. Finalizer exit0, status COMPLETE/PASS; không sửa hoặc chạy lại trace.
-Đã lưu initial-finalization-failure.json, metric-recount-verification.json và source
  finalizer. Runner hiện tại đã sửa checker cho các lần chạy tiếp; source snapshot
  của đợt này vẫn giữ bản thực sự đã dùng.

Đọc:
- [REPORT.md](../../target/workload-v2-baselines-development-20261030/REPORT.md): toàn bảng và từng scenario.
- [core-metrics-summary.csv](../../target/workload-v2-baselines-development-20261030/core-metrics-summary.csv):
  gồm background DVR, total/UAV energy, on-time counts, delivery latency và censoring.
- [runtime-summary.csv](../../target/workload-v2-baselines-development-20261030/runtime-summary.csv):
  thời gian episode+ghiCSV và thời gian audit; không phải latency quyết định trên UAV.
- [post-run-review.json](../../target/workload-v2-baselines-development-20261030/post-run-review.json):
  receipt cuối.

## Tái chạy

Output phải mới; các lệnh không train hoặc tải dataset:
```powershell
.\.venv-drl\Scripts\python.exe -u -m drl.workload_baselines --output target/workload-v2-baselines-new
```

Pilot trước nếu thay source:
```powershell
.\.venv-drl\Scripts\python.exe -u -m drl.workload_baselines --output target/workload-v2-smoke-new --smoke
```

Bước tiếp theo vẫn là hiệu chuẩn compute/deadline theo [WORKLOAD_REPAIR.md](WORKLOAD_REPAIR.md),
rồi mới thiết kế lại Alibaba/scenario và đánh giá model học mới trên cùng môi trường đã chốt.
