# Đưa baseline và RISK_EDF vào môi trường UAV di động

Đã hoàn tất run30seed và independent verification. Kết quả và giới hạn:
[MOBILE_COMPARISON_RESULTS.md](MOBILE_COMPARISON_RESULTS.md).

Protocol trước launch, 29/10/2026. Tái sử dụng mobile kernel đã có; không đổi
trajectory/coverage để làm thuật toán mới thắng. Không train DQN trong bước này.

## Thiết lập và công bằng

- Một UAV đi theo **Round Robin** qua source còn sống; cùng policy cho mọi thuật toán.
  Cùng policy không bảo đảm cùng trajectory: upload chưa xong có thể giữ UAV ở stop lâu hơn.
- Bay thẳng 5m/s, cao10m, flight150W, hover80W, dwell30s, slant coverage65m.
  Local/UAV CPU chạy được khi bay; không upload khi bay. Không teleport.
- Task ngoài coverage chọn LOCAL ngay. ALL_UAV nghĩa là ALL_UAV_WHEN_COVERED.
  Không đợi UAV tới, không reset deadline, không migration. Upload dở giữ stop tới
  lúc hoàn thành/expiry/depletion, rồi mới bay tiếp. Không có radio contention.
- 12 CPU local500MIPS; UAV2000MIPS; 8/12 source có đường chuyển kết quả local.
  Local completion ở source disconnected không phải delivered result.
- Vùng250m và800m scale từ cùng layout seed42, 2 tải(light/overload), pin30kJ/1.6MJ,
  horizon600s, arrival[0,300)s. Power/compute/deadline là giả định, không calibration thực.
- 30 task seed95000..95029; estimate error0 và±40%. Shared offered workload giữa
  mọi policy/layout/battery trong một mức error. Không gọi đây là30layout độc lập.
- 9 cặp routing/scheduling trong `offloading/mobile-comparison-protocol.json`;
  gồm ALL_LOCAL+FIFO, ALL_UAV+FIFO/EDF/SPT, SHORTEST_FINISH+EDF,
  DEADLINE_ENERGY+FIFO/EDF/SPT và DEADLINE_ENERGY+RISK_EDF.
- 8case ×30seed ×9policy ×2error = **4320 episode**. Pilot local trước server.
  Không so tuyệt đối với fixed benchmark4CPU rồi quy tất cả khác biệt cho mobility.

## Metric bắt buộc

Giữ bộ core metric trong EVALUATION_METRICS.md. Total/UAV energy đã gồm propulsion
flight+hover; không cộng flight lần thứ hai. Thêm flight/hoverJ, travelledm,
covered/offloaded images và backgroundDVR để thấy UAV có thực sự tham gia hay không.

Tách rõ **compute DVR** và **delivered DVR**. Compute-completed đúng hạn tại source
mất kết nối vẫn thất bại về delivery. Báo J/ảnh đúng hạn theo cả hai định nghĩa;
không thay mẫu số hoặc đổi metric chính âm thầm. Truyền kết quả/backhaul hiện tức
thời khi có kết nối hoặc UAV relay; chưa có output transmission delay/energy.

Lifetime là thời gian UAV có năng lượng, có censoring tại600s, không phải lifetime
mạng hay AoI termination của paper. Primary latency chỉ completed images, chưa phải
độ trễ output delivery qua backhaul vật lý.

## Kiểm chứng

- Java hand test: guard loại task vô vọng trong lúc UAV bay, task tiếp theo chạy,
  drop vẫn là failure; flight/CPU dùng chung pin và cộng năng lượng đúng.
- Independent mobile audit: trajectory, speed, coverage, upload/departure, CPU,
  causal route forecasts, risk guard, energy và freshness/delivery updates.
- Verifier âm: trajectory/coverage/energy/selection corruption và false guard estimate.
  Nếu workload không có risk-drop, giữ nguyên kết quả đó và dùng hand fixture in-flight
  để kiểm tra negative guard replay; không đổi seed hoặc tăng tải để ép guard hoạt động.
- Metric test: không triple-count energy từ ba source rows, phân biệt compute/delivery.
- Chỉ gọi xong khi exit0 + COMPLETE manifests + PASS verifiers + completion marker.

Runner: `OUT_DIR=target/NEW bash scripts/run-mobile-comparison-server.sh`.
Các CSV/CORE_METRICS.md do verifier xuất tự động. Không gộp kết quả hai estimate
error; đọc theo từng layout/load/pin, không chỉ trung bình toàn bộ.
