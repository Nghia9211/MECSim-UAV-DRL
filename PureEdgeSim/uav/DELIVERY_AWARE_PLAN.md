# Delivery-aware offloading theo tiếp xúc hiện tại

Đã chạy và kiểm chứng đủ30seed. Kết quả, đánh đổi và recovery test:
[DELIVERY_AWARE_RESULTS.md](DELIVERY_AWARE_RESULTS.md).

Protocol trước khi chạy, 29/10/2026. Bước tối thiểu sau kết quả mobile:
policy cũ tối ưu compute completion, chưa biết kết quả local có đến trung tâm không.

## Thuật toán và phạm vi

`DELIVERY_AWARE` dùng cùng forecast của DEADLINE_ENERGY. Nếu source disconnected
và UAV đang available trong stop/coverage, có pin và predicted finish<=deadline,
chọn UAV để kết quả có đường delivery. Các trường hợp khác dùng DEADLINE_ENERGY.
Không đọc task tương lai, actual MI hoặc outage tương lai. Không teleport hoặc upload
khi bay; không thay CPU/power/deadline/range/layout để làm thuật toán mới thắng.

Đây là **current-contact delivery-aware routing**, chưa phải planner thời điểm ghé
trong tương lai. Chưa có buffer chờ chuyến bay, migration hoặc upload kết quả local
đã tính trước. Ngoài coverage vẫn xử lý local ngay và có thể không delivery.
Chỉ thêm một boolean localDeliveryAvailable từ connected flag đã có, mặc định true
trong fixed mode. Các routing cũ không dùng boolean này và phải giữ hành vi.

## Thiết kế thí nghiệm

- Giữ nguyên mobile model: RR, 12CPU local500MIPS, UAV2000MIPS, flight150W/hover80W,
  v5m/s, range65m, dwell30s, 2layout scale, 2load, 2pin, horizon600s/arrival300s.
- 30task seed95000..95029; estimate error0 và±40%; không tune threshold.
- 9policy: ALL_LOCAL+FIFO; ALL_UAV+FIFO/EDF/SPT; SHORTEST_FINISH+EDF;
  DEADLINE_ENERGY+EDF/RISK_EDF; DELIVERY_AWARE+EDF/RISK_EDF.
- 8case ×30seed ×9policy ×2error =4320episode. Pilot3seed trước server.
- So cùng run/kernel/seed/workload. Kiểm tra các baseline chung khớp run mobile trước;
  field trace mới không được làm đổi decision/task/energy của policy cũ.

## Metric và tiêu chí đọc kết quả

Giữ đầy đủ compute DVR, J/ảnh đúng hạn, completed-image mean/P95 và lifetime có
censoring theo EVALUATION_METRICS.md. Với thay đổi mục tiêu delivery này, đánh giá
thêm **delivered DVR và J/ảnh delivered đúng hạn**, không thay định nghĩa metric cũ.
Báo cả mean/P95 latency của các kết quả thực sự đã delivered (gồm late), số case
có deliveries, backgroundDVR, coverage/offload và flight/hover energy.

Lợi ích routing phải thể hiện qua delivered DVR; compute DVR và năng lượng có thể
đánh đổi. Không gọi số offload tăng tự nó là cải thiện. Không gộp thành weighted score
hoặc tuyên bố significance nếu chỉ có trung bình. Không khẳng định relay/backhaul
thực tế vì delivery hiện tức thời khi có đường truyền, chưa có RX/output energy.

## Kiểm chứng

- Java hand case: local rẻ nhưng disconnected, UAV tới sau10s; task trước contact
  vẫn local, task trong contact offload và delivered. Connected source giữ routing cũ.
- Audit độc lập tái tạo connected flag từ config và contact từ trajectory, kiểm tra
  route, deadline/pin forecast, task/energy/updates; trace boolean giả phải bị từ chối.
- Giữ test âm mobile/risk; thêm test thật sự gặp override delivery (không chỉ route
  giống baseline), false connectivity, missing observation, old route và missing update.
- Chỉ hoàn tất server khi exit0 + marker + COMPLETE manifest + PASS audit/test;
  tải bảng/metadata và đối chiếu checksum. Không train DQN trong đợt này.

Chạy Linux qua runner hiện có:

```bash
OUT_DIR=target/NEW PROTOCOL=PureEdgeSim/uav/offloading/delivery-aware-protocol.json DELIVERY_AUDIT=1 bash scripts/run-mobile-comparison-server.sh
```
