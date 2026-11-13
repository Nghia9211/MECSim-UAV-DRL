# Mô hình v2.1: các đòn bẩy làm bài toán khó hơn

Chỉ ghi phần khác [MODEL.md](MODEL.md) (v2.0). Mọi đòn bẩy **tắt mặc định**: cấu hình không bật đòn bẩy nào
phải cho trace giống hệt v2.0 từng bit. Lý do chọn đòn bẩy: [HEADROOM.md](HEADROOM.md) mục 4.
Nguồn: **P** = paper đã đối chiếu bản gốc, **G** = giả định có lý do ứng dụng, chưa có nguồn số liệu.

## L1. Kênh LoS xác suất (`radio.mode = "PLOS"`)

Mozaffari, Saad, Bennis, Debbah, *Drone Small Cells in the Clouds*, arXiv 1509.01655 (2015), Eq. (1)–(4) và Table I,
đã đọc từ PDF ngày 13/11/2026. Đây là mô hình suy hao trung bình (dB), tất định theo vị trí:

- góc ngẩng θ = atan(H / khoảng cách ngang), tính bằng độ;
- P_LoS(θ) = 1 / (1 + α·exp(−β(θ − α))), P_NLoS = 1 − P_LoS;
- L(dB) = 20·log₁₀(4π·f_c·d / c) + P_LoS·ξ_LoS + P_NLoS·ξ_NLoS, với d là khoảng cách 3D;
- hệ số kênh g = 10^(−L/10), thay cho β₀·d^(−α) của v2.0; công thức Shannon và chia băng thông giữ nguyên.

| Tham số | Giá trị | Nguồn |
|---|---|---|
| Môi trường | đô thị | P (Table I, môi trường duy nhất có số) |
| f_c | 2 GHz | P |
| ξ_LoS / ξ_NLoS | 1 dB / 20 dB | P. Table I in "ξ_LoS" hai lần; ngữ cảnh Eq. (2) cho thấy dòng thứ hai là ξ_NLoS |
| α / β | 9,6 / 0,28 | P |
| Nhiễu, công suất phát | giữ như v2.0 (−160 dBm/Hz; 0,1 W / 1 W) | v2.0 |

Hệ quả (tính tay, H = 100 m): ngay dưới UAV (d ≈ 100 m) suy hao ≈ 79,5 dB, mạnh hơn v2.0 (90 dB);
cách 1000 m theo phương ngang suy hao ≈ 117,9 dB, yếu hơn v2.0 (110 dB). Kênh phụ thuộc vị trí mạnh hơn nhiều.

## L2. Băng thông

`radio.uplink_hz` ∈ {20 (v2.0), 5, 2} MHz; downlink luôn bằng một nửa uplink như v2.0. **G**: hạ tầng hỏng, dùng băng khẩn cấp hẹp.

## L3. Diện tích vùng

`area_m` ∈ {600 (v2.0), 1200, 2000} m. Bán kính quỹ đạo CIRCLE = area/3 (v2.0: 200/600). 2000 m là cạnh vùng trong
Table I của Mozaffari et al. (**P** cho giá trị 2000, **G** cho việc áp vào bài toán này).

## L4. Điểm nóng (`hotspots`)

`hotspots = {"device_share": 0.3, "task_share": 0.7}`: 30% thiết bị (làm tròn lên, chọn bằng luồng seed `layout/hotspot`) sinh 70%
số task; các thiết bị còn lại chia đều phần còn lại. Thiết bị điểm nóng đặt gần nhau: tâm cụm rút ngẫu nhiên, thiết bị nằm trong
bán kính area/8 quanh tâm. **G**: thiệt hại tập trung theo cụm.

## L5. Đến theo đợt (`bursts`)

Quá trình Poisson điều biến hai trạng thái. Trạng thái cao: tốc độ ×3, thời gian ở lại trung bình 20 s (phân bố mũ);
trạng thái thấp: tốc độ ×0,5, trung bình 80 s. Tỉ lệ thời gian ở trạng thái cao = 0,2, nên tốc độ trung bình dài hạn
= 0,2·3 + 0,8·0,5 = 1,0 lần Λ, không đổi tải trung bình. Luồng seed riêng `task/burst`. **G**: dư chấn, đội cứu hộ tới theo đợt.

## L6. Tải theo công suất toàn hệ thống (`rho_system`)

Λ = ρ_sys · (f_UAV + Σ f_thiết bị) / E[Gcycle], tính trên layout của episode. ρ_sys ∈ {0,8; 1,0}.
Để so sánh: v2.0 "overload" (ρ_UAV = 1,3) tương ứng ρ_sys ≈ 0,6. **G**: không có nguồn cho mức tải; đây là cách định nghĩa tải đúng
khi CPU thiết bị cũng phục vụ được.

## L7. Pin ban đầu (`initial_charge`)

Mỗi thiết bị bắt đầu với tỉ lệ pin cho trước ∈ {1,0 (v2.0); 0,05}. Ở 5%: 2,5–4 kJ, so với idle 1,7–2,8 W trong 690 s ≈ 1,2–1,9 kJ.
**G**, dựa trên bối cảnh mất điện lưới của paper Azfar.

## Quỹ đạo STATIC tại điểm bất kỳ

`trajectory = {"type": "STATIC", "x_m": .., "y_m": ..}`; mặc định là tâm vùng như v2.0. Dùng cho cổng G7.

## Phiên bản

Mọi run ghi `model_version` = "v2.1" khi bật bất kỳ đòn bẩy nào, ngược lại "v2.0".
