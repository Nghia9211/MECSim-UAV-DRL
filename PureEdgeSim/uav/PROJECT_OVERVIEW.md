# Tài liệu đọc lại dự án UAV: đã làm gì và làm tiếp gì?

> **Mới nhất 24/10:** [PAPER_SEED_ISOLATION.md](PAPER_SEED_ISOLATION.md) đã kiểm chứng
> cùng-layout best 32/32/32 slot nhưng final 30/30,367/10 slot.
> [NEXT_EXPERIMENT_PROPOSAL.md](NEXT_EXPERIMENT_PROPOSAL.md) đã được ghi và
> [6 model reward/freshness đang được chạy](PAPER_CONVENTION_RETRAIN_STATUS.md).

> **Kết quả mới nhất 23/10:** đã train3synthetic DQN đủ1triệu bước/model,
> cấu hình8/8; mean21,000slot với best-validation checkpoint,19,678 với final1m.
> [PAPER_REFERENCE_RESULTS.md](PAPER_REFERENCE_RESULTS.md) phân biệt kết quả đã
> kiểm chứng với phần reproduction còn thiếu.

> **Giai đoạn audit paper 23/10:** tham số công bố đã audit, benchmark quy
> ước2.520 episode đã replay độc lập. Xem [PAPER_REPRODUCTION_AUDIT.md](PAPER_REPRODUCTION_AUDIT.md).
> Benchmark này kiểm tra heuristic và quy ước; kết quả DQN đủ ngân sách nằm ở mục mới nhất bên trên.

> **Cập nhật 23/10/2026:** đã nối tầng chọn thiết bị/di chuyển/coverage với
> offloading/scheduling. Đọc [ADAPTED_PAPER_SERVICE.md](ADAPTED_PAPER_SERVICE.md).
> Đã có adapter và DQN train thử 2.000 bước trong môi trường mở rộng:
> [MOBILE_DRL.md](MOBILE_DRL.md). Chưa chứng minh hội tụ hoặc vượt heuristic.

> **Cập nhật 22/10/2026:** đã mở rộng từ scheduling-only sang quyết định local/UAV
> kết hợp scheduling. Trạng thái mới và cách chạy ở
> [OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md).
> Kết quả và verification mới: [OFFLOADING_RESULTS.md](OFFLOADING_RESULTS.md).
> Nội dung bên dưới giữ làm snapshot ngày 21/10, khi offloading còn cố định.

Cập nhật ngày **21/10/2026**, đối chiếu working tree và artifact hiện có trong
`uav/MECSim`. Đây là tài liệu tổng quan để đọc trước; các liên kết bên dưới dẫn
tới mô hình, source và kết quả chi tiết. Phần mới đang ở working tree, **chưa thể
coi là đã commit hoặc đồng bộ lên GitHub**.

## 1. Nắm lại dự án trong 5 phút

**Đề tài rộng:** Energy-aware edge offloading cho UAV disaster analytics —
chuyển giao xử lý tới biên có xét năng lượng cho phân tích dữ liệu thiên tai
với sự hỗ trợ của UAV.

**Phạm vi bạn đã chọn để đi sâu:** lập lịch các tác vụ phân tích ảnh trên CPU
của UAV, trong khi UAV còn phải xử lý tải nền. Offloading và vị trí UAV được giữ
cố định để đánh giá riêng tác động của scheduler. Joint offloading, placement,
scheduling và cache là các hướng mở rộng; không bắt buộc triển khai tất cả.

**Đã có:** mô phỏng UAV và pin; task/queue/deadline; workload RescueNet + Alibaba;
FIFO, EDF, Priority, SPT; một cơ chế thử nghiệm xét deadline/pin/thời gian chờ;
benchmark nhiều seed, ablation và trình kiểm chứng độc lập.

