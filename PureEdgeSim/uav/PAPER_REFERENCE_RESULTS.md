# DQN synthetic đủ1triệu bước: cấu hình paper8/8

Ngày **23/10/2026**. Đã hoàn tất **3 model ×1.000.000 steps**, mỗi model
**249.975 gradient updates**. Đây là thí nghiệm trên đường chạy
`PaperSimulation` / `PaperGymBridge`, state24/action12; tách khỏi mobile129D.

**Trạng thái:** train/checkpoint/evaluation/replay thành công. Kết quả của một
cấu hình đã được đối chiếu; **chưa tái hiện toàn bộ số liệu paper**, chưa xác
nhận tương đương source tác giả hoặc tối ưu toàn cục.

## Protocol và kết quả chính

Protocol đã khóa: [paper_reference_protocol.json](../../drl/paper_reference_protocol.json).
3 learning/layout pairs là0/0,1/1,2/2. Có12 thiết bị,8 còn nguồn và8 còn kết nối,
vùng800×800m, task synthetic2–4MB, cùng constants/hyperparameters công bố.
Mỗi model train trên layout riêng, dùng30 task seed test2.000.000–2.000.029;
validation dùng5 task seed từ1.000.000.

Checkpoint chính được chọn theo mean lifetime validation; giữ checkpoint đầu
tiên khi hòa điểm. Các convention REFERENCE giữ nguyên: literal beta dBm,
age≥10, legacy freshness, A/O trước step, U và reward sau step, epsilon1e−6.

| Policy | Mean lifetime slots | SD giữa3 run means | Mean simulated lifetime (s) |
| --- | ---: | ---: | ---: |
| DQN, best validation checkpoint | **21,000** | 9,539 | **12.163,91** |
| Oldest Data | 19,433 | 8,310 | 11.420,67 |
| Round Robin | 12,533 | 3,557 | 7.520,00 |
| Random | 10,756 | 0,937 | 6.450,14 |

DQN cao hơn Oldest Data trung bình **1,567 slot**, trên mẫu3 learning/layout
pairs này. Đây là mô tả kết quả, chưa là kết luận superiority có ý nghĩa thống
kê. SD giữa run lớn do các layout khác nhau; learning và layout seed thay cùng
nhau nên chưa cô lập hai nguồn biến thiên.

| Learning/layout seed | DQN | Oldest | Round Robin | Random | Step của best checkpoint |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 32,000 | 29,000 | 16,600 | 11,833 | 910.000 |
| 1 | 15,000 | 14,000 | 11,000 | 10,133 | 210.000 |
| 2 | 16,000 | 15,300 | 10,000 | 10,300 | 700.000 |

Có **360 primary test episodes =3model ×30case ×4policy**. Đơn vị đánh giá độ
bất định giữa run là3 learning/layout pairs, không phải90 model hoặc90 layout.
Các task seed này không xuất hiện trong training hiện tại, nhưng đã dùng trong
những nghiên cứu development trước; không coi là final-test mới niêm phong.

## Checkpoint cuối1triệu bước

Để kiểm tra độ ổn định, đã đánh giá thêm `final_model.zip` của từng model trên
đúng30case tương ứng. Đây là diagnostic bổ sung, không dùng test để chọn model.

| Seed | Best-validation checkpoint: test mean | Final1m checkpoint: test mean |
| --- | ---: | ---: |
| 0 | 32,000 | 30,000 |
| 1 | 15,000 | 14,000 |
| 2 | 16,000 | 15,033 |
| Mean của3 run means | **21,000** | **19,678** |

Final thấp hơn best ở cả3 seed. Các validation cuối vẫn dao động, nên không
tuyên bố hội tụ ổn định chỉ từ việc train đủ ngân sách. Không đổi quy tắc chọn
checkpoint dựa trên việc số nào gần số liệu paper hơn.

## Đối chiếu paper

- Table5, cell power8/comms8: paper báo **mean18,3slot**; primary hiện tại21,0,
  chênh **+2,7slot / +14,75%**.
- Table6, cùng availability và reward cuối: paper báo **maximum28**; maximum
  của primary hiện tại32. Mean và maximum là hai metric khác nhau.
- Các seed tác giả không có đầy đủ để khớp layout/hardware/task/capacity/masks.
  Backlog, output-link, indexing và reward vẫn có giả định triển khai.
