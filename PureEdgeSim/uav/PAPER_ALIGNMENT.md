# Đối chiếu implementation với arXiv:2501.15305v1

**Sau đợt dọn source:** demo Milestone 1–7 và entry point dataset cũ đã được gỡ.
Source/test trước khi dọn: `archives/legacy-milestones-*.zip`. Các mục milestone
phía dưới là lịch sử thiết kế. Đường chạy hiện tại xem [README.md](README.md).

Nguồn: [PDF được cung cấp](../../../2501.15305v1.pdf), **Enhancing Disaster
Resilience with UAV-Assisted Edge Computing: A Reinforcement Learning Approach
to Managing Heterogeneous Edge Devices**, Azfar, Huang và Ke. Đối chiếu ngày
20/09/2026, theo số trang PDF 1–17; tập trung §3–5 và Tables 1–7.

## Kết luận và điều chỉnh phạm vi

**Cập nhật DRL 21/09/2026:** đã thêm `PaperGymBridge` + Gymnasium, DQN
Stable-Baselines3, PPO/A2C, 11 reward của Table 6, train/save/load/evaluate và
runner lưới Table 5/6. Dùng trực tiếp kernel Java cho cả synthetic lẫn mixed.
Xem [DRL.md](DRL.md) về tham số được công bố, lựa chọn bổ sung và lệnh chạy.
Đã chạy pilot; chưa chạy trọn lưới 1 triệu bước/model, chưa có SUMO case study.

**Cập nhật 21/09/2026:** theo yêu cầu mở rộng đánh giá, đã tích hợp RescueNet và
Alibaba vào cùng `PaperSimulation.Manager` qua chế độ `paper.workload=datasets`.
Xem [DATASET_EVALUATION.md](DATASET_EVALUATION.md) để chạy và đọc giả định,
queue CPU hữu hạn, ảnh hưởng tải nền và kết quả. Chế độ synthetic vẫn giữ nguyên;
những mục dưới mô tả mô hình paper gốc trừ khi ghi rõ là extension.

Chuỗi Milestone 1–7 trước đây là một bộ thử nghiệm UAV-MEC tổng quát, **chưa phải
implementation của bài này**. Định hướng đưa RescueNet/Alibaba/Google, cache và
joint offloading-placement-scheduling-caching vào làm điều kiện tiên quyết để tái
lập bài là không đúng. Những phần đó có thể hữu ích cho đề tài mở rộng riêng.

Bài này hỏi: **một UAV nên đến thiết bị nào tiếp theo để trì hoãn thiết bị đầu tiên
hết pin hoặc có dữ liệu quá cũ?** Thiết bị là các edge camera/board dị thể, cố định
trên mặt đất; không phải 10 UE đồng nhất gửi task tới Local/UAV/Edge/Cloud.

Đường chạy chính cho hướng bài báo hiện là `uav.PaperSimulation`. Nó tái sử dụng
MECSim event engine và `Location3D`, `UAVMobilityModel`, `UAVEdgeNode`,
`UAVEnergyModel`. `PaperParameters` chứa Tables 1–3. Đây là **environment
bằng Java với các quy ước công khai**, nay có Gym/DRL adapter; không phải mã nguồn tác giả.
Các thiết bị mặt đất được lưu bằng `DeviceSpec` và trạng thái pin/tuổi dữ liệu
trong manager; UAV là computing-node entity thật. Chưa tích hợp các thiết bị này
vào legacy `DataCentersManager`/ReMEC network graph.

## Phần giữ, phần không cần cho bài và phần thiếu

