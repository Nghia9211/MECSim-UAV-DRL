# So sánh baseline với thuật toán hiện tại theo bộ metric thống nhất

Protocol trước khi chạy: 29/10/2026. Không tune theo kết quả.

- Giữ fixed-UAV, RescueNet metadata + Alibaba background, 3 load, 2 pin, horizon 600s.
- Dùng lại 30 seed 94000..94029 và hai estimate error 0/0.4 của run adapted-methods.
- Chạy mới 9 baseline: ALL_LOCAL+FIFO; ALL_UAV+FIFO/EDF/SPT;
  SHORTEST_FINISH+EDF; DEADLINE_ENERGY+FIFO/EDF/SPT/PRIORITY.
- 3240 episode mới; ghép với 2880 episode cơ chế mới đã được audit. Duplicate
  DEADLINE_ENERGY+EDF/SPT phải trùng metric từng case trước khi gộp, không tính hai lần.
- Ứng viên mới nhất chính: DEADLINE_ENERGY+RISK_EDF. Giữ RISK_SPT và TRANSFER_AWARE
  trong bảng để nhìn ablation và kết quả âm.
- Metric và censoring theo EVALUATION_METRICS.md; không suy diễn lifetime từ năng lượng.
- Java tests, independent audit và adversarial verifier tests phải PASS.
- Chỉ ghép khi workload hashes, case sets, estimate error và shared kernel hashes khớp.
- Đọc cả từng load/pin; average 600s-survivor là restricted lifetime, không lifetime thật.
- Không DQN/MARL training; không kết luận tái hiện paper hoặc kiểm định thống kê.

Runner: `scripts/run-core-metrics-comparison-server.sh` với `OUT_DIR` mới dưới target.
Các verifier chuẩn đã tự xuất core metrics để các run sau tiếp tục dùng cùng quy ước.
