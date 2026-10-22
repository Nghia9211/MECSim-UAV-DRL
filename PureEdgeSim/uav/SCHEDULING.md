# UAV disaster analytics — task scheduling

> Benchmark nền tảng giữ offloading cố định. Extension local/UAV ngày 22/10/2026:
> [OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md),
> [OFFLOADING_RESULTS.md](OFFLOADING_RESULTS.md).

Ngày21/10/2026. Đã hoàn tất nền tảng task/queue/deadline, ba baseline và benchmark
development dùng raw RescueNet + Alibaba. Chưa có cơ chế scheduling cải tiến
trong benchmark nền tảng; các chi phí inference vẫn là giả định.
Cập nhật tiếp: đã thử FEASIBLE_AGING, SPT và ablation trên task streams mới,
gồm pin thấp: [SCHEDULING_AGING_RESULTS.md](SCHEDULING_AGING_RESULTS.md).
Chưa có bằng chứng giảm đồng thời tổng energy và mọi chỉ số dịch vụ.

## 1. Phạm vi đã chốt

RQ: Lập lịch tác vụ phân tích thiên tai dưới tải nền biến thiên ảnh hưởng thế
nào tới tỷ lệ vi phạm deadline, độ trễ và ngân sách năng lượng UAV?

Một UAV bay treo ở(400,400,10m), một CPU2000 MI/s. Ảnh được mô phỏng phát sinh
ở nguồn mặt đất ngay dưới UAV, tự offload lên UAV; Alibaba là tải nền tại CPU UAV.
RescueNet vốn là ảnh chụp trên không; ở đây nó là nguồn ảnh đầu vào đại diện,
không khẳng định có tọa độ camera mặt đất hoặc arrival timeline thực.
Vị trí/offloading cố định giữa các scheduler. Không tối ưu placement/cache.

Đường chạy riêng `uav.scheduling.SchedulingBenchmark`, dùng PureEdgeSim event
engine và UAVEdgeNode/UAVEnergyModel thật. Không sửa transition hay action24/12
của PaperSimulation/DQN. Checkpoint cũ không phải scheduler cho queue mới.

## 2. Task và thời gian

`SchedulingTask` là input immutable:

| Field | Đơn vị/ý nghĩa |
| --- | --- |
| id, source, sourceIndex | ID ổn định và ánh xạ về ảnh/source line Alibaba |
| arrivalSeconds | Thời điểm phát sinh, theo giây mô phỏng |
| readySeconds | Lúc CPU được phép chạy; ảnh cần upload xong |
| deadlineSeconds | Deadline tuyệt đối = arrival + ngân sách end-to-end |
| priority | Giả định application biết trước, không dùng nhãn mask |
| inputBytes | Dung lượng upload ảnh nén; background dùng0 vì là tải tại UAV |
| computeMi | Nhu cầu xử lý được mô hình hóa, đơn vị MI |

Ràng buộc: ready>=arrival, deadline>arrival, MI>0, field hữu hạn, ID không trùng.
Cho phép ready>deadline để ghi nhận ảnh trễ ngay do truyền. Đầu vào benchmark
yêu cầu mọi deadline<=horizon, tránh coi task chưa tới hạn là miss/censored.

`SchedulingSimulation` giữ queue và remaining MI qua mọi event; không có slot
600s hay drop cuối slot. CPU không preempt: task đang chạy tiếp tục dù có task
khẩn cấp mới đến. Task còn chờ hoặc đang truyền hết hạn thì EXPIRED_WAITING;
task đang chạy vượt deadline tiếp tục và có thể COMPLETED_LATE. Quy tắc này
giống nhau giữa mọi baseline; không tự loại task dựa trên dự báo infeasible.

Tại cùng timestamp: hạch toán work/energy, xử lý completion, expiry, pin/horizon,
nhận task ready, rồi dispatch. Hoàn thành đúng deadline được tính on-time.
Hết pin dừng CPU và UAV cùng thời điểm; remaining work không biến thành completed.
Khi hệ thống hết pin, cả task dự kiến đến sau đó trong trace cũng là dịch vụ
không cung cấp được, tính DROPPED_BATTERY trong offered-load denominator.

Các trạng thái cuối: COMPLETED_ON_TIME, COMPLETED_LATE, EXPIRED_WAITING,
DROPPED_BATTERY, UNFINISHED_HORIZON. Task đang chạy bị horizon cắt có executed MI
và remaining MI riêng. `resolved_s` là thời điểm chốt trạng thái, không nhất
thiết là completion time; với task chưa đến khi hết pin, nó có thể trước arrival.

## 3. Scheduler interface và đối chứng

`TaskScheduler.choose(readyQueue, context)` chỉ nhận danh sách bất biến các task
đã ready, chưa hết hạn. Context chứa clock hiện tại, pin còn lại, MIPS, công suất
CPU/hover và horizon. Không nhận task tương lai, RNG seed, source pool, nhãn mask
hoặc kết quả sau quyết định. MI được coi biết chính xác theo cost model hiện tại;
chưa khảo sát sai số ước lượng thời gian xử lý.

