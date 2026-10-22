# P0 — Thông tin trước quyết định và scenario có kiểm soát

Phiên bản: `paper-decision-v1`, `paper-scenario-v1`; ngày 01/10/2026.
Đã triển khai trong `PaperSimulation`, `PaperScenario`, `PaperGymBridge` và
`drl/environment.py`. Estimator và SERVICE_AWARE được bổ sung ở P1;
đặc tả, kết quả và giới hạn: [P1_RESULTS.md](P1_RESULTS.md).

API phụ P1: `env.service_estimates()` gửi RPC `estimate`, trả schema
`paper-service-estimate-v1`, `state` v1, `prior`, `assumption` và `candidates`.
Mỗi candidate có action, flight/duration, device/UAV energy, normalized energy
cost, urgency/uniform/coverage gain, delivered và local_alone dự báo.
Prior chỉ chứa trung bình bytes, image/background MI, MIPS, CPU W và finite_cpu
từ pool đã khai báo. Không có sample/seed tương lai; gọi lặp không advance RNG
hoặc simulation clock. Không cho gọi trước reset hoặc sau terminal/truncated.
Policy P1 nhận packet này; checkpoint24D cũ không tự nhận thêm feature.

## 1. Ranh giới thời gian và quyền truy cập

Trình tự của một slot vẫn là:

1. Kết thúc slot trước, cập nhật pin/age và vị trí UAV.
2. Trả observation24D; nếu bật, trả thêm `info.decision_state`.
3. Policy chọn action.
4. Simulator mới sinh/lấy task của slot sắp chạy, tính truyền/CPU và transition.

Sau `reset`, snapshot có thời gian0 và `slots_completed=0`. Sau `step`, snapshot
là trạng thái sau action vừa thực hiện, dùng cho quyết định kế tiếp nếu
`action_allowed=true`. Snapshot terminal/truncated có `action_allowed=false`.
Mỗi lần gọi tạo bản sao, không cho policy sửa state của simulator.

Observation của DQN cũ vẫn **24 floats**: 12 battery fractions rồi 12 ages.
Snapshot là API phụ **opt-in**, không tự mở rộng mạng hoặc thay reward/action.
Policy mới chỉ nên nhận `decision_state`, không nhận toàn bộ info hoặc manifest.
`layout_seed`/`task_seed` đã có trong reset info phục vụ audit, không được dùng
làm feature. Không chuyển checkpoint24D sang observation khác shape.

## 2. Feature contract v1

Đây là telemetry chính xác trong simulator, giả định policy biết thiết bị và
trạng thái nguồn/kết nối. Chưa mô hình hóa nhiễu, chi phí thu thập hay độ trễ
telemetry thực tế; khi đánh giá policy mới phải công bố giả định này.

| Field | Đơn vị/loại | Nguồn và thời điểm | Quyền sử dụng |
| --- | --- | --- | --- |
| `schema` | chuỗi version | API | Kiểm tra tương thích |
| `time_s`, `slots_completed` | s, số slot | Clock/state hiện tại | Được dùng trước action |
| `action_allowed` | bool | terminated/truncated hiện tại | Kiểm tra được chọn action hay phải reset |
| `slot_cap_s`, `data_age_limit_slots` | s, slot | Config episode | Giả định công khai, mặc định600/10 |
| `workload_mode` | synthetic/datasets | Config | Nhận diện mô hình workload, không tiết lộ sample |
| `uav.x_m/y_m/h_m` | m | Mobility hiện tại | Vị trí trước quyết định kế tiếp |
| `uav.battery_j/capacity_j` | J | Energy state/config | Pin thực tế còn lại và capacity |
| `uav.speed_mps/range_m` | m/s, m | PaperParameters | Tham số công khai; range là khoảng cách3D |
| `uav.flight_w/hover_w` | W | PaperParameters | Hệ số mô hình, chưa hiệu chuẩn thực địa |
| `devices[].physical_id` | số0–11 | Index vật lý ổn định | Ánh xạ action; không coi số ID là đại lượng vật lý |
| `devices[].x_m/y_m/h_m` | m | DeviceSpec cố định; h=0 | Vị trí ground device |
| `devices[].hardware/vision_task` | enum | DeviceSpec | Loại thiết bị/thuật toán xử lý cố định; không phải task sample sắp tới |
| `devices[].capacity_j/battery_j` | J | Config/state | Powered device không trừ battery khi dùng nguồn ngoài theo model hiện tại |
| `devices[].data_age_slots` | slot | Kết quả slot trước | Giá trị hiện có, không phải age dự đoán |
| `devices[].powered/connected` | bool | Availability cố định episode | Nguồn ngoài/kết nối mặt đất; không đồng nghĩa hoàn thành local |
| `devices[].local_rate_bytes_s` | byte/s | Table3 × `localRateScale` | Hệ số quy đổi trong model, không phải measured RescueNet inference speed |
| `devices[].standby_w/active_w` | W | Tables1/2 | Trong code, active draw được cộng vào standby; giữ quy ước hiện tại |
| `compute.finite_cpu` | bool | Dataset mode | Synthetic dùng negligible CPU |
| `compute.uav_mips/cpu_power_w` | MI/s, W | Dataset config | Synthetic trả0 như sentinel; không chia workload cho0 |
| `compute.carry_over` | false | Quy ước hiện tại | Không có queue tồn qua slot; không suy ra CPU slot mới rảnh hoàn toàn |

