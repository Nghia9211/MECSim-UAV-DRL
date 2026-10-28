# Kiểm toán mô hình paper và độ nhạy quy ước — 23/10/2026

> **Cập nhật sau audit:**3synthetic DQN đủ1m/model đã chạy xong tại cấu hình8/8;
> kết quả mới ở [PAPER_REFERENCE_RESULTS.md](PAPER_REFERENCE_RESULTS.md).
> Nội dung bên dưới giữ lại kết quả và kế hoạch tại giai đoạn convention audit.

**Kết luận:** code mặc định khớp các tham số công bố được kiểm tra trong Tables
1–4. Đã chạy và replay độc lập **2.520 episode synthetic**, nhưng đây là
benchmark heuristic kiểm tra environment, **chưa phải tái hiện số liệu DQN của
paper**. Không lấy kết quả mobile129D, RescueNet hoặc Alibaba để thay thế bước đó.

Nguồn kiểm tra: [paper trích xuất theo trang](../../../2501.15305v1.md),
[PDF gốc](../../../2501.15305v1.pdf), §3.1–4 và Tables1–4,5,6.
Snapshot paper/source nằm trong run, không chỉnh sửa PDF gốc.

## Những gì đã có trong paper và code

| Nội dung | Nguồn paper | Kiểm tra hiện tại |
| --- | --- | --- |
| 12 thiết bị, UAV5m/s, H10m, range65m, flight150W/hover80W, pin1600kJ | Table1, trang8 | Khớp constants và hand tests |
| Khu vực800×800m | §5, trang9 | Khớp |
| Pin ground50–80kJ, task2–4MB, bandwidth20MHz, TX0,1W | Table1 | Khớp; MB dùng decimal bytes là quy ước công khai |
| Standby của5 loại board | Table1 | 5 giá trị khớp |
| Công suất/tốc độ xử lý theo hardware × task | Tables2–3, trang9 | 25+25 giá trị so trực tiếp với hàng trích xuất paper: khớp |
| State24, action0–11, MLP64/64 ReLU | §3.2, trang6; Table4, trang10 | Khớp source và Gym |
| LR0,0071, gamma0,98, batch16, epsilon1→0,05/35% | §4 và Table4 | Khớp source; ngân sách công bố1.000.000 bước/model |
| Cap10phút; reward gọi cuối step | §4, trang7–8 | Đã quy định rõ, không coi là thông tin bị thiếu |
| Kết thúc khi data age đạt10 | §4, trang8 | Default dùng `age>=10` |

Audit tham số không xác nhận mọi transition hoặc số liệu công bố là giống nhau.
Replay độc lập bên dưới kiểm tra transition **theo từng quy ước được khai báo**.

## Các lựa chọn phải công khai

| Vấn đề | Default REFERENCE được giữ | Biến thể kiểm tra |
| --- | --- | --- |
| β₀ ghi−50dBm nhưng dùng trong biểu thức channel gain | Literal dBm→10⁻⁸, noise power10⁻¹³W, không bình phương noise lần nữa | GAIN_DB dùng10⁻⁵ như gain−50dB |
| §4 nói đạt10; §5 nhắc baseline11 | AT_LIMIT: age≥10 | AGE_GT10: age>10, là probe indexing, không tự nhận đúng hơn |
| Eq.(1f) dựa kết nối/visit; xử lý incomplete work chưa được chỉ rõ | LEGACY: connected hoặc upload hoàn tất thì age reset | LOCAL_COMPLETION yêu cầu local xong và connected; RESET_ON_ARRIVAL chỉ cần đến coverage |
| Reward tính cuối step, nhưng thời điểm chụp A/O chưa đủ rõ | A/O trước transition, U sau transition | REWARD_AFTER lấy A/O sau cập nhật age |
| `log(0)` không có quy tắc cụ thể | Clamp1e−6 | EPS_1E3 dùng1e−3 |
| Slot bị cắt khi hết pin | Tính final attempted/partial slot vào lifetime | Xuất thêm số fully elapsed slots, chưa đổi objective hoặc transition |
| Cap10phút nhưng backlog sau cap chưa mô tả đủ | Discard phần dư, slot sau nhận workload mới | **Chưa chạy biến thể carry-over** |
| Output local1kB đã được nêu; link tương ứng chưa đủ tham số | Output/relay tức thời, bỏ chi phí output | **Chưa hiệu chuẩn hoặc chạy biến thể output-link** |

