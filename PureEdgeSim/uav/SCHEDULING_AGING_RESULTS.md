# Scheduler xét deadline, pin và thời gian chờ — kết quả development

Ngày21/10/2026. Đã triển khai, kiểm thử và chạy trên raw RescueNet + Alibaba.
**Có tín hiệu cải thiện so với bốn baseline trong pilot, nhưng aging chưa chứng
minh lợi ích trên objective tổng hợp; chưa có tuyên bố novelty hoặc SOTA.**

## 1. Cơ chế và quyền quyết định

Tên làm việc `FEASIBLE_AGING`, class `scheduling/FeasibleAgingScheduler.java`.
Dùng cùng task/CPU/queue, fixed offloading/UAV hovering và nguyên tắc nonpreemptive
như [benchmark nền tảng](SCHEDULING.md). Không thêm admission, rejection, DVFS,
idling hoặc thông tin tương lai. Mọi task vẫn được tính trong offered denominator.

Với mỗi task đã ready, ước lượng thời gian xử lý p=remaining MI/MIPS. Dự kiến
đủ điều kiện nếu kết thúc trước deadline/horizon và còn đủ pin để trả cả CPU
và hover trong p giây. Đây là điều kiện tại thời điểm dispatch, không phải cam
kết rằng mọi task đang chờ sẽ được phục vụ trước hạn.

```text
eligible(k):
    now + p_k <= min(deadline_k, horizon)
    (P_hover + P_cpu) * p_k <= remaining_battery

aged(k): now - ready_k >= alpha * (deadline_k - ready_k)

relative_slack_k = max(0, deadline_k-now-p_k) / max(epsilon, deadline_k-ready_k)
score_k = max(1,priority_k) / [max(epsilon,p_k)*(1+relative_slack_k)]
```

Nếu có task aged trong eligible, chọn EDF trong nhóm đó. Nếu không, chọn score
lớn nhất. Khi không có eligible, chạy task ngắn nhất trong ready queue để giữ
cùng quyền điều khiển với baseline. Hòa theo ready, arrival, ID.
Không hard-drop task chỉ vì dự báo infeasible. Aging là cơ chế giảm bỏ đói,
**không có bảo đảm chống starvation hoặc background SLA** dưới tải tùy ý.

MI được biết chính xác theo cost model đang dùng; chưa kiểm tra sai số dự báo
inference. Thống kê/pin hiện tại là thông tin policy được phép dùng; không đọc
future arrivals, masks hoặc offline outcome. Power/MI/deadline vẫn là giả định
chưa hiệu chuẩn trên UAV thực tế.

## 2. Protocol khóa trước khi xem outcomes

Protocol nguồn: [aging-study-protocol.json](scheduling/aging-study-protocol.json),
copy/hash trong output. Giữ horizon600s, arrival window300s, ba mức arrival và
cost model của baseline nền tảng. Có hai budget:1,600,000J và30,000J.

- Validation seeds31000–31009; evaluation seeds32000–32029, không trùng.
- Sáu cấu hình cố định:3 mức tải×2 pin. Mỗi seed tạo cùng offered workload cho
  mọi policy; hai budget của cùng seed/load dùng cùng input.
- Chọn alpha trong{0.25,0.5,0.75} bằng loss validation nhỏ nhất:
  `0.75*image_DVR + 0.25*background_DVR`, hòa chọn alpha nhỏ hơn.
  Empty source được tính0 trong selection loss, quy tắc đã khai báo trước.
- Trọng số0.75/0.25 là giả định ưu tiên nghiên cứu, chưa phải SLA người dùng
  hoặc trọng số suy ra từ dataset. Primary không trực tiếp minimize energy.
- Baseline FIFO, EDF, PRIORITY, **SPT**. SPT được thêm vào protocol trước khi
  xem bảng outcomes để kiểm tra lợi ích đơn thuần từ task ngắn.
- Ablation NO_AGING, NO_ENERGY_GUARD, NO_DEADLINE_GUARD, giữ nguyên alpha đã
  chọn. NO_DEADLINE_GUARD vẫn giữ horizon guard và thành phần slack trong score;
  nó chỉ bỏ eligibility theo deadline, không bỏ toàn bộ thông tin deadline.
- Validation420 episodes; evaluation1440 episodes. Không retrain DRL hoặc mở
  final-test ranges của nhánh paper. Đây vẫn là development evaluation.

