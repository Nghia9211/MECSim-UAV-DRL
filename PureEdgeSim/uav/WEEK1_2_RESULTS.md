# Kết quả bổ sung cho tuần 1–2 — 01/10/2026

## Kết luận

Đã có bằng chứng thực nghiệm để mô tả các điểm yếu **của baseline và checkpoint
trong implementation hiện tại**. DQN cải thiện nhỏ trên cấu hình đã học nhưng
không chuyển tốt sang cấu hình mới; policy nhạy với thứ tự ID; cap/ánh xạ chi phí
workload ảnh hưởng đáng kể đến kết quả. Chưa thể quy thất bại riêng cho thiếu tọa
độ, kết luận phương pháp của tác giả nói chung kém, hoặc coi đây là tái lập paper.

Các giới hạn còn lại là câu hỏi cho nghiên cứu cải tiến, không ngăn việc hoàn
thành báo cáo mô hình + baseline + benchmark nhỏ + complexity/objective/runtime.

## 1. Artifact và đơn vị thực nghiệm

Raw output: [`target/week12-20261001`](../../target/week12-20261001).
Mỗi stage có `manifest.json`, snapshot source và `complete.json`. Hash của 5
checkpoint, cấu hình huấn luyện và phần cứng được lưu trong manifest.

Dataset và checkpoint gốc không bị sửa.

| Thí nghiệm | Quy mô | Đơn vị cần phân biệt |
| --- | --- | --- |
| Frozen checkpoint evaluation | 5 model × 2 chế độ × 30 case × 4 policy = 1.200 episode | 5 learning seeds, 30 layout/task pairs; baseline bị lặp giữa model |
| Đối chiếu server | 600 same-layout records | So slots, reason, seconds; không phải thêm mẫu độc lập |
| ID permutation | 5 model × 3 layout × 6 phép đổi nhãn = 90 trace | 15 identity + 75 nonidentity; thêm 15 canonical control |
| Sensitivity | 9 cấu hình × 9 case × (5 DQN + 3 baseline) = 648 episode | 3 layout × 3 task seeds, không phải 9 layout |
| Runtime | 28.672 policy calls; 80 episode sau warm-up | Microbenchmark trên máy local |
| Pilot gần paper | 3 seeds × 2 workloads × 20.000 steps | 6 lần training mới, ngân sách nhỏ |

`same`: layout42 và 30 task seeds 2.000.000–2.000.029.
`unseen`: 30 layout seeds 2.000.000–2.000.029, mỗi layout ghép cùng một task seed.
**Đây là 30 layout mới, không phải layout seed30.**

Trong source hiện tại, đổi `layout_seed` còn đổi **hardware, vision task,
capacity pin và danh tính thiết bị mất nguồn/kết nối**, ngoài tọa độ. Vì vậy kết
quả là chuyển sang cấu hình mới tổng hợp, chưa cô lập riêng ảnh hưởng tọa độ.
Số còn nguồn/kết nối giữ 8/8, tổng 12 thiết bị, 1 UAV.

Những layout đã xem để chẩn đoán là development cases. Phải dành tập layout/task
seed mới cho kết luận cuối về cơ chế cải tiến; không tiếp tục gọi chúng là test
chưa từng được sử dụng. Source pools vẫn dùng chung giữa train/validation/test.

## 2. Đánh giá lại 5 checkpoint trên 30 layout

[Raw episodes](../../target/week12-20261001/evaluate/episodes.csv),
[summary theo learning seed](../../target/week12-20261001/evaluate/summary.csv),
[đối chiếu kết quả server](../../target/week12-20261001/evaluate/original_parity.csv).

**600/600 same-layout records khớp** slots và reason, chênh lệch seconds < 1e-6.
Kết quả unseen rerun cũng khớp bảng console server người dùng cung cấp. Đây là
raw kết quả chạy lại local, không giả làm các folder evaluation cũ trên server.

| Policy | Layout42: mean slots | 30 cấu hình mới: mean slots |
| --- | ---: | ---: |
| DQN | 17,80 | 10,00 |
| Oldest Data | 17,00 | 18,83 |
| Round Robin | 10,00 | 10,10 |
| Random | 10,07 | 10,00 |