**Kết quả chính:** cơ chế thử nghiệm tốt hơn bốn baseline trên mục tiêu tổng hợp
đã chọn trong pilot. Tuy nhiên, bỏ aging lại cho mục tiêu tổng hợp tốt hơn bản
đầy đủ. Chưa thể chốt aging là cải tiến, chưa có bằng chứng giảm tổng năng lượng,
và chưa có tuyên bố thuật toán mới hoặc SOTA.

**Bước tiếp theo nên làm:** kiểm tra scheduler khi ước lượng thời gian xử lý bị
sai, thay vì tiếp tục giả định biết chính xác chi phí từng task. Sau đó hiệu
chuẩn workload bằng profiling inference và làm rõ mức dịch vụ cần giữ cho tải nền.
Đây là kế hoạch, chưa phải các phần đã triển khai.

## 2. Hai bài toán khác nhau trong cùng codebase

| Nội dung | Nhánh đối chiếu bài báo / DRL cũ | Nhánh task scheduling hiện tại |
| --- | --- | --- |
| Câu hỏi | UAV nên phục vụ thiết bị nào tiếp theo? | CPU UAV nên chạy task nào tiếp theo? |
| Quyết định | Chọn một trong 12 thiết bị/điểm đến | Chọn một task đã sẵn sàng trong queue |
| Trạng thái chính | Pin và tuổi dữ liệu của thiết bị | Task, deadline, thời gian chờ, compute và pin UAV |
| Đánh giá chính | Lifetime, tính theo slot | Task hoàn thành đúng hạn, tách ảnh và background |
| UAV | Có di chuyển theo lựa chọn thiết bị | Bay treo cố định để kiểm soát yếu tố không gian |
| Thuật toán | DQN và heuristic thứ tự phục vụ | FIFO / EDF / Priority / SPT / cơ chế thử nghiệm |
| Tài liệu | [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md), [DRL.md](DRL.md) | [SCHEDULING.md](SCHEDULING.md), [SCHEDULING_AGING_RESULTS.md](SCHEDULING_AGING_RESULTS.md) |

Checkpoint DQN cũ chọn thiết bị, không phải bộ lập lịch cho task queue mới.
Kết quả lifetime của nhánh cũ không chứng minh scheduler mới giảm deadline miss.
Tuổi dữ liệu cũng khác deadline: tuổi dữ liệu đo mức cũ của cập nhật; deadline
là hạn hoàn thành của một tác vụ cụ thể.

MECSim là nền tảng mở rộng từ PureEdgeSim. Các thuật toán orchestration của
MECSim gốc vẫn tồn tại; chúng không tự động trở thành baseline trong nhánh UAV
task scheduling. Nhánh mới dùng event engine và mô hình UAV của project.

## 3. Vai trò của bài báo gốc và các công việc trước đó

Bài báo đang đối chiếu là Azfar, Huang và Ke, *Enhancing Disaster Resilience
with UAV-Assisted Edge Computing: A Reinforcement Learning Approach to Managing
Heterogeneous Edge Devices*, bản arXiv v1 năm 2025.
Xem [PDF gốc](../../../2501.15305v1.pdf) và [đối chiếu implementation](PAPER_ALIGNMENT.md).

Bài toán chính của bản này là **đơn mục tiêu: kéo dài lifetime**, dưới giới hạn
pin và tuổi dữ liệu. Action DQN là chọn thiết bị phục vụ. Không nên mô tả nó là
đã tối ưu đồng thời task scheduling, cache, power allocation và trajectory.
Các hướng joint trong related work không đồng nghĩa với action của phương pháp
chính. Code Java ở đây là bản triển khai/diễn giải trong project, chưa phải mã
nguồn được xác nhận của tác giả.

Các phần đã làm trước nhánh task scheduling:

- Mô hình vị trí, chuyển động và năng lượng UAV; các test mobility/energy.
- Nối Java environment với Gymnasium, hỗ trợ train/evaluate DRL và workload
  synthetic hoặc RescueNet + Alibaba.
- Các run DQN nhiều seed, chẩn đoán layout/trạng thái và baseline lifetime.
  Xem [WEEK1_2_RESULTS.md](WEEK1_2_RESULTS.md) và [P0_RESULTS.md](P0_RESULTS.md).