Mọi lựa chọn trên đều là giả định triển khai. Không chọn profile theo con số
Table5/6 để ép khớp. Giữ REFERENCE làm baseline hiện hành vì nó giữ hợp đồng
cũ và theo cách đọc §4/Eq.(1f) đã công khai, không vì nó đã được tác giả xác nhận.
Radio của môi trường mobile vẫn dùng default riêng không bị global property đổi.

## Benchmark đã chạy

Run: [paper-convention-v2-20261023](../../target/paper-convention-v2-20261023/).

- 7 profile: reference +6 can thiệp, mỗi profile đổi đúng một lựa chọn.
- 4 cấu hình còn nguồn/còn kết nối:12/12,8/8,6/6,10/8.
- 30 seed0–29; layout=seed, task=seed+1, policy RNG=seed+2.
- 3 heuristic: Round Robin, Oldest Data, Random. **Không train DQN ở stage này.**
- Tổng **7×4×30×3=2.520 episode**, **544.260 device–slot rows**.
- Mỗi seed dùng cùng geometry/hardware/capacity giữa các cấu hình availability;
  không coi120 case hoặc2.520 episode là120/2.520 layout độc lập.
- Trình kiểm tra độc lập không gọi Java: tự tái lập Java RNG, task draws,
  policy, slot duration, slant rate, flight/hover, standby/active energy,
  depletion, UAV position, age/expiry/reward và summary.

[verification.json](../../target/paper-convention-v2-20261023/verification.json):
**PASS** cho toàn bộ2.520 episode.

## Kết quả độ nhạy

Mỗi dòng so360 case với reference tương ứng (cùng seed/scenario/policy).
“Thay đổi lifetime” là khác số slot, chưa phải kiểm định thống kê.

| Can thiệp | Case đổi lifetime /360 | Độ lệch mean slot lớn nhất trong12 nhóm scenario/policy |
| --- | ---: | --- |
| GAIN_DB | 11 | +0,433 slot, Round Robin10/8 |
| AGE_GT10 | 173 | +1,767 slot, Random10/8 |
| LOCAL_COMPLETION | 147 | −18,333 slot, Random12/12 |
| RESET_ON_ARRIVAL | 11 | +0,433 slot, Round Robin10/8 |
| REWARD_AFTER | 0 | Reward đổi; chưa retrain nên không kết luận không ảnh hưởng DQN |
| EPS_1E3 | 0 | Reward đổi; chưa retrain nên không kết luận không ảnh hưởng DQN |

Ở8/8, mean slots theo30 seed:

| Profile | Round Robin | Oldest Data | Random |
| --- | ---: | ---: | ---: |
| REFERENCE | 11,800 | 21,000 | 10,467 |
| GAIN_DB | 12,233 | 21,000 | 10,467 |
| AGE_GT10 | 12,833 | 21,000 | 12,100 |
| LOCAL_COMPLETION | 10,600 | 21,200 | 10,233 |
| RESET_ON_ARRIVAL | 12,233 | 21,000 | 10,467 |

Kết quả cho thấy completion/freshness và indexing đáng ưu tiên kiểm tra. Tác
động radio nhỏ trong **mẫu heuristic này**, không chứng minh radio không quan
trọng hoặc DQN retrain sẽ có cùng độ nhạy. Không dùng Oldest21slot để so như
thể đó là DQN paper18,3slot: thuật toán và khởi tạo khác nhau.

