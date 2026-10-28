# REFERENCE và setting nghiên cứu offloading + scheduling

Cập nhật: 28/10/2026. Tài liệu tóm tắt phạm vi và trạng thái code, không thay đổi protocol đang chạy.

**REFERENCE hỏi: UAV phục vụ thiết bị nào để mạng sống lâu hơn?**

**Setting nghiên cứu hỏi: task phân tích thiên tai nên xử lý ở đâu và theo thứ tự nào để đáp ứng deadline với năng lượng giới hạn?**

Hai setting kế thừa cùng bối cảnh UAV–edge nhưng khác đơn vị quyết định và mục tiêu. Không so trực tiếp lifetime của REFERENCE với DVR của setting mới để kết luận thuật toán nào tốt hơn.

## 1. So sánh ngắn gọn

| Thành phần | REFERENCE đang dùng | Setting nghiên cứu dự định phát triển |
| --- | --- | --- |
| Bài toán chính | Duy trì hoạt động của thiết bị mất nguồn/kết nối | Xử lý tác vụ ảnh thiên tai dưới tải nền biến thiên |
| Quyết định | Chọn thiết bị/điểm đến UAV tiếp theo | Offloading local/UAV + thứ tự xử lý task; lựa chọn thiết bị có thể là tầng phục vụ giữ cố định hoặc nghiên cứu riêng |
| Đơn vị công việc | Mỗi slot sinh một task synthetic cho mỗi thiết bị | Task đến theo thời gian mô phỏng, có arrival, ready time, deadline, priority và compute demand |
| Dữ liệu | Synthetic 2–4 MB/task | RescueNet tạo task ảnh; Alibaba tạo tải nền cạnh tranh CPU |
| CPU UAV | Synthetic coi thời gian tính toán UAV không đáng kể | CPU hữu hạn, có hàng đợi và thời gian xử lý |
| Task chưa xong | Bỏ phần dở cuối slot, không giữ tiến độ | Queue và remaining work tồn tại qua nhiều event; task đang chạy có thể trễ, task chờ có thể expired theo quy tắc đã công bố |
| Offloading | Coverage quyết định nhánh upload/local, không có policy routing độc lập từng task | Policy chọn toàn task local hoặc UAV tại arrival, có xét queue, thời gian truyền và pin |
| Scheduling CPU | Không tối ưu thứ tự task trong nhánh synthetic | FIFO/EDF/Priority/SPT và cơ chế nghiên cứu; bản đầu không preemption |
| Cập nhật thông tin | Thiết bị connected **hoặc** upload thành công thì reset tuổi, dù local chưa xử lý xong | Phân biệt compute hoàn thành, đúng deadline và kết quả đã tới nơi nhận; local disconnected chưa được tính là delivered |
| Ràng buộc thời gian | Tuổi dữ liệu theo slot; đạt 10 slot thì failure | Deadline end-to-end của từng task tính từ arrival; tuổi dữ liệu theo giây có thể báo riêng |
| Mục tiêu chính | Tăng lifetime của mạng | Tăng số/tỷ lệ task hữu ích hoàn thành đúng hạn dưới ngân sách năng lượng; đánh giá latency và energy cùng nhau |
| Kết thúc episode | Thiết bị/UAV hết pin hoặc vi phạm giới hạn tuổi; safety cap 200 slot | Horizon cố định trong benchmark hiện tại; UAV chết không tự dừng CPU local còn sống |
| Năng lượng | Pin thiết bị, UAV bay/hover, local/TX theo mô hình paper; không có CPU UAV hữu hạn trong synthetic | UAV flight/hover/compute và ground idle/compute/TX; báo UAV, ground và tổng |
| Tính di động | UAV đến thiết bị được chọn | Bản cô lập offloading/scheduling dùng UAV cố định; bản mobile đã nối chọn thiết bị, di chuyển và coverage |
| State RL | 24D theo paper; 125D là biến thể đã thử | Mobile pilot có 129D tổng hợp UAV, thiết bị và queue; không phải state 125D |
| Phạm vi hiện tại | Một cấu hình/layout tham chiếu, chưa toàn bộ Tables 5/6 | Environment và baseline đã có; chưa hoàn tất hiệu chuẩn hoặc thuật toán joint được xác nhận |

## 2. Ba quyết định phải phân biệt

```text
Chọn thiết bị phục vụ → UAV di chuyển, tạo coverage
                                  ↓
Offloading task → xử lý local hoặc upload lên UAV
                                  ↓
CPU scheduling → chọn task sẵn sàng để chạy tiếp
                                  ↓
Completion → deadline / delivery / energy
```