- Thử heuristic `SERVICE_AWARE` dự báo chi phí phục vụ: có lợi trên synthetic
  nhưng chưa cải thiện objective trên mixed workload, còn vấn đề bỏ đói.
  Xem [P1_RESULTS.md](P1_RESULTS.md). Đây không phải `FEASIBLE_AGING` hiện tại.
- Audit lại sự lệch giữa đề tài rộng và code khi đó:
  [CODEBASE_AUDIT_20261021.md](CODEBASE_AUDIT_20261021.md). Đây là ảnh chụp trạng
  thái **trước khi bổ sung nhánh task scheduling**, không phải kết luận hiện tại.

Đã tạo [PDF tiếng Việt giữ bố cục](../../../output/pdf/azfar-2025-vi-reviewed-20261021/2501.15305v1-vi.pdf)
và [phần dịch bổ sung](../../../output/pdf/azfar-2025-vi-reviewed-20261021/PHAN_CON_THIEU_VI.md).
**Bản PDF chưa dịch toàn bộ:** một số trang và nhãn vẫn tiếng Anh; đọc cùng phần
bổ sung và PDF gốc. Không coi đây là bản dịch hoàn chỉnh.

## 4. Mô hình nghiên cứu hiện tại

**Câu hỏi nghiên cứu làm việc:** Trong hệ thống UAV hỗ trợ phân tích thiên tai
dưới tải nền biến thiên, lập lịch tác vụ ảnh có xét deadline, mức độ quan trọng
và pin ảnh hưởng thế nào tới tỷ lệ không hoàn thành đúng hạn, độ trễ và hiệu quả
sử dụng năng lượng?

```text
RescueNet: ảnh đầu vào ── upload ──┐
                                 ├── ready queue ── scheduler ── CPU UAV
Alibaba: tải CPU nền ─────────────┘                     │
                                             deadline / pin / kết quả
```

| Thành phần | Quy ước đang chạy |
| --- | --- |
| UAV | Một UAV bay treo tại (400, 400, 10 m) |
| Nguồn ảnh | Mô phỏng ở mặt đất ngay dưới UAV; khoảng cách truyền 10 m |
| Compute | Một CPU, 2.000 MI/s; MI là triệu lệnh theo cost model |
| Năng lượng | Bay treo 80 W; CPU thêm 20 W khi bận |
| Pin trong study mới | 1.600.000 J và 30.000 J |
| Thời gian | Horizon 600 s; task phát sinh trong [0, 300) s |
| CPU scheduling | Nonpreemptive: task đã chạy không bị ngắt bởi task mới |
| Offloading / placement / cache | Offload lên UAV cố định / vị trí cố định / chưa mô phỏng cache |

**Input task:** ID, nguồn dữ liệu, arrival, ready sau upload, deadline tuyệt đối,
priority, input bytes và nhu cầu compute MI.

**Output quyết định:** ID task được chạy tiếp khi CPU rảnh. Scheduler chỉ được
thấy task đã ready, thời gian hiện tại và trạng thái tài nguyên; không thấy
arrival tương lai, seed hoặc kết quả sau quyết định.

**Ràng buộc thực thi:** CPU chạy một task tại một thời điểm; không chạy trước
ready; không vượt ngân sách pin; task chờ hết hạn sẽ kết thúc ở trạng thái
expired; task đang chạy quá hạn vẫn có thể hoàn thành muộn. Hoàn thành đúng
deadline được tính đúng hạn. Mọi policy dùng cùng quy tắc.

**Giới hạn quan trọng:** compute MI hiện được coi biết chính xác. Không có
inference thực, CPU preemption, admission/rejection, DVFS, tranh chấp wireless
hoặc tối ưu đường bay trong benchmark này. Không dùng model đơn giản này để
khẳng định độ chính xác thực địa.

## 5. Hai dataset đang được kết hợp như thế nào?

