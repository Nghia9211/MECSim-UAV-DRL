# Kế hoạch tiếp theo: từ chẩn đoán đến cơ chế cải tiến

**Cập nhật 22/10/2026:** đã bổ sung local/UAV offloading kết hợp queue scheduling.
Đọc [OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md) trước; các kế hoạch bên
dưới là lịch sử, không tự chạy tiếp lifetime P2 hoặc train DQN cũ.

**Cập nhật21/10/2026:** người dùng chọn tập trung task scheduling. Task model,
persistent queue, physical-time workload, FIFO/EDF/Priority và benchmark270
episode đã triển khai/verify: [SCHEDULING.md](SCHEDULING.md).
Đã thử thêm cơ chế deadline/pin/aging, SPT và ablation bằng validation riêng:
[SCHEDULING_AGING_RESULTS.md](SCHEDULING_AGING_RESULTS.md). Full vượt bốn baseline
theo primary pilot, nhưng NO_AGING có primary tốt hơn full; chưa chốt thuật toán cuối.
Kế hoạch lifetime P0/P1/P2 bên dưới là nhánh nghiên cứu trước; không tự động
chạy tiếp P2 hoặc retrain checkpoint24D cho queue mới.

Ngày: 01/10/2026. Trạng thái: **P0 và P1 prototype/development đã hoàn tất; P2 chưa bắt đầu**.
P1 chưa đạt cải thiện objective trên mixed: [P1_RESULTS.md](P1_RESULTS.md).
Kết quả: [P0_RESULTS.md](P0_RESULTS.md); API: [FEATURE_CONTRACT.md](FEATURE_CONTRACT.md). Căn cứ:
[WEEK1_2_RESULTS.md](WEEK1_2_RESULTS.md). Phạm vi trước mắt: tuần 3–6;
tuần 7–9 là giai đoạn xác nhận và đóng gói, không phải kết quả đã có.

## 1. Câu hỏi nghiên cứu và giới hạn

**RQ chính:** Với một UAV hỗ trợ 12 thiết bị, chính sách kết hợp độ khẩn cấp cập
nhật, khả năng hoàn thành dự kiến và chi phí phục vụ có kéo dài lifetime so với
Oldest Data trên các cấu hình chưa dùng để lựa chọn thuật toán hay không?

Giả thuyết: tránh phục vụ lặp lại thiết bị ít cần hỗ trợ và ưu tiên các cập nhật
có thể hoàn thành sẽ cải thiện lifetime. Đây là giả thuyết, chưa có bằng chứng
policy đề xuất tốt hơn hoặc mới so với tài liệu nghiên cứu.

Giữ mục tiêu chính của implementation paper: **lifetime theo slot**, cap 600s,
giới hạn tuổi dữ liệu 10 slot, dừng khi có vi phạm pin/age. Báo cáo thêm seconds,
failure reasons, energy, delivery fraction, latency của task đã hoàn thành và
runtime. Reward chỉ phục vụ học, không thay cho objective đánh giá.

Action vẫn chọn thiết bị/điểm đến trong 12 lựa chọn. Chưa triển khai joint
offloading–placement–scheduling–cache, multi-UAV hoặc tối ưu Pareto trong bước
này. Đây là giai đoạn nền tảng của đề tài rộng hơn, không phải đã giải quyết
toàn bộ đề tài. Không sửa quy tắc completion/drop để làm policy trông tốt hơn.

## 2. Bằng chứng → công việc cần làm

| Bằng chứng hiện tại | Điều chưa biết | Công việc |
| --- | --- | --- |
| Unseen DQN10 vs Oldest18,83 slot | Phần nào của cấu hình mới gây khó? | Tách position, hardware/task, battery, outage |
| Hoán đổi ID làm layout42 giảm về10 | Cải tiến nào giảm phụ thuộc index? | Kiểm tra tính nhất quán ID; architecture là ablation riêng |
| DQN thất bại do cập nhật không hoàn thành | Policy có dự đoán được thiết bị cần hỗ trợ? | Heuristic xét urgency, completion và cost |
| Cap ảnh hưởng slot và seconds | Lợi ích có bền dưới giả định khác? | Giữ cap600 ở primary test; sensitivity tách riêng |
| Synthetic/mixed pilot đều giảm zero-shot | Full-budget synthetic có tương tự không? | Đối chứng ngân sách rõ, không suy từ pilot20k lên1m |

