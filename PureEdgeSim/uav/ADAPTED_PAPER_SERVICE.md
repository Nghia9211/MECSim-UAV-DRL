# Nối chọn thiết bị của paper với offloading và CPU scheduling

Ngày **23/10/2026**. Đã bổ sung tầng phục vụ thiết bị di động vào cùng
`OffloadingSimulation`, dùng lại local/UAV queues, pin, policy offloading và
scheduler. Đây là **môi trường mở rộng có heuristic chọn thiết bị được thích
nghi**, không phải bản tái hiện nguyên vẹn Azfar. Bản benchmark RR/Oldest bên
dưới chưa train DQN; adapter và lượt train DQN development bổ sung sau đó được
ghi riêng tại [MOBILE_DRL.md](MOBILE_DRL.md).

## 1. Luồng thực thi mới

```text
Round Robin / Oldest Data chọn thiết bị còn sống
                      ↓
UAV bay tới tọa độ thiết bị (thời gian bay + năng lượng bay)
                      ↓
Hover phục vụ: các source trong slant coverage 65 m có thể upload
                      ↓
Policy offloading chọn local/UAV cho từng task khi nó phát sinh
                      ↓
FIFO local / scheduler CPU UAV
                      ↓
Task completion → deadline + năng lượng + cập nhật dữ liệu nhận được
```

Các source trong coverage đều có thể upload, không chỉ thiết bị đích. Không
upload trong khi bay. CPU local và CPU UAV vẫn có thể chạy trong lúc UAV bay;
CPU và propulsion cùng chia pin UAV, dừng tại cùng thời điểm cạn pin.

**Quy tắc task ngoài coverage:** xử lý local ngay, không chờ một chuyến UAV
tương lai. Đây là common feasibility rule cho mọi policy. Vì vậy `ALL_UAV`
trong mobile mode có nghĩa **ALL_UAV_WHEN_COVERED**; ngoài coverage, khi stop
đã đóng hoặc UAV đã chết thì task ảnh còn source sống chuyển local. Không so
tên này như thể nó có quyền offload ngoài coverage. Background Alibaba luôn
là workload phát sinh sẵn tại CPU UAV.

Quyết định task là irrevocable; không migration/retry sau khi route. Task
local không tự chuyển lên UAV khi UAV tới sau. Deadline tính từ arrival,
không được reset khi UAV tới, upload xong hoặc CPU bắt đầu chạy.

## 2. Quy tắc phục vụ và các mốc thời gian

- UAV chọn thiết bị lần đầu tại t=0, trước batch arrival tại t=0.
- Bay thẳng với tốc độ cấu hình; không được teleport. Task xuất hiện trên
  đường bay vẫn arrival và xử lý theo quy tắc local.
- Đến nơi thì mở stop phục vụ trong **30 s**. Coverage và rate được tính theo
  tọa độ UAV đang hover, không dùng reference 10 m của workload làm rate thật.
- Hết dwell thì stop đóng, không nhận upload mới. Nếu upload đang dở, UAV ở
  lại tới khi tất cả upload đó xong, hết deadline hoặc mất pin nguồn/UAV.
- Sau đó gọi policy chọn điểm đến tiếp. Không cần chờ CPU UAV rỗng: computation
  có thể tiếp tục trong chuyến bay kế.
- Task/CPU completion và upload completion thắng tie ở cùng timestamp với
  deadline/pin. Xử lý completion, expiry và death trước cập nhật lượt phục vụ;
  sau đó nhận task arrival, cuối cùng mới dispatch CPU.
- Nếu tất cả source đã chết, không còn chọn đích; background vẫn có thể chạy
  trên UAV còn pin. Node vẫn trả idle/hover tới horizon hoặc depletion.

Trong log, `planned_arrival_s` là kế hoạch; nếu hết pin giữa đường, UAV dừng
ở vị trí đã bay được. Không được coi planned arrival là đã đến nơi.

## 3. Trạng thái thiết bị, độ mới và giới hạn so với paper

Tầng chọn thiết bị chỉ nhận tọa độ/trạng thái hiện tại, pin source, connected
flag, latest delivered generation và age; không có task tương lai, actual MI,
mask label hoặc outcome chưa xảy ra. API trả ID source sống. Round Robin bỏ qua
source chết; Oldest Data chọn age lớn nhất, hòa theo vòng từ target trước.

Trong extension này:

```text
latest_generation[d] = thời điểm phát sinh mới nhất trong các task đã có kết quả nhận được
age_seconds[d](t)    = t − latest_generation[d]
```

Khởi tạo generation=0 là giả định có một cập nhật nền tại t=0. Local completion
chỉ cập nhật nếu source `connected=true`; local compute khi mất kết nối chưa
được coi là trung tâm đã nhận kết quả. UAV completion relay kết quả tức thời.
Cả completed-on-time và completed-late có thể cập nhật thông tin, nhưng late
vẫn là deadline miss. Kết quả cũ hoàn thành sau không làm generation lùi lại.