DQN same-layout run means: 18, 17, 18, 18, 18; sample SD giữa 5 run means = 0,447.
Trên unseen, cả 5 model có mean10 và SD giữa 30 episodes = 0. Baseline SD giữa
30 layout/task pairs: Oldest Data5,760; Round Robin0,305; Random0. Baseline chỉ
lấy learning_seed0 khi tổng hợp, không nhân số mẫu lên5.

Trên 30 cặp case, mean của 5 DQN checkpoint thấp hơn Oldest Data **8,833 slot**:
thua28, hòa2, thắng0. Bootstrap ghép cặp theo 30 layout/task pairs, 10.000 lần,
RNG123: khoảng percentile95% cho chênh lệch DQN−Oldest là **[−10,867; −6,867]**.
Đây là mô tả bất định thăm dò, có điều kiện trên 5 checkpoint cố định; không
phản ánh đầy đủ bất định khi retrain và không phải kiểm định trên final test mới.

## 3. Trace giải thích điều gì xảy ra?

Toàn bộ 150 DQN unseen episodes dừng ở slot10 vì **data age**, không do hết pin.
Tất cả 1.500 slot dài600s. Có656 trường hợp thiết bị vi phạm age, tính theo
device–episode; đây không phải656 thiết bị vật lý độc lập:

- 624 trường hợp chưa từng nằm trong vùng phục vụ tại các điểm UAV chọn.
- 32 trường hợp có vào vùng phục vụ nhưng không hoàn thành truyền dữ liệu.
  Tổng58 candidate-slot tương ứng đều có thời điểm upload xong dự kiến vượt
  thời điểm kết thúc slot; không có trường hợp trong nhóm này đã upload xong
  rồi chỉ bị CPU chặn. Vào vùng phủ sóng không đảm bảo hoàn thành trước cap.
- 340 trường hợp có kết nối mặt đất,316 mất kết nối. Có kết nối không đảm bảo
  cập nhật thành công: mixed đòi hỏi hoàn thành xử lý local; công việc quá cap
  bị bỏ ở cuối slot.

Ba case minh họa dùng checkpoint seed0; case cuối được chọn vì Oldest Data có
lifetime cao nhất, nên không coi là mẫu đại diện ngẫu nhiên:

| Layout seed | DQN / Oldest slots | Điều quan sát được |
| --- | --- | --- |
| 2.000.000 | 10 / 18 | DQN chọn `5 8 8 8 8 8 11 8 10 2`; device9 không được phủ sóng, local cần tối thiểu1.023s > cap600s; age lên10 |
| 2.000.001 | 10 / 13 | Devices3,4,6,7,9 đều hết hạn dữ liệu, chưa từng được phủ sóng. Device3/9 mất kết nối; device4/6/7 có kết nối nhưng local quá chậm |
| 2.000.025 | 10 / 31 | DQN bỏ lỡ devices0,3,4,7,9; Oldest cập nhật được lâu hơn và cuối cùng hết pin UAV |

Ví dụ [slots](../../target/week12-20261001/evaluate/traces/s0/unseen/000-DQN/slots.csv),
[device history](../../target/week12-20261001/evaluate/traces/s0/unseen/000-DQN/devices.csv),
[workload](../../target/week12-20261001/evaluate/traces/s0/unseen/000-DQN/dataset-tasks.csv).

Kết luận được hỗ trợ: policy hiện tại không duy trì cập nhật cho các thiết bị
cần hỗ trợ trong những case này. **Chưa chứng minh** điều đó chỉ do thiếu tọa
độ, reward, thiếu training steps hay architecture. Các nguyên nhân này cần
đối chứng thay đổi từng yếu tố.

## 4. Đổi nhãn ID có kiểm soát

Giữ nguyên Java layout, task sampling, pin, hardware, outage và CPU tie-breaking.
Chỉ đổi thứ tự cặp `(battery, age)` đưa vào mạng, rồi giải mã action trở lại
device ID vật lý. Như vậy dữ liệu của một thiết bị vẫn đi cùng chính thiết bị đó.

15/15 identity controls khớp canonical action sequence và lifetime. Với reverse
và4 shuffle cố định101–104:

