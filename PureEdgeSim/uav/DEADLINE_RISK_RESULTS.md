# Deadline-risk guard + EDF/SPT: pilot triển khai

Ngày: 29/10/2026. Trạng thái: local, không train DRL, chưa push/server. Lấy cảm hứng từ kiểm soát rủi ro deadline trong [Fan et al.,2024](https://doi.org/10.1038/s41598-024-67886-x); **không tái hiện MA-SDRC**, không thêm MARL hoặc reward của bài đó.

## Cơ chế đã implement

Khi CPU UAV rảnh, trước khi chọn task tiếp theo, kiểm tra mọi task WAITING đã ready:

```text
if now + estimated_remaining_MI / UAV_MIPS > absolute_deadline + tolerance:
    mark DROPPED_DEADLINE_RISK
    executed_work = 0
else:
    keep task for EDF or SPT
```

Task vừa đúng deadline vẫn được chạy. Không ngắt task RUNNING, không hủy upload đang dở, không áp guard lên CPU local. Nếu task vượt estimate khi đang chạy thì tiếp tục như baseline; vì vậy đây là guard ở dispatch, không phải hệ thống bảo đảm deadline hoặc full multi-stage risk control.

Task bị hủy vẫn nằm trong offered và failure denominator. Trong metrics API hiện tại nó được cộng vào nhóm expired; trace giữ tên status riêng để không nhầm với expiry tại deadline. Source/UAV energy đã tiêu hao trước drop vẫn được tính. Giữ nguyên quy tắc coverage/horizon và các baseline không guard.

Dự báo offloading của DEADLINE_ENERGY dùng đúng quy tắc guard trong projected queue khi chọn scheduler có guard. Do đó routing có thể thay đổi giữa EDF và guard+EDF; dùng đối chứng ALL_UAV để cô lập ảnh hưởng scheduler/drop khỏi routing.

## Pilot khóa cấu hình

- RescueNet metadata + Alibaba background, cùng generator/cost model development cũ; không inference thật, deadline/công suất vẫn là giả định.
- UAV cố định;4source; horizon600s;3mức tải ×2pin UAV ×3seed91000–91002 ×8policy.
- Hai lượt estimate error0 vàuniform±40%: **288episode tổng cộng**. Mọi trường actual workload/arrival/deadline/source giống nhau giữa hai lượt; chỉ estimated MI thay đổi.
- 8policy gồm ALL_UAV và DEADLINE_ENERGY, mỗi routing ghép EDF/SPT/RISK_EDF/RISK_SPT. Mỗi đối chứng có cùng quyền execution; guard là thay đổi được đo rõ, không giấu việc cho phép early drop.
- Rho/QIOS không tham gia. Không chọn threshold theo dữ liệu: điều kiện duy nhất là earliest predicted finish không kịp deadline.
- Các seed này đã dùng trong pilot QIOS: **development**, không phải tập final mới. Không kết luận statistical superiority/generalization từ3seed.

## Kết quả

Macro-average18case; DVR tính mọi task late/drop/expired/unfinished. Tổng năng lượng gồm source+UAV. Mức điện nhỏ hơn chỉ có ý nghĩa khi đọc cùng mức dịch vụ.

### Estimate chính xác

| Routing | Scheduler | Image DVR | Background DVR | Tổng kJ |
| --- | --- | ---: | ---: | ---: |
| ALL_UAV | EDF | 10,404% | 11,258% | 42,671 |
| ALL_UAV | Guard+EDF | **5,771%** | 6,593% | 42,405 |
| ALL_UAV | SPT | 8,112% | 1,829% | 42,620 |
| ALL_UAV | Guard+SPT | 7,743% | **1,829%** | 42,339 |
| DEADLINE_ENERGY | EDF | **0,000%** | 0,654% | 43,177 |
| DEADLINE_ENERGY | Guard+EDF | **0,000%** | **0,327%** | 42,925 |
| DEADLINE_ENERGY | SPT | 0,141% | **0,327%** | 43,173 |
| DEADLINE_ENERGY | Guard+SPT | 0,141% | **0,327%** | 42,919 |

### Estimate sai số ±40%

| Routing | Scheduler | Image DVR | Background DVR | Tổng kJ |
| --- | --- | ---: | ---: | ---: |
| ALL_UAV | EDF | 10,404% | 11,258% | 42,671 |
| ALL_UAV | Guard+EDF | **6,216%** | 6,951% | 42,403 |
| ALL_UAV | SPT | 8,144% | **1,502%** | 42,605 |
| ALL_UAV | Guard+SPT | 7,858% | **1,502%** | 42,324 |
| DEADLINE_ENERGY | EDF | **2,898%** | 0,654% | 43,171 |
| DEADLINE_ENERGY | Guard+EDF | 3,050% | **0,327%** | 42,914 |
| DEADLINE_ENERGY | SPT | 3,191% | **0,327%** | 43,173 |
| DEADLINE_ENERGY | Guard+SPT | 3,191% | **0,327%** | 42,908 |

## Nhận định giới hạn

Guard+EDF giảm image DVR4,633điểm phần trăm khi ALL_UAV và estimate chính xác; vẫn có lợi trong pilot±40%. Với DEADLINE_ENERGY vốn đã có routing tốt, lợi ích nhỏ hơn: exact estimate giữ0imageDVR và giảm background miss/energy; với±40%, imageDVR tăng0,152điểm phần trăm. **Chưa có một policy tốt hơn mọi metric/cấu hình.**

Không kết luận imageDVR tăng là do hủy nhầm chỉ từ bảng: routing forecast và queue tương lai cũng thay đổi. Cần paired per-task trace để xác định nguyên nhân. Test dựng tay xác nhận khả năng hủy nhầm khi estimate quá cao; đó là rủi ro có thật của cơ chế, chưa phải giải thích đã xác nhận cho mọi case pilot.

## Verification

-3test Java mới: task impossible bị drop nhưng vẫn failure; đúng biên deadline và không preempt running; overestimate có thể hủy task actual làm kịp.
- Verifier Python đối chiếu đủ **288episode/16.704task outcomes**, quyết định routing, forecasts, EDF/SPT dispatch, risk predicate, CPU work và energy, upload và deadline. Không chỉ kiểm tra summary.
- Có143risk drops trong lượt estimate0 và155trong lượt±40%, tính trên các policy/episode lặp; không coi đây là số task độc lập duy nhất.
-4test verifier guard đạt (trace gốc, estimated cost sai, drop mà có execution, bật status risk trong policy không guard).
-7corruption tests verifier offloading cũ đạt; source Java snapshot/checksum được kiểm tra.
-1.044workload rows giữa hai lượt khớp mọi trường trừ estimated MI, gồm các trường hợp lặp hai mức pin; không nhân thành thêm workload độc lập.
- Giới hạn: verifier chưa tái dựng quá trình lấy mẫu từ raw pools; chỉ replay generated workload. Fixed-UAV connected output nên compute on-time trùng delivery; chưa xác nhận cho mobile/disconnected.

## Source và chạy lại

Source chính: `DeadlineRiskScheduler.java`, `OffloadingSimulation.dispatch/predict`, chế độ`qios.riskOnly` của `QueueImpactBenchmark`. Script kiểm tra: `verify-deadline-risk.py`, `test-deadline-risk-verifier.py`.

```powershell
mvn -o test
mvn -o compile exec:java "-Dexec.mainClass=uav.offloading.QueueImpactBenchmark" "-Dqios.output=target/risk-NEW" "-Dqios.riskOnly=true" "-Dqios.seeds=3" "-Dqios.estimateError=0"
python scripts/verify-deadline-risk.py target/risk-NEW
python scripts/test-deadline-risk-verifier.py target/risk-NEW
```

Lượt±40% dùng output mới và`-Dqios.estimateError=0.4`. Artifact hiện tại: `target/deadline-risk-pilot-e0-20261029/` và`target/deadline-risk-pilot-e40-20261029/`, có REPORT.md, episodes.csv, verification.json và full trace.

## Bước tiếp theo

Phân tích từng task trong case DEADLINE_ENERGY+guard bị regression khi estimate sai. Nếu cải tiến, chỉ thử một cơ chế bảo thủ đối với overestimate trên validation mới; không thay threshold theo test vừa xem. Sau đó đánh giá nhiều seed/hardware và delivery trong outage/mobile. Không cần train DRL để xác nhận lợi ích ban đầu của guard.
