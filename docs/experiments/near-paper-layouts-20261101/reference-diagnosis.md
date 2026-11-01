# Phân tích trace hiện có: không chạy lại mô phỏng

Run: target/near-paper-final-20261101; scenario primary; 30 workload seed, layout 42.
Đơn vị đếm là task occurrence (seed, id), không phải ảnh thật độc lập.

| So với ALL_LOCAL | Task occurrences |
|---|---:|
| retained_success | 421 |
| rescued | 37 |
| harmed | 0 |
| failed_both | 274 |

Rescued/harmed là chênh lệch paired của toàn policy: có thể bao gồm ảnh hưởng lên queue và contact sau đó; không chứng minh riêng tác động CPU offload.

| Policy | Phân loại độc quyền | Task occurrences |
|---|---|---:|
| ALL_LOCAL__EDF | delivered_ontime | 421 |
| ALL_LOCAL__EDF | local_intrinsic_compute_exceeds_budget | 246 |
| ALL_LOCAL__EDF | local_ontime_undelivered | 65 |
| ALL_UAV__EDF | delivered_ontime | 458 |
| ALL_UAV__EDF | local_intrinsic_compute_exceeds_budget | 216 |
| ALL_UAV__EDF | local_ontime_undelivered | 46 |
| ALL_UAV__EDF | uav_contact_upload_compute_exceeds_budget | 1 |
| ALL_UAV__EDF | uav_upload_alone_exceeds_budget | 11 |

Phân loại là kiểm tra lower bound thời gian theo route đã thực thi, không khẳng định một nguyên nhân nhân quả duy nhất.
Ảnh local đúng hạn nhưng nguồn disconnected không được tính là giao thành công. Model chưa thu gom kết quả local về sau.

| Năng lượng mean/episode | ALL_LOCAL J | ALL_UAV J | Δ J |
|---|---:|---:|---:|
| flight_j | 159597.049 | 143482.927 | -16114.122 |
| hover_j | 58881.574 | 67475.772 | 8594.199 |
| uav_compute_j | 0.000 | 63.330 | 63.330 |
| uav_tx_j | 0.000 | 0.000 | 0.000 |
| ground_idle_j | 60192.000 | 60192.000 | 0.000 |
| ground_compute_j | 11498.191 | 10778.229 | -719.962 |
| ground_tx_j | 0.000 | 26.398 | 26.398 |
| total_j | 290168.814 | 282018.655 | -8150.158 |

Flight và hover được tách khỏi UAV idle_j trước khi cộng, không cộng hai lần.
Quyết định offload có thể pin stop lâu hơn, làm thay đổi flight/hover; không gọi toàn bộ chênh lệch năng lượng là tiết kiệm compute.
Không cần rerun baseline cũ. Giữ các trace gốc và hashes đầu vào để truy ngược.
