# Kiểm tra lại codebase theo đề tài UAV disaster analytics

> Tài liệu lịch sử: audit này được viết trước khi bổ sung nhánh task scheduling.
> Để xem trạng thái hiện tại, đọc [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md),
> [SCHEDULING.md](SCHEDULING.md) và [SCHEDULING_AGING_RESULTS.md](SCHEDULING_AGING_RESULTS.md).

Ngày kiểm tra: 21/10/2026. Kiểm tra trực tiếp working tree, source, raw data,
artifact và PDF; không dùng kết luận hội thoại cũ làm bằng chứng.
Repo: `uav/MECSim`, HEAD `1620ad4dc588153fd87cdd911bd326611a544ca5`.
Working tree có thay đổi chưa commit; báo cáo này đánh giá cả phần đó.

## 1. Kết luận

**Codebase có nền tảng UAV và năng lượng phù hợp với chủ đề, nhưng luồng UAV
hiện giải một bài toán hẹp hơn: chọn thứ tự thiết bị được UAV phục vụ để kéo
dài lifetime dưới ràng buộc pin và tuổi dữ liệu. Chưa triển khai bộ điều khiển
joint offloading, placement, scheduling, cache để giảm latency, energy và
deadline violation theo đề tài đã nêu.**

Đây là khác biệt về mô hình, action, objective và metric; thêm dataset hoặc
train nhiều seed trên environment hiện tại không tự giải quyết khác biệt này.
Không nên dùng kết quả lifetime hiện có để khẳng định đã giải bài toán joint.

## 2. Các phần đang có và đường thực thi

Đã lập inventory source trong `PureEdgeSim`, `drl`, `scripts`, `src/test`:
149 Java files gồm source/test, 14 Python files, 1 shell script, 2 PowerShell scripts.
Đọc các đường thực thi chính và tìm kiếm chéo tính năng trong framework.
Đây là audit kiến trúc/phạm vi; không phải kiểm chứng mọi thuật toán legacy.

```text
applications.Main
  -> Simulation + DependentTaskGenerator
  -> ReMEC / DELTA / BQProfit / RMEAC / FP-TOSM
  -> legacy task, network, MEC/Cloud, scheduling, latency/deadline/reliability

drl.run -> PaperEnv -> JSON bridge -> PaperSimulation.Manager
                                  -> PureEdgeSim event engine
                                  -> UAVEdgeNode / UAVMobilityModel / UAVEnergyModel
                                  -> optional PaperDatasetWorkload

drl.service_experiment -> ServicePolicy -> read-only ServiceEstimator
                                          -> cùng PaperSimulation kernel
```

- [applications/Main.java](../applications/Main.java:15): default settings/output
  là ReMEC, đăng ký DAG task generator và chọn orchestrator theo GlobalConfig.
- [PaperSimulation.java](PaperSimulation.java:122): tự quản lý DeviceSpec, pin,
  age và một UAV. Không chuyển task của luồng này qua ReMEC orchestrator/network.
- [UAVEdgeNode.java](UAVEdgeNode.java:8): thực sự extend DefaultComputingNode;
  movement/energy được manager tiến theo event. Việc là computing-node entity
  không có nghĩa đã tích hợp legacy task scheduler hoặc network graph.
- [UAVMobilityModel.java](UAVMobilityModel.java:7): waypoint thẳng trong không
  gian3D; paper manager cố định altitude10m, speed5m/s và bay tới tọa độ thiết bị.
- [UAVEnergyModel.java](UAVEnergyModel.java:6): có bay, hover, compute, TX/RX.
  Paper synthetic chủ yếu dùng bay/hover; mixed thêm CPU20W. Các API TX/RX có
  tồn tại nhưng luồng paper chưa mô hình hóa đầy đủ radio/output relay của UAV.
- [drl/environment.py](../../drl/environment.py:83): action Discrete(12),
  observation24D. [drl/run.py](../../drl/run.py:28) hỗ trợ DQN/PPO/A2C.
  [drl/service_policy.py](../../drl/service_policy.py) chấm điểm candidate nhưng
  vẫn chọn một trong12 đích; không mở rộng thành bốn nhóm quyết định joint.