**Không nối một dòng Alibaba thành nhãn cho một ảnh RescueNet.** Hai dataset
tạo hai luồng công việc độc lập, cùng cạnh tranh CPU UAV.

| Dataset | Phần đang dùng | Vai trò và ánh xạ | Điều chưa có |
| --- | --- | --- | --- |
| RescueNet | 449 ảnh validation và mask tương ứng | Bytes ảnh cho upload; megapixel × 833,3333 cho MI | Chưa chạy segmentation; mask không quyết định priority/độ nghiêm trọng |
| Alibaba 2018 | Pool 1.000 root task, một instance, thời lượng dương | MI = (end − start) × plan_cpu/100 × 1.000 | Không replay DAG/timeline cluster; plan_cpu không phải CPU utilization đo được |

Các row Alibaba được lấy từ phần đầu file đủ điều kiện, không phải mẫu đại diện
toàn bộ trace. Mỗi episode lấy mẫu có hoàn lại từ source pool. Arrival dùng
Poisson theo giây mô phỏng, với RNG riêng cho arrival/ảnh/priority/background.

| Mức tải | Ảnh, task/s | Background, task/s |
| --- | ---: | ---: |
| Light | 0,08 | 0,02 |
| Medium | 0,14 | 0,06 |
| Overload | 0,24 | 0,10 |

Ảnh: xác suất 25% priority 3 / deadline 20 s, còn lại priority 2 / deadline 60 s.
Background: priority 1 / deadline 120 s. Đây là giả định application, **không
phải nhãn có sẵn trong dataset**. RescueNet vốn là ảnh trên không; dùng nó làm
proxy input không tạo ra tọa độ camera mặt đất hoặc timeline thiên tai thực.

Hầu hết ảnh có cùng độ phân giải nên compute ảnh gần như đồng nhất theo model
hiện tại. Các seed dùng chung source pool; chưa có source-data holdout. Vì vậy
sự kết hợp này **phù hợp cho pilot về tranh chấp tài nguyên**, chưa đủ để khẳng
định hiệu quả phân tích thiên tai ngoài thực tế hoặc khả năng tổng quát hóa dữ liệu.

Raw đang được đọc từ `datasets/raw/rescuenet/validation/{val-org-img,val-label-img}`
và `datasets/raw/alibaba2018/batch_task.csv`. Chưa tích hợp Google Cluster/C2A;
chưa cần tải thêm để làm bước robustness tiếp theo.

## 6. Thuật toán, objective và cách đọc kết quả

| Scheduler | Quy tắc chính |
| --- | --- |
| FIFO | Task ready sớm nhất |
| EDF | Deadline sớm nhất |
| PRIORITY | Priority cao nhất; chưa bảo đảm chống bỏ đói |
| SPT | Thời gian xử lý ngắn nhất |
| FEASIBLE_AGING | Lọc khả năng hoàn thành theo deadline/pin; ưu tiên task chờ lâu hoặc score theo priority, thời gian xử lý và slack |

Nếu không có task đủ điều kiện dự kiến, `FEASIBLE_AGING` quay về SPT; không tự
drop task hay được thêm quyền điều khiển so với baseline. Aging là ưu tiên theo
thời gian chờ, không phải bằng chứng có hard fairness/SLA.

Với từng nguồn dữ liệu:

`DVR = (số task offered − số task hoàn thành đúng hạn) / số task offered`.

Task trễ, expired, mất phục vụ do pin và unfinished đều là không hoàn thành đúng
hạn. Khi hết pin, cả task dự kiến đến sau đó trong offered trace cũng bị tính
không được phục vụ. Không chỉ tính tỷ lệ trễ trong các task đã hoàn thành.

Benchmark cơ chế mới dùng mục tiêu chính:

`loss = 0,75 × DVR_ảnh + 0,25 × DVR_background`, càng thấp càng tốt.