- FIFO: ready time nhỏ nhất, hòa theo arrival rồi ID.
- EDF: deadline sớm nhất, hòa theo FIFO.
- PRIORITY: priority cao nhất, hòa theo FIFO. Đây là strict priority baseline,
  chưa có aging hay bảo đảm chống starvation.

CPU work-conserving: dispatch ngay khi rảnh và có task hợp lệ. Comparator chạy
trên queue sẵn sàng tại thời điểm dispatch, không sort trước toàn bộ future jobs.
Scheduler chọn ID ngoài readyQueue bị từ chối. Chưa có admission/DVFS.

## 4. Workload, split và giả định

`SchedulingWorkload` tạo hai luồng Poisson theo giây mô phỏng bằng RNG riêng;
arrival, sample ảnh, priority và sample background có stream độc lập. Sinh
workload một lần rồi dùng cùng input immutable cho ba policy, lưu CSV+SHA256.
Đổi background rate không đổi ảnh/arrival/priority của luồng ảnh cùng config/seed.

Raw pool:449 ảnh validation,1000 Alibaba root task có một instance; chọn từ đầu
file đủ điều kiện, không đại diện toàn bộ cluster. Source pool/số row bị loại,
image SHA256 và source line được lưu cùng run. Lấy mẫu có hoàn lại; không replay
Alibaba timestamps hoặc DAG. Không ghép một dòng Alibaba thành nhãn của một ảnh.

| Giả định development | Giá trị |
| --- | --- |
| Horizon / cửa sổ sinh task | 600s / [0,300)s |
| Image rate light / medium / overload | 0.08 /0.14 /0.24 task/s |
| Background rate tương ứng | 0.02 /0.06 /0.10 task/s |
| Ảnh priority3 /priority2 | Xác suất25% /75%, độc lập mask |
| Deadline ảnh priority3 /priority2 | 20s /60s từ arrival |
| Background priority/deadline | 1 /120s từ arrival |
| Image MI | megapixels×833.3333333333334 |
| Alibaba MI | (end-start)×plan_cpu/100×1000, work scale1 |
| UAV CPU /CPU draw | 2000 MI/s /20W khi bận |
| Hover /pin UAV | 80W /1,600,000J |
| Upload | Slant10m, radio PaperParameters, link độc lập full bandwidth |

Các deadline/priority/MI/power là **giả định thử nghiệm chưa hiệu chuẩn**, không
phải ground truth từ RescueNet/Alibaba. Với ảnh cùng độ phân giải, MI gần nhau
là hệ quả cost model, không tự tạo độ đa dạng giả. Output relay tức thời, không
mô phỏng contention, RAM pressure, cache fetch hay năng lượng nguồn mặt đất.

Seeds0–29 là30 task streams trong cấu hình không gian cố định. Đây là pilot
development, không phải30 layouts hoặc30 training seeds. Chưa có source-data
holdout/profiling inference; chưa dùng range final test của nghiên cứu cũ.

## 5. Metric và công bằng

Primary: DVR của task RescueNet = (offered images - on-time images)/offered images.
Task expired, late, không được phục vụ do pin và unfinished đều nằm trong mẫu số.
Tách metrics ALL/RESCUENET/ALIBABA để thấy tác động lên tải nền. `mean_dvr` là
trung bình qua seed; `pooled_dvr` là tỷ số từ tổng task. Hai số có thể khác nhau.

Secondary: số task on-time/late/expired; latency từ arrival tới completion cho
task đã hoàn thành; CPU waiting time từ ready tới start cho task đã bắt đầu;
queue max; hover/compute J, pin còn lại; runtime dispatch và toàn simulation.
Latency là conditional metric, luôn đọc cùng DVR/throughput.

Energy là UAV hover +CPU, không phải tổng energy toàn hệ thống. Khi tất cả work
đều hoàn thành, đổi thứ tự đơn thuần không giảm compute energy ở cùng MIPS/W.
Có test riêng xác nhận điều này. Energy khác trong pilot chủ yếu do khác lượng
work được thực thi/drop. Chưa thể kết luận scheduler tiết kiệm energy từ bảng DVR.
Pin hiện không binding trong benchmark; depletion được kiểm tra riêng bằng fixtures.

Runtime dispatch chỉ đo lời gọi comparator, không gồm chuẩn bị views, event
processing, raw I/O hay IPC. Simulation wall time gồm kernel và lưu outcome trong
memory, không gồm ghi CSV. Có warm-up và luân phiên thứ tự policy theo seed;
số đo nhỏ vẫn chịu ảnh hưởng JIT/OS, không là latency phần cứng UAV thực địa.

## 6. Kiểm chứng đã thực hiện

- Task1: model/timing và input validation.
- Task2: queue bền và remaining work; fixture vượt600s.
- Task3: scheduler API, FIFO/EDF/Priority, visibility và dispatch hợp lệ.
- Task4: raw dataset mapping, fixed physical-time arrivals, paired input hash.
- Task5: deadline/drop denominator và work/energy/battery conservation.
- Task6: benchmark30 seeds×3 mức tải×3 policy =270 episodes.

