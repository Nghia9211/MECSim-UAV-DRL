# Hàng đợi chờ tiếp xúc của chuyến bay đã chọn

Đã hoàn tất run30seed và kiểm chứng. Xem [CONTACT_WAIT_RESULTS.md](CONTACT_WAIT_RESULTS.md).

Protocol trước launch server, 29/10/2026. Nối tiếp DELIVERY_AWARE, không train model.

## Quyền chờ chung

`allowContactWait=true` là capability của toàn môi trường, không đặc quyền của
DELIVERY_AWARE. Cả9routing/scheduler dùng cùng luật sau:

- Nếu đang hover phục vụ trong range, upload ngay như cũ.
- Nếu đang bay, chỉ xem endpoint của **chuyến bay đã chọn trước arrival của task**.
  Source tại đích hoặc lân cận trong slant range65m có thể reserve upload tại ETA.
  ETA phải trước deadline. Không nhìn các stop chưa chọn, không thay RR/teleport.
- Ngoài hai loại contact này vẫn LOCAL ngay. ALL_UAV buộc chọn UAV khi có contact,
  dù upload/CPU có thể trễ hoặc thiếu pin; đây vẫn là baseline forced, không được
  âm thầm lọc mọi task khó bằng admission tối ưu.
- DELIVERY_AWARE chỉ ưu tiên UAV cho source disconnected khi forecast có pin và
  kịp deadline. Connected source dùng DEADLINE_ENERGY. SHORTEST_FINISH cũng được
  forecast và chọn cùng contact tương lai đã biết nếu nó có lợi.

Chọn UAV là quyết định irrevocable từ arrival. Task nằm chờ tại source, không
compute local song song, không migration/retry hoặc chuyển kết quả local đã tính.
Deadline giữ từ arrival. Source trả idle và compute đang chạy nếu có; **TX=0 khi
chờ**, chỉ bắt đầu khi tới endpoint đã định. Source/UAV chết hoặc deadline tới
đều kết thúc task theo luật cũ, không tạo upload ảo sau khi chết.

Pending contact dùng nội bộ phase TRANSFERRING với planned start trong tương lai;
phase này không có nghĩa radio đang phát. Bộ đếm radio và uploaded_s dùng start
thực sự có thể bắt đầu, không dùng arrival. Không đổi ordinal các trạng thái cũ.
Upload chưa xong giữ UAV ở stop sau dwell như cũ; CPU UAV chạy được trong lúc bay.

## Forecast và telemetry

- Forecast tính thời gian chờ + upload + admitted CPU queues bằng estimated MI.
- Pin UAV gồm phần bay còn lại của leg đã biết và hover/CPU; không dùng các leg
  tương lai chưa chọn. Sau contact, forecast vẫn giả định hover như mô hình cũ.
- Source budget gồm wait/idle, giữ observed CPU load, TX chỉ khoảng upload và các
  transfer đã biết. Đây là forecast heuristic, không bảo đảm khi xuất hiện task mới
  hoặc estimate sai. Kernel luôn clip tại depletion và ghi mọi failure.
- Coverage trace giữ physical coverage/rate tại arrival, thêm offload_available,
  planned_upload_start_s, planned_upload_s, planned_slant_m. Task trace thêm planned
  upload start; planned timestamp không chứng minh UAV/source sống tới lúc đó.
- Verifier độc lập tái tạo plan từ visit đã biết tại arrival; không tin cột plan
  mà bỏ qua kiểm tra geometry, timing, source/UAV energy hoặc route forecast.

## Thí nghiệm

- Giữ nguyên12source, RR, layoutSeed42 ở2scale, 2load, 2pin, CPU/power/deadline,
  horizon600s vàarrival300s. 30task seed95000..95029, estimate error0/±40%.
- Cùng9policy của DELIVERY_AWARE protocol, chỉ bật capability chờ chung:
  `offloading/contact-wait-protocol.json`.
- 8case ×30seed ×9policy ×2error =4320episode. Không tune threshold theo kết quả.
- Pilot3seed/error. Chạy thêm pilot chế độ chờ tắt trên code mới và đối chiếu với
  pilot DELIVERY_AWARE cũ để kiểm tra compatibility, không giả định code mới tương
  đương chỉ vì nó compile. Các default API/protocol cũ vẫn allowContactWait=false.
- So thuật toán trong cùng run khi mọi baseline có quyền chờ. Đối chiếu run cũ
  không-chờ là ablation capability, không phải bằng chứng thắng baseline cùng quyền.

## Metric và kiểm chứng

Giữ toàn bộ compute/delivered DVR, J/ảnh đúng hạn theo hai định nghĩa, mean/P95
latency, lifetime và censoring theo EVALUATION_METRICS.md. Thêm số reservations,
số thật sự upload, số delivered đúng hạn từ reservation, tổng thời gian chờ thực,
số image có eligible contact. Failure của reservation vẫn nằm trong mẫu số DVR.

Java hand cases: chờ đúng ETA/noTX trước đó; timeout không reset deadline; không
đoán future visits; source/UAV chết trước contact; upload pinning và expiry release.
Giữ audit/test cũ và thêm5test âm contact-wait. Chỉ xong khi COMPLETE + PASS audits
và tests + exit0/marker, tải metadata/bảng với checksum và parity local/server.

```bash
OUT_DIR=target/NEW PROTOCOL=PureEdgeSim/uav/offloading/contact-wait-protocol.json DELIVERY_AUDIT=1 WAIT_AUDIT=1 bash scripts/run-mobile-comparison-server.sh
```