Trọng số này là lựa chọn thử nghiệm, chưa phải SLA đã chốt. Khác với benchmark
nền tảng chỉ lấy image DVR làm primary. Nó cũng **không trực tiếp tối thiểu hóa
năng lượng**. Theo dõi thêm latency, task đúng hạn, energy UAV và runtime.
Latency của task hoàn thành phải đọc cùng DVR để tránh hiểu nhầm do task khó bị bỏ.

## 7. Đã chạy và kiểm chứng những gì?

| Giai đoạn | Thiết kế | Artifact |
| --- | --- | --- |
| Benchmark nền tảng | 30 seed × 3 tải × FIFO/EDF/Priority = 270 episode | [scheduling-verified-20261021](../../target/scheduling-verified-20261021/) |
| Chọn hệ số aging | 10 seed validation × 6 cấu hình × 7 policy = 420 episode | `validation/` trong study mới |
| Đánh giá cơ chế/ablation | 30 seed evaluation × 6 cấu hình × 8 policy = 1.440 episode | [scheduling-aging-verified-20261021](../../target/scheduling-aging-verified-20261021/) |

Study mới có 6 cấu hình = 3 tải × 2 mức pin. Validation seeds 31000–31009;
evaluation seeds 32000–32029. Chọn alpha = 0,75 trên validation rồi giữ nguyên
cho evaluation và ablation. Cùng workload/hash giữa các policy trong mỗi case.
Đây là 30 **task seed**, không phải 30 layout hoặc 30 lần train DRL.

Đã có bằng chứng kiểm chứng trong artifact:

- 64 Java tests đạt, không failure/error/skip: [log](../../target/scheduling-aging-verified.log).
- Verifier độc lập kiểm tra 27.062 validation + 92.816 evaluation task outcomes:
  nguồn task, dispatch, CPU work, pin/energy, deadline/drop và thống kê.
- Kiểm tra selection chỉ dùng validation, seed không trùng, alpha cố định và
  source/protocol hash. Các bản cố ý sửa counts/energy/hash bị từ chối.
- Verifier mới cũng kiểm tra đạt benchmark nền tảng 270 episode.

Đây là kết quả kiểm chứng đã lưu, không phải tuyên bố vừa chạy lại toàn bộ test
khi viết tài liệu tổng quan này. Xem [study-verification.json](../../target/scheduling-aging-verified-20261021/study-verification.json)
và [extra-checks.json](../../target/scheduling-aging-verified-20261021/extra-checks.json).

### Kết quả chính của study mới

Trung bình DVR theo case, mỗi policy có 180 case = 30 seed × 6 cấu hình:

| Policy | Image DVR | Background DVR | Primary loss |
| --- | ---: | ---: | ---: |
| FIFO | 24,68% | 9,95% | 0,2100 |
| EDF | 21,54% | 22,48% | 0,2178 |
| PRIORITY | 14,20% | 33,09% | 0,1892 |
| SPT | 18,19% | 6,97% | 0,1538 |
| FEASIBLE_AGING | 13,94% | 7,65% | 0,1237 |
| NO_AGING | 12,80% | 9,33% | **0,1193** |
| NO_ENERGY_GUARD | 13,96% | 8,56% | 0,1261 |
| NO_DEADLINE_GUARD | 22,67% | 13,11% | 0,2028 |

Nguồn: [macro.csv](../../target/scheduling-aging-verified-20261021/macro.csv).
Mean theo case khác pooled DVR tính từ tổng task; không trộn hai cách tổng hợp.

**Diễn giải được phép:**

- Priority bảo vệ ảnh nhưng có thể làm background chịu nhiều miss.
- Cơ chế đầy đủ cải thiện primary so với bốn baseline trong pilot đã khóa.
- NO_AGING có primary tốt hơn full: aging bảo vệ background nhưng đánh đổi ảnh.
  Chưa chọn full làm thuật toán cuối cùng.
- Deadline guard có tín hiệu lợi ích rõ; energy guard có ích ở một số case pin
  thấp. Khi mọi policy dùng hết 30.000 J, không có bằng chứng tiết kiệm tổng J.
