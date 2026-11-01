# Hiệu chuẩn compute/deadline — 01/11/2026

**Đã đo runtime kiến trúc trên workstation và kiểm chứng tích hợp; còn provisional.**
Chưa có checkpoint RescueNet đã train, số đo Pi/Jetson, điện năng hay SLA ứng dụng.
Người dùng đã chọn dùng laptop/server hiện có và deadline theo kịch bản/sensitivity.

## Phép đo

DeepLabV3–MobileNetV3-Large (Torchvision), 11 lớp, FP32, batch 1, resize 512×512.
Trọng số ngẫu nhiên seed cố định, không đo accuracy. CPU AMD Family 25 Model 80 trên
Windows; Torch 2.9.1+cu126/Torchvision 0.24.1+cu126; intra-op 1, inter-op 8, không CUDA.
60 ảnh chọn bằng hash tên file × 3 repeats; warmup 10. Đây là 180 timing rows trên
60 ảnh, không phải 180 ảnh độc lập hay source holdout.

| Thành phần | Mean (s) | P95 (s) |
|---|---:|---:|
| Đọc/decode/resize/normalize | 0,136398 | 0,173833 |
| Transfer | 0,000015 | 0,000024 |
| Forward | 0,321721 | 0,401591 |
| Argmax/tạo mask CPU | 0,066212 | 0,081085 |
| Tổng | **0,524349** | **0,640962** |

Không gồm queue, flight, encode mask, result relay hoặc đo điện năng. Hash ngoài timing;
file có thể nằm trong OS cache. P95 nearest rank trên 180 repeats, không cộng P95
từng thành phần; chưa có nhiều phiên đo/CI/kiểm soát thermal.

## Compute mới, chỉ bật khi khai báo

Cũ dùng độ phân giải ảnh gốc × MI/megapixel: ảnh 4000×3000 có 10.000 MI,
local 20 s và UAV 5 s. Đây là giả định, không phải thời gian segmentation đo được.

Với input model cố định 512×512, thêm **imageFixedMi**, không tăng inference cost
theo pixel ảnh gốc. Decode/preprocess được xấp xỉ bằng mean; variance được báo cáo
nhưng chưa phát lại thành phân phối compute. Không dùng semantic label để đặt compute.

Đặt reference rate R=1000 work units/s:
imageFixedMi=R×mean(T_local)=524,349422;
localMips=R; uavMips=imageFixedMi/mean(T_uav).
MI ở đây là đơn vị công việc chuẩn hóa, không phải machine instructions thực đo,
không đổi GFLOPs thành MI. Tỷ số work/rate giữ đúng thời gian đo.

Chỉ có một profile: **shared-hardware**, local/UAV cùng 1000 unit/s, cùng 0,524349 s/ảnh.
Đây là hai vai trò mô phỏng, không phải hai thiết bị đã đo và không khẳng định UAV
nhanh hơn local. Khi có hai profile cùng model/checkpoint/input panel, dùng ratio runtime thực.

## Deadline là kịch bản, chưa phải SLA

Deadline tuyệt đối = arrival + ngân sách. Không suy ra yêu cầu cứu hộ từ inference time.

| Kịch bản | Khẩn cấp | Thường | Background |
|---|---:|---:|---:|
| tight | 10 s | 30 s | 120 s |
| reference | 20 s | 60 s | 120 s |
| relaxed | 40 s | 120 s | 120 s |

Đây là 0,5×/1×/2× ngân sách ảnh cũ; background giữ nguyên để tách yếu tố.
Priority vẫn theo protocol, không theo semantic mask; không điều chỉnh theo policy thắng/thua.

## Input-only feasibility

60 case development, 2.929 image task:
ở cả ba deadline, 0 ảnh bất khả thi khi CPU local cô lập;
0 ảnh bất khả thi khi upload 10 m + CPU UAV cô lập;
**2.929/2.929 ảnh bất khả thi ở 65 m** theo radio hiện tại dù bỏ qua queue/flight.

Đây là cận lạc quan từng task, không phải algorithm DVR hay chứng minh khả thi
đồng thời. Bỏ qua queue, contact, pin, contention, result-return; local disconnected
không giao được kết quả dù compute kịp.

