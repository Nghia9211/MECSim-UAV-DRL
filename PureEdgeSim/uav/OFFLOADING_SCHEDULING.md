# Offloading + task scheduling cho UAV disaster analytics

Cập nhật **22/10/2026**. Đây là hướng mở rộng đang triển khai: quyết định nơi
xử lý task ảnh **local/UAV** kết hợp thứ tự phục vụ CPU UAV. Không phải bản tái
hiện kết quả paper Azfar và không thay action/checkpoint DQN cũ.

## 1. Bài toán và phần đã bổ sung

```text
RescueNet → task ảnh tại thiết bị mặt đất
                      │
              quyết định offloading
                 ┌────┴─────┐
                 ↓          ↓
            queue local   upload → queue UAV ← tải nền Alibaba
                 ↓                       ↓
             CPU local             scheduler CPU UAV
                 └───────────┬───────────┘
                      deadline / energy
```

Trước đây, mọi task ảnh được cố định gửi lên UAV. Hiện đã có:

- CPU, FIFO queue, pin và hạch toán idle/compute/TX riêng cho từng thiết bị.
- Quyết định toàn task tại arrival: local hoặc UAV, không đổi nơi xử lý sau đó.
- Upload chỉ áp dụng cho đường UAV; local có thể chạy từ arrival. Deadline
  vẫn tính end-to-end từ arrival, không reset lúc upload xong.
- Queue UAV dùng scheduler được chọn. Background là tải được mô phỏng phát
  sinh sẵn trên UAV, không phải task có thể offload.
- Dự báo completion bằng cách replay queue đã tiếp nhận theo chính scheduler
  UAV đang dùng. Do đó thay scheduler có thể thay cả quyết định offloading.
- Tách **estimated MI** policy được thấy khỏi **actual MI** kernel thực thi.
- Mất pin UAV không dừng CPU local; thiết bị hết pin làm mất local/upload chưa
  xong, nhưng không xóa task đã upload thành công lên UAV.
- Metrics và trace cho local, upload, CPU, deadline và năng lượng mọi node.

Đây là infrastructure và các policy đối chứng/prototype. Chưa có DRL mới hoặc
tuyên bố cơ chế là novel/SOTA. Kernel scheduling-only và paper/DRL cũ được giữ
nguyên để đối chiếu; test ALL_UAV kiểm tra parity với kernel scheduling cũ.

## 2. Phạm vi và input/output

RQ làm việc: **Kết hợp quyết định offloading với lập lịch có xét deadline và
trạng thái năng lượng ảnh hưởng thế nào tới tỷ lệ hoàn thành tác vụ phân tích
thiên tai đúng hạn dưới tải nền biến thiên?**

| Thành phần | Định nghĩa |
| --- | --- |
| Input task | Arrival, deadline tuyệt đối, priority, input bytes, actual MI, estimated MI, source và device |
| Quyết định offloading | LOCAL hoặc UAV tại arrival của từng ảnh |
| Quyết định scheduling | ID task ready được chạy tiếp khi CPU UAV rảnh |
| CPU local | FIFO cố định, mỗi thiết bị có một CPU riêng |
| UAV | Một UAV thật trong PureEdgeSim event engine, hovering cố định (400,400,10 m) |
| Ràng buộc | Một task chạy trên mỗi CPU; không chạy trước ready; không vượt pin; không preemption/migration/rejection |
| Metric | Image/background DVR, completed latency, throughput, năng lượng UAV/ground/tổng và runtime |

Local và UAV có thể xử lý song song; các CPU local khác nhau cũng độc lập.
Thiết bị có thể vừa compute vừa TX, cùng chia một ngân sách pin. Nhiều upload
có thể chạy đồng thời và cộng công suất TX. **Radio hiện không có contention**:
mỗi upload hưởng đầy đủ link rate độc lập. Không có edge server thứ ba/cloud,
cache, tối ưu placement/trajectory, DVFS hoặc đường return hữu hạn.

## 3. Hai dataset và các giả định

Giữ cách đọc raw và tạo actual workload của [SCHEDULING.md](SCHEDULING.md):
449 ảnh RescueNet validation và pool 1.000 Alibaba task đủ điều kiện. Không
chạy neural inference; không dùng mask làm nhãn độ khẩn cấp. Không replay
Alibaba timestamp/DAG. `plan_cpu` là requested CPU, không phải utilization đo.