Các hằng số radio còn lại theo `PaperParameters`, được version-control cùng
source. Đọc hằng số không phải đọc kết quả tương lai. Không thêm queue/job mẫu
vào v1 khi simulator chưa cung cấp queue đó trước action.

## 3. Thông tin bị cấm và thông tin chỉ được ước lượng

**Không đưa vào policy:** task/layout RNG seeds; chỉ số ảnh/job sắp sinh; input
bytes hoặc MI thực tế của slot sắp tới; `CpuPlan` của slot đó; planned/realized
completion; kết quả sau action; file trace tương lai; nhãn train/test.

**Được ước lượng trong P1:** kích thước input, compute demand, completion
probability, service duration và energy cho các lựa chọn. Estimator phải dùng
metadata/phân phối training pool đã khóa hoặc lịch sử đã quan sát; không đọc
sample tương lai bằng cách tái tạo RNG. Metadata đã biết trước phải có đường
truyền nhân quả được khai báo, không mặc định toàn bộ raw pool là feature.

Ghi riêng predicted và realized khi đánh giá; báo sai số calibration và runtime
ước lượng. V1 chưa trả các dự đoán này. Dùng cùng feature set và action rules khi
so cơ chế mới; reference24D vẫn được báo riêng như reference ít thông tin hơn.

## 4. Scenario contract

`layout_seed` vẫn chỉ base layout, mặc định42. `scenario_mode` và `shift_seed`
điều khiển can thiệp. Base được tạo bằng bộ RNG legacy nguyên bản; mỗi factor
của phần can thiệp có một stream Java Random riêng, seed được trộn SplitMix64
và ghi nguyên giá trị vào manifest. Không dùng các stream này để sinh task.

| Mode | Thay đổi | Giữ nguyên |
| --- | --- | --- |
| `legacy` | Không can thiệp, bỏ qua shift seed | Chính xác layout cũ |
| `position` | x,y | Hardware/task, battery capacity, outage |
| `hardware_task` | Hardware và vision task cùng nhóm | Vị trí, capacity, outage |
| `capacity` | Capacity và pin ban đầu | Vị trí, hardware/task, outage |
| `power` | Danh tính thiết bị có nguồn ngoài | Số lượng powered, connectivity và yếu tố khác |
| `connectivity` | Danh tính thiết bị có kết nối | Số lượng connected, power và yếu tố khác |
| `outage` | Cả power và connectivity masks | Hai số lượng và các yếu tố khác |
| `full` | Kết hợp tất cả factor streams trên | Số lượng powered/connected, ID vật lý |

`hardware_task` chưa tách riêng hardware và loại thuật toán; không suy kết quả
của nhóm này thành tác động hardware đơn lẻ. `full` dùng cùng từng factor như
các can thiệp riêng để so composition, **không bằng** `layout(shift_seed)` cũ.
Các range phân phối giữ theo model, nhưng cách ghép RNG khác.

