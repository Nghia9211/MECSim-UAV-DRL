# Thử hướng scheduling đơn giản sau PPO/DQN

Ngày2026-10-30. Mục tiêu: tìm cải thiện thực nghiệm với thay đổi thuật toán nhỏ, không thêm
framework, state, reward, mạng neural hay training. Đây là so sánh thêm các phương pháp
đã có trong codebase; không phải đóng góp thuật toán mới.

PPO143D gần như bằng DELIVERY_AWARE cố định về delivered DVR; chưa vượt RISK_EDF về J/ảnh.
Thử đổi nguyên tắc xếp hàng trước khi tiếp tục RL:

1. RISK_SPT: loại task ước lượng không thể kịp deadline ngay cả khi chạy ngay; sau đó chọn
   estimated remaining work nhỏ nhất. Có thể giúp tránh task dài chặn nhiều task ngắn.
2. FEASIBLE_AGING: chọn task có deadline/energy khả thi, tính score từ priority, estimated
   duration và relative slack; task đã chờ75% budget được ưu tiên bằng deadline. Khi không
   có task khả thi thì chọn task ngắn, không phải từ chối toàn bộ. Đây là heuristic hiện có.

Mỗi scheduler ghép DELIVERY_AWARE và DEADLINE_ENERGY:4 cặp bổ sung. Giữ9 cặp contact-wait
cũ, gồm DELIVERY_AWARE/RISK_EDF làm đối chứng mạnh.13 policies x8 scenarios x30 seeds x2
estimate-error =6.240 episodes, first seed95000. Cùng RR service-selection rule; thời điểm
rời stop vẫn phụ thuộc upload pinning. Giữ nguyên CPU, pin, topology, workload và contact
waiting. Không thay đổi physics để tạo lợi thế cho thuật toán.

Source protocol: `offloading/simple-scheduling-protocol.json`. Seeds/layout dùng lại từ
contact-wait campaign: development comparison, không phải fresh holdout. Không đối chiếu
trực tiếp số ALL với đợt RL seed2800000 vì workload seed khác; các baseline được chạy lại
trong cùng run. Không train vision model; RescueNet+Alibaba vẫn là mapper workload hiện có.

Kiểm chứng: independent mobile audit, adversarial physical/risk/delivery/contact-wait tests,
source snapshots, paired workload hashes, exit0 + completion marker + COMPLETE/PASS.
Dùng scripts/offloading_metrics.py để xuất compute/delivered DVR, whole-system J/on-time
image và delivered image, completed/delivered latency mean/P95, UAV battery service time
với censoring, UAV/total energy, background DVR và số delivered on-time. Giữ per-scenario.
Zero successes là efficiency NA; sống qua600s là lifetime>=600, không phải hết pin600s.

Không có bảo đảm SPT tốt hơn EDF với deadlines/arrivals/energy. Không có claim tối ưu hoặc
mới. Nếu cả4 cặp không hơn RISK_EDF: dừng mở rộng scheduler này, phân tích mức contention
và giới hạn contact/delivery trước khi đầu tư phương pháp phức tạp hơn. Kết luận tốt hơn
phải xét tradeoff DVR, energy, latency và background, không chọn riêng metric thuận lợi.

Tham khảo ý tưởng shortest-job scheduling: Carnegie Mellon,
https://www.cs.cmu.edu/~garth/15719/lectures/719-s17-proj3-intro.pdf

Run server: target/simple-scheduling-20261030-v1-e0 và -e40.
Control: target/simple-scheduling-control-20261030-v1.
Tmux: uav-simple-scheduling-20261030-v1. Định danh run không phải bằng chứng COMPLETE.
