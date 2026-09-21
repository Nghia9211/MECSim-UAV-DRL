# Đánh giá mở rộng PaperSimulation bằng RescueNet + Alibaba

Đây là chế độ đánh giá mở rộng theo yêu cầu ngày 21/09/2026. Cả hai nguồn được
đưa vào **cùng một episode của `PaperSimulation.Manager`**, dùng vị trí UAV,
link rate, pin, outage, state/action và policy chọn thiết bị của paper environment.
Không gọi scheduler của Milestone 5 để thay thế paper environment.

## Chạy

Từ thư mục `uav/MECSim`, dữ liệu đã có sẵn trong `datasets/raw`:

```powershell
# 30 seed x 3 policy x 3 chế độ = 270 episode tại cấu hình 8/8
.\scripts\run-paper-datasets.ps1 -Mode evaluate -Seeds 30 -Offline

# Một episode mixed, seed 42, policy OLDEST_DATA
.\scripts\run-paper-datasets.ps1 -Mode single -Offline

# Kiểm tra độ nhạy với mức tải Alibaba gấp 5
.\scripts\run-paper-datasets.ps1 -Mode evaluate -Seeds 30 -BackgroundScale 5 -Offline
```

`-Offline` dùng dependency Maven đã cache; bỏ cờ này ở máy cần tải dependency.
Có thể đổi `-Powered`, `-Connected`, `-BackgroundTasksPerSlot`. Các số power/comms
là số thiết bị **còn** nguồn/kết nối. Script chứa các giả định thử nghiệm rõ ràng,
không tự suy ra chúng từ ảnh hoặc từ bài báo.

Entry point trực tiếp vẫn là `uav.PaperSimulation` với `-Dpaper.workload=datasets`.
Không đặt cờ này thì synthetic gốc giữ nguyên. `uav.PaperDatasetEvaluation`
là runner chạy nhiều episode trên cùng manager, không phải environment khác.

## Dataset ảnh làm gì?

- Đọc tối đa 449 ảnh JPG/PNG theo tên, kiểm tra kích thước mask nếu cung cấp,
  đo file bytes, dimensions và SHA-256; không sửa file gốc.
- Mỗi slot mỗi thiết bị lấy một ảnh từ pool, lấy mẫu có hoàn lại bằng seed +
  slot + device, độc lập với policy và mức tải nền. Vì vậy không bị giới hạn
  10 task như adapter Milestone 7 cũ.
- Payload upload bằng dung lượng file ảnh nén thực. Local processing vẫn dùng
  `file bytes / tốc độ Table 3`; đây là phép ánh xạ chưa được hiệu chuẩn cho
  ảnh RescueNet, không phải đo hiệu năng inference thật.
- UAV compute demand = `width * height / 1e6 * imageMiPerMegapixel`.
  Ví dụ script chọn 833.333 MI/MP, tức ảnh 12 MP cần 10000 MI. Giá trị này là
  giả định, không phải nhãn hay phép đo từ RescueNet.
- Mask chỉ dùng kiểm tra pairing/kích thước; không suy ra priority hoặc đánh
  giá độ chính xác segmentation. Không tải weights hoặc chạy neural inference.

## Dataset Alibaba làm gì?

- Đọc streaming tối đa 100000 dòng, chọn tối đa 1000 task đầu đủ điều kiện:
  Terminated, một instance, root task, runtime dương, số liệu hợp lệ.
- Mỗi slot lấy mẫu task nền có hoàn lại từ pool, đưa vào CPU UAV ở đầu slot.
  Script mặc định một task/slot. Không replay timestamp gốc, DAG, placement
  cluster hoặc memory pressure. `plan_cpu` là requested CPU, không phải CPU
  utilization đo được. Đây là tải nền **được tạo từ trace**, không full replay.
- Công việc CPU:
  `MI = (end-start) * (plan_cpu/100) * referenceMips * durationScale * backgroundScale`.
  Script mặc định reference=1000 MIPS, durationScale=1, backgroundScale=1.
- `backgroundScale=0` loại tải nền để tạo đối chứng RescueNet-only. So sánh
  RescueNet-only với mixed mới tách riêng được ảnh hưởng của Alibaba.