| Thành phần hiện tại hoặc đã gỡ | So với bài | Trạng thái sau khi dọn |
| --- | --- | --- |
| `Location3D`, `UAVMobilityModel`, `UAVEdgeNode` | Có thể tái sử dụng cho vị trí, bay giữa thiết bị | Giữ, cấu hình theo Table 1 |
| `UAVEnergyModel` | Bay/hover phù hợp; tải CPU/radio riêng chưa có tham số UAV trong bài | Giữ, paper run dùng 150/80 W và không thêm tải minh họa |
| Demo `UAVMilestone1`–`UAVMilestone7`, `UAVAlibaba` | Các kịch bản thử nghiệm trước đây | Đã gỡ; source cũ trong ZIP khôi phục |
| `AirToGroundChannel`, `OffloadingTask`, `ModelCache` | Chỉ dùng bởi demo cũ | Đã gỡ; paper channel dùng `PaperParameters.rateBps` |
| `RescueNetWorkload`, `AlibabaWorkload` | Đọc dữ liệu cho extension | Giữ metadata/source pool; đã bỏ API task/scheduler cũ |
| `UAVMobilityTest`, `UAVEnergyTest` | Kiểm thử class dùng chung | Giữ kiểm tra thành phần; tích hợp engine được kiểm tra trong paper tests |
| ReMEC DAG, replica, pricing, Cloud và Ground Edge server | Là tính năng MECSim gốc, không phải hệ thống §3–4 | Không kích hoạt trong paper run; không xóa framework |
| Power/communication outage, pin từng thiết bị, data age | Thiếu trong các milestone cũ, là cốt lõi bài | Đã thêm trong `PaperSimulation` |
| DQN/Gym, PPO/A2C và nhiều reward | Đã có luồng huấn luyện | Pilot đã chạy; lưới Table 5/6 đầy đủ chưa chạy |
| SUMO, trọng số traffic, tần suất thiết bị hỏng đầu tiên | Chưa có | Chỉ cần cho case study §5.1, Table 7 |

Các thư mục output `target/uav-milestone*/`, `target/uav-alibaba-*` và log thử
nghiệm cũ đã được xóa. Các kết quả paper/baseline/dataset được giữ nguyên.
Đường dẫn kết quả lịch sử đã xóa trong ghi chép cũ không còn truy cập được.

## Mô hình chính trong bài

| Mục | Theo bài | Baseline hiện tại |
| --- | --- | --- |
| Vùng | 800×800 m (§5, trang 9) | Đã dùng |
| Thiết bị | 12, vị trí/type/task/pin ngẫu nhiên uniform | Đã dùng, seed tái lập |
| Phần cứng | Raspberry Pi 4B/3B, Firefly, Jetson Nano, NanoPC-T4 | Đã chép Tables 1–3 |
| CV task | HAAR, MMOD, DNN, Dlib, YOLOv3 | Tốc độ Bytes/s và công suất theo từng cặp |
| Pin thiết bị | 50–80 kJ | Đã dùng; có nguồn thì không trừ pin theo δE của Eq. (1d) |
| UAV | Một UAV, xuất phát góc (0,0), H=10 m, v=5 m/s | Đã dùng |
| Pin UAV | 1600 kJ = khoảng 444.444 Wh | Chuyển J↔Wh khi gọi model có sẵn |
| Năng lượng UAV | Bay 150 W, hover 80 W | Tích phân theo thời gian |
| Kênh | R=W log2(1+p β0 d^(-4)/noise), W=20 MHz, p=0.1 W | Đã có, xem quy ước đơn vị bên dưới |
| Coverage | Range 65 m | Dùng khoảng cách 3D; có thể phục vụ nhiều thiết bị |
| Workload | Mỗi thiết bị mỗi slot nhận 2–4 MB random | Đã dùng; không đọc ảnh/video/cluster trace |
| Slot | Độ dài thay đổi, chờ thiết bị chậm nhất, cap 600 s | Đã có quy ước cụ thể bên dưới |
| State | 12 battery fractions + 12 data ages (§3.2, trang 7) | `Manager.observation()`, copy riêng |
| Action | Số nguyên 0…11: thiết bị UAV sẽ đến | `Policy.choose(observation)` |
| Data age | Không liên lạc và không được phục vụ thì +1; phục vụ thì reset | Đã có; tuổi theo slot, không phải deadline giây |
| Kết thúc | Thiết bị hết pin hoặc dữ liệu hết hạn; UAV cũng bị giới hạn pin | Đã ghi nguyên nhân/ID, kể cả nhiều lỗi đồng thời |
| Metric chính | Số slot đến khi hệ thống hỏng | `slots.csv`; kèm giây vật lý để diễn giải |