Image offered utilization nếu toàn bộ lên UAV: 0,042 (light), 0,126 (nhãn cũ overload).
Cộng background proxy: khoảng 0,158/0,823. Tên overload không còn chứng nhận tải >1.
Background vẫn có 1/174 và 8/850 task vượt riêng compute budget 120 s; chưa lọc bỏ chúng.

Radio có thể đang chi phối benchmark; cần tách contact/placement/CPU-load trước khi
kết luận scheduling. Constant image compute cũng không tạo lợi thế SPT chỉ từ độ dài ảnh.
Không tạo dị thể task giả hoặc đổi arrival rate để làm một thuật toán thắng.

## Artifact và cách dùng

Bằng chứng gọn: [docs/calibration/workstation-cpu-20261101](../../docs/calibration/workstation-cpu-20261101/README.md).
Có profile/CSV gốc, calibration receipt và ba config/protocol; không có raw ảnh/checkpoint.

~~~powershell
.\.venv-drl\Scripts\python.exe scripts/profile-image-inference.py --images datasets/raw/rescuenet/validation/val-org-img --output target/profile-new --device cpu --limit 60 --repeats 3 --warmup 10 --threads 1 --timing-only
.\.venv-drl\Scripts\python.exe -m drl.task_calibration --local target/profile-new --shared-hardware --workloads target/workload-v2-inputs-20261030 --output target/calibration-new
~~~

Model thực: thay --timing-only bằng --checkpoint PATH, state_dict tương thích đúng
kiến trúc 11 lớp. Script không tải/train model. Hai máy: dùng --local DIR_LOCAL
--uav DIR_UAV thay --shared-hardware, cùng checkpoint/preprocessing/panel ảnh.
Minimum 30 ảnh × 3 repeats và warmup >=5 chỉ là kiểm tra input, chưa chứng nhận thống kê.

~~~python
import json
from pathlib import Path
from drl.mobile_environment import MobileConfig
settings = json.loads(Path("docs/calibration/workstation-cpu-20261101/mobile-config-reference.json").read_text())
cfg = MobileConfig(**settings, allowContactWait=True)
# Truyền cfg vào MobileEnv/ContactEnv; controller/policy chọn riêng.
~~~

~~~powershell
mvn -o exec:java -Dexec.mainClass=uav.offloading.WorkloadExport -Dworkload.protocol=docs/calibration/workstation-cpu-20261101/mobile-protocol-reference.json -Dworkload.output=target/calibrated-inputs-new
.\.venv-drl\Scripts\python.exe scripts/audit-workload-export.py target/calibrated-inputs-new
~~~

Output phải mới. Entrypoint drl.workload_baselines vẫn dùng cost/expected hashes cũ;
không chạy nó rồi gọi là benchmark đã hiệu chuẩn. Campaign mới phải nhận config,
snapshot calibration ID, audit và xuất đủ metric. Chưa train policy hoặc chạy lại
campaign 4.320 episode. Input-only export cả ba partition; chưa đánh giá algorithm
trên validation/evaluation.

## Verify và phần còn thiếu

134 Java tests, 67 Python tests bật dataset thật đều PASS, không skip.
Sau bổ sung provenance guard: 7 test bị ảnh hưởng chạy lại PASS.
180 case / 11.868 task được Python độc lập dựng lại từ Java export; các trường
ngoài actual/estimated work giữ nguyên so với input cũ ở reference deadline.
Integration chạy Java thật và audit trace; test âm phát hiện sửa cost/profile/calibration ID.

Còn thiếu: checkpoint vision đã train + accuracy; nhiều phiên đo/thiết bị thật nếu
muốn dị thể; power/energy; SLA nghiệp vụ; radio/delivery/load review.
Alibaba duration×requested CPU×reference rate vẫn là proxy, chưa hiệu chuẩn CPU-time,
DAG/multi-instance hoặc sampling đại diện. Giữ power model và benchmark cũ để đối chiếu;
chưa gọi toàn bộ dataset workload là đã hiệu chuẩn.