Nguồn các dòng trên: báo cáo tuần 1–2, mục 2–7. Chưa kết luận thiếu tọa độ là
nguyên nhân duy nhất hoặc phương pháp của tác giả thất bại nói chung.

## 3. P0 — Khóa giao thức và thông tin trước quyết định

Ưu tiên làm ngay, trước khi train thêm.

- [x] Tạo manifest cho scenario và development seed split; lưu tọa độ, hardware/task,
  capacity, powered/connected masks, nguồn workload và hash cấu hình.
- [x] Tạo fixture với các biến thể: giữ nguyên; chỉ đổi tọa độ; chỉ đổi
  hardware/task; chỉ đổi capacity; chỉ đổi outage; đổi toàn bộ; chỉ relabel ID.
  Các nhóm dùng chung task sequence khi kiểm tra một yếu tố.
- [x] Viết bảng feature contract: tên, đơn vị, thời điểm quan sát, nguồn,
  measured/estimated, và policy nào được quyền dùng.
- [x] Xác nhận default fixture tái hiện kết quả cũ; đổi một yếu tố không kéo
  theo thay đổi yếu tố khác qua cùng một RNG. Dùng RNG stream tách biệt.

Điểm đặt code: `PaperSimulation.java` (layout/decision state),
`PaperGymBridge.java` và `drl/environment.py` (giao thức phiên bản mới nếu cần).
Đã thêm `PaperScenario`, `drl/scenarios.py`, protocol JSON và các tests mới.
Relabel ID tiếp tục dùng policy adapter của `drl.diagnostics`, giữ Java physical
IDs; `hardware_task` là một nhóm, chưa tách riêng hai thuộc tính. Development
protocol đã khóa; collision audit/freeze final study vẫn là việc cần làm sau.

**Thông tin nhân quả:** hiện task của slot được sinh sau khi chọn action. Vì
vậy policy mới không được đọc task RNG seed, ảnh/job tương lai, realized CPU
completion hoặc dữ liệu trace sau action. Giữ nguyên thứ tự simulator; dùng
ước lượng workload từ training pool hoặc metadata thực sự đã có trước quyết
định. Ghi rõ sai số ước lượng và chi phí thu thập feature. Không âm thầm biến
heuristic thành policy biết trước tương lai.

Đầu ra: manifest schema, fixtures, feature contract và kiểm thử parity. Điều
kiện hoàn thành: có thể chứng minh mỗi phép thử chỉ thay đúng yếu tố đã nêu.

## 4. P1 — Heuristic xét khả năng cập nhật và chi phí

Tên làm việc: `SERVICE_AWARE` — tên kỹ thuật, không phải tuyên bố thuật toán mới.

- [x] Viết estimator thuần, không thay trạng thái/RNG của simulator. Với mỗi
  điểm đến, ước lượng flight, coverage, truyền, CPU/local completion và năng
  lượng dựa trên feature contract. Tái sử dụng công thức vật lý hiện có.
- [x] Chấm điểm lợi ích cập nhật của **tất cả thiết bị** trong vùng phục vụ,
  trừ những cập nhật dự kiến tự hoàn thành local; không chỉ xét thiết bị đích.
- [x] Bản đầu dùng urgency `1 / max(1, 10 − age)` nhân lợi ích cập nhật dự kiến,
  trừ chi phí năng lượng chuẩn hóa theo pin còn lại và thời gian theo cap600.
  Chuẩn hóa, hệ số và cách ước lượng phải được ghi trong config, chưa chốt từ
  kết quả final test. Lưới nhỏ hệ số trên validation, chẳng hạn {0; 0,1; 1}.
- [x] Không hard-mask vĩnh viễn thiết bị đắt/khó phục vụ. Khi không có lựa chọn
  có lợi ích dự kiến, fallback Oldest Data và log lý do. Quy tắc tie-break
  dựa trên thuộc tính vật lý ổn định khi relabel; nếu đối xứng hoàn toàn thì
  chọn ngẫu nhiên có seed, kiểm tra tính tương đương theo phân phối.
- [x] Kiểm thử tình huống: dữ liệu sắp hết hạn; upload quá cap dù trong range;
  local tự hoàn thành; nhiều thiết bị cùng coverage; pin gần cạn; mọi lựa chọn
  dự kiến không khả thi; relabel nhất quán.