State của bài không có tọa độ UAV, pin UAV, hardware type hoặc cache. Không tự
mở rộng vector này rồi gọi là cùng bài toán RL. Những thông tin đó vẫn được lưu
trong environment và log; sự thiếu chúng trong observation là một giới hạn cần
lưu ý khi huấn luyện xuyên nhiều layout.

## Các quy ước chưa thể xác nhận từ PDF

Chưa có source/config của tác giả để kiểm chứng các điểm sau. Vì vậy chưa thể
khẳng định số slot của baseline khớp số liệu báo cáo, kể cả khi dùng cùng tham số.

1. **Kênh:** Table 1 ghi β0=-50 dBm, dù Eq. (4) dùng như channel gain. Baseline
   chuyển literal dBm→W: β0=10^-8; noise=-100 dBm→10^-13 W, không bình phương
   noise thêm lần nữa. Với d=10 m, rate=20 Mbps. Cách hiểu β0=-50 dB là gain
   sẽ cho kết quả khác rất lớn; cần source tác giả để chốt. Dùng slant range 65 m
   và full 20 MHz độc lập cho mỗi upload đồng thời; bài không chỉ rõ phân chia
   băng thông khi nhiều thiết bị cùng coverage.
2. **Thời gian:** thiết bị không offload bắt đầu compute ở đầu slot, song song
   với UAV bay. Thiết bị offload chờ UAV đến rồi truyền; không compute đồng thời
   phần task đó. Slot bằng `max(local durations, flight + upload durations)`,
   giới hạn 600 s. Công suất standby chạy suốt slot; active compute/TX là phần
   cộng thêm. UAV compute coi không đáng kể theo giả thiết nhanh hơn nhiều của §3.
3. **Cap:** local compute quá dài bị cắt ở 600 s và không đưa phần dư sang slot
   kế; upload chỉ có `600-flight` giây. Không reset data age nếu upload chưa
   xong. `capped_work_items` cho biết bao nhiêu công việc đã bị cắt. Bài không
   mô tả rõ backlog/cap, nên đây là quy ước triển khai, không phải kết quả xác nhận.
4. **Kênh output mặt đất:** bài nhắc output 1 kB cho thiết bị có liên lạc nhưng
   không cung cấp vị trí BS hay link rate tương ứng. Baseline coi output/relay
   này tức thời và bỏ chi phí của nó; **đây là phần xấp xỉ còn thiếu**, không dùng
   một BS hoặc link rate giả để tuyên bố tái lập đầy đủ. Không có neural inference
   thật hay lưu kho tất cả frame chưa gửi.
5. **Data expiry:** §4 trang 8 nói kết thúc khi tuổi đạt 10, Eq. (1g) viết `<=10`,
   trong khi §5 trang 12 nhắc baseline 11 slot. Hiện chọn `age>=10`, đúng câu
   mô tả implementation. Phải kiểm tra indexing với tác giả trước khi so Table 5.
6. **Reward:** Table 6 dòng cuối là `U + log(A/O)`. Hiện U là số slot đã thực
   hiện, A/O lấy từ đầu slot trước reset tuổi, dùng `max(age,1e-6)` để tránh
   log(0). Bài không nêu epsilon, log base hay thời điểm lấy A/O; hiện dùng ln.
   Không khẳng định đây là reward code nguyên gốc.
7. **Cạn pin giữa slot:** dừng tại thời điểm vật lý đầu tiên, không dịch chuyển
   UAV đến đích nếu pin hết trên đường. Slot kết thúc dở vẫn được tính là một
   bước đã thực hiện và cập nhật tuổi; xem duration và reason khi phân tích.
   Bài không chỉ rõ quy tắc partial-slot này. Pin không xuống dưới zero; thiết bị
   có nguồn vẫn tiêu thụ năng lượng nhưng năng lượng đó không lấy từ battery.