## Compute, queue, pin và dữ liệu

Một CPU UAV 2000 MIPS trong script, FIFO không preempt. Background sẵn sàng ở
đầu slot; ảnh chỉ vào queue khi upload xong. Job sẵn sàng trước chạy trước,
nếu trùng thời điểm thì thứ tự background, sau đó device index. Không chạy
hai job đồng thời trên CPU này; upload trên các link vẫn có thể song song.
UAV compute draw thêm 20 W khi CPU bận, cộng vào flight/hover 150/80 W.
CPU có thể chạy tải nền trong khi UAV bay. MIPS và 20 W là giả định extension.

Slot chờ local compute, upload và CPU, tối đa 600 giây. **Queue chỉ tồn tại trong
slot**: job chưa xong ở cap bị hủy và log `DROPPED_SLOT_CAP`; nếu episode kết thúc
trước thì log `DROPPED_EPISODE_END`. Không âm thầm coi task đó là hoàn thành,
không carry-over backlog. Đây là lựa chọn hữu hạn theo cap hiện tại; nếu muốn
đánh giá queue dài hạn cần thêm chính sách carry-over/expiry trong nghiên cứu sau.

Khác với synthetic gốc, dataset mode chỉ reset tuổi khi **có kết quả được giao**:

- Task offload: upload và CPU UAV đều xong; relay output coi tức thời.
- Task local: compute xong và thiết bị có kết nối.
- Chưa xong hoặc không chuyển được kết quả: age +1.

Thiết bị trong coverage được offload ngay, không có local fallback khi CPU bị
kẹt. Energy local/TX/standby vẫn dùng các thông số paper environment. Không thêm
mô hình radio UAV/output-link energy chưa hiệu chuẩn. Cạn pin giữa flight hoặc
compute dừng ở thời điểm vật lý đầu tiên, không trừ công việc/điện sau khi chết.

Observation vẫn 24 phần tử (battery fractions + ages), action vẫn 0..11.
Queue và workload không nằm trong observation: đây là giới hạn khi huấn luyện
policy cho tải thay đổi, không tuyên bố state này đầy đủ Markov cho extension.

## Đánh giá và file kết quả

Runner so ba chế độ, cùng seed layout/task/policy:

1. `synthetic`: mô hình gốc (UAV compute không đáng kể).
2. `rescuenet`: ảnh thật, CPU hữu hạn, không Alibaba.
3. `mixed`: cùng ảnh/cấu hình CPU, có Alibaba.

`ROUND_ROBIN`, `OLDEST_DATA`, `RANDOM` vẫn là các policy chọn nơi UAV đến,
không phải FIFO/EDF/PRIORITY. FIFO chỉ là quy tắc cố định bên trong CPU UAV.

Output `target/uav-dataset-evaluation-*/` có:

- `REPORT.md`, `summary.csv`, `episodes.csv`: lifetime slots/seconds, sample SD,
  delivery fraction, compute joules, CPU task completion, truncation và lý do lỗi.
- `source-pools/`: danh mục ảnh kèm SHA-256, các dòng Alibaba gốc được chọn,
  giới hạn scan, config, cách ánh xạ. Source Java được snapshot cùng lần chạy.
- `traces/seed-N/{synthetic,rescuenet,mixed}/POLICY/`: layout, slots, devices.
- Dataset trace thêm `dataset-tasks.csv` (slot/device → source image index,
  input bytes, MI, local time, delivered/latency), `cpu-tasks.csv` (source line
  Alibaba/image index, ready/start/finish tuyệt đối, MI yêu cầu/đã chạy, status),
  `dataset-summary.csv` và config/pool để đọc độc lập.

`planned_start_s`/`planned_finish_s` là lịch **dự kiến**; job bị drop chưa chắc đã
bắt đầu. `executed_mi` là công việc thực sự đã chạy trước khi cap/hết pin.
`mean_delivered_latency_s` chỉ tính task đã giao, task không giao có latency NaN.
Delivery fraction tính trên mọi ảnh sinh ra, gồm local có kết nối và UAV xử lý;
**không phải DVR**, vì môi trường này dùng data age limit chứ không task deadline.