| Tham số development | Giá trị |
| --- | --- |
| Horizon / arrival window | 600 s / [0,300) s |
| Thiết bị mặt đất | 4 thiết bị đồng nhất; source assignment ngẫu nhiên tái lập |
| CPU local | 500 MI/s; incremental CPU 3 W; idle 0,5 W |
| TX source | 0,1 W incremental electrical, giả định riêng; không suy ra từ RF power |
| Pin từng source | 5.000 J |
| CPU UAV | 2.000 MI/s; incremental CPU 20 W |
| Hover / pin UAV | 80 W / 1.600.000 hoặc 30.000 J |
| Link | Cùng slant 10 m cho mọi source; radio theo PaperParameters, khoảng 20 Mbps |
| Image MI | Megapixel × 833,3333333333334 |
| Background MI | (end − start) × plan_cpu/100 × 1.000 |
| Image priority / deadline | 25% priority 3 / 20 s; còn lại priority 2 / 60 s |
| Background priority / deadline | 1 / 120 s |
| Arrival ảnh / background | Light 0,08/0,02; medium 0,14/0,06; overload 0,24/0,10 task/s |

**Thông số CPU/power/deadline, vị trí và source assignment là giả định**, chưa
được hiệu chuẩn phần cứng. Link giống nhau là cách kiểm soát yếu tố không gian;
không có nghĩa là đã tái tạo địa hình/GPS của RescueNet. Các source được xem là
cùng nằm ngay dưới UAV trong mô hình link, chưa có hình học riêng từng thiết bị.
Không đồng nhất task
Alibaba gốc với một phép inference ảnh: nó chỉ làm tải nền cạnh tranh CPU.

OffloadingJob.assign tạo RNG riêng cho source assignment và estimate noise;
thay noise không thay arrival, priority, actual MI hoặc source device. Noise
hiện là multiplicative uniform trong [1−error,1+error], không phải mô hình
dự báo đã học. Mặc định error=0; có pilot error=0,4. Mọi policy cùng case dùng
cùng workload/hash và cùng estimate. Không có source-data holdout.

Khi task chạy vượt estimate, remaining estimate được clamp dương nhỏ; forecast
có thể quá lạc quan. Đây là baseline point-estimate, chưa là mô hình dự báo
remaining time đã hiệu chuẩn hoặc có bảo đảm robustness.

## 4. Quyền quan sát và dự báo queue

Policy offloading nhận immutable task view chứa **estimated MI**, và dự báo cho
hai nơi xử lý. Không nhận OffloadingJob/actual MI, seed, mask hoặc task chưa
arrive. Scheduler chỉ nhận task ready, estimated remaining MI và context pin,
CPU, thời gian hiện tại, horizon.

Dự báo chỉ dùng các job đã tiếp nhận, gồm upload đã bắt đầu nhưng chưa xong:

1. Giữ phần còn lại dự kiến của task đang chạy; không preempt.
2. Replay các dispatch theo FIFO local hoặc scheduler UAV được chọn.
3. Áp dụng ready/deadline, tính thời gian hoàn thành dự kiến của candidate.
4. Ước tính pin cần trả cho idle/hover và công việc trong queue đến completion.
5. Với offload, kiểm tra thêm source đủ pin upload; giữ công suất CPU source
   đang chạy trong suốt upload là một xấp xỉ bảo thủ.

Estimated remaining = max(1e−6, estimated total − observed executed work).
Đã chạy bao lâu là thông tin causal; actual remaining không được đưa cho policy.
Forecast không biết các task sẽ đến sau quyết định, không bảo đảm completion
thật khi estimate sai, queue thay đổi hoặc nguồn hết pin.

Scheduler dùng trong projection phải **thuần, không có side effect**: cùng input
cho cùng output. Các scheduler tích hợp đáp ứng hợp đồng này. Chưa hỗ trợ một
scheduler stateful được gọi dự báo rồi vô tình thay đổi trạng thái thật.

Các task cùng arrival được quyết định theo ID tăng dần, sau khi xử lý completion,
expiry và battery tại timestamp đó; dispatch CPU sau cả batch. Task xuất hiện
sau trong batch chưa nằm trong forecast của task trước. Quy tắc này giống nhau
cho mọi policy, được ghi lại để kiểm tra causal visibility.

## 5. Policy đối chứng và ý nghĩa “joint”

| Offloading policy | Quy tắc |
| --- | --- |
| ALL_LOCAL | Ép mọi ảnh xử lý local |
| ALL_UAV | Ép mọi ảnh lên UAV, kể cả UAV đã mất pin thì ghi nhận không phục vụ được |
| SHORTEST_FINISH | Chọn nơi available có predicted finish sớm hơn; hòa chọn local |
| DEADLINE_ENERGY | Nếu chỉ một nơi dự kiến đủ pin và kịp deadline thì chọn nơi đó; nếu cả hai đáp ứng thì chọn marginal energy thấp hơn; còn lại chọn earliest finish để best effort |