Đây là **continuous-time freshness theo generation**, khác tuổi tăng theo
slot của paper. Chưa dùng age làm hard termination constraint, chưa có lifetime
objective hay outage power-grid dynamics. `connected` chỉ mô hình hóa khả năng
chuyển kết quả local tức thời; mọi source trong pilot đều battery-powered.
Chưa mô phỏng backhaul/RX/output delay hoặc mất liên lạc theo thời gian.

Không nối `PaperGymBridge` hoặc checkpoint DQN cũ vào mobile mode. Cùng 12 thiết
bị không làm transition/reward/state mới tự tương đương paper. Adapter mới
`MobileGymBridge`, state/reward và lượt train thử được ghi trong
[MOBILE_DRL.md](MOBILE_DRL.md); paper reproduction vẫn ở đường chạy riêng trong
[PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md).

## 4. Cấu hình và công bằng thí nghiệm

Protocol: [mobile-protocol.json](offloading/mobile-protocol.json).

| Thành phần | Cấu hình development |
| --- | --- |
| Thiết bị | 12 CPU local đồng nhất, 500 MI/s; idle 0,5 W + CPU 3 W + mỗi upload 0,1 W; pin 5.000 J |
| Vị trí | 12 tọa độ chuẩn hóa random seed42, scale thành vùng 250×250 hoặc 800×800 m |
| UAV | Bắt đầu (0,0,10 m), v=5 m/s, range slant65 m, flight150 W/hover80 W |
| CPU/pin UAV | 2.000 MI/s, CPU20 W; pin1.600.000 hoặc30.000 J |
| Kết nối | Cùng8/12 source connected qua mask độc lập cố định |
| Thời gian | Horizon600 s, arrival[0,300) s |
| Tải | Light0,08/0,02; overload0,24/0,10 image/background task/s |
| Policy | 2 selector ×2 offloading (ALL_UAV, DEADLINE_ENERGY) ×2 scheduler (FIFO, EDF) |
| Seed task | 51000–51029; shared workload/source assignment giữa mọi policy và layout/battery của cùng load/seed |

RescueNet/Alibaba mapping, synthetic MI/deadline/priority và source pool giữ
như [OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md). Reference upload_ready
trong `workload.csv` chỉ là giá trị của link 10 m để giữ source input độc lập
geometry; actual ready nằm ở task trace, dynamic duration ở coverage trace.

30 task seeds không phải30 layout độc lập. Chỉ có hai spatial layouts scale
từ cùng tọa độ chuẩn hóa. Có8 cấu hình×30 seed×8 policy=**1.920 episode**,
240 paired cases nhưng chỉ60 offered workloads khác nhau (2load×30seed).
Không nhân các source rows thành nhiều mẫu độc lập.

Forecast route chỉ dùng admitted queues và estimated MI. Các chuyến đi tương
lai chưa được policy quyết định nên forecast giả định hover sau stop hiện tại;
đây không phải một planner nhìn trước lộ trình. Scheduler energy guard vẫn dùng
hover baseline; nó không bảo đảm đủ pin khi CPU chạy cùng một chuyến bay tương
lai. Kernel luôn tính actual flight energy và cắt work chính xác khi hết pin.

## 5. Source và lệnh chạy

- [DeviceSelectionPolicy.java](offloading/DeviceSelectionPolicy.java): selector causal.
- [MobileService.java](offloading/MobileService.java): geometry/service config và telemetry.
- [OffloadingSimulation.java](offloading/OffloadingSimulation.java): runMobile, movement/coverage gate/freshness trên kernel chung.
- [MobileServiceBenchmark.java](offloading/MobileServiceBenchmark.java): paired benchmark và snapshot.
- [MobileServiceTest.java](../../src/test/java/uav/MobileServiceTest.java): hand cases và parity.
- [verify-uav-mobile.py](../../scripts/verify-uav-mobile.py): independent audit dùng lại queue/energy audit với propulsion động.

Từ `uav/MECSim`, Java17/Maven/Python3, raw dataset sẵn có, CPU là đủ:

```powershell
mvn -o test
.\scripts\run-uav-mobile.ps1 -Seeds 30 -Output target/mobile-new -Offline
python scripts/verify-uav-mobile.py target/mobile-new
python scripts/test-uav-mobile-verifier.py target/mobile-new
```

Linux dùng entrypoint Java tương đương (chưa có runner shell mobile riêng):

```bash
mvn -o compile exec:java -Dexec.mainClass=uav.offloading.MobileServiceBenchmark -Dexec.classpathScope=compile -Dmobile.seeds=30 -Dmobile.output=target/mobile-new
python scripts/verify-uav-mobile.py target/mobile-new
python scripts/test-uav-mobile-verifier.py target/mobile-new
```

Output mới phải chưa tồn tại; `-o` chỉ khi dependencies đã cache. Lần triển
khai này chạy local, **chưa push GitHub hoặc triển khai run mới trên server**.

## 6. Đọc artifact và bước tiếp