Code đã có: `ServiceEstimator.java`, `drl/service_policy.py` và runner
`drl/service_experiment.py`; giữ
API/baseline cũ. Không dùng shadow rollout đọc workload tương lai làm estimator.
Chi phí đánh giá N điểm đến × N thiết bị có thể O(N²), cộng chi phí ước lượng
CPU; bản mixed hiện có O(N³) worst-case vì quét completion theo device.
Runtime đã đo gồm estimator RPC, không gồm chi phí telemetry thực địa;
chi tiết và ranh giới đo trong báo cáo P1.

Đối chứng development: Random, Round Robin, Oldest Data, nearest-device,
urgency-only với cùng feature set, và SERVICE_AWARE. Ablation bỏ riêng completion,
energy hoặc urgency; cả full policy và ablation dùng cùng protocol tuning.

**Gate:** estimator và tests đúng, runtime được đo, paired development results
có đủ failure traces và variance. Chỉ chuyển sang nghiên cứu học máy nếu thấy
cấu trúc có ích hoặc hạn chế cụ thể mà learning có thể giải quyết. Kết quả không
cải thiện vẫn được báo cáo; không đổi simulator để ép vượt Oldest Data.

**Kết quả gate:** kiểm thử/parity và benchmark đã đạt; chưa đạt cải thiện mixed.
Đã chạy660 validation +1320 development episodes. Service +3.66% synthetic nhưng
−2.55% mixed so với Oldest; 9 mixed episodes vi phạm age thuộc3 fixture.
Hệ số chọn trên validation là energy1/time0 cho cả hai workload.
Không tune lại theo development. P1.1 đề xuất kiểm tra cơ chế tránh bỏ sót
thiết bị/khả năng phục vụ trước hạn, có ablation riêng; chưa triển khai.

## 5. P2 — Tách nguyên nhân trong DRL

Chạy sau P0/P1. Không thêm nhiều thay đổi rồi gán toàn bộ lợi ích cho một cơ chế.

| Nhánh | Observation | Train layout | Vai trò |
| --- | --- | --- | --- |
| A | Battery/age24D cũ | Cố định | Reference triển khai hiện tại |
| B | Battery/age24D cũ | Nhiều layout | Tách tác động training distribution |
| C | Feature contract mở rộng | Cố định | Tách thông tin bổ sung so với A |
| D | Feature mở rộng như C | Nhiều layout như B | Tương tác thông tin và phân phối |
| E | Chính xác feature của D | Như D | Thay MLP bằng policy xử lý tập thiết bị |

Observation mới version riêng; không load checkpoint24D vào model khác shape.
So E/D giữ cùng dữ liệu, reward, budget, hyperparameter search budget; báo cáo
số tham số và compute vì architecture có thể khác kích thước.

Original DQN/Oldest là reference. So sánh cơ chế cần thêm đối chứng có cùng thông
tin và cùng action restrictions; tách lợi ích do thêm thông tin khỏi lợi ích do
thuật toán. Không áp dụng feasibility mask cho một policy mà giấu thay đổi này.

Ngân sách screening dự kiến: A–E × 5 learning seeds0–4 × 100k steps = 2,5 triệu
steps cho mixed. Đây là pilot; exploration schedule theo budget phải công bố.
Synthetic là đối chứng riêng. Để nói về paper ở ngân sách công bố, chạy ít nhất
synthetic DQN5 seeds ×1m như một gói riêng, không lấy mixed thay thế synthetic.

## 6. Split, thống kê và tiêu chí đánh giá

Seed split **đề xuất cần kiểm tra không trùng artifact trước khi khóa manifest**:

| Tập | Layout seeds | Task seeds | Cách dùng |
| --- | --- | --- | --- |
| Development cũ | 42; 2.000.000–2.000.029 | Đã dùng | Debug, giải thích trace; không dùng cho kết luận final |
| Train nhiều layout | 100–199 | [0; 1.000.000) | Lấy mẫu layout và task độc lập |
| Validation | 1.100.000–1.100.029 | 1.200.000–1.200.002 | Checkpoint/tuning; ghép mỗi layout với3 task seeds |
| Final test mới | 3.000.000–3.000.029 | 4.000.000–4.000.002 | 30 layout ×3 task sequences =90 case; mở sau khi khóa phương pháp |

