# Chẩn đoán và ablation admission background

Thứ tự: phân tích trace cũ → chốt cơ chế từ nguyên nhân → test/smoke → full hover → review → mobile.
Development evidence; chưa claim novelty, SOTA, calibrated real-world energy hoặc global schedulability.

## 1. Chẩn đoán từ dữ liệu trước can thiệp

Ở hover/EDF: 2.627 ảnh trễ đều có overlap với background CPU;94,9% tổng thời gian overlap đó là background đã chạy trước khi ảnh sinh.
Đây là observed blocking, không phải counterfactual rescue. Cannot anticipate a future task từ trace.
Ở mobile RR/ALL_UAV/EDF: 2.600 local on-time disconnected;790 upload-compute intrinsic misses;42 contact-wait intrinsic;104 CPU misses.
Các loại failure này theo hierarchy loại trừ nhau. No-contact flag là chiều chồng lấp, không cộng thêm vào tổng.

## 2. Cơ chế thử và ablation

BG_CAP_EDF: tại idle dispatch, từ chối background có estimated compute time > B, rồi EDF các task còn lại.
B = critical image deadline − max frozen JPEG upload ở10m − reference image compute.
Max JPEG10.658851MB; upload4,2635404s; reference compute0,5243494s.
B theo tight/reference/relaxed = khoảng5,2121/15,2121/35,2121s. Không tuning từ score và không xem future task arrivals.
RISK_EDF chỉ drop task đã không thể kịp deadline theo estimate; RISK_SPT là baseline khác.
RISK_BG_CAP_EDF kết hợp risk+cap; PRIORITY kiểm tra chỉ ưu tiên ảnh thay vì admission.
Cap là admission/rejection, không phải chỉ đổi thứ tự; background bị từ chối vẫn là failure và work không được coi completed.
B chỉ là ngân sách isolated reference10m; không bảo đảm link xa, queue ảnh, estimate error hoặc contact wait.
Non-preemptive, không migration, không tạo compute giả; radio/geometry/payload/power không thay để tạo chiến thắng.

## hover: 2160 verified episodes

| Policy | Image DVR % | Delivered DVR % | J/ảnh ontime | J/ảnh delivered | Background DVR % | Mean/P95 image s |
|---|---:|---:|---:|---:|---:|---:|
| ALL_UAV__BG_CAP_EDF | 0.000 | NA | 725.076 | NA | 7.237 | 3.356/7.245 |
| ALL_UAV__EDF | 10.192 | NA | 827.873 | NA | 6.914 | 5.812/17.869 |
| ALL_UAV__PRIORITY | 10.073 | NA | 826.699 | NA | 7.025 | 5.446/17.439 |
| ALL_UAV__RISK_BG_CAP_EDF | 0.000 | NA | 725.076 | NA | 7.237 | 3.356/7.245 |
| ALL_UAV__RISK_EDF | 2.346 | NA | 751.146 | NA | 0.986 | 4.895/15.546 |
| ALL_UAV__RISK_SPT | 2.483 | NA | 752.178 | NA | 0.986 | 4.664/14.633 |

Không so trực tiếp trị số gộp hover với mobile: khác tập scenario và routing/contact.
Read per-scenario tables. Macro DVR/latency; ratio-of-sums J/ảnh. Completed-only latency không gồm drop.
CI ghép cặp theo seed; bảng ALL lấy mean các scenario trong seed trước bootstrap, không coi120/360case là120/360seed độc lập.

| Policy | Background offered | Cap rejected | Risk rejected | Background work executed % |
|---|---:|---:|---:|---:|
| ALL_UAV__BG_CAP_EDF | 7647 | 573 | 0 | 33.16 |
| ALL_UAV__EDF | 7647 | 0 | 0 | 86.25 |
| ALL_UAV__PRIORITY | 7647 | 0 | 0 | 86.14 |
| ALL_UAV__RISK_BG_CAP_EDF | 7647 | 498 | 75 | 33.16 |
| ALL_UAV__RISK_EDF | 7647 | 0 | 84 | 53.99 |
| ALL_UAV__RISK_SPT | 7647 | 0 | 84 | 53.99 |

## Đánh giá và giới hạn

Không chọn cap làm phương pháp cuối chỉ vì image DVR tốt: phải đọc background DVR và phần CPU work bị từ chối.
RISK_EDF là baseline mạnh sẵn có; không gọi chênh lệch từ EDF là đóng góp mới.
Đây là kiểm chứng cơ chế có đánh đổi, chưa là novel scheduling algorithm. Muốn novelty phải literature review và cơ chế mới có cơ sở.
Không sửa threshold sau khi nhìn holdout. Chỉ mở validation/evaluation sau khóa protocol/candidates/metrics bằng hash.
Chưa train RL; CPU model còn random-weight architecture timing, power/deadline giả định, Alibaba duration/requestedCPU proxy.
Nguồn raw và source snapshots được giữ tại target. Smoke không gộp vào cỡ mẫu full.
UAV sống hết600s phải báo >=600s/censored, không kết luận lifetime tăng.

