# QIOS: projection và routing đã nối, kết quả pilot đầu

Ngày thực hiện: 28/10/2026. Trạng thái local; chưa push hoặc train server. Đây là prototype nghiên cứu, chưa có claim novelty hoặc ưu thế.

## Phần đã bổ sung

- `KnownQueueProjection`: event projection riêng, snapshot immutable của node và task đã admit. Không tạo simulation entity hoặc chạy lồng kernel. Chỉ dùng estimated remaining work, không đọc actual MI/FUTURE.
- Tính task đang chạy không preempt, upload chưa xong, queue chờ, expiry, horizon và cạn pin. CPU local và upload cạnh tranh cùng pin source; task upload xong sống tiếp khi source chết. Hoàn thành đúng timestamp thắng tie với expiry/depletion.
- Scheduler QIOS ở dispatch UAV thử từng first-action với EDF tail, trên **full admitted snapshot** gồm cả upload/local. Routing thử local/UAV với chính scheduler QIOS; không recursion vô hạn vì tail trong mỗi lookahead là EDF.
- Routing so tổng weighted on-time service, rồi total incremental energy trên cùng horizon, rồi latency và stable tie. Priority ảnh là trọng số; background weight1. Không reject task, không đổi quy tắc late/drop của kernel.
- Lưu snapshot và predicted outcomes/score cho cả hai route, cùng route được chọn. Baseline cũ giữ nguyên; verifier cũ mặc định vẫn kiểm tra đầy đủ. Verifier QIOS dùng physical audit chung và tự kiểm tra lại routing/scheduling bằng Python độc lập.

## Phạm vi được hỗ trợ

**UAV cố định, các source có kết nối đầu ra như benchmark offloading cũ.** Kernel chủ động từ chối full QIOS trong mobile thay vì dự báo sai chuyển động tương lai. Projection có trường connected và test local disconnected, nhưng chưa tích hợp mobile/relay/retry. Không gọi đây là bản mobile đầy đủ.

Projection chỉ thấy arrivals đã xảy ra. Nó không dự đoán future arrivals; vì vậy tiết kiệm pin cho queue hiện tại có thể làm dịch vụ tương lai kém đi. Không có bảo đảm optimality, fairness hoặc deadline khi estimate sai.

## Verification

- Toàn bộ **117 Java tests đạt**, gồm3 test ready-scheduler và5 test projection/integration mới.
- Kiểm tra projector với kernel: đang có running job và upload, pin source CPU/TX dùng chung, upload hoàn thành cùng lúc source chết, local disconnected không delivered, loại FUTURE khỏi snapshot.
- **72 episode,4.176 task,744 routing counterfactual audits và4.153 dispatch actions** qua verifier Python độc lập.
- Verifier tái dựng admitted snapshot từ task/decision/energy trace; không chỉ tin snapshot Java đã ghi. Tái tính full projection, chọn route, dispatch và kết quả score. Kiểm tra work/energy conservation, deadlines, non-overlapping CPU và upload duration.
- **8 test verifier QIOS đạt**, gồm trace gốc và các lỗi cố ý: score, energy, pin, route, ready time, estimated MI và bỏ air projection. Không sửa file kết quả trong các test.
- **7 test corruption verifier offloading cũ đạt** sau thay đổi API verifier. Không dùng tùy chọn physics-only để gọi toàn bộ policy checks là PASS; script QIOS thực hiện phần checks còn lại riêng.
- Lưu source Java snapshot/checksum và metadata pool; task-to-pool generation chưa được reconstruct độc lập trong verifier QIOS. Đây là giới hạn verification cần bổ sung trước campaign xác nhận.

## Pilot dữ liệu thật

3 development seeds91000–91002 ×3 mức tải ×2 mức pin ×4policy =72episode. Dùng generator RescueNet/Alibaba hiện tại, same workload hash mỗi case, estimate=actual, horizon600s, local4node500MIPS, UAV2000MIPS; các cost/deadline vẫn là giả định.

| Cặp policy | Image DVR, mean | Background DVR, mean | Weighted service, mean | Tổng năng lượng, mean |
| --- | ---: | ---: | ---: | ---: |
| DEADLINE_ENERGY + EDF | 0,00% | 0,65% | 108,11 | 43,18kJ |
| DEADLINE_ENERGY + SPT | 0,14% | 0,33% | 107,89 | 43,17kJ |
| DEADLINE_ENERGY + QIOS | 0,00% | 0,33% | **108,22** | 43,18kJ |
| QIOS routing + QIOS scheduler | 1,25% | 1,73% | 105,22 | **42,33kJ** |

Macro-average18case; không phải CI, không coi các task là mẫu độc lập. Weighted service là tổng điểm trong episode, không phải tỷ lệ. Với fixed-hover connected setting này, on-time compute tương đương on-time delivery; không suy sang mobile disconnected.

**Full QIOS chưa cải thiện working objective.** Năng lượng giảm đi kèm dịch vụ giảm nên không gọi là thuật toán tốt hơn. Chỉ3seed và một hardware/layout; một số đối chứng gần0DVR nên mức tải hiện tại chưa tạo nhiều khoảng cải thiện. Không tự tăng tải hoặc chỉnh rho sau khi thấy test để làm QIOS thắng.

DEADLINE_ENERGY+QIOS dùng full-context QIOS ở actual dispatch, nhưng candidate-only forecast của DEADLINE_ENERGY vẫn dùng contract ready-only cũ. Đây là ablation triển khai, không phải cùng full forecast như QIOS routing. Phải giữ khác biệt này rõ khi giải thích kết quả.

Chi phí episode QIOS đầy đủ cao hơn baseline; xem `wall_ms` trong CSV. Đó là thời gian toàn episode, bao gồm projection lặp và kernel, không phải latency ngoài thực địa hoặc policy p95. Chưa benchmark runtime ổn định nhiều lượt.

## Chạy lại

Từ thư mục MECSim, chọn output mới:

```powershell
mvn -o test
mvn -o compile exec:java "-Dexec.mainClass=uav.offloading.QueueImpactBenchmark" "-Dqios.output=target/qios-NEW" "-Dqios.seeds=3"
python scripts/verify-qios.py target/qios-NEW
python scripts/test-qios-verifier.py target/qios-NEW
```

Artifact đã verify: `target/qios-joint-pilot-20261028-v3/` gồm episodes.csv, REPORT.md, manifest.json, verification.json và trace. Lượt v1 dừng vì serializer record của Jackson cũ; v2 chạy và verify cơ học; v3 bổ sung source snapshot. Dùng v3 làm kết quả hiện tại, không gộp các lần chạy lại thành thêm mẫu.

## Bước tiếp theo

Phân tích paired case full routing mất service: candidate và queue nào bị ảnh hưởng, route nào khác baseline, forecast so thực tế khi có arrival mới. Chỉ sau đó chọn một giả thuyết thay đổi (ví dụ reserve capacity hoặc penalty forecast uncertainty), viết protocol validation trước khi chạy. Cần robustness estimate error, zero-background, nhiều cấu hình và runtime profiling trước kết luận khoa học.

Thiết kế gốc: [JOINT_OFFLOADING_SCHEDULING_DESIGN.md](JOINT_OFFLOADING_SCHEDULING_DESIGN.md). Pilot ready-only lịch sử: [QIOS_PILOT_RESULTS.md](QIOS_PILOT_RESULTS.md).
