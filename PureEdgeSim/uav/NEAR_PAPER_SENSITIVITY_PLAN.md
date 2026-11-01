# Kế hoạch sensitivity gần paper — khóa trước khi chạy

## Câu hỏi và phạm vi

Xác định mức phụ thuộc của baseline offloading vào CPU UAV, deadline và thời gian dừng.
Không thêm thuật toán, train model, đổi radio hay tăng tải để tạo lợi thế scheduler.
Đây là nghiên cứu sensitivity synthetic, chưa phải inference RescueNet hoặc tái hiện paper.

Reference: target/near-paper-layout-full-20261101, đã audit 1.500 episode.
Tái sử dụng subset 900 episode của ALL_LOCAL/ALL_UAV/DEADLINE_ENERGY; không chạy lại mốc giữa.
DEADLINE_ENERGY là baseline mạnh; DELIVERY_AWARE có cùng core metrics ở campaign trước,
nên không thêm lại arm trùng; SHORTEST_FINISH được giữ trong báo cáo trước.

## Thiết kế

Giữ 10 environments 100–109 × 30 workload seeds 0–29 × 3 routing policies, RR + EDF.
Mỗi yếu tố chỉ có hai mức mới và một mốc reference:
- CPU throughput UAV: 0,5 / **2** / 8 MB/s, MB thập phân.
- Deadline cả hai priority class: 300 / **600** / 900 giây kể từ arrival.
- Dwell tối thiểu: 15 / **60** / 180 giây; active upload vẫn pin stop.

Tổng 5.400 episode mới, 900 reference episode tái sử dụng, 6.300 analysis cases duy nhất.
Không đếm reference ba lần hoặc smoke vào số full sample.
CPU watts giữ 20 W khi thay throughput: capacity sensitivity thuần túy, không phải DVFS/hardware calibration.
Deadline không vượt horizon: arrival window 600 s + deadline cao nhất 900 s <= horizon 1.800 s.
Các môi trường thay geometry/hardware/task/pin/connectivity theo paper RNG; không chỉ geometry.

## Trình tự và cổng

1. Unit tests; smoke cả ba giai đoạn (36 episode mới, 6 reference reused).
2. Full CPU phase; kiểm tra audit, pairing, negative control và đọc kết quả.
3. Chỉ khi CPU phase review PASS mới full deadline phase.
4. Chỉ khi deadline review PASS mới full dwell phase.
5. Tổng hợp và xác định nút thắt; không chọn mức nào làm config thật chỉ vì metric đẹp.

PASS nghĩa là simulation/audit/design đúng, không bắt buộc effect cải thiện.
Nếu fail thì dừng xử lý lỗi; không đổi grid theo arm thắng hoặc đi tiếp với trace thiếu.

## Kiểm chứng

- Khóa source/protocol hashes trước khi chạy.
- Từng Java run exit 0, manifest COMPLETE, independent verifier PASS; mandatory metrics export.
- CPU/dwell: workload CSV/hash giống reference từng seed.
- CPU negative control: ALL_LOCAL task/energy/position/visit/update traces phải byte-identical reference.
- Deadline: chỉ deadline_s thay; arrivals, bytes, actual/estimated MI, priority và source assignment giữ nguyên.
- Tất cả arm trong setting có cùng protocol và workload.
- Recount metrics từ live full traces, energy conservation và source hashes.
- Không sửa simulator/baseline hoặc artifacts cũ để chạy campaign này.

## Phân tích

Báo từng setting và environment:
compute/delivered DVR; J/on-time compute/delivery; completed/delivered mean và mean episode P95;
total/UAV energy; counts; UAV restricted availability + censoring; flight/hover/distance;
coverage/offload counts; background DVR NA vì background tắt.

Primary contrasts exploratory:
- Routing: ALL_UAV vs ALL_LOCAL; DEADLINE_ENERGY vs ALL_LOCAL và vs ALL_UAV, giữ setting.
- Factor effect: mức low/high vs reference, giữ policy.
- Delivered DVR CI 95% bằng 5.000 crossed bootstrap: resample environments và shared workload seeds.
- Không coi 5.400 policy episode độc lập, không tuyên bố confirmatory significance qua nhiều contrast.
- Energy ratios báo ratio of sums; latency chỉ trên completions/deliveries, gồm cả muộn.
- Không có successes => efficiency NA; pin chưa cạn => censored, không suy ra lifetime tăng.
- Giữ bảng per-environment để không che harms/regressions bằng mean.

Đường chạy: scripts/near-paper-sensitivity.py; plan/protocol/source snapshots trong output mới.
