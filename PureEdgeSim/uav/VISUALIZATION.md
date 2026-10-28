# Cửa sổ so sánh thuật toán

Từ thư mục gốc MECSim, double-click **`Open-UAV-Dashboard.cmd`**.
Dashboard mở trong cửa sổ Edge riêng và chỉ đọc kết quả hiện có; không train lại.
Nếu không có Edge, launcher dùng trình duyệt mặc định.

Hoặc chạy:

```powershell
.\.venv-drl\Scripts\python.exe scripts\open_uav_dashboard.py
```

Launcher in URL localhost và dùng lại server nếu còn hoạt động. Port được chọn
tự động, vì vậy URL có thể đổi sau khi khởi động lại. Xem URL hiện tại trong
`target/uav-dashboard/server.json`. Server chỉ lắng nghe trên `127.0.0.1`.

## Thao tác

1. Chọn bộ thí nghiệm, cấu hình, checkpoint DQN và chỉ số cần so sánh.
2. Xem mean của DQN, Round Robin, Oldest Data, Random; các chấm là mean từng
   learning/layout seed nếu có. Chúng không phải confidence interval.
3. Đối chiếu best/final trên cùng test case. Best được chọn bằng validation;
   kết quả final không được dùng để chọn model.
4. Chọn learning seed, task seed và thuật toán ở bản đồ. Bật/tắt từng đường,
   nhấn **Phát đường bay**, kéo thanh thời gian, xem pin và vị trí UAV.
5. Nhấn **Xuất bảng CSV** để lấy bảng đang xem. Phần nguồn dữ liệu cuối trang
   ghi phạm vi, đường dẫn nguồn và các giới hạn của thí nghiệm.

Đường bay paper nội suy theo tốc độ 5 m/s rồi hover; không bay chậm đều suốt
slot. Vòng phủ sóng khi hover là bán kính ngang `sqrt(65² − 10²) ≈ 64,2 m`
với độ cao 10 m. Tuổi dữ liệu được giữ theo mốc slot trong trace.

## Kết quả được nạp ngày 24/10/2026

| Bộ thí nghiệm | Nguồn trong `target/` | Dòng kết quả | Trace |
| --- | --- | ---: | ---: |
| Paper · Reward & freshness | `paper-convention-retrain-20261024` | 810 | 810 |
| Paper · 3 learning/layout pairs | `paper-reference-1m-restart-20261023` | 450 | 450 |
| Mobile · Offloading + EDF pilot | `mobile-dqn-smoke-20261023` | 40 | 4 |

Có 1.300 dòng kết quả và 1.264 trace được tham chiếu trong dashboard. Một phần
kết quả REFERENCE được dùng lại giữa các đối chứng; tổng số này không có nghĩa
là 1.300 episode độc lập mới. Heuristic dùng chung chỉ được tính một lần/case
khi tổng hợp, không nhân thêm theo số learning seed DQN.

Hai bộ paper dùng workload synthetic. Bộ mobile là pilot 2.000 bước, không
phải kết quả hội tụ. Chỉ task seed 2000000 của mobile đã lưu trace cho bốn
thuật toán; dropdown bản đồ chỉ cho chọn case đó, còn biểu đồ tổng hợp dùng
đủ 10 case. Không sinh thêm đường bay cho các case thiếu trace.

**Phạm vi chỉ số:** paper hiển thị lifetime và năng lượng UAV. Mobile hiển thị
deadline violation, năng lượng toàn hệ thống, số task hoàn thành đúng hạn và
offloaded. Không gộp hai môi trường vào một bảng xếp hạng. Một episode kết
thúc sớm có thể dùng ít năng lượng hơn do hoạt động ngắn hơn, nên riêng mức
tiêu hao nhỏ không chứng minh thuật toán tốt hơn. Chênh lệch biểu đồ là mô tả,
không phải kết luận kiểm định thống kê.

## Tạo lại và kiểm tra

Builder/launcher chỉ cần Python stdlib; không thêm thư viện vào môi trường train.
Để cập nhật nội dung sau khi có kết quả mới ở những campaign trên:

```powershell
.\.venv-drl\Scripts\python.exe scripts\uav_dashboard.py
```

Sau đó refresh cửa sổ. Để chạy server ở terminal hoặc lấy URL mà chưa mở cửa sổ:

```powershell
.\.venv-drl\Scripts\python.exe scripts\uav_dashboard.py --serve
.\.venv-drl\Scripts\python.exe scripts\open_uav_dashboard.py --no-open
```

Kết quả HTML, CSS, JS, metadata và log chỉ được ghi vào `target/uav-dashboard/`
(đã ignore Git). Raw CSV, model và kết quả train không bị sửa. Các campaign
nguồn cũng nằm trong `target/`, nên checkout mới từ GitHub cần chép kết quả
về trước khi build; dashboard không tự tải dataset hoặc kết quả server.

Source giao diện: `visualization/dashboard.html`, `dashboard.css`, `dashboard.js`.
Source đọc kết quả: `scripts/uav_dashboard.py`.

Browser QA ngày 24/10: **PASS** trên Edge headless; đối chiếu mean với CSV,
các profile/checkpoint/metric, tốc độ di chuyển, playback, coverage, export,
sáng/tối và màn hình rộng 520 px; không có JavaScript page error.
Receipt: `target/uav-dashboard/browser-verification.json`.
Screenshot: `preview-desktop.png`, `preview-dark.png`, `preview-mobile.png`.

Lệnh QA: `node scripts/test-uav-dashboard.cjs` (đọc URL trong `server.json`).
Script cần Playwright và Edge ở máy phát triển (có thể đặt `PLAYWRIGHT_MODULE`
trỏ tới module Playwright đã cài); người chỉ xem dashboard không cần chúng.
