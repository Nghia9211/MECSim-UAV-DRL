# P0 hoàn tất: scenario và thông tin trước quyết định

Ngày 01/10/2026. Đã triển khai/kiểm thử P0 trong [NEXT_STEPS.md](NEXT_STEPS.md).
Tại thời điểm P0 chưa triển khai SERVICE_AWARE, chưa train model mới và chưa dùng
final-test seeds. Kết quả triển khai tiếp theo được ghi riêng ở [P1_RESULTS.md](P1_RESULTS.md).
Đặc tả API, feature availability và lệnh chạy: [FEATURE_CONTRACT.md](FEATURE_CONTRACT.md).

## Thay đổi đã thực hiện

- `PaperScenario`: giữ bộ sinh legacy, bổ sung position, hardware_task, capacity,
  power, connectivity, outage và full; named RNG streams tách khỏi task RNG.
- `PaperSimulation.Manager.decisionState`: snapshot v1 tại action boundary;
  vị trí, pin, age, hardware/task và availability hiện tại; không có next tasks.
- Bridge/Gym: mode/shift và decision_state là option, mặc định legacy/0/false;
  observation24D và physics cũ giữ nguyên. Trace thêm `scenario.json` với
  layout SHA256 đầy đủ độ chính xác và các seed phục vụ audit.
- `drl/protocol_p0.json`: khóa bộ development nhỏ; các range final mới chỉ dự
  trữ và không được runner sử dụng. `drl/scenarios.py` xuất fixtures và đánh giá
  frozen policies, tách snapshot giàu thông tin khỏi đầu vào policy24D.

## Benchmark đã chạy

Output local: [`target/p0-20261001`](../../target/p0-20261001).
Raw outputs được ignore, không có sẵn khi chỉ clone source từ GitHub.

- Base layout42; powered8, connected8; cap600s, giới hạn age10slot.
- Shift seeds2.100.000–2.100.002; task seeds2.000.000–2.000.002.
- 22 fixtures/workload = legacy1 + 7 modes ×3 shift seeds; tổng44 fixtures.
- 66 cases/workload = 22 ×3 task seeds.
- Mỗi case chạy Oldest Data, Round Robin và 5 DQN checkpoint server cũ:
  2 workloads ×66 ×7 policies = **924 episodes**; không có truncation.
- Snapshot ban đầu và trace Oldest Data ở task đầu mỗi fixture được lưu.
  Không lưu trace của mọi policy/episode trong suite này.

Tất cả 5 DQN được train **mixed** trước đây. Cột synthetic bên dưới là probe
chuyển workload của chính các checkpoint này, không phải synthetic-trained DQN
và không thay thế pilot synthetic riêng đã báo cáo ở tuần1–2.

| Can thiệp | Mixed DQN | Mixed Oldest | Synthetic DQN chuyển workload | Synthetic Oldest |
| --- | ---: | ---: | ---: | ---: |
| Legacy, không thay | 17,800 | 17,000 | 16,400 | 17,000 |
| Chỉ tọa độ | 17,733 | 17,000 | 16,400 | 17,000 |
| Hardware + vision task | 10,000 | 17,667 | 19,022 | 20,556 |
| Dung lượng pin | 17,467 | 16,667 | 16,533 | 17,000 |
| Danh tính thiết bị có nguồn | 19,267 | 21,444 | 19,533 | 21,667 |
| Danh tính thiết bị có kết nối | 10,000 | 16,000 | 10,000 | 16,333 |
| Cả nguồn và kết nối | 10,000 | 21,000 | 10,000 | 21,667 |
| Tất cả factor | 10,000 | 19,667 | 10,000 | 19,889 |

Đơn vị: mean lifetime slots. DQN lấy trung bình cân bằng 5 checkpoint × cases;
baseline chạy một lần mỗi case. Legacy có3 task cases/model, mỗi mode khác có
9 case/model (3 shift ×3 task); không coi chúng là45 layout độc lập. Các mode
cùng neo vào layout42; mẫu nhỏ, chưa chạy kiểm định confirmatory.

Chi tiết từng policy/seed: [summary.csv](../../target/p0-20261001/summary.csv).
Paired differences đến legacy cùng task seed có trong
[episodes.csv](../../target/p0-20261001/episodes.csv).

## Có thể kết luận gì?

Trong các can thiệp đã thử, thay tọa độ riêng không tái hiện mức suy giảm lớn
như thay connectivity hoặc nhóm hardware/task trong mixed. Do đó chưa có cơ
sở coi thiếu tọa độ là nguyên nhân duy nhất và chỉ thêm tọa độ vào DQN là đủ.
`hardware_task` thay hai thuộc tính liên quan cùng lúc, không cô lập hardware
đơn lẻ. Kết quả synthetic khác mixed nhắc lại vai trò completion model/workload.

Đây là bằng chứng chẩn đoán trên một base và ba shift seeds, không chứng minh
tọa độ không quan trọng nói chung, không ước lượng hiệu quả SERVICE_AWARE chưa
implement, và không bác bỏ phương pháp gốc của paper. `full` là composition
của các stream mới, không phải cùng bộ30 unseen layouts trước đây.

**Ưu tiên P1:** estimator phân biệt thiết bị có thể tự cập nhật local với thiết
bị cần UAV, rồi xét tuổi dữ liệu, khả năng upload/compute hoàn thành và chi phí
phục vụ. Availability và hệ số xử lý cần được đưa vào ablation riêng; thông tin
bổ sung phải được công bố khi so với DQN24D. Không cho estimator đọc next tasks.

## Validation

- **41 Java tests pass**, gồm3 tests mới cho legacy parity, field isolation,
  factor composition, exact availability counts, reproducibility và manifest.
- **14 Python tests pass**, bật raw dataset tests; gồm4 tests mới cho causal
  snapshot, schema/option validation và paired synthetic/mixed task sequences.
- Cả44 fixture checks xác nhận field ngoài nhóm can thiệp giữ nguyên.
- 21 mixed legacy records khớp slot/reason/seconds với bộ tuần1–2, tolerance1e-6.
- 8.604 device–slot rows thuộc prefix giao nhau của các trace giữ cùng input
  bytes khi đổi scenario. Prefix comparison không yêu cầu episode dài bằng nhau.
- Initial snapshot không phụ thuộc future task seed; snapshot bật/tắt giữ cùng
  observation, reward và transition. Java CLI/Gym parity tests cũ vẫn pass.

Kết quả kiểm tra artifact: [validation.json](../../target/p0-20261001/validation.json).
Manifest có config, protocol hash, model hashes, source snapshot và counters:
[manifest.json](../../target/p0-20261001/manifest.json).

Không cần dataset mới cho bước P1. Giữ các artifact cũ để so sánh; không chạy
`mvn clean` khi còn cần dữ liệu dưới target. P0 không tự commit/push thay đổi mới.