**58 Java tests đạt**:46 tests cũ +12 tests mới (SchedulingSimulation10,
SchedulingWorkload2). Bao gồm đúng-deadline tie, late completion, nonpreemption,
upload hết deadline, horizon partial work, hết pin, trường hợp queue rỗng,
đối xứng tie, pin/CPU snapshot, và30 run boundary ngẫu nhiên trên3 policy.
**17 Python regression tests đạt** cho luồng paper/Gym, gồm raw mixed.

Verifier Python stdlib độc lập đã kiểm tra **90 paired workloads,270 episodes,
17,370 task outcomes**: tính lại mapping từ source, lựa chọn FIFO/EDF/Priority
tại từng dispatch, không idle giả, CPU không overlap, work/energy conservation,
DVR và bảng summary. Dùng assert fail-closed, không chỉ đọc log BUILD SUCCESS.
Đã thử làm sai số task on-time, compute energy và workload hash trong dữ liệu
đọc vào verifier; cả ba lỗi đều bị từ chối (`verifier-negative-checks.json`).

Run chính: `target/scheduling-verified-20261021/`; xem `verification.json` và
`REPORT.md`. Logs: `target/scheduling-verified-check.log`,
`target/scheduling-python-regression.log`. Đây là kiểm chứng mô hình đã định
nghĩa, chưa xác nhận mô hình phản ánh hardware hoặc disaster arrivals thực tế.

## 7. Kết quả development đầu tiên

DVR ảnh trung bình qua30 seed, đơn vị phần trăm; thấp hơn tốt hơn.

| Tải | FIFO | EDF | Priority |
| --- | ---: | ---: | ---: |
| Light | 3.09% | 2.11% | 2.11% |
| Medium | 13.59% | 6.10% | 5.15% |
| Overload | 42.42% | 41.43% | 23.06% |

Ở overload: latency ảnh hoàn thành FIFO37.396s, EDF38.274s, Priority33.372s.
Mean UAV energy tương ứng55,040.1J /55,502.9J /55,315.1J.
Priority giảm miss ảnh so với FIFO nhưng **background DVR tăng từ3.19% lên65.17%**.
EDF cũng tăng background DVR lên31.86%. Do vậy chưa có policy thắng trên mọi
tiêu chí; strict priority có đánh đổi dịch vụ nền rõ ràng.

Không tune hệ số theo bảng này; không tuyên bố significance/novelty/SOTA.
Mean±sample SD, pooled ratios và runtime đầy đủ nằm trong CSV của run.

## 8. Cách chạy và đọc output

Từ `uav/MECSim`, dùng output chưa tồn tại:

```powershell
.\scripts\run-uav-scheduling.ps1 -Seeds 30 -Output target/scheduling-new -Offline
python scripts/verify-uav-scheduling.py target/scheduling-new
```

Linux/Windows trực tiếp:

```bash
mvn -o compile exec:java -Dexec.mainClass=uav.scheduling.SchedulingBenchmark -Dexec.classpathScope=compile -Dscheduling.seeds=30 -Dscheduling.output=target/scheduling-new
python scripts/verify-uav-scheduling.py target/scheduling-new
```

Bỏ `-o` nếu cần tải Maven dependencies. Verifier chỉ dùng Python stdlib.
Đổi đường dẫn raw bằng `-Dscheduling.images=...`, `-Dscheduling.masks=...`,
`-Dscheduling.alibaba=...`. Output tồn tại bị từ chối, không ghi đè.

- manifest.json: assumptions, settings, nguồn, trạng thái COMPLETE/RUNNING.
- source-pools/: nguồn ảnh/hash và Alibaba rows đã dùng.
- source/: snapshot code của lần chạy.
- scenario/seed-N/workload.csv: offered trace chung của ba scheduler.
- scenario/seed-N/FIFO.csv, EDF.csv, PRIORITY.csv: outcome, start/resolution, executed/remaining MI.
- episodes.csv: metrics từng seed/policy/source; summary.csv và REPORT.md tổng hợp.
- verification.json: kết quả kiểm tra độc lập và hash verifier.

## 9. Complexity và bước nghiên cứu tiếp

Comparator baseline hiện quét queue O(Q), tạo immutable views O(Q). Calendar
TreeSet O(log N) mỗi thao tác, nhưng kernel còn quét toàn bộ N task ở mỗi event;
worst-case cả episode O(N²), bộ nhớ O(N). Không nhầm runtime comparator với
runtime simulator. Chưa benchmark scaling N lớn hoặc tối ưu heap cho từng policy.

Nền tảng đã sẵn sàng để thử scheduler xét slack/priority cùng ràng buộc năng
lượng và mức phục vụ tối thiểu cho background. Cần khóa cơ chế, ablation và
validation split trước khi chạy; không tối ưu trực tiếp theo270 development
episodes này. Nếu bổ sung admission/DVFS, phải thêm cost model, metric task bị
từ chối và kiểm thử riêng. Chưa train DRL mới; chưa cần tải thêm dataset.