Marginal energy dùng để so route:

```text
Local = estimated MI / local MIPS × incremental local CPU W
UAV   = upload seconds × source TX W
      + estimated MI / UAV MIPS × incremental UAV CPU W
```

Idle/hover không cộng riêng vào marginal cost vì là baseline mission chung,
nhưng **có tính vào battery feasibility và energy đo toàn episode**. Đây là
heuristic cost, không phải dự báo chính xác thay đổi tổng energy cả hệ thống;
route có thể thay queue, thời gian chết pin và lượng công việc được thực thi.

Nếu cả hai nơi dự kiến không kịp/không đủ pin, task vẫn được route best effort;
không được loại khỏi offered denominator. Không fallback/migrate sau quyết định.

Cross 4 policy trên với 5 scheduler UAV: FIFO, EDF, PRIORITY, SPT,
FEASIBLE_AGING(alpha=0,75). Hệ số aging giữ từ development cũ, không chọn lại
trên benchmark này. Local luôn FIFO. **Không có kết luận mặc định rằng full aging
là tốt nhất**; benchmark scheduling trước cho thấy NO_AGING tốt hơn về loss
tổng hợp khi đó. Ở đây 20 cặp nhằm kiểm tra factor offloading/scheduling, chưa
phải bộ ablation đầy đủ cho một thuật toán cuối.

“Joint” ở đây là route xét queue theo scheduler thực sự sẽ chạy, và route thay
đổi queue mà scheduler phục vụ. Không phải tối ưu toàn cục có chứng minh, cũng
không phải DRL điều khiển đồng thời hai action.

## 6. Thời gian, failure và hạch toán năng lượng

Task local ready tại arrival; offloaded ready sau upload. Hoàn thành đúng
deadline hoặc đúng thời điểm hết pin được ghi completion trước. Task đang chạy
không bị ngắt chỉ vì qua deadline: có thể COMPLETED_LATE. Task chưa chạy/upload
chưa xong khi tới deadline là EXPIRED_WAITING.

Hết pin source: dừng CPU local và mọi upload của source cùng timestamp. Task
đã upload xong vẫn được xử lý trên UAV. Task ảnh đến sau source chết được đếm
DROPPED_DEVICE_BATTERY tại arrival, không gọi policy nữa. Hết pin UAV: dừng CPU
UAV và upload đến UAV; local tiếp tục. Background đến sau UAV chết vẫn nằm trong
offered count và nhận DROPPED_UAV_BATTERY tại arrival. Policy adaptive có thể
chọn local cho ảnh mới sau khi UAV chết.

Các status cuối: COMPLETED_ON_TIME, COMPLETED_LATE, EXPIRED_WAITING,
DROPPED_UAV_BATTERY, DROPPED_DEVICE_BATTERY, UNFINISHED_HORIZON.
`resolved_s` là lúc chốt status, không luôn là completion. Mọi deadline không
vượt horizon để mẫu số không chứa task còn chưa đến hạn.

```text
E_ground = Σ_device (idle W × powered seconds
                  + CPU W × CPU busy seconds
                  + TX W × tổng thời gian upload thực tế)
E_UAV    = hover W × powered seconds + CPU W × CPU busy seconds
E_total  = E_ground + E_UAV
```

Mọi node tiếp tục trả idle/hover tới horizon hoặc lúc chết pin, dù queue rỗng;
không tự trả UAV về sớm hay tắt node để tạo lợi ích riêng cho một policy.
RX và truyền kết quả bị bỏ qua trong model này, không gọi E_total là năng
lượng toàn hệ thống vật lý đã đo. Giảm J do chết sớm/drop nhiều không phải cải
thiện; luôn đọc energy cùng DVR, throughput và J/task đúng hạn.

Không gộp latency/energy/DVR thành một reward hoặc primary tùy ý trong benchmark
này. Cần chốt mức dịch vụ background/objective trước khi chọn cơ chế cuối.
Completed-only latency cũng có selection bias, phải đọc cùng tỷ lệ task không
hoàn thành đúng hạn.

## 7. Source, cách chạy và artifact