Các episode có lifetime khác nhau nên số task cũng khác nhau. Delivery fraction
trong summary là tổng delivered / tổng submitted, không phải trung bình tỷ lệ mỗi
episode. Cần đọc cùng lifetime, số task và failure reason; không dùng một metric
riêng để khẳng định thuật toán tốt hơn. Synthetic→dataset còn thay đổi compute và
quy tắc completion nên không thể quy toàn bộ chênh lệch cho dữ liệu ảnh.

Đây là đánh giá các heuristic trên môi trường mở rộng của bài; chưa có DQN được
huấn luyện nên chưa thể kết luận thuật toán DQN trong bài hoạt động ra sao trên
RescueNet/Alibaba. Không cần tải dataset mới cho giai đoạn này.

## Kết quả đã kiểm chứng ngày 21/09/2026

Pool thực tế: 449 ảnh kèm mask được kiểm tra; 1000 task Alibaba hợp lệ lấy từ
5303 dòng được scan (37 malformed, 4266 excluded). Các ảnh/row được lấy mẫu có
hoàn lại, không phải duyệt tuần tự toàn bộ dataset trong mỗi episode.

Đã chạy 30 seed 0–29 tại cấu hình powered=8, connected=8, ba policy cho ba chế độ.
Chạy thêm cùng thiết kế với backgroundScale=5: tổng 540 episode (các đối chứng
được lặp lại, không phải 540 mẫu thống kê độc lập). Không episode nào truncation.

| Chế độ | ROUND_ROBIN slots | OLDEST_DATA slots | RANDOM slots |
| --- | --- | --- | --- |
| Synthetic gốc | 11.80 ± 2.11 | 21.00 ± 7.01 | 10.47 ± 1.11 |
| RescueNet, không tải nền | 10.17 ± 0.46 | 19.37 ± 6.88 | 10.00 ± 0.00 |
| RescueNet + Alibaba x1 | 10.17 ± 0.46 | 19.37 ± 6.88 | 10.00 ± 0.00 |
| RescueNet + Alibaba x5 | 10.17 ± 0.46 | 19.30 ± 6.85 | 10.00 ± 0.00 |

Với OLDEST_DATA, compute energy trung bình lần lượt 2046.73 J (RescueNet),
4056.56 J (mixed x1), 9090.99 J (mixed x5). Delivery fraction 36.36%, 36.36%,
36.31%. Alibaba có ảnh hưởng thực đến CPU/energy; lifetime ở mức tải này chủ yếu
vẫn bị local compute, age và pin thiết bị chi phối. Không diễn giải lifetime
gần nhau là tải nền bị bỏ qua, hoặc như bằng chứng hai chế độ tương đương.

Tỷ lệ giao kết quả khá thấp: nhiều ảnh không được UAV phục vụ, local compute
vượt cap hoặc thiết bị không còn liên lạc. Đây là kết quả của ánh xạ/cap hiện tại,
không phải độ chính xác của một mô hình RescueNet. Chưa hiệu chuẩn local Bytes/s
với ảnh nén thực; muốn kết luận hiệu năng thực tế cần đo phần cứng/inference.

Output:

- x1: `target/uav-dataset-evaluation-4501383296327366031/`.
- x5: `target/uav-dataset-evaluation-17485747363257969086/`.
- Single mixed seed 42: `target/uav-paper-9868301130048657298/`, 17 slots,
  dừng do `DEVICE_8_BATTERY`.

Trước khi dọn demo, `mvn -o test`: 62/62 test pass. Sau khi dọn, bộ kiểm thử
hiện tại có 32 test; các test dành riêng cho demo cũ đã được gỡ. Có 7 test kiểm tra queue, compute draw,
age khi CPU chưa xong, giới hạn slot, cạn pin device/UAV giữa công việc và pool
lớn hơn giới hạn adapter cũ. Script kiểm tra độc lập:

```powershell
python scripts/verify-paper-datasets.py target/uav-dataset-evaluation-4501383296327366031
python scripts/verify-paper-datasets.py target/uav-dataset-evaluation-17485747363257969086
```

Cả hai pass: paired layout/ảnh khớp, queue không overlap, executed MI khớp thời
gian CPU và joules, summary khớp task trace, mean/SD được tính lại bằng Python.
