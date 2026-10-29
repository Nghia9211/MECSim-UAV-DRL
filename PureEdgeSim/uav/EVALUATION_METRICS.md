# Quy ước đánh giá offloading + scheduling

Áp dụng từ 29/10/2026 cho các thuật toán mới và baseline trên cùng setting.
Ứng viên đang đánh giá: DELIVERY_AWARE + EDF/RISK_EDF trong mobile mode;
giữ DEADLINE_ENERGY + EDF/RISK_EDF và SHORTEST_FINISH + EDF làm đối chứng.
Không đồng nhất với DQN của paper Azfar.

1. **Image DVR**: 1 − số ảnh hoàn thành đúng hạn / tất cả ảnh được tạo.
   Từ chối, risk-drop, hết pin, hết hạn và chưa xong đều không phải thành công.
2. **J/ảnh đúng hạn**: tổng năng lượng UAV + tất cả thiết bị nguồn / số ảnh đúng hạn.
   Bao gồm hover, idle, compute, TX và năng lượng xử lý background trong mô hình;
   chưa có RX hoặc truyền kết quả về. Không có thành công: NA, không phải 0.
3. **Latency ảnh trung bình và P95**: resolved − arrival, chỉ trên COMPLETED_ON_TIME và
   COMPLETED_LATE; bao gồm chờ, upload, compute. Mô hình hiện chưa có đường truyền kết quả về.
   Không tính thời gian drop thành latency của task hoàn thành. Báo cùng số hoàn thành/DVR.
4. **Lifetime UAV**: thời gian UAV có năng lượng để cung cấp dịch vụ; không phải lifetime
   toàn mạng vì CPU local vẫn có thể chạy khi UAV mất nguồn. Task routing không thể
   tắt hover trong model hiện tại. Nếu sống đến horizon, lifetime chỉ có cận dưới.
   Bảng tự động báo restricted time = min(lifetime, horizon) và số case bị censor.
   Không suy diễn lifetime thực hoặc tuổi thọ liên tục khi workload dừng sinh sau 300s.

Chỉ số hỗ trợ: tổng năng lượng, UAV energy, số ảnh đúng hạn, background DVR, số case
không thành công. Chi phí quyết định chỉ báo nếu có đo; không lấy wall time cả episode
làm thời gian mỗi quyết định.

## Tổng hợp và so sánh

- Chạy cùng seed, workload hash, cấu hình, estimate error và kernel; không so số từ các
  đợt khác seed như một phép so ghép cặp. Tách estimate chính xác và sai số ±40%.
- DVR, latency trung bình và P95: trung bình đều theo episode. P95 là nearest-rank
  từng episode rồi lấy trung bình, không phải percentile gộp toàn bộ task.
- Năng lượng/ảnh: tỷ số tổng năng lượng trên tổng ảnh đúng hạn; báo cả zero-success cases.
- Xuất cả từng load/pin và toàn bộ. Không dùng trung bình gộp để che regression từng setting.
- Với pin lớn nếu mọi case sống hết 600s, ghi >=600s; không xếp hạng lifetime thật.
- Ưu tiên DVR, sau đó năng lượng/ảnh; latency và lifetime đọc kèm. Không tự gộp weighted score.
- Báo cáo hiện tại là mô tả; chưa có kiểm định để khẳng định ý nghĩa thống kê.

## Bắt buộc trong quy trình chạy

Sau mô phỏng phải chạy verifier phù hợp. CLI của `verify-uav-offloading.py` và
`verify-deadline-risk.py` tự động xuất:

- `core-metrics-episodes.csv`: metric mỗi episode.
- `core-metrics-summary.csv`: toàn bộ và từng load/pin.
- `CORE_METRICS.md`: bảng đọc nhanh, định nghĩa và censoring.

Mọi thuật toán fixed-UAV mới phải xuất cùng task/workload/energy trace để dùng bộ này.
Verifier mobile cũng gắn cùng exporter: energy UAV gồm flight+hover+CPU, bổ sung
flight/hover/distance, coverage và offloaded counts. Tách compute DVR và delivered
DVR: xử lý local xong trên source disconnected không được tính là đã chuyển kết quả
về. Báo J/ảnh đúng hạn cho cả compute và delivery. Output/backhaul delay hiện bằng0
khi có đường delivery; không gọi compute latency là độ trễ truyền kết quả thực.
Exporter mobile cũng báo mean/P95 trên các kết quả thực sự delivered (gồm late),
và số case có delivery; case không có delivery không được gán latency0.
Entrypoint mới phải gắn exporter và định nghĩa năng lượng trước khi kết luận.
Không coi một run thiếu bộ metric này là báo cáo hoàn chỉnh.

```text
python scripts/offloading_metrics.py RUN_DIR
python scripts/offloading_metrics.py BASELINE_RUN NEW_RUN --output NEW_COMPARISON_DIR
python scripts/test_offloading_metrics.py
```

Chỉ chạy exporter trên full traces sau independent verification PASS. Bản tải về chỉ
có summary không đủ để tái tính latency hoặc lifetime.
