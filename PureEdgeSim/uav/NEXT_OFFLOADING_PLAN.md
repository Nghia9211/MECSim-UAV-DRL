# Việc tiếp theo: offloading có xét thời gian giữ UAV tại stop

Ngày 01/11/2026. **Đề xuất cần kiểm chứng, chưa triển khai và chưa khẳng định novelty.**

## Quyết định phạm vi

Tập trung energy-aware offloading; giữ ROUND_ROBIN và EDF cố định.
Không bắt buộc đồng thời phát triển placement/scheduling/cache.
Chưa cần train lại DQN, tăng CPU, tải dataset mới hoặc dùng GPU cho vòng tiếp theo.

Bằng chứng: [sensitivity đã verified](NEAR_PAPER_SENSITIVITY_RESULTS.md).
CPU UAV ít ảnh hưởng trong dải đã thử; deadline ảnh hưởng mạnh đến DVR;
dwell đổi energy chủ yếu qua flight/hover.
Mỗi task upload có thể kéo dài stop và đổi cơ hội phục vụ task/thiết bị khác.
Các baseline hiện tại đã có deadline/finish/battery feasibility checks;
chỉ thêm các checks đó không đủ để gọi là đóng góp mới.

## Câu hỏi cần kiểm chứng

Khi giữ nguyên mô hình, deadline và lịch chọn thiết bị,
policy offloading có xét thêm thời gian giữ UAV tại stop có giảm delivered DVR
hoặc J/ảnh giao đúng hạn so với DEADLINE_ENERGY mà không làm P95 xấu đi đáng kể không?

Đây là giả thuyết; có thể không cải thiện.
Không coi việc nới deadline, tăng dwell hoặc đổi radio là thuật toán tốt hơn.

## Thứ tự thực hiện

1. **Định nghĩa cơ chế và thông tin được phép thấy.**
   Tính phần thời gian upload kéo dài quá lịch rời stop đã biết.
   Tách thời gian chờ chuyến bay, upload, CPU queue và compute;
   CPU có thể chạy khi bay nên không tự cộng CPU time thành stop extension.
   Chỉ dùng task đã đến, estimated MI, vị trí/radio và kế hoạch contact hiện có.
   Không dùng actual MI, task tương lai chưa đến hoặc rollout oracle.
   Rà related work trước khi gọi cơ chế là đóng góp mới.

2. **Triển khai một policy nhỏ, có kiểm chứng.**
   Bắt đầu từ baseline DEADLINE_ENERGY.
   Bổ sung thông tin causal cần thiết và đúng một cơ chế quản lý stop extension;
   công thức/threshold và quyền fallback phải được ghi rõ trước benchmark.
   Không sửa đồng thời workload, radio, pin, deadline, RR hoặc EDF để tạo lợi thế.

3. **Đánh giá development và ablation.**
   Dùng môi trường/workload đã khai thác để phát triển, không gọi đó là fresh holdout.
   So với ALL_LOCAL, ALL_UAV, SHORTEST_FINISH, DEADLINE_ENERGY, DELIVERY_AWARE.
   Ablation bỏ riêng cơ chế stop-extension; không nhân đôi baseline có cùng behavior thành bằng chứng mới.
   Theo dõi rescues/harms, contact/upload duration, flight/hover/compute/TX,
   delivered DVR, J/ảnh, completed/delivered mean/P95 latency, censored UAV lifetime và runtime.
   Giữ mọi kết quả xấu; không chọn setting đẹp nhất rồi gọi là kết luận chung.

4. **Khóa cơ chế trước khi xác nhận.**
   Sau development, khóa code, tham số và protocol.
   Các environment 110–119 đang được ghi dự phòng và chưa chạy trong hai campaign mới;
   kiểm tra lịch sử sử dụng trước khi tuyên bố holdout.
   Dùng workload seeds xác nhận tách biệt với các seed phát triển nếu protocol cho phép.
   Chỉ chạy xác nhận một lần sau khi khóa; nếu sửa cơ chế thì không coi bộ đã xem là holdout nữa.

## Điều kiện để đi tiếp

- Test causal visibility, route/stop-extension và trường hợp không có contact.
- Independent trace verifier + mandatory metrics PASS.
- Cùng workload hashes và điều kiện mô phỏng giữa các policy.
- Energy efficiency dùng tổng system energy / tổng on-time delivered images;
  task drops vẫn thất bại; pin còn ở horizon là censored.
- Báo chi phí quyết định riêng nếu có đo; kernel wall time không phải per-decision latency.
- Nếu cơ chế không cải thiện, phân tích vì sao rồi quyết định giữ/dừng;
  không bắt buộc phải thắng cả latency, energy và DVR.

## Dataset và việc người dùng cần làm

Hiện chưa cần tải thêm dữ liệu. Vòng này dùng scenario synthetic gần paper để tách cơ chế.
Chỉ chuyển sang RescueNet/Alibaba sau khi cơ chế được kiểm tra;
khi đó giữ rõ mapping workload và phần cứng/cost model, không coi metadata replay là inference thật.

Việc nên làm ngay: đọc bảng kết quả sensitivity, chốt với người hướng dẫn rằng phạm vi là
**offloading với ảnh hưởng tới contact**, rồi phát triển bước 1–2 ở trên.
Không cần đổi deadline 600 s hoặc CPU 2 MB/s chỉ để hạ tỷ lệ lỗi.
