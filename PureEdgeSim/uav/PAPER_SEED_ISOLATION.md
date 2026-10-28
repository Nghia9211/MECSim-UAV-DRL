# Đối chứng seed huấn luyện trên một layout paper cố định

Ngày 24/10/2026. **Đã hoàn tất: 2 model train mới đủ 1 triệu bước và 1 model
được dùng lại; 270 trace và kiểm tra artifact đều đạt.**

## Kết quả đã kiểm chứng

| Learning seed, cùng layout 0 | Best-validation checkpoint | Final đúng 1 triệu bước |
| --- | ---: | ---: |
| 0, dùng lại | 32,000 slot | 30,000 slot |
| 1, train mới | 32,000 slot | 30,367 slot |
| 2, train mới | 32,000 slot | 10,000 slot |

Mean best = **32,000 slot**, SD giữa ba run means = **0**. Mean final =
**23,456 slot**, SD giữa ba run means = **11,654**. Best được chọn trước test
bằng validation; không được dùng việc ba best giống nhau để khẳng định training
ổn định. Final seed 2 dừng do `DEVICE_8_DATA_AGE` ở cả 30 test case, trong khi
best của nó dừng do pin UAV. Đây là mô tả checkpoint, chưa chứng minh nguyên nhân.

Trên cùng layout/test case: Oldest Data **29,000 slot**, Round Robin **16,600**,
Random **11,833**. Đây là một layout development đã quan sát; không so mean này
trực tiếp với Table 5 của paper hoặc khái quát sang mọi bố trí.

**Kết luận:** best-selection theo validation tìm được lifetime tương tự giữa
ba learning seed trên layout này, nhưng model cuối vẫn có thể suy giảm mạnh.
SD nhỏ của best không loại trừ bất ổn của quá trình học. Chưa thể nói chênh lệch
ở thí nghiệm trước chỉ do layout hoặc chỉ do seed.

Biên bản: [verification.json](../../target/paper-seed-isolation-20261024/verification.json),
[final-artifact-check.json](../../target/paper-seed-isolation-20261024/final-artifact-check.json),
[COMPARISON_REPORT.md](../../target/paper-seed-isolation-20261024/COMPARISON_REPORT.md).
150 case dùng lại/heuristic khớp kết quả lịch sử; runtime versions và model/source
hashes khớp. Có 3 test mới cho protocol/reuse và 3 test reference cùng 9 verifier
tests đạt trước khi chạy. Cấu hình và mô hình vật lý không được thay trong đợt này.

Đề xuất tiếp theo và phạm vi đã được phép chạy:
[NEXT_EXPERIMENT_PROPOSAL.md](NEXT_EXPERIMENT_PROPOSAL.md).

## Thiết kế và cách chạy lại

Thí nghiệm trước dùng learning/layout pairs0/0,1/1,2/2; vì hai loại seed thay
cùng nhau, SD giữa ba run không thể gọi là độ bất ổn do seed huấn luyện đơn lẻ.
Đợt này giữ nguyên layout0 và chỉ thay learning seed0/1/2.

Protocol đã khóa:
[paper_seed_isolation_protocol.json](../../drl/paper_seed_isolation_protocol.json).

- Dùng lại model seed0/layout0 đủ1triệu bước đã được kiểm chứng trong
  [PAPER_REFERENCE_RESULTS.md](PAPER_REFERENCE_RESULTS.md); không train lại,
  không đổi checkpoint hoặc log cũ.
- Train mới seed1/layout0 và seed2/layout0, mỗi model1.000.000 steps.
- Vẫn synthetic2–4MB, DQN24D/12action, power8/comms8, geometry/hardware/task/
  capacity/outage masks của layout0, cùng hyperparameters và convention REFERENCE.
- Learning seed ảnh hưởng khởi tạo, exploration, minibatch và chuỗi task training;
  **không phải** chỉ thay khởi tạo trọng số.
- Best checkpoint theo mean validation5case; final1m là diagnostic bổ sung.
  Mỗi checkpoint đánh giá30 task seeds2.000.000–2.000.029.
- Trong bảng chính, Round Robin/Oldest Data/Random chỉ lấy một lần/case, không
  nhân baseline theo số learner. Primary có90DQN +90heuristic traces;
  secondary90DQN final traces. Lệnh train mặc định còn có automatic evaluation
  trong từng run; các case trùng đó không được tính thêm vào mẫu phân tích.
- Chỉ một layout development đã được quan sát, không phải generalization hoặc
  tập test final mới. Không so trực tiếp mean layout0 với Table5 trung bình trên
  các khởi tạo tác giả không công bố đầy đủ.

Run hiện tại:
[paper-seed-isolation-20261024](../../target/paper-seed-isolation-20261024/).

Sau khi train hoàn tất, runner tự kiểm tra config/checkpoint, replay lựa chọn
best trên validation, và replay độc lập270physical/action traces. Mọi state
vật lý được kiểm tra cùng layout hash; báo cáo `REPORT.md` chỉ ghi khi audit đạt.

```bash
python -u -m drl.paper_seed_isolation train --workers 2 --output target/paper-seed-isolation-new
```

PowerShell local dùng `.\.venv-drl\Scripts\python.exe` thay `python`.
Reuse yêu cầu campaign nguồn đã có trong checkout và khớp config/hashes; runner
không tự tải checkpoint hoặc viết lại dữ liệu cũ. Trong clone chưa có artifact,
cần chạy reference campaign trước hoặc điều chỉnh protocol được review rõ ràng.

Các kết luận được phép sau khi có kết quả: mô tả biến thiên learning seed có
điều kiện trên layout0; so best/final và heuristic trên cùng task cases. Không
suy ra tỷ lệ đóng góp phương sai của geometry/hardware/outage từ một layout,
không gọi là reproduction toàn paper hoặc thuật toán mới.
