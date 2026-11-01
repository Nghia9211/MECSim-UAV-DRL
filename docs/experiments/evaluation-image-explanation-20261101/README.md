# Vì sao ảnh không được giao đúng hạn?

**Trong simulator hiện tại, nguyên nhân chính không phải thời gian CPU xử lý một ảnh quá lâu.**
Nguồn: evaluation-full đã audit PASS; ROUND_ROBIN+ALL_UAV+RISK_EDF làm ví dụ chính.
240episode =30task seed×2geometry×2area scale×2load. Task xuất hiện lại ở các scenario, không phải17.008 ảnh gốc độc lập.

Tổng17,008 task ảnh;11,114 được giao đúng hạn;5,894 không được giao đúng hạn.
Đếm gộp có34.654% không giao đúng hạn. Con số macro mean từng episode ở báo cáo trước là34,589%; khác mẫu số/cách gộp, không mâu thuẫn.

| Nguyên nhân quan sát | Số task | % toàn bộ ảnh | % task không giao đúng hạn |
|---|---:|---:|---:|
| Local xử lý xong đúng hạn nhưng mất kết nối | 4676 | 27.493% | 79.335% |
| Upload + compute đã vượt deadline dù không có CPU queue | 1086 | 6.385% | 18.426% |
| Phần chờ contact làm vượt deadline dù không có CPU queue | 52 | 0.306% | 0.882% |
| Upload + compute cô lập kịp nhưng chờ CPU / risk rejection | 80 | 0.470% | 1.357% |

## Compute ảnh thực sự mất bao lâu?

Service demand/rate của mọi task ảnh bằng0,524349s, trên cả local và UAV trong shared-hardware setting.
Observed CPU start→completion của mọi ảnh completed khớp service time này. Không gán0s cho ảnh chưa được chạy.
Deadline tương đối20s/60s;0 task có compute đơn lẻ vượt deadline.
Đây là cost model được gán từ architecture timing trên workstation với random weights, không phải mỗi ảnh được chạy qua model RescueNet đã train trong mô phỏng.
Do đó kết luận chỉ áp dụng mô hình hiện tại; không khẳng định mọi phần cứng thật xử lý segmentation trong0,524s.

## Xử lý xong khác với giao được kết quả

Local source disconnected hoàn thành tính toán vẫn không tạo delivery update.
Ngoài contact khả dụng, ALL_UAV fallback LOCAL. Với nguồn mất kết nối, local completion không giải quyết việc chuyển kết quả về.
Code chưa có cơ chế lưu output local rồi để UAV nhận kết quả nhỏ về sau; cũng không retry/migrate task local đã kết thúc.
Đây là giới hạn semantics/mô hình, không phải segmentation chậm hoặc accuracy thấp.
Riêng nhóm4.676local on-time disconnected, không có contact UAV hợp lệ tại quyết định offload:
- UAV đang bay, không có known-flight contact đủ điều kiện: 2796 task.
- UAV hover ngoài65m: 1422 task.
- Stop đã đóng không nhận upload mới: 458 task.

## Upload và CPU queue

Trong1086 intrinsic upload+compute misses, có1086 task mà riêng thời gian upload đầy đủ đã vượt toàn deadline.
Các full-upload delay là thời gian cần thiết dự kiến; task có thể expire sớm, không được nói đã thực sự truyền hết quãng thời gian đó.
Khoảng cách trong range65m chưa bảo đảm tốc độ đáp ứng deadline; JPEG gốc gần5MB không tự nhỏ lại khi inference resize512×512.
Trong nhóm80 CPU misses, 80 có observed background overlap trong phần chờ.
Observed overlap không phải số task chắc chắn được cứu nếu đổi scheduler; không phải counterfactual experiment.

## Đối chiếu các phương pháp trên cùng evaluation workload

| Phương pháp RR | Offered | Delivered on time | Local ontime disconnected | Upload intrinsic | Contact-wait intrinsic | CPU miss |
|---|---:|---:|---:|---:|---:|---:|
| BG_CAP_EDF | 17008 | 11181 | 4676 | 1086 | 52 | 13 |
| EDF | 17008 | 10999 | 4676 | 1086 | 52 | 195 |
| RISK_EDF | 17008 | 11114 | 4676 | 1086 | 52 | 80 |

Cap giảm CPU misses nhưng không thay đổi các nhóm mất kết nối/radio trên cùng RR trajectory.
RISK_EDF→cap thêm67 task ảnh được giao đúng hạn trên17.008 offered task, không giải quyết toàn bộ nhóm còn lại.
Lợi ích đó đi kèm background harm đã báo ở admission-final-20261101; không kết luận dominance.
Các nhóm failure có hierarchy loại trừ nhau, không coi là nguyên nhân nhân quả duy nhất.
Kết quả CPU-blocking trong hover control không được dùng đại diện toàn bộ ảnh không-delivery ở mobile.

## Nên sửa đúng chỗ nào?

Ưu tiên làm rõ mô hình result delivery: có cho UAV thu output của task local đã xử lý xong không, link output/size/wait/energy như thế nào.
Nếu thêm, đây là một adaptation riêng, phải tính trễ từ generation đến delivery, không reset deadline hay giả lập delivery tức thời.
Tiếp đó tối ưu contact/routing theo độ trễ upload; giữ CPU scheduler/admission làm thành phần riêng.
Không cần tăng tốc compute giả hoặc sửa radio để che nhóm disconnected delivery.
Chưa đổi simulator/protocol hay chạy lại thuật toán trong analysis này.

