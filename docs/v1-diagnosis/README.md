# Chẩn đoán v1 (P0) — vì sao offloading/scheduling không tạo khác biệt

Ngày 12/11/2026. Chỉ đọc trace có sẵn, không sửa hay chạy lại kernel v1.
Nguồn: `target/workload-v2-baselines-development-20261030` (mixed-v2, 16 scenario × 30 seed × 9 policy = 4.320 episode).

```powershell
.\.venv-drl\Scripts\python.exe scripts\diagnose_v1.py target\workload-v2-baselines-development-20261030 --output docs\v1-diagnosis\diagnosis.json
```

Số liệu đầy đủ: [diagnosis.json](diagnosis.json).

## Kết quả

| Mã | Nghi vấn ban đầu | Kết quả | Kết luận |
|---|---|---|---|
| D1 | UAV đứng yên vì upload đang chạy giữ nó lại | 480/480 episode `CONTACT_GREEDY` chỉ thăm 1 điểm. 5.769/5.769 lần quyết định chọn lại đúng điểm cũ. Chỉ 126/5.769 lần rời điểm bị upload giữ lại, trung vị 1,0 s, tối đa 3,1 s | **Nghi vấn sai.** UAV đứng yên vì điểm số greedy luôn chọn lại điểm hiện tại, không phải vì upload |
| D2 | Chỉ thiết bị ngay dưới UAV offload kịp | 4.847 ảnh offload đúng hạn: trung vị khoảng cách xiên 10,0 m (= độ cao), 93,7% < 15 m, 98,9% < 20 m, tối đa 25 m | **Xác nhận.** Vùng phủ 65 m chỉ là danh nghĩa |
| D3 | Năng lượng gần như hằng số giữa các policy | Hệ số biến thiên năng lượng giữa 9 policy cùng seed: trung vị 1,0%, p90 9,7%. Năng lượng bay/hover chiếm trung vị 85,9% tổng năng lượng | **Xác nhận.** Policy gần như không đổi được năng lượng |
| D4 | EDF/FIFO/SPT chọn cùng task | Khi hàng đợi ≥ 2, ba luật chọn khác nhau ở 55–70% lần. Nhưng tính trên mọi lần dispatch, chỉ 3,2% (EDF) và 6,4% (FIFO) | **Xác nhận** theo nghĩa: scheduler hiếm khi có cơ hội tác động |
| D5 | Hàng đợi UAV hiếm khi ≥ 2 task | Trung vị 1, p90 = 1. Hàng đợi ≥ 2 ở 5,8% (EDF) và 9,1% (FIFO) lần dispatch | **Xác nhận.** Gốc của D4 |

Kết hợp với kết quả đã có trong v1 (đổi CPU UAV 0,5 / 2 / 8 MB/s → DVR 55,78 / 55,40 / 55,69%,
[NEAR_PAPER_SENSITIVITY_RESULTS.md](../history/v1/NEAR_PAPER_SENSITIVITY_RESULTS.md)):
nút thắt của v1 là đường truyền và vị trí UAV, không phải CPU hay thứ tự xếp hàng.

## Tự kiểm tra của script

- D4/D5 tái dựng hàng đợi UAV từ trace. Kiểm tra: với policy dùng EDF, lựa chọn EDF trên hàng đợi tái dựng
  trùng task thật sự được dispatch ở **424/424** lần (hàng đợi ≥ 2); với policy FIFO trùng **736/736** lần.
- D1 đối chiếu tay episode `a250-light-b1600000-e0/seed-1005481242`: đến điểm 11 lúc 45,03 s,
  dwell 30 s, quyết định kế tiếp lúc 75,03 s chọn lại điểm 11. Khớp.

## Hệ quả cho v2