Validation chọn **alpha=0.75**. Loss của alpha0.25/0.5/0.75 lần lượt
0.0876573 /0.0878040 /0.0874779. Chênh lệch nhỏ, chưa kết luận lựa chọn alpha bền.
Giá trị được ghi `selected.json` trước khi chạy evaluation; không đổi hệ số sau
khi đọc các bảng dưới đây.

## 3. Kết quả trên task streams mới

Mean trên180 case/policy (30 seed×6 cấu hình). Các cấu hình dùng chung seed có
tương quan; không coi180 case là180 mẫu độc lập. DVR tính mọi task không hoàn
thành đúng hạn, gồm expired/battery/horizon. Đơn vị bảng là phần trăm.

| Policy | Image DVR | Background DVR | Primary loss |
| --- | ---: | ---: | ---: |
| FIFO | 24.68% | 9.95% | 0.2100 |
| EDF | 21.54% | 22.48% | 0.2178 |
| Priority | 14.20% | 33.09% | 0.1892 |
| SPT | 18.19% | 6.97% | 0.1538 |
| FEASIBLE_AGING | 13.94% | 7.65% | 0.1237 |
| NO_AGING | 12.80% | 9.33% | **0.1193** |
| NO_ENERGY_GUARD | 13.96% | 8.56% | 0.1261 |
| NO_DEADLINE_GUARD | 22.67% | 13.11% | 0.2028 |

Full tốt hơn cả bốn baseline theo primary đã khóa. So SPT, full giảm image DVR
nhưng background DVR trung bình cao hơn một chút. Vì vậy không thắng mọi metric.
NO_AGING có primary tốt hơn full: aging giúp background nhưng làm mất thêm một
số task ảnh. **Chưa chứng minh aging là thành phần cải tiến theo primary này.**
Deadline eligibility có tín hiệu đóng góp lớn trong ablation; chưa suy ra
novelty, tính tối ưu hoặc hiệu quả ngoài cost model hiện tại.

### Tải cao, pin1,600,000J

| Policy | Image DVR | Background DVR | Mean UAV energy |
| --- | ---: | ---: | ---: |
| FIFO | 44.30% | 8.93% | 55,098.8J |
| EDF | 42.58% | 35.22% | 55,482.4J |
| Priority | 19.65% | 64.68% | 55,372.8J |
| SPT | 26.26% | 7.25% | 55,028.1J |
| Full | 18.07% | 4.03% | 55,272.3J |
| NO_AGING | 14.64% | 12.37% | 55,183.6J |

Full giảm mạnh background miss so với Priority trong cấu hình này, đồng thời
giảm image miss. Nhưng tổng năng lượng vẫn cao hơn SPT/FIFO, không phải cải
thiện đồng thời mọi mục tiêu.

### Tải cao, pin30,000J

Full: image28.17%, background17.22%; Priority: image27.86%, background90.32%;
SPT: image33.84%, background10.79%; NO_AGING: image25.06%, background17.51%.
SPT giữ background tốt hơn full trong case pin thấp. Mọi policy dùng hết30,000J;
energy guard giúp phân phối pin cho công việc hữu ích hơn, không làm tổng J giảm.

## 4. Paired differences và độ bất định

Tính trung bình chênh lệch full−reference qua sáu cấu hình trong mỗi seed, rồi
bootstrap30 seed clusters,10,000 resamples, seed bootstrap20261021. Giữ pairing
policy và các cấu hình cùng seed. Các interval95% là **descriptive, unadjusted**,
conditional trên alpha đã chọn, source pool và mô hình; không phải kiểm định
confirmatory hoặc đánh giá uncertainty của cả quá trình chọn thuật toán.

| Reference | Delta primary | Descriptive interval95% |
| --- | ---: | --- |
| FIFO | −0.08634 | [−0.11648; −0.06121] |
| EDF | −0.09411 | [−0.11334; −0.07681] |
| Priority | −0.06552 | [−0.07542; −0.05593] |
| SPT | −0.03018 | [−0.04137; −0.02138] |
| NO_AGING | +0.00437 | [+0.00167; +0.00720] |
| NO_ENERGY_GUARD | −0.00247 | [−0.00355; −0.00158] |
| NO_DEADLINE_GUARD | −0.07917 | [−0.09502; −0.06494] |

Delta âm tốt hơn. Không dùng bảng này để chọn lại alpha hoặc bỏ ablation bất lợi.

## 5. Hai trace giải thích cơ chế

