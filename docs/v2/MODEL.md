# Mô hình v2: offloading + scheduling với UAV di chuyển

Đặc tả cho package `uav.mec`. Code phải khớp từng mục; khi đổi mô hình, sửa file này trước.
Giá trị tham số dưới đây là **giá trị khởi điểm**; giá trị khóa sau hiệu chuẩn ghi trong
[CALIBRATION.md](CALIBRATION.md). Cột "nguồn": **P** = paper (xem
[bảng paper](../v1-diagnosis/README.md#paper-tham-khảo-cho-v2)), **Đ** = đo trong repo, **G** = giả định.

## 1. Hệ thống

- 1 UAV mang một máy tính edge (1 CPU), bay theo **quỹ đạo cho trước**, độc lập với mọi quyết định
  offloading/scheduling. Quỹ đạo không bị upload hay hàng đợi giữ lại (khác v1, xem chẩn đoán D1).
- N thiết bị mặt đất cố định, mỗi thiết bị có 1 CPU và hàng đợi riêng. Vị trí và loại thiết bị
  sinh từ `layout_seed`.
- Thời gian liên tục, mô phỏng theo sự kiện. Mọi tốc độ (CPU, đường truyền) không đổi giữa hai sự kiện.

| Tham số | Khởi điểm | Nguồn |
|---|---|---|
| Vùng | 600 m × 600 m | G |
| Số thiết bị N | 10 | G |
| Độ cao UAV H | 100 m | G (giá trị hay gặp trong paper UAV-MEC; chưa đối chiếu toàn văn) |
| Horizon | cửa sổ sinh task + deadline lớn nhất | — |

### 1.1 Quỹ đạo

| Loại | Mô tả |
|---|---|
| `STATIC` | Hover tại tâm vùng |
| `CIRCLE` | Bay tròn quanh tâm, bán kính R, tốc độ V không đổi, bắt đầu ở góc 0 |

Khởi điểm: `CIRCLE`, R = 200 m, V = 10 m/s (chu kỳ ≈ 126 s). `STATIC` dùng làm đối chứng.

### 1.2 Năng lượng bay (sổ nền)

Công thức Zeng et al. 2019, Eq. (6):

P(V) = P₀(1 + 3V²/U_tip²) + Pᵢ(√(1 + V⁴/(4v₀⁴)) − V²/(2v₀²))^½ + ½·d₀·ρ·s·A·V³

Table I: W = 100 N, ρ = 1,225 kg/m³, s = 0,05, A = 0,79 m², Ω = 400 rad/s, R = 0,5 m, U_tip = 200 m/s,
v₀ = 7,2 m/s, d₀ = 0,3, δ = 0,012, k = 0,1. P₀ = (δ/8)ρsAΩ³R³ ≈ 580,65 W và
Pᵢ = (1+k)W^1,5/√(2ρA) ≈ 790,67 W do mình tính theo Eq. (61); paper không in hai số này.
Hover P(0) ≈ 1371 W; P(10 m/s) ≈ 1108 W. Pin UAV 1,6 MJ (P, Azfar Table 1).

## 2. Thiết bị

Ba loại, trộn theo trọng số. Tốc độ CPU đo bằng **Gcycle tương đương workstation mỗi giây** (Gc/s):
1 Gc/s = tốc độ của một luồng CPU workstation dùng để đo DeepLab (mục 3).

| Loại | Trọng số | Tốc độ (Gc/s) | Công suất bận (W) | Idle (W) | Nguồn |
|---|---:|---:|---:|---:|---|
| PI3B | 1/3 | 0,25 | 1,90 | 1,69 | Công suất: P (Azfar Table 2, DNN). Tốc độ: G |
| PI4B | 1/3 | 0,50 | 3,234 | 2,65 | như trên |
| JETSON_NANO | 1/3 | 0,60 | 2,421 | 2,82 | như trên |
| UAV | — | 4,0 | 30 | — | G |

- Công suất bận là **phần tăng thêm** khi CPU chạy (sổ biên); idle thuộc sổ nền.
- Công suất điện khi phát (TX) 1,0 W, khi thu (RX) 0,5 W cho thiết bị; UAV phát 2,0 W, thu 0,5 W (G).
  Công suất bức xạ dùng trong công thức kênh nằm ở mục 4.
- Pin thiết bị U(50, 80) kJ (P, Azfar Table 1). Thiết bị hết pin: mọi task của nó chưa xong bị drop,
  task mới của nó bị drop ngay.

## 3. Task

Mỗi thiết bị sinh task theo quá trình Poisson, tốc độ như nhau λ = Λ/N.
Mỗi task có: lớp, thiết bị nguồn, thời điểm đến, dữ liệu vào (byte), khối lượng tính thật và ước lượng
(Gcycle), dữ liệu kết quả (byte), deadline tuyệt đối, mức ưu tiên.

| Lớp | Tỉ lệ | Dữ liệu vào | Khối lượng (Gcycle) | Kết quả | Deadline sau khi đến | Ưu tiên |
|---|---:|---|---|---|---|---:|
| DETECT | 0,40 | ảnh thu nhỏ: lognormal mean 0,3 MB, CV 0,3 | lognormal mean 0,3, CV 0,2 | 2 kB | U(1, 3) s | 3 |
| SEGMENT | 0,45 | ảnh RescueNet gốc: rút ngẫu nhiên từ 449 kích thước file thật | lognormal mean 2,1, CV 0,2 | 50 kB | U(8, 20) s | 2 |
| MAP | 0,15 | lognormal mean 4 MB, CV 0,3 | lognormal mean 10, CV 0,3 | 200 kB | U(30, 90) s | 1 |

- **Nguồn khối lượng SEGMENT (Đ):** DeepLabV3–MobileNetV3-Large đo 0,524 s/ảnh trên một luồng workstation
  ([TASK_CALIBRATION](../history/v1/TASK_CALIBRATION.md)) → quy ước 2,1 Gcycle ở 4 Gc/s ≈ 0,52 s.
  CV 0,2 phản ánh P95/mean = 1,22 của phép đo. DETECT, MAP và mọi deadline là **G**.
- **Ước lượng:** policy chỉ thấy khối lượng ước lượng = thật × (1 + e·u), u ~ U(−1, 1), e = sai số
  tương đối (0 hoặc 0,4). Kernel dùng khối lượng thật.
- Tải được khai báo bằng **ρ_UAV** = Λ·E[Gcycle]/f_UAV, tức hệ số sử dụng CPU UAV nếu mọi task được offload.
  E[Gcycle] = 0,4·0,3 + 0,45·2,1 + 0,15·10 = 2,565.

Mỗi luồng ngẫu nhiên (đến, lớp, kích thước, khối lượng, sai số, deadline) dùng seed riêng, suy ra bằng
SHA-256 từ (task_seed, tên luồng). Đổi một luồng không làm đổi luồng khác. Bố trí thiết bị dùng
`layout_seed` riêng.

## 4. Truyền thông

Kênh LoS tự do, mô hình phổ biến của UAV-MEC (theo trí nhớ, ví dụ Hu et al. 2019; chưa đối chiếu toàn văn,
nên xếp là G):

g(d) = β₀ / d^α, d = khoảng cách 3D, β₀ = −50 dB, α = 2.

Tốc độ một liên kết khi K liên kết cùng chiều chia đều băng thông B (FDMA):

r = (B/K) · log₂(1 + p·g(d) / (N₀·B/K)).

| Tham số | Khởi điểm | Nguồn |
|---|---|---|
| Băng thông uplink B_up | 20 MHz | P (Azfar Table 1) |
| Băng thông downlink B_dl | 10 MHz | G |
| Công suất bức xạ thiết bị p_dev | 0,1 W | P (Azfar Table 1) |
| Công suất bức xạ UAV p_uav | 1,0 W | G |
| Mật độ nhiễu N₀ | −160 dBm/Hz (≡ −100 dBm trên 1 MHz) | P / G |
| Khối fading | 1 s: khoảng cách lấy tại đầu mỗi khối 1 s | G |

- Tốc độ mỗi liên kết được tính lại khi K đổi hoặc sang khối mới.
- Task offload đi qua: uplink → hàng đợi UAV → CPU UAV → downlink kết quả. Chỉ hoàn thành khi kết quả về tới thiết bị.
- Năng lượng: thiết bị TX trong uplink, RX trong downlink; UAV RX trong uplink, TX trong downlink.
- Chế độ `IDEAL` (chỉ dùng cho cổng G5): truyền tức thời, không tốn năng lượng.

## 5. Tính toán và hàng đợi

- Mỗi CPU (thiết bị hoặc UAV) chạy một task một lúc, work-conserving.
- `preemptive = false`: chỉ chọn task mới khi CPU rảnh.
- `preemptive = true` (preemptive-resume): mỗi khi có task mới vào hàng đợi của CPU, scheduler chọn lại trong
  {task đang chạy} ∪ {hàng đợi}; task bị ngắt giữ phần đã chạy. Không tính chi phí chuyển ngữ cảnh (G).
- Cùng một scheduler áp dụng cho CPU UAV và mọi CPU thiết bị.
- **Deadline cứng:** tới deadline, task chưa xong bị hủy ở bất kỳ giai đoạn nào (chờ, upload, chạy, downlink).
  Phần năng lượng đã tiêu vẫn được tính.

## 6. Quyết định

| Quyết định | Lúc | Lựa chọn | Thông tin được thấy |
|---|---|---|---|
| Offloading | Task đến | LOCAL / UAV / REJECT | Task (lớp, byte, khối lượng **ước lượng**, deadline, ưu tiên); hàng đợi local và UAV (khối lượng ước lượng còn lại); số uplink đang chạy; khoảng cách hiện tại; pin; trạng thái sống của UAV |
| Scheduling | CPU rảnh hoặc có task mới (preemptive) | 1 task trong tập sẵn sàng | Các task sẵn sàng tại CPU đó (khối lượng ước lượng còn lại, deadline, ưu tiên, thời điểm sẵn sàng) |
| Admission | Ngay trước khi scheduler chọn | Giữ / drop | Như scheduling |

Policy **không** thấy task tương lai, khối lượng thật, hay vị trí UAV tương lai.
Quyết định offloading không đảo ngược. UAV hết pin: offloading buộc là LOCAL.

### Dự báo dùng chung (`Forecast`)

Ước lượng thời điểm xong nếu task chạy local hoặc UAV, giả định không có task mới và kênh giữ như hiện tại:

- local: t + (khối lượng chờ local + khối lượng task) / f_dev
- UAV: max(t + T_up, t + khối lượng chờ UAV / f_UAV) + khối lượng task / f_UAV + T_dl,
  với T_up, T_dl tính với K+1 liên kết ở khoảng cách hiện tại.

Năng lượng biên dự báo: local = c·P_busy/f_dev; UAV = c·P_busy,UAV/f_UAV + T_up·(TX_dev + RX_UAV) + T_dl·(TX_UAV + RX_dev).

## 7. Chỉ số

Theo [EVALUATION_METRICS.md](../../PureEdgeSim/uav/EVALUATION_METRICS.md), với hai thay đổi đã ghi trong AGENTS.md.

| Chỉ số | Định nghĩa |
|---|---|
| DVR | 1 − số task xong đúng hạn / số task sinh ra. Drop, reject, hết pin, chưa xong đều là vi phạm. Báo cả theo lớp |
| J biên / task đúng hạn | Σ năng lượng biên mọi nút / số task đúng hạn. Không có task đúng hạn: NA |
| J tổng / task đúng hạn | (biên + bay + idle) / số task đúng hạn |
| Latency | Kết quả về tới thiết bị − lúc đến, chỉ trên task hoàn thành. Trung bình và P95 (nearest rank) từng episode |
| Lifetime UAV | Thời điểm hết pin, hoặc ≥ horizon (censored) |
| Phụ | Tỉ lệ offload, độ dài hàng đợi UAV trung bình theo thời gian và lớn nhất, năng lượng biên theo nút |

Không có tải nền: background DVR = không có (unavailable).
Tổng hợp nhiều episode: DVR, latency trung bình theo episode; năng lượng/task = tổng trên tổng.
So sánh hai policy: hiệu ghép cặp theo (layout, seed), khoảng tin cậy bootstrap 95%.

## 8. Phân vùng seed

| Vai trò | Layout seed | Task seed |
|---|---|---|
| Development (hiệu chuẩn, chọn tham số) | 0–4 | 0–29 |
| Evaluation (kết luận cuối, chỉ mở một lần ở P5) | 100–104 | 1000–1029 |

## 9. Ngoài phạm vi

Placement/tối ưu quỹ đạo, cache, nhiều UAV, chia nhỏ task (partial offloading), nhiễu giữa liên kết,
chi phí chuyển ngữ cảnh, đo điện năng thật.