| Cấu hình vật lý | Trước đổi nhãn | Sau đổi nhãn: 5 model × 5 permutation |
| --- | ---: | ---: |
| Layout42 | 17,80 slot | 10,00 slot; 25/25 action sequences thay đổi |
| Layout2.000.000 | 10,00 | 10,00; 25/25 sequences thay đổi |
| Layout2.000.001 | 10,00 | 10,00; 25/25 sequences thay đổi |

[Episodes](../../target/week12-20261001/permutation/episodes.csv),
[phép hoán đổi](../../target/week12-20261001/permutation/orders.json).

Đã chứng minh **checkpoint nhạy với cách đánh số thiết bị** trên các phép đổi
nhãn đã thử. Chưa chứng minh “học thuộc ID là nguyên nhân duy nhất” hoặc tính
chất này vi phạm yêu cầu paper: policy MLP theo index, huấn luyện trên một cấu
hình cố định, vốn không được đảm bảo bất biến dưới permutation.

## 5. Runtime và complexity

Máy đo: AMD Ryzen7 5800HS, 8 cores/16 logical CPUs, RAM25.131.409.408 bytes
(khoảng23,41GiB); Windows build26200; Python3.11.9; Torch2.9.1+cu126 chạy **CPU
1 thread**; SB3 2.6.0; NumPy2.4.2; Java17. Không training/build đồng thời lúc đo.
Đây là máy local, không phải hardware server dùng để train5 model cũ.

Inference: cùng512 observations,128 calls warm-up,7 block ×512 calls/policy/model.
DQN17.920 calls từ5 model; mỗi baseline3.584 calls. Timer overhead không trừ.
Các baseline đang là Python implementation; không dùng bảng này để so Java
baseline với PyTorch hoặc suy ra bảo đảm hard real-time.

| Policy | Chọn action median / p95 (µs) | Bridge step median (ms) | Java handlers median (ms) | Episode gồm reset median (ms) |
| --- | ---: | ---: | ---: | ---: |
| DQN | 247,6 / 362,4 | 0,5372 | 0,1439 | 11,338 |
| Oldest Data | 3,3 / 7,5 | 0,2895 | 0,0379 | 6,138 |
| Round Robin | 0,5 / 1,1 | 0,3650 | 0,0646 | 4,393 |
| Random | 2,1 / 3,8 | 0,2583 | 0,0354 | 3,252 |

Bridge step gồm IPC, serialization, Python wrapper và Java; handler là phần
nằm trong bridge step, **không cộng hai cột này**. Handler bỏ thời gian đợi
Python chọn action, nhưng không bao phủ engine dispatch. Trace tắt lúc đo;
episode không bao gồm lưu trace, load model hoặc JVM startup. Episode timing
dùng50 DQN episodes và10 mỗi baseline sau warm-up; policies đi qua số slot và
state khác nhau nên không diễn giải thành phép so sánh kernel cùng đầu vào.
Đo tách inference mới dùng cùng observation pool.

Khởi động JVM/load dataset/reset đầu khoảng3,96–6,27s. Model load lần đầu2,612s,
các lần sau11,3–13,9ms trong cùng Python process. Năm runtime DQN model có median
inference riêng209,5–299,25µs. Tất cả là số đo một phiên, chịu jitter máy/OS.
Không nhầm milliseconds thực thi với seconds mô phỏng hoặc thời gian training.

[Policy timing](../../target/week12-20261001/runtime/policy_summary.csv),
[step timing](../../target/week12-20261001/runtime/step_times.csv),
[episode timing](../../target/week12-20261001/runtime/episode_times.csv),
[startup](../../target/week12-20261001/runtime/startup.csv).

Đặt N thiết bị, h hidden width, J CPU jobs/slot, I số lần bisection:

| Thành phần | Time complexity | Giải thích |
| --- | --- | --- |
| Random / Round Robin | O(1) | Riêng chọn action, không gồm đọc/tạo observation |
| Oldest Data | O(N) | Quét ages; implementation tạo danh sách tie-breaking O(N) memory |
| DQN inference | O(Nh + h²) | Mạng2N→h→h→N; hiện24→64→64→12 có6.540 tham số |
| Synthetic kernel/slot | O(N) | Quét thiết bị, năng lượng, age; không tính trace I/O |
| Mixed kernel/slot | O(N + J log J + NJ + IJ) | Sort FIFO arrivals; `deviceFinish` quét J cho từng device; tìm cạn pin quét J tối đaI=80 lần |
| DQN training | O(T·C_env + G·B·P + chi phí validation) | T steps, G optimizer updates, batchB, P network parameters |

