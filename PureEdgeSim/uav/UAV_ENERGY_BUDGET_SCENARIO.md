# Kịch bản ngân sách năng lượng UAV × deadline task

Yêu cầu của nhóm trưởng: thiết kế lại kịch bản thí nghiệm để quan tâm tới **deadline hoàn thành task**
và **năng lượng UAV sử dụng**. Đây là thay đổi về kịch bản và đo đạc; không thêm policy mới và không sửa kernel mô phỏng.

**Trạng thái: chưa chạy.** Máy phát triển không có JDK/Maven nên phần Java chưa được biên dịch và chưa có
episode nào. Chỉ test Python (`scripts/test_uav_energy_budget.py`, `scripts/test_offloading_metrics.py`) đã chạy.
Chưa có kết quả; chạy theo mục “Chạy” rồi mới đọc số.

## Thay đổi so với scenario near-paper

| Phần | Trước | Bây giờ |
|---|---|---|
| Pin UAV | cố định 1.600.000 J, không cạn trong horizon | **ngân sách tuyệt đối theo scenario** (`uavBatteryJ`), mặc định vẫn là pin paper |
| Scenario | một deadline = một load | deadline × ngân sách: `d{deadline}-b{kJ}kj` |
| Metric năng lượng | J/ảnh toàn hệ thống (UAV + mọi thiết bị) | thêm năng lượng UAV tách flight/hover/compute/TX |
| Hover | lẫn trong tổng | **chi phí cố định**; năng lượng điều khiển được = flight + compute + TX |
| Hết ngân sách | chỉ có trong nhóm pin 30 kJ | báo `exhausted`, `budget_used` cho từng scenario |

Hết ngân sách UAV dùng đúng cơ chế sẵn có của kernel: UAV dừng CPU và upload, task còn lại là
`DROPPED_UAV_BATTERY` và tính là thất bại. Local vẫn chạy.

## Lưới thí nghiệm

[uav-energy-budget-protocol.json](offloading/uav-energy-budget-protocol.json), tạo bằng
`scripts/uav-energy-budget-study.py prepare`.

- Deadline: 300 s và 600 s (giống near-paper).
- Ngân sách UAV: **60, 100, 150, 200, 1600 kJ** (tuyệt đối). 1600 kJ là đối chứng không ràng buộc.
- Policy: RR + {ALL_LOCAL, ALL_UAV, SHORTEST_FINISH, DEADLINE_ENERGY, DELIVERY_AWARE} + EDF (baseline có sẵn).
- 30 workload seed, một layout, mọi tham số vật lý giữ nguyên near-paper.
- 2 × 5 × 30 × 5 = **1.500 episode**. Workload không phụ thuộc ngân sách nên mọi ngân sách cùng deadline/seed dùng chung workload hash (so sánh ghép cặp).

Cơ sở chọn ngân sách (tính số học, chưa phải kết quả mô phỏng): hover 80 W suốt horizon 1800 s tốn 144 kJ; bay tốn 150 W.
60 kJ cạn sau tối đa 750 s hover (400 s bay), tức trong lúc còn xử lý task. 100 kJ cạn sau 1250 s hover. 150 kJ đủ để chỉ hover tới horizon.
200 kJ chừa chỗ cho bay. 1600 kJ là pin paper.
**Cần kiểm tra khi chạy smoke:** các mức thấp thực sự bị ràng buộc (cột `Exhausted`) và đối chứng 1600 kJ không. Nếu không, chỉnh lưới
dựa trên điều kiện *ràng buộc có xảy ra hay không*, không dựa trên policy nào thắng, rồi khóa protocol trước khi chạy đầy đủ.

## Metric (theo `EVALUATION_METRICS.md`, thêm phần UAV)

Trục deadline: delivered DVR, compute DVR, mean/P95 latency của ảnh hoàn thành.
Trục năng lượng UAV: `uav_energy_j` (flight + hover + compute + TX), `uav_flight_j`, `uav_hover_j`, `uav_compute_j`,
`uav_controllable_j`, `uav_budget_used_frac`, `uav_budget_exhausted`, và J UAV trên mỗi ảnh đúng hạn (tổng và điều khiển được; cả delivered).
Không gộp thành weighted score; đọc hai trục cùng nhau trong từng scenario. Không có ảnh đúng hạn thì J/ảnh là NA, không phải 0.
Giảm năng lượng do UAV cạn pin sớm hoặc drop nhiều không phải cải thiện; đọc cùng DVR và `Exhausted`.

Lưu ý: bay 150 W thay cho hover 80 W. Hover được coi là cố định nên `uav_controllable_j` tính toàn bộ flight J, không trừ phần hover
mà UAV lẽ ra tốn nếu đứng yên. Static-hover chưa là baseline trong selector hiện có.

## Chạy

Cần JDK 17, Maven, Python 3.11. Output phải là thư mục mới.

```bash
python scripts/uav-energy-budget-study.py prepare --protocol target/budget-smoke.json --smoke
python scripts/uav-energy-budget-study.py run --protocol target/budget-smoke.json --output target/budget-smoke-run
# đầy đủ:
python scripts/uav-energy-budget-study.py run --protocol PureEdgeSim/uav/offloading/uav-energy-budget-protocol.json --output target/budget-full-run
```

`run` biên dịch và chạy `NearPaperBenchmark`, chạy verifier độc lập (`near-paper-study.py verify`, đã kiểm tra thêm ngân sách theo scenario),
xuất `core-metrics-*.csv` / `CORE_METRICS.md` (có mục “UAV energy and budget”) và `ENERGY_BUDGET_RESULTS.md`.
`verify` chạy lại các bước sau trên output đã có.

## Giới hạn

Một layout; task synthetic 2–4 MB; CPU UAV, deadline là giả định near-paper; chưa có RX/truyền kết quả về; chưa có policy nhận biết ngân sách;
lưới ngân sách là thiết kế ban đầu chưa kiểm chứng bằng mô phỏng.
