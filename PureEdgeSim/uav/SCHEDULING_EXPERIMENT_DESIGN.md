# Thiết kế thí nghiệm offloading + scheduling sau audit radio

Ngày 01/11/2026. **Thiết kế ban đầu; đã thực thi một phần theo trình tự được yêu cầu.**

Đã hoàn tất1440episode hover, đánh giá rồi mới chạy1200episode mobile; đọc
[SEQUENTIAL_STUDY_RESULTS.md](SEQUENTIAL_STUDY_RESULTS.md) để biết protocol/phạm vi thực chạy.
Các mục mở rộng khác bên dưới vẫn là đề xuất, không phải đã được đánh giá.
Dựa trên [radio audit](RADIO_UPLOAD_AUDIT.md) và [compute calibration sơ bộ](TASK_CALIBRATION.md).
Không gọi script benchmark cũ là đã dùng các setting mới dưới đây.

## Câu hỏi cần trả lời riêng

RQ-S: Khi workload, service geometry và offloading giữ nguyên, thứ tự CPU UAV có giảm
image deadline violation và năng lượng hệ thống trên mỗi ảnh giao đúng hạn không?

RQ-O: Khi scheduler và service geometry giữ nguyên, quyết định local/UAV có cải thiện
các chỉ số đó không?

RQ-M: Khi offloading/scheduler giữ nguyên, thay cách UAV phục vụ có cải thiện hơn đối
chứng hover cố định hoặc tuyến cố định không?

Không gộp ba loại can thiệp thành “scheduler mới” và không dùng reward RL làm bằng
chứng cải thiện objective. Cache chưa cần trong giai đoạn này.

## Giai đoạn A — đối chứng CPU/queue có kiểm soát

Mục đích: tránh mọi failure bị quyết định trước bởi radio/flight.

- UAV hover cố định, link tham chiếu d=10 m, rate default 20 Mbit/s; upload nguyên JPEG.
  Đây là queue-control abstraction, không phải layout disaster 800 m.
  Dùng fixed-UAV kernel/ready times; mọi policy cùng có cùng upload-ready timestamps.
- ALL_UAV với mọi image; background ở UAV; route không phải biến quyết định trong thí nghiệm này.
- Compute mean 0,524349 s/ảnh, cùng profile CPU tham chiếu local/UAV, chưa gọi là target-device calibrated.
- Image arrival rate cố định 0,24/s. Không tăng compute hoặc tạo image-size-dependent
  inference giả chỉ để SPT/RL có lợi.
- Target offered utilization 0,3/0,6/0,9/1,2. Đây là lượng công việc được chào vào,
  không phải CPU utilization thực sau expiry/drop hay finite-window effect.
- Giữ image rate, đổi background arrival rate từ mean service của pool, không theo policy score.
  Alibaba vẫn resampling proxy, không phải replay timestamp thực của Alibaba.
- Deadline ảnh tight/reference/relaxed = 10/30,20/60,40/120 s; background 120 s.
- Horizon600 s, arrival window300 s, pin lớn1.600.000 J để kiểm tra queue trước.
  Vẫn báo lifetime censoring; không suy diễn “kéo dài lifetime” nếu mọi case sống hết horizon.

Từ pool Alibaba1000 dòng hiện tại, mean proxy service=8,3015 s ở reference1000 unit/s.
Công thức: lambda_bg=(rho_target - 0,24×0,524349)/8,3015.

| rho mục tiêu | lambda_bg /s |
|---|---:|
| 0,3 | 0,020979 |
| 0,6 | 0,057117 |
| 0,9 | 0,093255 |
| 1,2 | 0,129393 |

Lưu cả seed mean/variance, task lớn hơn deadline và finite-window offered work.
Không xóa task bất khả thi để cải thiện metric. Nếu cần stress phân phối khác,
tạo scenario riêng có tên/version, vẫn giữ scenario nguồn gốc làm đối chứng.

So FIFO, EDF, SPT, PRIORITY trên cùng khả năng giữ/drop task; tất cả non-preemptive
như kernel hiện tại. Đây là order-only study, không cho riêng một policy oracle actual work.
RISK_EDF/RISK_SPT có thêm reject/drop mechanism nên cần ablation riêng, không gọi
chênh lệch với EDF là chỉ do thứ tự CPU.

Dự kiến 4 load ×3 deadline ×4 scheduler ×30 development seeds = 1.440 episode.
Đã có runner và1.440episode được audit; xem SEQUENTIAL_STUDY_RESULTS.md.
Scheduling image compute đồng nhất; khác biệt SPT chủ yếu đến từ background/tác vụ
khác lớp, chưa chứng minh lợi thế cho image service-time prediction.

## Giai đoạn B — offloading khi giữ geometry/scheduler