Run chính: [mobile-verified-20261023](../../target/mobile-verified-20261023/).
`episodes.csv` có từng source/case; `summary.csv` do verifier tạo. Flight/hover
và total energy được tách riêng trong episodes. Dòng energy UAV `idle_j` ở mobile
mode là **tổng propulsion flight+hover**, không chỉ hover; legacy fixed mode
vẫn có nghĩa hover-only. Không cộng energy lặp giữa ALL/RESCUENET/ALIBABA.

Trong từng scenario/seed, xem:

- `*-visits.csv`, `*-views.csv`: lựa chọn điểm đến và state causal lúc chọn.
- `*-positions.csv`: vị trí và pin theo các event timestamp, không phải đều1s.
- `*-coverage.csv`: available/slant/duration của từng image khi policy được gọi.
- `*-tasks.csv`, `*-decisions.csv`, `*-energy.csv`: execution/offloading/pin.
- `*-updates.csv`: generation và thời điểm nhận kết quả, gồm completed-late.

Không so DVR của run mới12local CPU trực tiếp với run cũ4CPU rồi quy mọi
khác biệt cho selector. Deadline20/60s không scale theo vùng: ở vùng rộng nhiều
task sẽ local vì UAV còn trên đường. Ít offload có thể giảm queue miss nhưng
làm UAV hỗ trợ ít hơn; cần đọc counts/coverage cùng DVR và energy. Final age
tại600s còn bị ảnh hưởng drain period không có arrival sau300s, không thay cho
time-average age hoặc lifetime.

## 7. Kết quả đã kiểm chứng ngày 23/10/2026

- **95 Java tests đạt**, không failure/error/skip, gồm 11 test mobile mới.
- **17 Python regression tests đạt**, có kiểm tra đường chạy dataset cũ.
- **7 test verifier offloading cũ và 8 test verifier mobile đạt**. Các test âm
  sửa trajectory, coverage, state, arrival, update, energy hoặc decision trong
  bản sao và xác nhận auditor phát hiện sai lệch.
- Run chính: **1.920 episode, 131.232 task outcomes, 240 paired cases**.
  [Kiểm tra độc lập: PASS](../../target/mobile-verified-20261023/verification.json).
  [Bảng tổng hợp](../../target/mobile-verified-20261023/summary.csv) chứa đủ 8
  cấu hình × 8 policy, tách ALL/RESCUENET/ALIBABA. Đây là benchmark development
  với hai kích thước vùng trên cùng layout chuẩn hóa, không phải 30 layout.

Ví dụ **vùng 250×250 m, overload, pin UAV 1.600.000 J**, trung bình 30 task
seeds. DVR chỉ tính task RescueNet; energy là tổng của toàn bộ các node và cả
hai workload; offloaded là số task ảnh được route lên UAV trung bình mỗi episode.

| Selector / offloading / CPU | Image DVR | Tổng năng lượng (kJ) | Ảnh offloaded | Final mean age (s) |
| --- | ---: | ---: | ---: | ---: |
| Round Robin / ALL_UAV / FIFO | 15,92% | 74,36 | 8,93 | 430,5 |
| Oldest Data / ALL_UAV / FIFO | 18,23% | 70,27 | 11,20 | 416,9 |
| Round Robin / ALL_UAV / EDF | 15,69% | 74,37 | 8,93 | 430,5 |
| Oldest Data / DEADLINE_ENERGY / EDF | 9,53% | 74,26 | 0,30 | 429,2 |

**Diễn giải:** Oldest Data giảm final age và năng lượng trong ví dụ này nhưng
tăng DVR; không có một policy thắng mọi tiêu chí. Đổi FIFO sang EDF trong cùng
Round Robin/ALL_UAV chỉ cải thiện nhỏ ở cấu hình này. DEADLINE_ENERGY giảm DVR
nhưng hầu như chọn local (0,30 ảnh offloaded/episode); chưa thể gọi đây là cải
thiện khả năng hỗ trợ của UAV. Cần kiểm tra mô hình tải, compute và coverage
trước khi dùng kết quả làm bằng chứng cho thuật toán mới. Chưa thực hiện kiểm
định thống kê hoặc kết luận superiority từ các trung bình này.

Các test xác nhận flight duration/energy, UAV cạn pin giữa đường, upload giữ UAV
tại stop, coverage theo khoảng cách 3D, freshness không lùi và parity với kernel
cũ khi các node đồng vị trí. Auditor replay execution/queue/route/energy và
kiểm tra độc lập các trace service. Điều này xác nhận tính nhất quán của model
đã khai báo; chưa xác nhận model đã được hiệu chuẩn theo phần cứng thực tế.

Adapter/train thử đã được bổ sung trong [MOBILE_DRL.md](MOBILE_DRL.md). Bước
nghiên cứu tiếp theo là kiểm chứng objective, mức hỗ trợ thực sự của UAV và độ
nhạy với khả năng local/coverage trước khi train dài. Không gọi RR/Oldest trong
môi trường mới là đã reproduce paper hoặc kết luận thuật toán cải tiến chỉ từ
một cấu hình thuận lợi.