- Với cùng công suất và lượng work hoàn thành, đổi thứ tự không tự giảm compute
  energy. Nên đo thêm công việc đúng hạn trên mỗi joule.

Chênh lệch primary full − SPT là −0,03018; interval bootstrap mô tả 95%
[−0,04137; −0,02138]. Full − NO_AGING là +0,00437
[+0,00167; +0,00720]. Bootstrap theo **30 seed cluster**, giữ các cấu hình cùng
seed đi chung; không coi 180 case là 180 mẫu độc lập. Interval chưa điều chỉnh
đa so sánh và chưa phải nghiên cứu xác nhận cuối cùng.

Selection scheduler O(Q) theo số task ready; kernel cả episode còn O(N²)
worst-case. P95 selection full khoảng 1,7–2,9 microsecond trong run này, chỉ đo
lời gọi chọn task, không phải end-to-end hay runtime trên phần cứng UAV.
Chưa có benchmark scalability. Chi tiết và trace giải thích:
[SCHEDULING_AGING_RESULTS.md](SCHEDULING_AGING_RESULTS.md).

## 8. Công việc tiếp theo, theo thứ tự

| Thứ tự | Task đề xuất | Mục đích và tiêu chí hoàn thành |
| --- | --- | --- |
| 1 | Tách compute ước lượng khỏi compute thực thi | Kernel giữ actual work; policy chỉ thấy estimate. Test bảo đảm không lộ actual/future và scheduler không làm sai bảo toàn work/energy. |
| 2 | Benchmark sai số estimate | Giữ actual workload cố định, thêm sai số theo task với RNG riêng; thử nhiễu và lệch thấp/cao. Dùng cùng estimate giữa policy, báo DVR/latency/công việc đúng hạn trên J. Không chỉ nhân cả actual và estimate cùng hệ số. |
| 3 | Chốt yêu cầu bảo vệ background | Xác định cần hard SLA, tỷ lệ phục vụ tối thiểu hay chỉ weighted loss. Giải thích vì sao cần aging; so sánh cả NO_AGING, không bỏ kết quả bất lợi. |
| 4 | Profile một model phân tích ảnh cụ thể | Chọn model, input resolution và phần cứng; đo thời gian preprocess/inference, p50/p95. Chỉ gọi energy là đo thực nếu có phép đo; nếu không vẫn ghi là power model. |
| 5 | Hoàn thiện và kiểm tra cơ chế | Dựa trên failure case và literature; đánh giá deadline/energy guard, fairness, sai số dự báo. Nếu đổi preemption/admission phải cho baseline quyền tương đương và tính overhead. |
| 6 | Robustness, scalability và xác nhận | Khóa cấu hình mới trên validation; dùng seed/config mới để xác nhận. Khảo sát tải, pin, deadline, MIPS, link, priority mix; thêm source holdout khi khả thi. Báo effect size/CI và kế hoạch nhiều so sánh. |
| 7 | Đóng gói báo cáo và reproducibility | Cố định version/protocol, lệnh tái chạy, môi trường và artifact. So sánh SOTA sau khi xác minh cùng bài toán/quyền điều khiển; không chỉ đổi tên tổ hợp heuristic để gọi là novelty. |

**Việc cần bạn quyết định khi tới bước tương ứng:** mức dịch vụ chấp nhận cho
background; model/hardware dùng profiling; mục tiêu cuối là deadline dưới pin
giới hạn hay có thêm tối ưu tổng năng lượng. Không cần tự tải thêm dataset ngay.
Nếu cần weights/model hoặc dữ liệu khác để profiling/holdout, phải chỉ rõ file,
dung lượng và cách tải trước khi yêu cầu bạn chuẩn bị.

Chưa cần mở đồng thời cache/multi-UAV/Google/C2A hoặc train lại DQN. Những phần
đó chỉ nên thêm nếu giải quyết một câu hỏi nghiên cứu cụ thể sau khi nền tảng
scheduling được kiểm tra đủ.