Replay memory xấp xỉ O(MN), M là buffer capacity; network O(P).
N hiện **hard-code12**, nên đây là phân tích từ source, chưa phải thực nghiệm
scalability hoặc chứng minh bài toán NP-hard. Runtime training+validation cũ
trung bình2.259,83s/model trên server là phép đo khác với inference local.

## 6. Sensitivity: cap và chi phí xử lý

5 frozen DQN ×3 task seeds trên layout42; các baseline ghép cùng3 task seeds.
Hai unseen layouts cũng có trong [raw episodes](../../target/week12-20261001/sensitivity/episodes.csv)
và [summary](../../target/week12-20261001/sensitivity/summary.csv).

| Cấu hình | DQN slots | DQN simulated seconds | Oldest slots | Oldest simulated seconds |
| --- | ---: | ---: | ---: | ---: |
| Cap300s | 19,40 | 5.757,53 | 33,00 | 9.659,80 |
| Cap600s mặc định | 17,80 | 10.177,30 | 17,00 | 9.659,91 |
| Cap900s | 11,80 | 10.143,27 | 11,00 | 9.659,94 |
| Local rate×0,5 | 17,80 | 10.169,80 | 17,00 | 9.659,91 |
| Local rate×2 | 16,20 | 9.310,35 | 17,00 | 9.659,91 |

Cap300 làm DQN tăng slot nhưng giảm thời gian sống tính bằng giây; thứ hạng với
Oldest cũng đổi. Đổi cap còn đổi thời hạn10slot theo thời gian thực, lượng công
việc phát sinh và tỷ lệ hoàn thành. Vì vậy **không so slots giữa các cap như
một thước đo thời gian có cùng đơn vị**. Đây là thay giả định môi trường, không
phải đánh giá checkpoint đã retrain tối ưu cho từng cap.

Trên layout42, image MI×0,5/×2 và Alibaba workload×0/×5 đều giữ DQN17,8slot;
UAV compute energy vẫn thay đổi: image MI×0,5 →1.522,16J; default2.402,98J;
image MI×2 →4.164,64J; background0 →1.761,65J; background×5 →4.968,32J.
Không đổi lifetime không chứng minh hệ thống không phản ứng với dataset.
Đây là năng lượng **compute**, không phải tổng bay+hover+compute.

Hai layout mới cho DQN10slot ở đa số cấu hình; cap900 làm layout2.000.001 giảm
còn8,2slot, local rate×2 làm layout2.000.000 tăng10,4slot. Lưới nhỏ không đủ để
loại trừ ảnh hưởng compute trong toàn bộ miền workload.

## 7. Pilot synthetic–mixed cùng ngân sách

Đã hoàn tất cả 6 run; protocol tại
[`pilot/protocol.json`](../../target/week12-20261001/pilot/protocol.json).
Mỗi run20.000 steps,4.975 optimizer updates, learning seeds0/1/2; layout42;
reward paper, cùng DQN hyperparameters, validation5 episodes mỗi5.000steps.
Best chỉ chọn trên validation; test30 task seeds same-layout và30 unseen pairs.
Epsilon decay vẫn 35% nhưng của 20k, không phải lịch 350k bước của run 1m.

| Workload | DQN same-layout: 3 run means | DQN unseen: 3 run means | Oldest same / unseen |
| --- | --- | --- | --- |
| Synthetic | 17 / 17 / 17 | 10 / 10 / 10 | 17,00 / 20,27 |
| RescueNet + Alibaba | 17 / 17 / 17 | 10 / 10 / 10 | 17,00 / 18,83 |

Mỗi run có 240 test records: 30 cases × 2 chế độ × 4 policies; tổng 1.440 records.
Không nhân baseline lặp giữa 3 learning seeds thành mẫu mới. Best của cả 6 run
được chọn tại bước 5.000: validation sau đó không vượt best; evaluator dùng best,
không phải mặc định final ở bước 20.000. Training vẫn hoàn tất 20.000 steps/run.
Training+validation local mất 30,67–43,19s/run; toàn stage gồm evaluation khoảng
265,44s. Không so trực tiếp tốc độ này với server khi khác phần cứng/ngân sách.