187/360 reference episodes có final partial slot; cách đếm có thể lệch một slot
trên từng episode. [slot-counting.csv](../../target/paper-convention-v2-20261023/slot-counting.csv)
lưu attempted/fully elapsed riêng. Đây là metric phụ để kiểm tra indexing;
không thay main metric hoặc tự kết luận cách đếm của tác giả.

## Validation và tương thích

- **107 Java tests đạt**, gồm7 hand tests mới cho các lựa chọn.
- **27 Python integration tests đạt**, bật raw dataset tests; gồm2 test Gym
  mới cho age11 và reward timing. Schema `paper-decision-v1` giữ nguyên.
- **9 test verifier đạt**, gồm corruption của task RNG, energy, duration,
  position, age, reward và bảng tham số.
- **360/360 episode REFERENCE khớp baseline lịch sử** về slots/reason/seconds;
  **1.080 CSV slots/devices/layout giống byte-for-byte**.
- 720 case reward-only giữ nguyên physics và device trace so reference.
- 38 source hashes của run khớp working tree lúc kiểm tra.

Biên bản bổ sung:
[additional-verification.json](../../target/paper-convention-v2-20261023/additional-verification.json).
Đợt chạy đầu và v2 là lần chạy lại để xác minh tương thích; **không gộp chúng
thành thêm mẫu độc lập**. V2 là artifact được báo cáo.

## Chạy lại

```powershell
.\scripts\run-paper-conventions.ps1 -Seeds 30 -Output target/paper-convention-new -Offline
```

Linux, từ repo:

```bash
mvn test compile exec:java -Dexec.mainClass=uav.PaperConventionBenchmark -Dexec.classpathScope=compile -Daudit.seeds=30 -Daudit.output=target/paper-convention-new
python scripts/verify-paper-conventions.py target/paper-convention-new
python scripts/test-paper-convention-verifier.py target/paper-convention-new
```

Không build Java đồng thời với Gym regression vì compiler có thể thay class
files đang được JVM mới nạp. Build xong rồi mới chạy Python integration tests.

## Bước tái hiện tiếp theo đã chuẩn bị

Protocol: [paper_reference_protocol.json](../../drl/paper_reference_protocol.json).
Đây là **kế hoạch, chưa chạy full-budget synthetic trong stage audit này**:

- DQN synthetic, p8/c8, REFERENCE;1.000.000 steps/model.
- 3 learning/layout seeds0/1/2; validation5, test30 task seeds/model.
- Chọn best bằng validation; báo cáo mean theo3 training/layout seeds, SD,
  seconds, failure reasons và attempted/completed-slot convention.
- Table5 cell p8/c8 là **mean18,3**; Table6 cùng cấu hình/reward là **max28**.
  Hai số khác metric, không dùng thay nhau. Paper không cung cấp đầy đủ seed gốc.

Ví dụ Linux chạy đúng protocol trên venv đã cài và classpath đã build:

```bash
for seed in 0 1 2; do
  .venv-drl/bin/python -u -m drl.run train \
    --algorithm DQN --workload synthetic --reward paper --steps 1000000 \
    --seed "$seed" --layout-seed "$seed" --powered 8 --connected 8 --max-slots 200 \
    --eval-freq 10000 --validation-episodes 5 --eval-episodes 30 --device cpu --threads 1 \
    --property paper.slotCapSeconds=600 --property paper.localRateScale=1 \
    --property paper.radioConvention=LITERAL_DBM --property paper.expiryConvention=AT_LIMIT \
    --property paper.deliveryConvention=LEGACY --property paper.rewardSnapshot=BEFORE \
    --property paper.rewardEpsilon=1e-6 --output "target/paper-reference-1m-s${seed}" || break
done
```

Chạy3model này chưa phải full Table5/6 hoặc SUMO. Những việc còn thiếu là train
full-budget, đối chiếu kết quả, kiểm tra reward sau retrain và làm rõ backlog/
output-link nếu cần equivalence chặt với source tác giả. Không cần dataset mới.
Stage này chạy local, chưa push GitHub hoặc thực thi trên server.
