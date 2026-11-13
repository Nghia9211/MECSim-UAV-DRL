# H0: vì sao trần thấp trong v2.0

Ngày 13/11/2026. Mô hình v2.0 khóa ở [CALIBRATION.md](CALIBRATION.md), seed development, không đổi tham số.
Run `target/mec/h0-headroom` (commit `4bd7fe7`, sạch), [experiments/h0-headroom.json](../../experiments/h0-headroom.json).
Verifier PASS: 1.440 episode, 480 có trace, 500.310 kết quả task.

```powershell
mvn -o -q compile exec:java "-Dexec.mainClass=uav.mec.MecRunner" "-Dexec.args=experiments/h0-headroom.json"
.\.venv-drl\Scripts\python.exe scripts\verify_mec.py target\mec\h0-headroom
.\.venv-drl\Scripts\python.exe scripts\mec_headroom.py target\mec\h0-headroom
.\.venv-drl\Scripts\python.exe scripts\bench_mec_env.py 5
```

Số liệu đầy đủ: [data/h0-headroom.json](data/h0-headroom.json).

## 1. Phân rã vi phạm của `DEADLINE_ENERGY+EDF+NONE`

30 episode mỗi ô (5 layout × 6 seed). Mỗi task trễ hạn vào đúng một nhóm (định nghĩa trong `scripts/mec_headroom.py`):
**bất khả thi** = không kịp kể cả khi chạy một mình với khối lượng thật và kênh lúc đến;
**xếp hàng** = kịp nếu một mình, và dự báo của tuyến được chọn đã báo trễ lúc quyết định;
**dự báo sai** = kịp nếu một mình, dự báo báo kịp, nhưng vẫn trễ.

| Ô | Task | Vi phạm | Bất khả thi | Xếp hàng | Dự báo sai | Thuộc lớp DETECT |
|---|---:|---:|---:|---:|---:|---:|
| light, không / có preemption | 14.085 | 60 / 7 | 0% / 0% | 100% / 100% | 0% / 0% | 60 / 7 |
| medium | 25.685 | 345 / 22 | 0% / 0% | 100% / 91% | 0% / 9% | 345 / 20 |
| overload | 36.740 | 893 / 62 | 0% / 0% | 100% / 81% | 0% / 19% | 893 / 55 |
| stress (thăm dò) | 50.465 | 3.061 / 221 | 0% / 0% | 99% / 74% | 1% / 26% | 2.956 / 133 |

## 2. Thang oracle

10 episode mỗi ô (5 layout × 2 seed). Các mức oracle định nghĩa trong `RolloutOracle.java`:

- **ORACLE:** rollout một lượt.
- **ORACLE_ITER:** rollout rồi tìm kiếm cục bộ đổi từng quyết định một, tối đa 5 lượt.
- **ORACLE_BEST:** ORACLE_ITER tốt nhất trên 5 scheduler × 2 chế độ admission.

Kiểm tra thứ tự BEST ≥ ITER ≥ ORACLE: **đúng ở mọi episode**.

| Ô | DVR %: heuristic → ORACLE → ITER → BEST | Sàn (bất khả thi) | J biên/task: heuristic → BEST |
|---|---|---:|---|
| light, không preemption | 0,51 → 0,09 → 0,09 → 0,09 | 0 | 16,35 → 16,22 (−0,8%) |
| light, có preemption | 0,07 → 0,00 → 0,00 → 0,00 | 0 | 16,29 → 15,98 (−1,9%) |
| medium, không | 1,30 → 0,33 → 0,19 → 0,16 | 0 | 16,22 → 15,86 (−2,2%) |
| medium, có | 0,07 → 0,00 → 0,00 → 0,00 | 0 | 16,05 → 15,59 (−2,9%) |
| overload, không | 2,30 → 0,74 → 0,47 → **0,38** | 0 | 16,61 → 16,01 (−3,6%) |
| overload, có | 0,21 → 0,03 → 0,00 → 0,00 | 0 | 16,30 → 15,73 (−3,5%) |
| stress (thăm dò), không | 5,20 → 2,14 → 1,26 → 1,05 | 0 | 17,43 → 16,23 (−6,9%) |
| stress, có | 0,28 → 0,07 → 0,00 → 0,00 | 0 | 16,66 → 16,09 (−3,4%) |

G6 tính lại với ORACLE_BEST ở các mức tải đã đăng ký: chênh lớn nhất 1,92 điểm DVR (overload, không preemption)
và 3,6% năng lượng. **Vẫn không qua** (ngưỡng 5 điểm hoặc 10%).

## 3. Tốc độ cầu nối RL

`scripts/bench_mec_env.py`, một tiến trình bridge, hành động ngẫu nhiên: **≈ 4.340 bước/s** (ρ_UAV = 0,9)
và **≈ 4.420 bước/s** (ρ_UAV = 1,8), đo khi máy đang chạy H0 với 16 luồng. Trên ngưỡng 2.000 của plan:
chưa cần chạy song song nhiều môi trường cho H5.

## 4. Kết luận cho H1

1. **Không có sàn:** mọi task đều khả thi nếu chạy một mình. Vi phạm hoàn toàn do tranh chấp tài nguyên,
   nên về nguyên tắc thuật toán có thể sửa được. Nhưng tranh chấp quá ít để tạo khoảng trống lớn, vì hệ thống còn dư công suất
   (CPU thiết bị cộng lại ≈ CPU UAV).
2. **Vi phạm dồn vào DETECT:** task nhỏ, deadline 1–3 s, chịu thiệt khi phải chờ sau task SEGMENT/MAP.
   Preemption EDF đã gỡ gần hết, còn lại chủ yếu do dự báo sai.
3. **Oracle yếu không phải lý do chính:** oracle mạnh hơn (ITER, BEST) chỉ thêm 0,1–1,1 điểm so với rollout một lượt.
4. Vì vậy khoảng trống phải đến từ **kịch bản**: tăng tranh chấp thật (đòn bẩy L6: tải theo ρ hệ thống; L4/L5: điểm nóng,
   bùng phát) và làm kênh phụ thuộc vị trí (L1–L3). Đây đúng là các đòn bẩy ưu tiên của H1.