8. **Seed và reset:** khởi tạo manager mới là episode mới. Layout/task/policy dùng
   RNG riêng; cùng seed và policy cho trace lặp lại được, không đảm bảo giống
   chuỗi random của Python tác giả. Safety limit tạo `truncated`, không gọi là
   system failure. Gym adapter gọi chính các transition này; mỗi env có JVM riêng,
   reset giữa episode giải phóng registry entity cũ bằng `finally` của event engine.

## Chạy baseline mới

Từ thư mục `uav/MECSim`:

```powershell
mvn compile exec:java "-Dexec.mainClass=uav.PaperSimulation" "-Dexec.classpathScope=compile" "-Dpaper.seed=42" "-Dpaper.powered=8" "-Dpaper.connected=8" "-Dpaper.policy=OLDEST_DATA"
mvn test
```

`paper.powered` và `paper.connected` là **số thiết bị còn nguồn/còn liên lạc**,
không phải số thiết bị hỏng. Mask được lấy mẫu độc lập, có thể chồng lấn.
Policy của CLI Java có `OLDEST_DATA`, `ROUND_ROBIN`, `RANDOM`, để kiểm tra environment.
DQN/PPO/A2C chạy qua CLI Python riêng trong `DRL.md`; không đổi ý nghĩa baseline này.

Output mới ở `target/uav-paper-*/`:

- `run.txt`: seed, policy, số thiết bị còn nguồn/kết nối và các quy ước.
- `layout.csv`: vị trí, hardware, CV task, pin ban đầu và outage masks.
- `slots.csv`: action, thời gian, vị trí UAV, pin, tuổi lớn nhất, số upload xong,
  số công việc bị cap, reward, termination/truncation và ID/nguyên nhân failure.
- `devices.csv`: mỗi thiết bị ở mỗi slot, bytes input, pin/energy và data age.
  `energy_used_j` là tổng điện tiêu thụ, kể cả thiết bị được cấp nguồn; không
  đồng nhất với độ giảm pin của thiết bị được cấp nguồn.

Kiểm thử kiểm tra seed, số lượng outage, state 24 phần tử, bảng/đơn vị kênh,
tiết kiệm pin do offload, phục vụ nhiều thiết bị, incomplete upload, cap 600 s,
data expiry 10 slot, bay/hover và failure giữa đường. Các test không xác nhận
thuật toán học hay tái lập số liệu bài báo.

Kiểm chứng ngày 20/09/2026: `mvn -o test` pass 55/55 test, trong đó 12 test cho
paper baseline. Chạy CLI mặc định thành công, seed 42, powered=8, connected=8,
OLDEST_DATA: 17 slot đã thực hiện (slot cuối dở), 9772.448489698 giây, kết thúc
do `DEVICE_8_BATTERY`. Đã kiểm tra 17 dòng slot và 204 dòng device, không có pin
âm hoặc metric không hữu hạn. Đây là smoke test của quy ước hiện tại, không phải
kết quả DQN/Table 5. Output: `target/uav-paper-13318557248538943123/`.

## Các bước còn lại để tiến tới tái lập

### Baseline nhiều seed đã chạy (21/09/2026)

`PaperBaselines` chạy tuần tự ba policy trên 30 seed (0–29), bốn cấu hình còn
nguồn/còn kết nối 12/12, 6/6, 8/8, 10/8: tổng 360 episode. Trong từng cặp
scenario/seed, các policy nhận cùng layout và chuỗi task. Engine dùng registry
entity tĩnh, vì vậy không chạy các episode song song trong cùng JVM.

```powershell
mvn compile exec:java "-Dexec.mainClass=uav.PaperBaselines" "-Dexec.classpathScope=compile"
```