[Summary](../../target/week12-20261001/pilot/summary.csv),
[completion](../../target/week12-20261001/pilot/complete.json).

Hiện tượng suy giảm zero-shot cũng xuất hiện ở synthetic trong pilot này,
không chỉ ở extension RescueNet–Alibaba. Chưa đủ để suy ra synthetic DQN train
1 triệu bước cũng thất bại, hoặc kết luận dataset không có ảnh hưởng. Synthetic
và mixed khác cả workload, CPU và quy tắc completion, nên đây là đối chứng hai
chế độ tổng thể, không phải ablation chỉ thay dữ liệu nguồn.

## 8. Kết luận nào được phép dùng trong slide?

- Random/Round Robin không chủ động xét battery/age; trong benchmark này thường
  không giữ được cập nhật10slot. Không kết luận heuristic nói chung đều yếu.
- Oldest Data là đối chứng mạnh trên cấu hình mới, nhưng không trực tiếp xét
  chi phí bay/xử lý. Hết pin dưới Oldest không tự chứng minh một policy khác
  chắc chắn tiết kiệm hơn; cần cost-aware đối chứng trên cùng case.
- DQN hiện tại có lợi nhỏ ở cấu hình huấn luyện, nhạy với relabeling và giảm
  hiệu quả zero-shot. Đây là điểm yếu được xác nhận của checkpoint triển khai.
- Objective gốc vẫn là lifetime theo slot dưới ràng buộc battery/data age;
  reward scalar không phải objective đa mục tiêu energy/latency/DVR.
- Bộ mixed là extension: finite CPU, completion-based age, cap/drop và chi phí
  ánh xạ từ dataset cần công bố; RescueNet chưa được chạy inference để đo độ
  chính xác mô hình thị giác. Alibaba chỉ là pool1000 task đủ điều kiện.

Đủ để đề xuất và kiểm chứng một cơ chế cải tiến có mục tiêu. Hướng ưu tiên là
policy xét **độ khẩn cấp cập nhật + khả năng hoàn thành + chi phí phục vụ**,
đối chiếu Oldest Data; nếu dùng DRL, cần tách thí nghiệm multi-layout training,
observation bổ sung và architecture không phụ thuộc ID. Không thay đồng thời
tất cả rồi quy lợi ích cho một cơ chế. Giữ test mới độc lập cho tuần3–6.

Còn thiếu để đánh giá **phương pháp paper gốc nói chung**: synthetic cùng ngân
sách1m qua nhiều learning seeds, PPO/A2C đối chứng phù hợp, đối chiếu source tác
giả/quy ước radio-completion, thêm layout train/test độc lập và kiểm soát riêng
position/hardware/outage. 20–30 learning seeds, full SOTA và scalability không
phải đã hoàn thành trong gói tuần1–2 này.

## 9. Validation và chạy lại

- Maven:38 tests pass,0 failures/errors, gồm4 test mới cap/rate/timer.
- Python:8 integration tests pass có raw datasets;2 test mới pass về relabeling
  và timer cumulative/transition invariance.
- 600 records parity server pass;15 identity controls pass.
- Kiểm tra artifact: đủ 1.200 evaluation records, 648 sensitivity records,
  90 permutation traces và 1.440 pilot test records; 40 case default sensitivity
  ghép được với evaluation khớp action/slots/reason/seconds. Metrics hữu hạn,
  không có truncation; timer Java không vượt bridge step tương ứng.
- Không sửa raw data hoặc checkpoint gốc; default cap600/rate1 giữ hành vi cũ.
- Raw outputs nằm trong `target` được ignore; source runner và báo cáo ở ngoài
  `target` để version-control. Các link raw output trong báo cáo chỉ mở được ở
  checkout đã có kết quả local; dữ liệu/checkpoint không được upload cùng source.

Kế hoạch tiếp theo: [NEXT_STEPS.md](NEXT_STEPS.md).

Lệnh tái chạy trong [DRL.md](DRL.md#chẩn-đoán-tuần-12).
Tổng hợp máy đọc được: [`analysis.json`](../../target/week12-20261001/analysis.json).