Giữ cùng near-link/hover abstraction và EDF. So ALL_LOCAL, ALL_UAV,
SHORTEST_FINISH, DEADLINE_ENERGY, DELIVERY_AWARE; giữ nguyên contact và CPU assumptions.

Phân tầng connected/disconnected vì local completion không phải local delivery.
Dùng shared-hardware 1× làm setting chính đang có bằng chứng runtime; mọi speedup
UAV khác là sensitivity giả định hoặc phải có profile độc lập.
Không tuyên bố offloading tiết kiệm năng lượng thực từ power model chưa đo.
ALL_LOCAL có UAV hover là routing baseline, không phải hệ thống “không UAV”;
nếu thêm no-UAV system, phải khai báo một đối chứng khác.

## Giai đoạn C — mobile và robustness

Chỉ mở sau khi A/B hoạt động đúng:

1. So proposed controller với static-hover, fixed-route/RR trên cùng layout, seed,
   offloading và scheduler. Static site được chốt theo geometry/development, không chọn
   bằng test score hoặc nhìn task tương lai; báo cách chọn.
2. Báo cả “trong coverage” và “truyền+compute có thể kịp deadline”; không đồng nhất chúng.
3. Giữ LITERAL_DBM làm reference hiện hành. GAIN_DB chỉ là convention sensitivity;
   cần wire tham số radio xuyên kernel/protocol/verifier và test trước khi chạy mobile.
   Chưa có kết luận convention nào khớp hệ thống thực hoặc source tác giả.
4. Giữ payload original JPEG. Resize/compression phải là adaptation riêng với đo
   preprocessing/bytes/accuracy và runtime; không sửa âm thầm workload cũ.
5. Giữ model independent-full-bandwidth chung cho tất cả policy. Bandwidth sharing
   là network-model ablation riêng, cần implementation/verifier trước khi dùng.
6. Bổ sung nhiều layout, kết nối, contact wait, estimate noise và load. Layout42 tại
   hai scale không phải unseen-layout evaluation. Định nghĩa layout partitions trước test.
7. Tách radio convention, bandwidth sharing, payload, compute heterogeneity thành
   từng can thiệp; không đổi đồng thời rồi quy thành cải tiến thuật toán.

## Protocol, thống kê, metric bắt buộc

- Giữ mixed-v2 và manifest 30 development/30 validation/30 evaluation task seeds.
  Dùng development cho debug và lựa chọn setting; khóa validation choices trước test.
  Source pools đang chung, không claim source-disjoint holdout.
- Mỗi policy trong một case dùng đúng task, assignment, estimate noise, ready times
  và workload hash. Đổi deadline giữ các stream không liên quan.
- Report theo load/deadline/connectivity/layout, không chỉ một bảng gộp.
- Phân biệt experimental unit: task seed trong fixed layout; layout độc lập cần tầng
  tổng hợp khác. Không coi mọi task là independent sample.
- Dùng paired differences theo seed; báo effect size và paired bootstrap CI.
  Khi đủ thiết kế/giả định, dùng kiểm định paired và chỉnh multiple comparisons;
  không coi repeat cùng seed thành mẫu độc lập.
- Image compute/delivered DVR; whole-system J/ảnh đúng hạn và J/ảnh delivered đúng hạn;
  completed-image mean/P95 latency; total/UAV energy, background DVR; lifetime censoring.
  Case zero-success là NA J/task, không phải0. Drop không phải completion.
- Đo decision runtime riêng nếu claim thời gian quyết định; wall time toàn episode
  không thay thế latency controller. Báo host/runtime config.
- Audit trace độc lập rồi chạy exporter theo EVALUATION_METRICS.md trước kết luận.
  Retain per-scenario tables, observed queue wait/dispatch, payload và RF conventions.
- Bootstrap/statistics chưa có kết quả trong audit này; plan không phải evidence.

## Thứ tự triển khai thực tế tiếp theo

1. Profile checkpoint vision đã train nếu có; nếu chưa, công bố cấu hình provisional.
   Rà sampler/CPU proxy Alibaba và task bất khả thi trước khi khóa benchmark chính.
2. Nối fixed-shape config + deadline + offered-load proposal vào runner fixed-UAV,
   preflight input và verify từng case nhỏ. Legacy/default replay phải giữ nguyên.
3. Chạy smoke ghép cặp FIFO/EDF/SPT/PRIORITY, kiểm tra queue/load/metric; sau đó campaign A.
4. Chỉ khi có khác biệt có thể giải thích, triển khai mechanism scheduling và ablation.
   Nếu không thấy leverage, báo kết quả âm và xem lại câu hỏi/ứng dụng có cơ sở,
   không sửa simulator để tạo chiến thắng.
5. Mở B/C, cuối cùng mới quyết định train DQN/PPO theo state/action/reward đã khóa.

Radio audit không đòi hỏi dataset mới. Không cần GPU để chạy những kiểm tra này.
