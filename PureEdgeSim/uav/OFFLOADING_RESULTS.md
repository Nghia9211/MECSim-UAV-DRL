# Kết quả kiểm chứng offloading + scheduling — 22/10/2026

Đã chạy implementation và raw RescueNet + Alibaba trên máy local. Đây là
**benchmark development với giả định chi phí**, không phải kết quả inference
thực, SOTA hoặc reproduce paper Azfar. Mô hình và lệnh chạy:
[OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md).

## 1. Những gì đã thực hiện

| Công việc | Bằng chứng |
| --- | --- |
| Regression Java | **84 tests đạt**, gồm 20 test mới cho local/offloading |
| Regression nhánh paper/DRL cũ | **17 Python integration tests đạt**, bật kiểm tra raw dataset |
| Kiểm tra verifier | **7 test đạt**: trace gốc, sửa work/energy/forecast/route, hand-case EDF/SPT, ẩn actual MI/future khỏi forecast |
| Run chính | 30 seed 41000–41029 × 3 tải × 2 pin UAV × 4 offloading × 5 scheduler = **3.600 episode** |
| Run noise | 5 seed 41000–41004, estimate sai số uniform ±40%, cùng grid = **600 episode** |
| Independent trace audit | **238.200 + 40.280 = 278.480 task outcomes đạt kiểm chứng** |

Run chính: [offloading-verified-20261022](../../target/offloading-verified-20261022/).
Run noise: [offloading-noise40-20261022](../../target/offloading-noise40-20261022/).
Log: [Java tests](../../target/offloading-tests-20261022.log),
[Python regression](../../target/offloading-python-regression-20261022.log).

Verifier độc lập kiểm tra work/energy/pin mọi node, upload một phần, CPU không
overlap/idle giả, dispatch theo scheduler, forecast causal chỉ dùng estimated
MI, lựa chọn route, source mapping, offered denominator và per-source summary.

Các negative checks bổ sung trên bản sao artifact đều bị từ chối: sửa source
hash, workload hash hoặc summary on-time. Source snapshot của hai run khớp code
hiện tại. Với các seed chung của run noise, **2.014 input rows** giữ nguyên mọi
field actual và device assignment, chỉ estimate thay đổi; số này gồm hai cấu
hình pin lặp cùng workload. Xem [extra-checks.json](../../target/offloading-verified-20261022/extra-checks.json).

Test Java xác nhận riêng:

- Local bỏ qua upload, FIFO local và nhiều CPU chạy song song.
- Task nền làm thay đổi lựa chọn local/UAV.
- Đổi FIFO→EDF có thể thay đổi forecast, route và khả năng kịp deadline.
- Hoàn thành đúng deadline/pin boundary; task chạy trễ khác task chờ expired.
- UAV chết không dừng local; source chết không xóa task đã upload xong.
- CPU local và nhiều upload chia cùng pin, dừng tại cùng thời điểm cạn pin.
- Estimated MI không thay actual execution; horizon giữ đúng remaining work.
- ALL_UAV với pin source đủ khớp kernel scheduling trước về outcome/energy UAV.

Đây không phải 3.600 mẫu độc lập: run chính có 30 task-seed clusters, 180
scenario/seed cases, 90 offered workloads khác nhau do hai mức pin dùng cùng
input. Source pool và vị trí được cố định. Noise dùng lại 5 seed đầu, không
phải một tập test độc lập mới. Chưa tính CI/kiểm định xác nhận cho nghiên cứu này.

## 2. Ví dụ kết quả: tải cao, scheduler EDF cố định

Mean theo 30 seed trong từng cấu hình, không phải pooled DVR. Energy gồm cả
UAV và các thiết bị mặt đất, tính trong cùng horizon 600 s hoặc tới khi node
hết pin. Background là task Alibaba mô phỏng tại CPU UAV.

### Pin UAV 1.600.000 J

| Offloading | Image DVR | Background DVR | Mean total energy | Completed image latency |
| --- | ---: | ---: | ---: | ---: |
| ALL_LOCAL | 44,70% | 5,43% | 55.022,0 J | 43,04 s |
| ALL_UAV | 45,34% | 36,60% | 56.881,8 J | 38,00 s |
| SHORTEST_FINISH | **2,73%** | 10,41% | 57.910,7 J | 20,49 s |
| DEADLINE_ENERGY | 4,84% | 5,53% | 56.759,4 J | 28,87 s |