## 9. Tìm source và tái chạy

| Muốn xem | File / đường dẫn |
| --- | --- |
| Task và quyền scheduler | [SchedulingTask.java](scheduling/SchedulingTask.java), [TaskScheduler.java](scheduling/TaskScheduler.java) |
| Queue / deadline / energy kernel | [SchedulingSimulation.java](scheduling/SchedulingSimulation.java) |
| Cách ghép dataset | [SchedulingWorkload.java](scheduling/SchedulingWorkload.java) |
| Baseline benchmark | [SchedulingBenchmark.java](scheduling/SchedulingBenchmark.java) |
| Cơ chế thử nghiệm | [FeasibleAgingScheduler.java](scheduling/FeasibleAgingScheduler.java) |
| Study và protocol | [SchedulingStudy.java](scheduling/SchedulingStudy.java), [aging-study-protocol.json](scheduling/aging-study-protocol.json) |
| Kiểm chứng / tổng hợp | [verifier](../../scripts/verify-uav-scheduling.py), [analyzer](../../scripts/analyze-uav-scheduling-study.py) |
| Test scheduling | [simulation](../../src/test/java/uav/SchedulingSimulationTest.java), [workload](../../src/test/java/uav/SchedulingWorkloadTest.java), [mechanism](../../src/test/java/uav/FeasibleAgingSchedulerTest.java) |

Chạy từ `uav/MECSim`, cần JDK 17, Maven, Python 3 và raw dataset đúng đường dẫn.
Nhánh scheduling + verifier không cần Stable-Baselines3. `-o` chỉ dùng khi Maven
đã có dependencies trong cache; thư mục output mới phải chưa tồn tại.

```powershell
# Chạy lại test Java
mvn -o test

# Benchmark nền tảng
.\scripts\run-uav-scheduling.ps1 -Seeds 30 -Output target/scheduling-new -Offline
python scripts/verify-uav-scheduling.py target/scheduling-new

# Study cơ chế + ablation; analyzer kiểm chứng và tạo báo cáo
mvn -o compile exec:java "-Dexec.mainClass=uav.scheduling.SchedulingStudy" "-Dexec.classpathScope=compile" "-Dscheduling.output=target/scheduling-aging-new"
python scripts/analyze-uav-scheduling-study.py target/scheduling-aging-new
```

Không cần chạy lại để đọc kết quả cũ: mở [REPORT.md](../../target/scheduling-aging-verified-20261021/REPORT.md),
`macro.csv` và `paired.csv`; mở `evaluation/<scenario>/seed-<seed>/` để xem
workload và outcome từng policy. `resolved_s` là lúc chốt trạng thái task,
không luôn là completion time. Các thư mục `target/`, raw và checkpoint là
artifact local/ignored; clone repo không đồng nghĩa đã có chúng.

## 10. Thứ tự đọc và cách dùng để báo cáo

1. Đọc tài liệu này để nắm phạm vi, bằng chứng và giới hạn.
2. Đọc [SCHEDULING.md](SCHEDULING.md) để nắm mô hình, task và giả định dataset.
3. Đọc [SCHEDULING_AGING_RESULTS.md](SCHEDULING_AGING_RESULTS.md) để xem cơ chế,
   ablation, interval và failure case.
4. Khi cần liên hệ paper, đọc [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md); P0/P1 và
   [kế hoạch lifetime cũ](NEXT_STEPS.md) là tài liệu lịch sử của nhánh trước.

Flow báo cáo: **bối cảnh → phạm vi/RQ → input/decision/constraints → dataset và
giả định → baseline → benchmark → objective/runtime/complexity → kết quả và
trade-off → giới hạn → task tiếp theo**.

Có thể trình bày rằng đã xây được environment và có bằng chứng development về
deadline scheduling. Chưa trình bày rằng đã hoàn thành joint optimization,
đã chứng minh novelty, đã tiết kiệm năng lượng thực địa hoặc đã xác nhận SOTA.