- Các số hiện tại cao hơn không có nghĩa implementation tốt hơn paper. Chưa
  kiểm định equivalence và chưa có full Table5/6 hoặc SUMO case study.

Primary đếm final attempted/partial slot. Cả90 DQN primary episodes dừng vì pin
thiết bị hoặc pin UAV và có final partial slot; `slot-counting.csv` ghi riêng
fully elapsed slots. Không đổi metric sau khi xem kết quả để ép khớp paper.

## Verification và artifact

Run được báo cáo:
[paper-reference-1m-restart-20261023](../../target/paper-reference-1m-restart-20261023/).

- **3/3 model COMPLETE**, đủ1m steps và249.975 updates/model; tất cả process exit0.
- Kiểm tra config/protocol, source hashes, checkpoint metadata, trọng số finite
  và thực sự thay đổi, optimizer losses đã ghi và hữu hạn.
- Tải lại best checkpoint, replay đúng mean validation dùng để chọn nó.
- **360/360 primary traces** replay độc lập: RNG workload, layout full precision,
  action, slant channel, time/flight/hover/ground energy, battery, age và reward.
- **90/90 secondary final-checkpoint traces** cũng replay độc lập. Đây là các
  case trùng primary, không cộng thành thêm450 case/model/layout độc lập.
- 3 test campaign protocol/layout/RNG và9 verifier corruption tests đã đạt
  trước khi train. Hand tests/regression trước đó:107Java/27Python đạt; không
  chạy Maven build đồng thời với training.
- Training+validation khoảng1.455–1.466s/model,3process CPU1thread chạy đồng
  thời trên local. Thời gian này không gồm build, final evaluation và audit,
  và không so trực tiếp với hardware của paper.

Biên bản máy đọc được:

- [verification.json](../../target/paper-reference-1m-restart-20261023/verification.json)
- [summary.csv](../../target/paper-reference-1m-restart-20261023/summary.csv)
- [runs.csv](../../target/paper-reference-1m-restart-20261023/runs.csv)
- [secondary-final-evaluation/summary.csv](../../target/paper-reference-1m-restart-20261023/secondary-final-evaluation/summary.csv)
- [REPORT.md](../../target/paper-reference-1m-restart-20261023/REPORT.md)
- [postprocess-verification.json](../../target/paper-reference-1m-restart-20261023/postprocess-verification.json)

### Lần bị gián đoạn

Lần trước ở `target/paper-reference-1m-20261023` bị host reboot sau mốc920k/910k/
910k. Parent manifest đã đánh dấu INTERRUPTED; checkpoint/log giữ nguyên, không
tính là3 model hoàn tất. Không có replay buffer để khôi phục training tương
đương run liên tục, nên thí nghiệm báo cáo ở đây được train lại từ đầu.
21mốc validation đầu/seed của lần chạy lại khớp lần cũ; đây là kiểm tra tái lập,
không phải thêm mẫu độc lập. Không tác động PID đã được hệ điều hành tái sử dụng.

## Chạy lại và bước tiếp

Build classpath/runtime trên chính máy chạy, rồi:

```bash
python -u -m drl.paper_reference train --workers 3 --output target/paper-reference-new
python scripts/finish-paper-reference.py target/paper-reference-new
```

Trong PowerShell local dùng `.\.venv-drl\Scripts\python.exe` thay `python`;
Linux server dùng Python của venv tương ứng. `workers=3` là3process/JVM riêng,
mỗi Torch1thread; dùng1 nếu cần chạy tuần tự. Runner từ chối ghi đè output.
`python -m drl.paper_reference verify RUN_DIR` đánh giá/audit lại model đã hoàn
tất, không train lại. Hậu xử lý kiểm tra trạng thái hoàn tất trước khi viết báo cáo.

Bước nghiên cứu tiếp theo là kiểm tra/retrain có kiểm soát các giả định reward/
freshness còn mơ hồ và tách ảnh hưởng learning seed với layout. Sau đó mới mở
rộng full Table5/6 nếu mục tiêu là reproduction toàn bài. Không cần dataset mới
cho đường synthetic này. Các thay đổi và run hiện ở local, chưa push GitHub
hoặc đồng bộ/chạy trên server.
