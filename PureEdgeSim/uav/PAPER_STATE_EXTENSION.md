# State extension: thử nghiệm trên aiotlab92

Đây là biến thể nghiên cứu của môi trường synthetic, không thay state của reproduction mặc định.

## Giả thuyết và thiết kế khóa trước khi train

Với delivery `LOCAL_COMPLETION`, bổ sung trạng thái vật lý hiện tại có thể giúp DQN tránh bỏ sót thiết bị. Không khẳng định trước rằng tăng state sẽ cải thiện. Không đổi reward BEFORE, cap 600 s, expiry >=10, đường truyền, action, optimizer, gamma hoặc architecture [64,64].

- Đối chứng **paper24**: 12 battery fraction + 12 tuổi theo slot.
- Biến thể **extended125**: giữ nguyên 24 giá trị đầu; thêm 5 global (x/y UAV, pin UAV, slot, thời gian) và 8 giá trị cho mỗi thiết bị (x/y, powered/connected, capacity, local rate, standby/active W).
- Chuẩn hóa chỉ phần bổ sung; first24 giữ đơn vị để phép so sánh không trộn thêm thay đổi normalization. Thang đo trong `drl/paper_state.py`; không clip âm thầm thông số ngoài miền hỗ trợ.
- Không có task tương lai, actual task bytes/compute sắp sinh, future queue hoặc seed trong state. Synthetic không có finite CPU queue nên không thêm queue giả.
- Mode mới bật causal telemetry đã có của Java; kernel và internal raw state dùng tính reward không đổi.

## Ngân sách

6 model = 2 mode × learning seeds 0/1/2, cùng layout0, nguồn/kết nối 8/8, synthetic, mỗi model 1.000.000 bước; tối đa 3 model CPU, một Torch thread/model, JVM riêng. Baseline 24D cũng train trên cùng server do Torch/NumPy ở server khác máy local.

Validation 5 task seed bắt đầu 1.000.000, mỗi 10.000 bước; chọn best validation đầu tiên và báo cả final. Đánh giá chính: 30 task seed **3.000.000–3.000.029**, không dùng để chọn checkpoint. Các case 2.000.000 cũ là development. Trainer chung có chạy một case development sau training để kiểm tra; không dùng case đó thay bảng chính.

Vẫn chỉ một layout đã nghiên cứu trước; không gọi đây là bằng chứng generalization. Mean từng learning seed là đơn vị tổng hợp giữa model; không nhân số mẫu heuristic lặp lại qua mode/checkpoint. Mạng đầu vào lớn hơn làm số tham số lớn hơn: đây là ablation state với hidden architecture cố định, chưa tách lợi ích thông tin khỏi capacity.

## Kiểm chứng và đầu ra

`drl/test_extended_state.py`: cùng action thì physics/reward/raw24 khớp; thay task seed không thay initial state; bounds và unsupported mode.

`drl/paper_state_campaign.py`: smoke train cả hai mode, save/load model, checks gradient budget, best selection, finite weights, reconstruct observation độc lập từ trace + layout đầy đủ, predict lại action checkpoint và replay physics/RNG/energy/age/reward bằng verifier Python. Source hash kiểm tra không đổi sau campaign. Best/final đều lưu đủ trace, gồm history125 chỉ khi ghi trace. Model24 cũ không được nạp như model125.

Chạy Linux sau khi đặt Java/Maven và `.venv-drl`:

```bash
OUT_DIR=target/state-extension-CHOOSE-UNIQUE bash scripts/train-state-extension-server.sh --dry-run
OUT_DIR=target/state-extension-CHOOSE-UNIQUE bash scripts/train-state-extension-server.sh
```

Đầu ra: `manifest.json`, process receipt/log từng model, `summary.csv`, `REPORT.md`, `verification.json`, checkpoint, validation curves và full trace. Chỉ gọi COMPLETE khi replay đạt; không coi tmux launch là train đã hoàn thành.

Các test legacy tái dùng artifact có kiểm tra checksum source cũ sẽ chủ động từ chối checkout mới; chúng không phải preflight cho campaign này. Giữ nguyên artifact cũ, không sửa manifest/checksum để làm test legacy pass.