**Lưu ý về cache/deadline trong source cũ:** ReMEC có `CACHING_TIME=5`, chi phí
lưu UMI/kết quả và xử lý lỗi/replica; có Task.maxLatency và thuật toán scheduling.
Những dòng này không chứng minh UAV đã có cache model/data với capacity,
admission/eviction và hit/miss, cũng không chứng minh task deadline đã được nối
vào PaperSimulation. Cần theo call path, không chỉ dựa vào từ khóa trong repo.

## 3. Bài báo thực sự là bài nào và tối ưu gì?

PDF có sẵn: `uav/2501.15305v1.pdf`, 17 trang. SHA256:
`fadde72b3fbdbd501ac03e294c4bd436f064580e43cd6544a78a19c559da09f3`.
Tiêu đề: *Enhancing Disaster Resilience with UAV-Assisted Edge Computing:
A Reinforcement Learning Approach to Managing Heterogeneous Edge Devices*.
Tác giả Talha Azfar, Kaicong Huang, Ruimin Ke. arXiv v1 ngày25/01/2025:
[trang nguồn](https://arxiv.org/abs/2501.15305v1).
PDF chứa metadata mẫu ACM năm2024 và DOI `XXXXXXX.XXXXXXX`; không dùng các
placeholder đó để khẳng định đã xuất bản ở một số tạp chí xác định.

Đọc §3–4, PDF trang4–8 và Table1/4:

| Thành phần | Bài gốc |
| --- | --- |
| Hệ thống | Một UAV, thiết bị biên mặt đất dị thể có thể mất nguồn hoặc liên lạc |
| Task | Phân tích video, lượng dữ liệu ngẫu nhiên2–4MB mỗi thiết bị mỗi slot |
| Quyết định | Chọn thiết bị UAV đến ở slot tiếp theo; nhiều thiết bị trong range có thể được phục vụ |
| Objective | Tối đa số slot hệ thống hoạt động trước thất bại |
| Ràng buộc chính | Pin và tuổi dữ liệu chưa truyền; tuổi10slot là ngưỡng vận hành |
| State/action RL | 12 tỷ lệ pin +12 tuổi dữ liệu; action0–11 |
| UAV | Vận tốc/độ cao/range cố định; Table1:5m/s,10m,65m |
| Thuật toán | DQN; so sánh PPO/A2C, nhiều hàm thưởng |
| Dataset/case study | Workload ngẫu nhiên và SUMO cho sơ tán Round Lake/Albany |

**Đây là bài toán đơn mục tiêu lifetime, có ràng buộc năng lượng và tuổi dữ liệu.**
Hàm thưởng chứa nhiều thành phần không tự biến objective thành bài toán Pareto.

Mô tả “power allocation và trajectory cho resilient coverage” cần sửa: trang3,
§2 nói tối ưu phân bổ công suất và quỹ đạo khi giới thiệu nghiên cứu [30], và
joint power/load/trajectory khi giới thiệu [9]. Trong phương pháp Azfar,
Table1 đặt transmission power0.1W cố định; action là chỉ số thiết bị cần thăm.
Có lập thứ tự di chuyển, nhưng không có biến công suất truyền được agent tối ưu.
Không có quyết định cache hoặc deadline xử lý từng task trong phương pháp này.

`PaperSimulation` là triển khai Java theo bài, không phải mã nguồn tác giả.
Bài mô tả Gym/Python/stable-baselines; repo dùng Java event engine + Python bridge.
Các điểm cần xác nhận khi gọi reproduction: đơn vị beta0/noise, chia băng thông,
output1kB/relay tới BS, partial-slot, ngưỡng age10/11 và convention reward.
Code công bố một số quy ước này trong PAPER_ALIGNMENT.md; kiểm thử source chỉ
xác nhận chúng nhất quán nội bộ, không xác nhận khớp code tác giả.

## 4. Đối chiếu với hướng đóng góp đề tài

| Yêu cầu | Bằng chứng hiện tại | Đánh giá |
| --- | --- | --- |
| Energy-aware UAV | Pin, bay/hover, năng lượng thiết bị, mixed CPU; Service có cost theo pin | Đã có nền tảng |
| Disaster analytics | RescueNet ảnh thật được lấy metadata, outage kịch bản | Một phần; chưa inference/profiling task thật |
| Offloading decision | Thiết bị trong range tự offload; ngoài range tự local | Chưa có lựa chọn độc lập cho từng task/đích xử lý |
| UAV-BS/edge placement | Chọn một trong12 vị trí thiết bị; speed/altitude cố định | Có quyết định đích rời rạc; chưa placement tổng quát hoặc ground-edge site selection |
| Task scheduling | FIFO CPU theo ready time trong slot, background đầu slot | Có mô hình thực thi; thứ tự không phải biến tối ưu, chưa EDF/priority, không carry-over |
| Cache | Storage host API có giá trị nhưng không có trạng thái cache trong paper kernel | Chưa có cache decision/hit/miss/fetch/eviction |
| Giảm latency | Mixed ghi latency của kết quả đã hoàn thành | Có metric phụ, chưa objective tối ưu tổng độ trễ |
| Giảm energy | Có đo tiêu thụ và pin; objective chủ yếu là lifetime | Chưa có objective energy trên cùng số task/horizon để so công bằng |
| Deadline violation | Chưa có task release/deadline trong PaperSimulation.Job/ImageTask | Chưa có DVR; data age10slot không thay cho deadline giây |
| Joint algorithm | Action space vẫn12, không biểu diễn offload/placement/schedule/cache | Chưa triển khai |

Chọn visitation order có thể được gọi là service scheduling; cần phân biệt với
lập lịch CPU của tác vụ. Tương tự, UAV di chuyển có tọa độ chưa có nghĩa đã tối
ưu placement liên tục. Nếu đề tài chỉ dùng candidate sites rời rạc thì vẫn hợp
lý, nhưng phải nêu rõ và có biến placement trong mô hình joint mới.

## 5. Dataset đã được dùng đến mức nào?

| Nguồn | Source/config đang chạy | Giới hạn quan trọng |
| --- | --- | --- |
| RescueNet | readMetadata: kích thước, compressed bytes, SHA256, đường dẫn ảnh/mask | Không chạy detector/segmenter; mask chỉ được kiểm tra tồn tại/kích thước |
| Alibaba2018 | batch_task.csv -> tối đa1000 root task đủ điều kiện | Lấy mẫu có hoàn lại; không replay timeline/DAG hay utilization thực |
| Google Cluster Data | Không tìm thấy adapter/config trong luồng source đã rà | Chưa tích hợp |
| C2A | Không tìm thấy adapter/config trong luồng source đã rà | Chưa tích hợp |

Kiểm tra raw tại máy: có Alibaba CSV/archive và898 tệp ảnh/mask trong thư mục
RescueNet. Smoke run thực dùng449 ảnh và1000 Alibaba rows; quét5303 rows,
37 malformed,4266 bị loại. Pool giới hạn này không phải toàn bộ Alibaba trace.

Trong [PaperDatasetWorkload.java](PaperDatasetWorkload.java:94):

```text
UAV image MI = megapixels * assumed MI per megapixel
Local processing seconds = compressed file bytes / Table3 rate
Alibaba MI = (end-start) * plan_cpu/100 * assumed reference MIPS
             * durationScale * backgroundScale
```

CPU/memory requests trong cluster trace không trực tiếp là năng lượng hay
runtime trên UAV. Code hiện quy đổi bằng giả định; `plan_mem` được đọc nhưng
chưa dùng làm ràng buộc bộ nhớ trong paper CPU. Background tasks ready ở đầu
slot, ảnh ready sau upload; FIFO, phần chưa xong bị drop cuối slot. Không có
backlog sang slot sau. Mỗi thiết bị nhận ảnh mới mỗi slot, không theo tọa độ hay
thời điểm thực của RescueNet. Không sử dụng nội dung nhãn để gán severity/priority.

Các split seed hiện dùng chung source pools; đổi seed/layout không tạo held-out
images/jobs. Vì vậy nên gọi đây là **mô phỏng dùng workload suy ra từ dataset**,
chưa phải benchmark đầu-cuối disaster analytics đã hiệu chuẩn. Không cần đưa cả
Google và Alibaba vào cùng lúc; có thể chọn một trace chính, trace kia để robustness.

## 6. Những điểm ảnh hưởng trực tiếp tới kết luận thực nghiệm

1. **Objective lệch:** maximize lifetime có thể thích hành động khác minimize
   latency/energy/DVR. Nhiều reward variants vẫn đánh giá theo lifetime.
2. **Age không phải deadline:** một slot có độ dài biến thiên, cap600s. Ngưỡng10
   slot không thể thay cho hạn xử lý một ảnh trong500ms/2s. Tỷ lệ ảnh giao được
   cũng không phải tỷ lệ đạt deadline.
3. **Latency bị chọn mẫu:** `deliveredLatencyMean` chỉ tính ảnh hoàn thành; bỏ
   task khó có thể làm latency trung bình đẹp hơn. Cần denominator gồm task
   đến, task hoàn thành, task trễ và task drop với quy ước rõ.
4. **Không có queue bền:** `DROPPED_SLOT_CAP` và `carry_over=false` hạn chế đánh
   giá overload, EDF, cache miss queueing và deadline qua nhiều bước.
5. **Observation thiếu biến:** DQN24D không thấy vị trí UAV, channel, CPU queue,
   cache hay task deadline. Service đọc metadata/forecast nhiều hơn; không thể
   gán mọi chênh lệch hiệu năng cho kiến trúc thuật toán.
6. **Các mode có khác nghĩa completion:** synthetic cho connected device reset
   age; mixed yêu cầu computation completion. Không gán toàn bộ chênh lệch cho
   Alibaba hoặc RescueNet nếu chưa tách tác động mô hình CPU/completion.
7. **Mô hình radio đơn giản:** range3D, full bandwidth độc lập cho từng upload;
   chưa contention/interference, output-link/relay latency hoặc cache fetch.
8. **Năng lượng/horizon:** lifetime khác nhau dẫn tới tổng năng lượng và số task
   khác nhau. Cần cùng horizon/offered load hoặc báo J/task thành công cùng DVR.
9. **Giới hạn số thiết bị:** hard-code12 ở parameters/action/state. Chưa suy được
   scalability qua N chỉ từ việc có công thức Big-O.

## 7. Những gì đã chạy lại trong lần audit này

Lệnh Maven offline test + build classpath: **46 tests,0 failure/error**.
Python unittest với raw datasets bật: **17 tests đạt**,32.520s.
Đây là kiểm tra vận hành và invariants, không kiểm chứng đóng góp joint còn thiếu.

Chạy thêm Oldest Data, layout42/task2000000,8 nguồn/8 kết nối:

| Chỉ số | Synthetic | Raw RescueNet + Alibaba |
| --- | ---: | ---: |
| Lifetime slots | 17 | 17 |
| Simulated seconds | 9772.428 | 9659.898 |
| Kết thúc | DEVICE_8_BATTERY | DEVICE_8_BATTERY |
| Ảnh submitted/delivered | Không áp dụng | 204/128 |
| Mean delivered latency | Không áp dụng | 124.643s |
| UAV compute energy | 0J | 2037.752J |

Các số này chỉ là smoke test của một case;124.643s không phải độ trễ inference
đo trên phần cứng thật. Không dùng chúng làm bằng chứng tối ưu.
Log/trace mới: `target/fresh-audit-20261021/`.

Cũng đã mở config/checkpoints/evaluation CSV trong5 thư mục `result/target/drl-server-*`
và manifest/summary `target/p1-20261001`. Cả5 config ghi COMPLETE, actual_steps
1,000,000, learning seeds0–4, cùng layout42, reward paper và workload datasets;
có best/final checkpoints. Chúng đánh giá environment24/12 và
lifetime hiện có; chưa đánh giá bộ action joint. P1 lưu1320 development episodes:
Service19.758 vs Oldest19.061 synthetic; mixed17.955 vs18.424. Đây là artifact
đã có được đọc lại, không phải benchmark1320 episode được chạy mới trong audit.
Kết quả này không chứng minh cơ chế joint hay lợi ích trên mọi dataset/layout.

## 8. Hướng sửa để đúng đề tài

Đề xuất giữ paper environment làm baseline riêng, xây một environment/version
mới cho bài toán joint để tránh làm mất khả năng đối chiếu.

1. **Khóa mô hình task và objective trước:** mỗi task có release time, bytes,
   compute demand, output bytes, deadline giây, priority và model/data cần dùng.
   Quy định deadline absolute/relative, drop và kết thúc episode/horizon.
   Đo L, E, DVR riêng; nếu dùng tổng có trọng số phải chuẩn hóa, công bố hệ số.
   Hoặc minimize energy subject to latency/DVR budget; Pareto là lựa chọn khác,
   không bắt buộc chỉ vì có nhiều chỉ số đánh giá.
2. **Thêm biến action có thể điều khiển:** x chọn Local/UAV/GroundEdge cho task;
   q chọn vị trí/waypoint UAV; pi chọn thứ tự hoặc cấp tài nguyên queue;
   c chọn model/data được cache. Phải có path thực thi và metric phản ứng với
   từng action; thêm field mà kernel không dùng là chưa implement.
3. **Thêm feasibility:** one destination/task, coverage/link khi offload,
   max speed/area/altitude, CPU và RAM, queue capacity, battery budget/reserve,
   cache capacity và điều kiện model availability/fetch. Có thể bắt đầu1UAV và
   finite candidate sites; không cần multi-UAV ngay.
4. **Xây baseline đúng bài toán:** Local-only, fixed/nearest UAV với FIFO,
   energy-aware greedy với EDF; cache No-cache/LRU trước. So trên cùng action
   constraints, dữ liệu và thông tin quan sát. Sau đó mới thêm cơ chế cải tiến
   và ablation offloading/placement/scheduling/cache riêng.
5. **Hiệu chuẩn workload:** RescueNet/C2A tạo task phân tích ảnh với profiling
   hoặc cost model công khai; Alibaba/Google tạo background arrivals theo thời
   gian, CPU/RAM. Tách source pools, không chỉ seed; khóa split/manifest.
6. **Benchmark mới rồi mới train:** kiểm tra gần/xa thay transmission latency;
   tải cao tăng queue delay; cache hit giảm fetch; EDF thay deadline misses;
   bay xa tăng propulsion energy. Sau đó chạy paired seeds, CI và runtime.

Theo phạm vi người dùng vừa xác định, ưu tiên mô hình task/deadline/queue và
action joint trước việc train thêm policy chọn thiết bị của bài cũ. Cải thiện
P1 tránh starvation có thể giữ làm nghiên cứu lifetime riêng, nhưng không đủ
để đóng góp cho cả bốn quyết định joint của đề tài rộng.

## 9. Bản dịch PDF và giới hạn

Đã dùng skill pdf-translate. Google bị429/CAPTCHA và đã dừng; chuyển handoff,
dịch93 segment rồi dựng bằng bundled core. Không thay PDF gốc.

Output: `uav/output/pdf/azfar-2025-vi-reviewed-20261021/2501.15305v1-vi.pdf`.
Kiểm tra17/17 trang, canvas khớp, SHA256 nguồn giữ nguyên, không marker sót,
không span vượt canvas; render toàn bộ và xem3 contact sheets, phóng to trang5/8.
Công thức/hình/bảng còn đọc được tại các trang đã kiểm tra chi tiết.

**Đây là bản dịch một phần:** engine giữ nguyên các trang12,14–17; một số nhãn
bảng/hình và header vẫn tiếng Anh. Dù missing-segment=0, đó chỉ là93 segment
được engine cho dịch, không có nghĩa100% bài đã sang tiếng Việt.
Bản dịch bổ sung phần văn xuôi trang12/14/15 ở
`uav/output/pdf/azfar-2025-vi-reviewed-20261021/PHAN_CON_THIEU_VI.md`.
Trang16–17 chủ yếu tài liệu tham khảo/thông tin xuất bản, giữ nguyên.