Các range trên thuộc namespace layout/task, tách khỏi learning seed. Training
sampler cho nhiều layout là công việc cần implement, CLI hiện tại chưa tự làm.
Chưa gọi đây là source-data holdout: cùng RescueNet/Alibaba pools vẫn chỉ đo
generalization qua cấu hình và chuỗi workload. Nếu đánh giá ảnh/job mới, tách
pool theo source trước, lưu manifest và tránh rò rỉ; không chỉ đổi seed.

- Chốt **20 independent learning seeds, 1m steps/model** cho nhánh được chọn và
  DRL đối chứng công bằng trong confirmatory mixed study. Khóa seed list và
  ngân sách trước khi xem final outcomes; số20 là ngân sách dự kiến, không phải
  chứng minh đủ power. Dùng pilot để ước lượng variance và báo chi phí khả thi.
- Nếu không đủ ngân sách, thu hẹp phạm vi trước khi mở final test; không dừng
  khi p-value vừa đạt ngưỡng, không chỉ giữ các seed tốt.
- Primary contrast: policy được chọn với Oldest Data trên paired cases, cap600,
  mean lifetime slots. Báo cả effect size và khoảng bất định, không chỉ p-value.
- Với DRL, bootstrap phân cấp/crossed phù hợp: resample learning seeds và layout
  clusters, giữ3 task repeats trong layout cùng nhau và giữ pairing giữa policy.
  Heuristic lặp cùng case không tạo thêm independent training sample.
- Xác định trước kiểm định paired ở đơn vị độc lập phù hợp; nếu nhiều contrasts
  confirmatory thì dùng Holm và báo toàn bộ contrasts, không chọn kết quả đẹp.
- Secondary: simulated seconds, failure reasons, delivery, energy từng thành
  phần, latency có điều kiện trên task hoàn thành, runtime median/p95. Không
  gọi delivered-only latency là latency của mọi task.
- Sensitivity cap300/600/900, workload/compute scale, outage và vị trí tách khỏi
  primary test. So cap khác phải kèm seconds và thay đổi ý nghĩa giới hạn10slot.
- Scalability N khác12 là phần triển khai riêng; không suy từ Big-O rằng đã
  benchmark nhiều kích thước. Nếu bổ sung, cần sửa các assumption hard-code và
  bảo đảm compatibility test N=12 trước.

## 7. Thứ tự thực hiện và deliverables

| Giai đoạn | Công việc | Đầu ra / điều kiện chuyển |
| --- | --- | --- |
| Tuần3, ưu tiên đầu | P0 protocol + feature contract + controlled fixtures | Parity, split manifest, kiểm tra không nhìn tương lai |
| Tuần3–4 | P1 estimator + SERVICE_AWARE + paired development benchmark | Full/ablation tables, trace, runtime; quyết định có cần DRL |
| Tuần4–5 | P2 screening, synthetic đối chứng theo ngân sách riêng | Tách observation/distribution/architecture; validation-only selection |
| Tuần6 | Khóa thiết kế, chạy confirmatory theo ngân sách đã chốt | 20 learning seeds, paired statistics, robustness/sensitivity |
| Tuần7–9 | Đối chiếu literature/SOTA phù hợp, case study, đóng gói | Claim-to-evidence, configs/hashes, scripts, báo cáo giới hạn |

Đây là lịch theo phụ thuộc, không cam kết thời gian train trước khi đo trên
server. Đánh giá novelty/SOTA cần literature review mới trước khi tuyên bố đóng
góp; hiện mới có cơ chế dự kiến. Không cần tải dataset mới cho P0/P1. Khi cần
source holdout lớn hơn hoặc SUMO case study, sẽ có hướng dẫn tải riêng.

**Việc triển khai kế tiếp cụ thể:** P1.1 tránh bỏ sót thiết bị dựa trên failure
traces P1, khóa protocol trước khi đánh giá. Chưa chạy thêm hàng loạt DRL seeds;
chưa mở final test hoặc tuyên bố novelty.

## 8. Trạng thái và tự kiểm tra kế hoạch

P0 hoàn tất chưa phải kết quả cải tiến thuật toán. Đã rà soát nội bộ về causal features,
fairness, đơn vị thống kê và tính khả thi; không phải peer review bên ngoài.
Các rủi ro còn mở: estimator sai, thêm thông tin gây so sánh lệch, workload chưa
hiệu chuẩn, budget không đủ và lợi ích không bền. Mỗi rủi ro có đối chứng/gate
trong P0–P2. Báo cáo tuần1–2 là mốc bằng chứng; không sửa số liệu cũ theo kỳ vọng.