Để đo đóng góp offloading + scheduling, có thể giữ tầng chọn thiết bị bằng Round Robin/Oldest Data hoặc một policy đã khóa. Nếu đồng thời thay cả ba tầng thì phải có ablation để tách tác động.

**DQN mobile hiện chỉ học chọn thiết bị.** Offloading và scheduler được cấu hình cố định trong từng run; chưa có một DQN học chung cả ba quyết định.

## 3. LOCAL_COMPLETION nằm ở đâu?

`LOCAL_COMPLETION` là **biến thể kiểm tra quy ước của nhánh paper**, không phải toàn bộ setting nghiên cứu mới:

- REFERENCE: connected là đủ để reset tuổi.
- LOCAL_COMPLETION: local phải connected **và** xử lý xong trong slot mới reset tuổi.
- Nhưng vẫn sinh task theo slot, bỏ task dở và chưa có persistent task queue/deadline từng task.

Trên layout 0, quy tắc completion làm thêm 5 thiết bị connected không thể tự cập nhật trong cap 600 s. Cộng 4 thiết bị disconnected, có 9 thiết bị phụ thuộc UAV. Điều này làm bài toán khó hơn; không nên chuyển nguyên quy tắc bỏ task dở đó sang hệ thống queue mới mà không có lý do ứng dụng.

## 4. Phần đã có và phần còn thiếu

**Đã có trong code:** local/UAV routing, CPU/queue/pin riêng, queue bền, deadline end-to-end, baseline scheduling, tách actual/estimated compute, mobile/coverage và verifier trace. DQN mobile đã train pilot; state 125D được thử riêng trên nhánh paper.

**Cần làm tiếp để củng cố đề tài:**

1. Chốt objective chính và yêu cầu dịch vụ: deadline miss, delivery hay priority-weighted on-time completion; định nghĩa rõ năng lượng được tính và task drop. Chưa chốt các hệ số reward development thành đóng góp cuối.
2. Hiệu chuẩn chi phí inference, công suất và deadline; hiện nhiều giá trị vẫn là giả định. RescueNet chưa chạy inference thật; Alibaba chưa replay đầy đủ timestamp/DAG.
3. Khóa một benchmark workload theo thời gian với cùng arrival/actual work cho mọi policy; khảo sát tải, pin và sai số estimate. Tách task-seed holdout khỏi source-data/layout holdout.
4. So sánh cùng quyền quyết định: offloading baseline × scheduler baseline, rồi thêm thuật toán nghiên cứu. Với mobile, giữ policy chọn thiết bị cố định trước khi mở rộng ablation.
5. Đánh giá nhiều seed/layout, báo cả image/background DVR, delivery, latency, drop, năng lượng tổng và năng lượng trên task hữu ích. Không gọi năng lượng giảm do phục vụ ít task hơn là thành công.

Placement/trajectory tối ưu, cache, DVFS và multi-UAV **chưa là yêu cầu bắt buộc** của phạm vi hiện tại. Bản đầu có thể tập trung offloading + CPU scheduling.

## 5. Đọc kết quả hiện tại cho đúng

- REFERENCE, layout 0: DQN24 best trung bình **31,56 slot**, final **30,33**; Oldest Data **29,00**. DQN125 best **31,67**, final **22,89**. Chưa xác nhận lợi ích đáng tin cậy của state125.
- PPO/A2C đang được bổ sung vào **cùng REFERENCE**, không phải benchmark joint scheduling mới. Hyperparameter PPO/A2C là lựa chọn implementation, không phải cấu hình tác giả công bố.
- REFERENCE là tên quy ước implementation; các bất định về radio, output-link và slot cuối vẫn phải công bố. Chưa được gọi các số trên là đã tái hiện toàn bộ paper hoặc cải thiện so với tác giả.
- Horizon 600 s của môi trường scheduling mới khác **cap 600 s mỗi slot** của REFERENCE. Ít năng lượng trong horizon cố định chưa chứng minh lifetime dài hơn.

## Tài liệu chi tiết

- [Protocol REFERENCE](PAPER_REFERENCE_STATE_PLAN.md)
- [Giả định và đối chiếu paper](PAPER_ALIGNMENT.md)
- [Mô hình offloading + scheduling](OFFLOADING_SCHEDULING.md) — mô tả bản UAV cố định ban đầu.
- [Tầng mobile được thích nghi từ paper](ADAPTED_PAPER_SERVICE.md)
- [State/reward của mobile DQN pilot](MOBILE_DRL.md)
- [Đợt baseline PPO/A2C](REFERENCE_BASELINES_PLAN.md)