Physical ID không đổi trong các mode này nên ảnh/job theo device index và task
seed vẫn ghép đúng thiết bị. Relabel ID là thao tác ở policy adapter trong
`drl.diagnostics --stage permutation`, không reorder Java device list. Nếu sau
này relabel snapshot v1, phải đổi cả feature rows và ánh xạ action; không chỉ
hoán đổi hai vector battery/age rồi bỏ quên thuộc tính khác.

Khi `save_trace`, bridge thêm `scenario.json`: schema, base/shift seeds, exact
stream seeds, counts, task seed, workload mode, diagnostics và SHA256 layout.
Hash chuẩn dùng vị trí/capacity dạng IEEE754 hex string đầy đủ độ chính xác,
enum, flags và ID theo thứ tự; không hash CSV đã làm tròn. Đây là **audit-only**.
Layout CSV, dataset-config và source pools ở cùng trace. Manifest không phải
input của policy.

## 5. Sử dụng API

```python
from drl.environment import EnvConfig, PaperEnv

with PaperEnv(EnvConfig(decision_state=True)) as env:
    obs, info = env.reset(seed=0, options={
        "layout_seed": 42, "task_seed": 2000000,
        "scenario_mode": "position", "shift_seed": 2100000,
        "trace": True,
    })
    state = info["decision_state"]
    # P0 chưa có policy mới; chọn action hợp lệ chỉ để minh họa API.
    obs, reward, terminated, truncated, info = env.step(0)
    env.save_trace("target/p0-example")
```

Có thể lưu mode/shift/decision_state trong EnvConfig hoặc override từng reset.
Mặc định legacy/0/false. `shift_seed` phải là signed64-bit int và decision_state
phải là bool; giá trị sai bị từ chối trước khi khởi động JVM. Giao thức JSON
vẫn protocol1 vì các field mới là optional và response mặc định giữ nguyên.

## 6. Protocol development và cách chạy

Protocol được lưu trong [`drl/protocol_p0.json`](../../drl/protocol_p0.json):
base42, ba shift seeds2.100.000–2.100.002, ba task seeds2.000.000–2.000.002,
hai workload, cap600, 8/8 availability. Mỗi workload có22 fixtures (legacy1 +
7 modes ×3 shifts), 66 cases. Task sampling ghép cặp; shared source pools,
chưa phải source-data holdout. Đây là development protocol cố định, không phải
final test. Các range final được dự trữ, còn cần collision audit trước khi
khóa confirmatory study; runner này không dùng chúng.

Chạy từ repo sau khi build Java; chọn thư mục output chưa tồn tại:

```powershell
.\scripts\build-drl.ps1 -Offline
.\.venv-drl\Scripts\python.exe -m drl.scenarios --output target/p0-new --runs result/target
```

Linux thay bằng `.venv-drl/bin/python`. Bỏ `--runs` để chỉ chạy Oldest Data và
Round Robin. Có `--runs` sẽ nạp các `best_model.zip` trong `drl-server-*`, không
train và không thay checkpoint. Đối với model đã train mixed, chạy synthetic
trong suite này là workload-transfer probe, **không phải synthetic-trained DQN**.

Output: protocol, source snapshot, manifest, episodes, summary, fixture checks,
decision snapshots và trace của Oldest Data ở task đầu mỗi fixture. Các policy
đều chỉ nhận observation24D trong suite; snapshot giàu thông tin được lưu riêng.
Không so runtime của suite với microbenchmark đã chạy; suite có trace I/O.

## 7. Tiêu chí nghiệm thu P0

- Default layout và transition/reward cũ khớp; schema không làm đổi24D.
- Can thiệp giữ nguyên các field ngoài nhóm được chọn, giữ counts chính xác.
- Các factor trong full khớp factor tương ứng chạy riêng với cùng shift seed.
- Cùng task seed/action prefix giữ input sequence khi đổi scenario, cả synthetic
  lẫn raw datasets; không đổi ID vật lý hoặc đọc RNG cho snapshot.
- Initial snapshot không thay khi đổi future task seed; timestamp và state sau
  step khớp observation, snapshot không giữ tham chiếu mutable vào simulator.
- Có source/config/layout provenance; kết quả development không bị gọi là
  final test hoặc bằng chứng duy nhất về nguyên nhân thất bại.

Kết quả thực thi P0 được ghi trong [P0_RESULTS.md](P0_RESULTS.md).