Kết hợp hai nơi xử lý giảm image miss rõ trong cấu hình development này.
SHORTEST_FINISH có image DVR thấp hơn DEADLINE_ENERGY, nhưng background DVR
và total J cao hơn. DEADLINE_ENERGY thấp hơn ALL_UAV về ba chỉ số DVR ảnh,
DVR background và total J ở cấu hình này, **nhưng không thấp hơn ALL_LOCAL về
total J**. Latency ở bảng chỉ tính task đã hoàn thành, phải đọc cùng DVR.

### Pin UAV 30.000 J

| Offloading | Image DVR | Background DVR | Mean total energy |
| --- | ---: | ---: | ---: |
| ALL_LOCAL | 44,70% | **5,74%** | 34.677,0 J |
| ALL_UAV | 50,08% | 61,37% | **31.215,9 J** |
| SHORTEST_FINISH | 5,63% | 35,37% | 32.744,3 J |
| DEADLINE_ENERGY | **4,97%** | 9,26% | 34.384,5 J |

ALL_UAV có total energy nhỏ nhất nhưng bỏ lỡ nhiều công việc: **đó không phải
bằng chứng sử dụng năng lượng tốt nhất**. Node hết pin sớm ngừng tiêu thụ và
không phục vụ được task sau đó. Cần đánh giá năng lượng cùng mức dịch vụ.

Nguồn số liệu: [summary.csv](../../target/offloading-verified-20261022/summary.csv).
Toàn bộ 20 cặp policy ở [REPORT.md](../../target/offloading-verified-20261022/REPORT.md).
Không lấy một cấu hình thuận lợi để kết luận thắng toàn bộ benchmark.

## 3. Vai trò của scheduler đã thực sự được nối vào offloading

Ví dụ cùng DEADLINE_ENERGY, overload, pin UAV 1.600.000 J:

| Scheduler UAV | Mean image DVR |
| --- | ---: |
| FIFO | 6,86% |
| EDF | 4,84% |
| PRIORITY | 4,79% |
| SPT | 5,53% |
| FEASIBLE_AGING | 4,55% |

Scheduler thay thứ tự CPU và forecast dùng khi route, nên đây không còn là một
biến tên không ảnh hưởng execution. Tuy nhiên bảng này gồm tác động qua cả
route và dispatch; muốn tách riêng cần một ablation đóng băng routing/đổi
scheduler. Không đủ để khẳng định aging hoặc tổ hợp này có novelty.

## 4. Noise pilot chứng minh điều gì?

Pilot ±40% đã qua replay độc lập cho **600 episode / 40.280 outcomes**. Nó xác
nhận execution theo actual work và policy theo estimate vẫn giữ conservation,
deadline và offered counts; **không chứng minh policy robust** trước mọi sai số.

Không so trung bình noise 5 seed trực tiếp với run chính 30 seed để quy mọi
khác biệt cho noise. Muốn phân tích ảnh hưởng phải lọc đúng 5 seed chung hoặc
chạy đủ 30 seed, rồi dùng paired differences. Chưa khảo sát systematic bias,
correlated errors, source holdout hoặc profiler inference.

## 5. Giới hạn và bước tiếp theo

- CPU/power/deadline/link/source assignment chưa được hiệu chuẩn; model ảnh
  gần đồng nhất về MI do độ phân giải gần nhau. Không có semantic urgency từ mask.
- Source battery depletion đã kiểm tra bằng fixtures; pin source 5.000 J trong
  grid này chưa thay thế sensitivity về nhiều ngân sách pin thiết bị.
- Radio độc lập full-bandwidth, không contention; return/RX bỏ qua; UAV đứng
  cố định. Không suy ra performance khi UAV di chuyển hoặc ngoài coverage.
- Queue forecast không biết future arrivals và dùng point estimate. Khi task
  chạy quá estimate, remaining estimate được clamp dương nhỏ, có thể lạc quan.
- Chưa có objective cuối/background SLA, SOTA, scalability hoặc confirmatory
  statistics. Routing có replay O(Q²) worst-case mỗi quyết định, cần đo khi queue lớn.

Tiếp theo nên chốt objective/background service requirement, profile cost local
và UAV, rồi thiết kế ablation và cơ chế cải tiến trên mô hình đã có. Không cần
tải thêm dataset hoặc train lại DQN lifetime chỉ để sử dụng nền tảng này.
