# Diễn giải bổ sung sau campaign

Phân tích mô tả từ trace đã verified, không chạy thêm simulator, không phải protocol chọn thuật toán mới.

| Candidate vs ALL_LOCAL | Retained success | Rescued | Harmed | Failed both |
|---|---:|---:|---:|---:|
| ALL_UAV__EDF | 2766 | 415 | 34 | 4105 |
| SHORTEST_FINISH__EDF | 2800 | 422 | 0 | 4098 |
| DEADLINE_ENERGY__EDF | 2800 | 451 | 0 | 4069 |
| DELIVERY_AWARE__EDF | 2800 | 451 | 0 | 4069 |

## Khi nào ALL_UAV gây hại?

- uav_contact_upload_compute_exceeds_budget: 2 task occurrences.
- uav_upload_alone_exceeds_budget: 32 task occurrences.

Harmed = cùng task đã được ALL_LOCAL giao đúng hạn nhưng candidate không giao đúng hạn. Rescued là chiều ngược lại.
Không phải cùng ảnh thật được quan sát 10 lần độc lập: đây là cùng workload trên 10 môi trường khác nhau.
Nhóm nguyên nhân dùng lower-bound thời gian thực theo route, không khẳng định nguyên nhân nhân quả duy nhất.

## Phân rã năng lượng của ALL_LOCAL và ALL_UAV

| Mean/episode | ALL_LOCAL J | ALL_UAV J | Δ J |
|---|---:|---:|---:|
| flight_j | 160162.968 | 149880.153 | -10282.815 |
| hover_j | 58579.750 | 64063.918 | 5484.168 |
| uav_compute_j | 0.000 | 67.799 | 67.799 |
| ground_idle_j | 58152.600 | 58152.600 | 0.000 |
| ground_compute_j | 15510.469 | 14438.789 | -1071.680 |
| ground_tx_j | 0.000 | 20.286 | 20.286 |
| total_j | 292405.788 | 286623.546 | -5782.242 |

Flight/hover là thay thế cho UAV idle_j khi phân rã, không cộng hai lần.
Hiệu quả năng lượng gồm thay đổi thời gian dừng/đường bay; chưa tách isolated compute effect.

## Quyết định bước tiếp

Có bằng chứng robustness của việc cho phép offloading so với chỉ local trong các môi trường đã lấy mẫu.
Tuy nhiên ALL_UAV không phải cơ chế tốt nhất ở mọi chỉ tiêu; cần so với baseline có deadline/energy trước khi tuyên bố cải tiến.
DEADLINE_ENERGY và DELIVERY_AWARE có cùng core metrics ở campaign này; không xem đó là hai bằng chứng độc lập.
Kiểm tra sensitivity CPU/deadline/dwell trước, giữ scheduler EDF. Không coi kiểm tra deadline upload đơn giản là novelty: baseline hiện có đã dùng dự đoán finish/feasibility.
Chưa train DQN, chưa làm cache, chưa có inference RescueNet. Chưa suy ra tăng lifetime khi mọi UAV còn sống đến horizon.