**Aging đánh đổi ảnh với background:** overload-low-battery/seed32000, tại
139.210s, full chọn Alibaba task13 đã chờ từ44.333s, service11s, deadline164.333s.
NO_AGING chọn ảnh task50, service5s, deadline176.928s. Đây là lần dispatch đầu
tiên khác nhau. Aging bảo vệ background đã chờ lâu nhưng chiếm CPU lâu hơn;
full có primary cao hơn NO_AGING khoảng0.08120 trong case này.

**Energy guard tránh bắt đầu task không thể hoàn thành:** medium-low-battery/
seed32019, tại293.188s, NO_ENERGY_GUARD chọn Alibaba task17 cần13.5s rồi bị cắt
do hết pin tại300.610s. Full chọn task21 cần0.5s và hoàn thành. Pin hiện tại đủ
cho khoảng7.42s ở hover+CPU100W, không đủ13.5s. Full có primary thấp hơn khoảng
0.06696. Cả hai vẫn tiêu hết cùng budget; đây là hiệu quả sử dụng pin, không
phải bằng chứng giảm tổng energy.

Trace và workload ở `evaluation/<scenario>/seed-<seed>/` của run chính.

## 6. Verification và runtime

- **64 Java tests đạt**, gồm6 test mới cho cơ chế/SPT: urgency/priority,
  aging/ablation, energy bao gồm hover, deadline guard/fallback và pin thấp
  thực thi qua kernel với mọi task vẫn được đếm.
- Verifier độc lập replay từng dispatch từ ready queue và pin suy ra từ work
  đã thực thi, kiểm tra source mapping, CPU/energy conservation, deadline/drop
  và summaries: **27,062 validation +92,816 evaluation task outcomes**.
- Phân tích kiểm lại alpha từ validation-grid, primary loss từ per-source DVR,
  split seed và các ablation chỉ tắt đúng một switch, cùng alpha.
- Verifier mới vẫn kiểm tra đạt270 episode của benchmark baseline trước.
- Không đổi kernel scheduling/physics trong bước này; không chạy DRL mới.

Comparator full O(Q) thời gian và O(Q) bộ nhớ tạm, baseline quét O(Q). P95
dispatch full khoảng1.7–2.9 microseconds trong các strata của run này. Đó chỉ
là selection call, không phải end-to-end latency hoặc hiệu năng UAV thực địa.
Kernel toàn episode vẫn O(N²) worst-case do quét state mỗi event. Chưa đo scaling.

## 7. Artifact và tái chạy

Run chính: `target/scheduling-aging-verified-20261021/`.

```powershell
mvn -o compile exec:java "-Dexec.mainClass=uav.scheduling.SchedulingStudy" "-Dexec.classpathScope=compile" "-Dscheduling.output=target/scheduling-aging-new"
python scripts/analyze-uav-scheduling-study.py target/scheduling-aging-new
```

Linux dùng cùng Maven arguments. Output mới phải chưa tồn tại. Runner đọc raw
dataset sẵn có; không tải thêm hoặc ghi đè kết quả.

- protocol.json, manifest.json, source-pools/, source/: thiết kế/nguồn và snapshot.
- validation-grid.csv, selected.json: lựa chọn alpha trước evaluation.
- validation/, evaluation/: manifest, paired workload.csv, per-policy outcomes,
  episodes.csv, summary.csv và verification.json.
- macro.csv, paired.csv, REPORT.md, study-verification.json: phân tích/kiểm chứng.
- Log cục bộ: `target/scheduling-aging-verified.log`.

## 8. Bước tiếp theo hợp lý

Chưa nên tăng ngân sách DRL. Trước hết cần hiệu chuẩn compute cost hoặc khảo sát
sai số ước lượng bằng cách tách estimated demand khỏi actual demand trong kernel.
Sau đó xác định yêu cầu tối thiểu của background: weighted loss và hard SLA là
hai bài toán khác nhau. Nếu cần aging, phải kiểm tra nó dưới yêu cầu dịch vụ
đã chốt, không chỉ thêm vì trực giác. Một giới hạn khác là CPU không preempt;
task dài đang chạy vẫn chặn ảnh mới đến dù policy chọn tốt tại dispatch.

Nếu phát triển tiếp, dùng split validation/development mới khi thay đổi thiết kế;
giữ outcomes hiện tại làm development evidence. Chưa có source holdout, mô hình
inference thực, biến động link/trajectory, DVFS hoặc admission. Bản này là cơ sở
để chọn hướng nghiên cứu tiếp, chưa phải thuật toán cuối cùng của đề tài.