| Phát hiện | Thiết kế v2 |
|---|---|
| D1: lỗi nằm ở policy di chuyển, không ở kernel | v2 giữ UAV di chuyển (theo quyết định của người dùng) nhưng theo quỹ đạo cho trước, độc lập với policy offloading/scheduling. Quỹ đạo không bị upload giữ lại |
| D2: suy hao d⁻⁴ với hệ số -50 dBm cho tốc độ 0,016 Mbps ở 65 m | Dùng mô hình kênh LoS tự do d⁻² thường dùng trong UAV-MEC, tham số cấu hình được |
| D3: năng lượng bay chiếm ~86% | Tách năng lượng biên (CPU, TX, RX) khỏi năng lượng nền (bay, idle). So sánh policy bằng năng lượng biên |
| D4–D5: hàng đợi gần như rỗng | Hiệu chuẩn tải theo hệ số sử dụng ρ; task nhiều lớp, deadline theo slack ngẫu nhiên |

## Ghi chú sau khi merge nhánh `refactor/scenario-registry`

`scripts/test_near_paper_sensitivity.py` từ nay báo lỗi `Live code changed: PureEdgeSim/uav/PaperSimulation.java`.
Đây là khóa nguồn của campaign near-paper (hash `9a43bb3d…` = bản trước merge; bản sau merge `6844741d…`).
Test phát hiện đúng việc mã v1 đã đổi sau campaign. Không sửa: v1 đã đóng băng ở tag `v1-final`;
muốn chạy tiếp campaign near-paper phải checkout commit `04fde96`.

## Paper tham khảo cho v2

Đã kiểm tra tồn tại và thông tin xuất bản bằng tìm kiếm web ngày 12/11/2026. Chi tiết mô hình đánh dấu
"(trí nhớ)" chưa đối chiếu với toàn văn.

| Paper | Bài toán | Lấy gì cho v2 |
|---|---|---|
| M. Tang, V. W. S. Wong, *Deep Reinforcement Learning for Task Offloading in Mobile Edge Computing Systems*, IEEE TMC 21(6):1985–1997, DOI 10.1109/TMC.2020.3036871; arXiv 2005.02459 | Offloading có deadline, task bị drop khi quá hạn, hàng đợi ở thiết bị và edge; đánh giá tỉ lệ drop và delay | Deadline cứng có drop; quyết định offload theo từng task khi đến; hàng đợi ở cả hai phía; cặp chỉ số drop ratio + delay |
| Q. Hu, Y. Cai, G. Yu, Z. Qin, M. Zhao, G. Y. Li, *Joint Offloading and Trajectory Design for UAV-Enabled Mobile Edge Computing Systems*, IEEE IoT-J 6(2):1879–1892, 2019, DOI 10.1109/JIOT.2018.2878876 | UAV di chuyển phục vụ người dùng mặt đất; tối ưu quỹ đạo, tỉ lệ offload, lịch phục vụ để giảm delay | UAV di chuyển làm kênh thay đổi theo thời gian; kênh LoS β₀/d² (trí nhớ) |
| L. Huang, S. Bi, Y.-J. A. Zhang, *DROO*, IEEE TMC 19(11):2581–2593, 2020, DOI 10.1109/TMC.2019.2928811; arXiv 1808.01977 | Offload nhị phân trực tuyến bằng DRL | Quyết định nhị phân local/edge; có code công khai để đối chiếu sau P5 |
| Y. Zeng, J. Xu, R. Zhang, *Energy Minimization for Wireless Communication with Rotary-Wing UAV*, IEEE TWC 2019; arXiv 1804.02238 | Mô hình công suất bay của UAV cánh quạt | Eq. (6) công suất bay P(V) và Table I. P₀, Pᵢ do mình tính từ Table I theo Eq. (61) phụ lục, paper không ghi số |
| Y. Mao et al., *A Survey on Mobile Edge Computing: The Communication Perspective*, IEEE COMST 2017 (trí nhớ) | Tổng quan MEC | Năng lượng tính toán κ·f²·C cho mỗi chu kỳ CPU |
| T. Azfar et al., arXiv 2501.15305 (paper hiện tại) | Chọn thiết bị phục vụ để kéo dài lifetime | Bối cảnh thảm họa, thông số pin/công suất thiết bị; không dùng mô hình kênh d⁻⁴ |