- [OffloadingJob.java](offloading/OffloadingJob.java): tách actual/estimate, source assignment.
- [OffloadingPolicy.java](offloading/OffloadingPolicy.java): decision API và 4 policy.
- [OffloadingSimulation.java](offloading/OffloadingSimulation.java): local/UAV queues, forecast, pin, execution.
- [OffloadingBenchmark.java](offloading/OffloadingBenchmark.java): paired benchmark và trace.
- [benchmark-protocol.json](offloading/benchmark-protocol.json): tham số đã khai báo.
- [OffloadingSimulationTest.java](../../src/test/java/uav/OffloadingSimulationTest.java): ca biên, queue coupling, parity và conservation.
- [verify-uav-offloading.py](../../scripts/verify-uav-offloading.py): kiểm chứng độc lập từ trace.

Từ `uav/MECSim`, dùng Java 17 + Maven + Python 3 stdlib. Không cần GPU/SB3,
không cần tải thêm dataset nếu raw đã có theo [DATASET_SETUP.md](DATASET_SETUP.md).

```powershell
mvn -o test

.\scripts\run-uav-offloading.ps1 -Seeds 30 -Output target/offloading-new -Offline
python scripts/verify-uav-offloading.py target/offloading-new
python scripts/test-uav-offloading-verifier.py target/offloading-new

# Estimate noise, giữ nguyên actual input/source assignment của các seed chung
.\scripts\run-uav-offloading.ps1 -Seeds 5 -EstimateError 0.4 -Output target/offloading-noise-new -Offline
python scripts/verify-uav-offloading.py target/offloading-noise-new
```

Linux hoặc chạy Java trực tiếp:

```bash
# Java 17/JDK, Maven và Python phải có trên PATH; có thể activate Conda trước.
bash scripts/run-uav-offloading-server.sh --seeds 30 --output target/offloading-new --offline

# Hoặc gọi từng bước, nếu muốn điều khiển riêng test/benchmark/verification:
mvn -o compile exec:java -Dexec.mainClass=uav.offloading.OffloadingBenchmark -Dexec.classpathScope=compile -Doffloading.seeds=30 -Doffloading.firstSeed=41000 -Doffloading.output=target/offloading-new
python scripts/verify-uav-offloading.py target/offloading-new
```

Linux runner chạy Java tests, benchmark, verifier và 7 test của verifier. Có
`--dry-run`, `--first-seed`, `--estimate-error`; dùng output mới cho mỗi lần.
Không chạy cả runner lẫn các lệnh thủ công vào cùng một thư mục output.

`-o`/`-Offline` chỉ dùng nếu Maven dependencies đã cache. Output phải chưa tồn
tại, lỗi không được coi là run complete. Không chạy đồng thời episode trong
cùng JVM vì engine có registry tĩnh; các run riêng process không chia registry.

Artifact gồm manifest/protocol/source hashes, source pools, workload từng case;
`<policy>-tasks.csv`, `-decisions.csv`, `-energy.csv`; `episodes.csv`. Verifier
tạo `verification.json`, `summary.csv`, `REPORT.md`; không sửa raw traces.

`mean_dvr` là trung bình theo case, `pooled_dvr` từ tổng số task; không trộn hai
cách tổng hợp. Tổng energy lặp lại ở các dòng source, **không cộng ba dòng
ALL/RESCUENET/ALIBABA**. `total_j_per_on_time` là tổng energy chia số task đúng
hạn của source được chọn, không phải năng lượng attribution riêng cho source đó.

Chi phí selection scheduler O(Q); hai queue forecast O(Q²) worst-case mỗi
quyết định offloading. Cả episode có thể O(N³) worst-case ở bản replay đơn giản
này. Routing runtime có gồm forecast, scheduler runtime chỉ selection. Chưa
được benchmark scalability hoặc đo trên thiết bị UAV thực.

## 8. Việc còn lại sau nền tảng này

Kết quả đã chạy và kiểm chứng: [OFFLOADING_RESULTS.md](OFFLOADING_RESULTS.md).
Gồm 84 Java tests, 17 regression Python, 7 test verifier và 4.200 episode được
replay độc lập; không coi các episode dùng chung seed là mẫu độc lập.

1. Chốt objective và yêu cầu dịch vụ background; kiểm tra trade-off thay vì
   chọn policy sau khi xem chỉ số thuận lợi.
2. Profile local/UAV inference, thời gian truyền và power để thay giả định MI/W.
3. Khảo sát estimate bias, pin source, link contention và heterogeneity; noise
   uniform pilot không thay cho các kiểm tra này.
4. Xây cơ chế cải tiến có giả thuyết cụ thể, ablation và so sánh cùng quyền
   điều khiển; giữ seed/config mới cho đánh giá xác nhận.
5. Placement/trajectory/cache chỉ thêm khi trở thành biến nghiên cứu cần thiết.
   Không gọi kết quả hiện tại là đã giải toàn bộ joint hoặc reproduce paper.
