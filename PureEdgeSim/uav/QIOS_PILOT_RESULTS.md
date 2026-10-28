# QIOS: thử cơ học scheduler đầu tiên

Trạng thái: prototype local, chưa push/server. Chưa phải full joint QIOS.

Đã implement `QueueImpactScheduler`: thử từng ready task ở vị trí đầu, rollout EDF phần còn lại, xét weighted on-time service, energy horizon và latency; stable tie-breaking. Không thay baseline hoặc kernel. Projection chỉ xét queue đã ready, không dự báo upload/future arrival; không dùng actual work trong API scheduler.

Ba kiểm thử chuyên biệt đạt: ảnh hưởng task dài lên nhiều task ngắn; hoàn thành đúng biên deadline/pin; đối chiếu từng first-action projection với kernel về served value và energy trong queue biết trước, estimate chính xác. Có kiểm tra không mutate input và tính ổn định khi đảo thứ tự danh sách.

Pilot:30seed ×4scheduler =120episode. Mỗi seed có18task synthetic cùng arrival0, upload0, pin dư; ALL_UAV cố định. Đây là stress test batch để kiểm tra scheduling, không phải workload disaster đã hiệu chuẩn và không phải benchmark RescueNet/Alibaba. Queue/task generation giống nhau giữa policy. Chưa có replay Python độc lập cho pilot này; không gán nhãn full-verifier PASS.

| Scheduler | Ảnh đúng hạn, mean | Background đúng hạn, mean | Weighted service, mean | UAV J, mean |
| --- | ---: | ---: | ---: | ---: |
| FIFO | 3,100 | 2,000 | 10,033 | 102,267 |
| EDF | 1,633 | 0,667 | 4,800 | 107,000 |
| SPT | 5,633 | 2,700 | **17,100** | 101,600 |
| QIOS_READY | **5,767** | 1,433 | 16,567 | **101,000** |

**Kết quả âm cần giữ:** prototype chưa vượt SPT theo working objective weighted service, dù mean số ảnh đúng hạn cao hơn. EDF tail ngắn hạn có thể bỏ qua thứ tự tốt hơn; ưu tiên từng quyết định nhìn trước không bảo đảm tối ưu toàn lịch. Background được phục vụ ít hơn SPT; không có bảo đảm fairness. Chưa phân tích CI hoặc hiệu năng runtime đáng tin cậy.

Full QIOS còn thiếu: projection cả task đang chạy/upload, pin source cạnh tranh TX+CPU, delivery connected/disconnected; routing lượng hóa ngoại tác trên mọi queue; trace/verifier độc lập và ablation cùng workload thật. Không nên báo thử nghiệm này là thuật toán joint hoàn thành hoặc cải thiện đã được xác nhận.

Lệnh chạy từ MECSim (output phải mới):

```powershell
mvn -o "-Dtest=QueueImpactSchedulerTest" test
mvn -o compile exec:java "-Dexec.mainClass=uav.scheduling.QueueImpactPilot" "-Dqios.output=target/qios-ready-NEW"
```

Kết quả local: `target/qios-ready-pilot-20261028/episodes.csv` và `REPORT.md`. Thiết kế: [JOINT_OFFLOADING_SCHEDULING_DESIGN.md](JOINT_OFFLOADING_SCHEDULING_DESIGN.md).

Bước tiếp theo: hoàn thiện projection event có upload/running task trước khi nối routing. Giữ SPT là baseline bắt buộc; không chỉnh thuật toán chỉ để thắng30seed batch đã xem.