Có thể đặt `-Dpaper.seeds=30`, `-Dpaper.firstSeed=0`, `-Dpaper.maxSlots=200`.
Output mỗi lần chạy nằm trong `target/uav-baselines-*/`: `REPORT.md`,
`summary.csv`, `episodes.csv`, `run.txt`, toàn bộ trace và bản chụp source/config.

Kết quả trung bình ± độ lệch chuẩn mẫu của số slot (bao gồm slot lỗi cuối):

| Còn nguồn / còn kết nối | RANDOM | ROUND_ROBIN | OLDEST_DATA |
| --- | --- | --- | --- |
| 12 / 12 | 30.37 ± 0.61 | 30.23 ± 0.63 | 30.23 ± 0.63 |
| 6 / 6 | 10.13 ± 0.73 | 10.90 ± 1.63 | 18.43 ± 5.81 |
| 8 / 8 | 10.47 ± 1.11 | 11.80 ± 2.11 | 21.00 ± 7.01 |
| 10 / 8 | 10.47 ± 1.11 | 11.87 ± 2.15 | 24.33 ± 6.47 |

Ở 12/12, mọi age đều zero nên tie-breaking của OLDEST_DATA cho cùng hành động
với ROUND_ROBIN; cả 90 episode đều dừng do pin UAV. Trong ba cấu hình có outage,
RANDOM dừng do data age ở cả 90 episode; OLDEST_DATA không có lỗi data age trong
90 episode đã thử, mà dừng vì pin thiết bị/UAV. Đây là mô tả mẫu thực nghiệm,
không phải bảo đảm cho mọi seed hay bằng chứng có ý nghĩa thống kê.

Đã kiểm tra 360 episode kết thúc tự nhiên, không truncation; 90 nhóm paired
layout/task khớp nhau; mean và sample SD của 12 nhóm được tính lại độc lập bằng
Python. Giới hạn vật lý, beta0, cap và output-link vẫn như phần quy ước bên trên;
không so trực tiếp những số này với kết quả DQN trong bài.

Lần chạy: `target/uav-baselines-16447354772174831620/`.

### Công việc tiếp theo

1. Xác nhận các quy ước còn mơ hồ với code/config tác giả, ưu tiên β0, slot cap,
   output 1 kB, age 10/11 và reward. Không điều chỉnh seed hay vật lý để ép khớp
   những con số trong bảng.
2. **Đã triển khai** Gym adapter và DQN Stable-Baselines3 (bài dùng Python 3.11.5): MLP
   `[64,64]` ReLU, batch 16, gamma 0.98, learning rate 0.0071, 1,000,000 steps,
   epsilon 1→0.05 trong 35% đầu. Replay buffer/target-update và các tham số chưa
   được công bố đã được ghi lại trong `DRL.md` và config mỗi run; không tự nhận
   default hiện nay là default tác giả. Cần chạy đủ ngân sách cho đánh giá chính thức.
3. Chạy nhiều seed cho lưới power/comms `{12,10,8,6,4}` (Table 5); phân biệt
   **average** ở Table 5 với **maximum** ở Table 6. Thử các reward và PPO/A2C
   đúng các cấu hình của Table 6. Báo cáo episode length, thiết bị hỏng đầu tiên,
   biến thiên qua seed, thời gian và toàn bộ config.
4. Cuối cùng mới làm case study SUMO Round Lake và downtown Albany (§5.1): cần
   road network, traffic flows/density và ánh xạ camera-road. Bài dùng 8 thiết bị
   còn nguồn, 6 còn comms, 300,000 training steps/test, 30 random seeds. Khi đến
   bước này mới hướng dẫn chuẩn bị dữ liệu tương ứng; **không cần tải thêm
   RescueNet, Alibaba hoặc Google cho reproduction này**.

Multi-UAV nằm ở future work (§6), còn joint offloading/placement/scheduling/cache
là đề xuất mở rộng riêng. Chỉ đưa vào sau khi có baseline và nêu rõ bài toán mới.
