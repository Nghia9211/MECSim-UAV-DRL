# Scenario gần paper để nghiên cứu offloading / scheduling

## Mục đích

Giữ nền vật lý và độ khác biệt giữa thiết bị của Azfar et al., arXiv:2501.15305v1.
Thêm khả năng chọn nơi xử lý và hàng đợi CPU hữu hạn để đánh giá **một trong hai hướng**.
Không bắt buộc offloading và scheduler đều cải thiện. Không đổi reward hoặc train RL trong pilot này.

Đây là **phần mở rộng từ paper**, không phải chạy lại nguyên kết quả paper.
Nhánh PaperSimulation/PaperParameters không bị sửa trong task này.

## Giữ gì từ paper, thêm gì?

| Thành phần | Cấu hình | Nguồn / giới hạn |
|---|---|---|
| Mặt bằng | 800 × 800 m; 12 thiết bị | PaperParameters; layout gọi trực tiếp PaperSimulation.layout |
| UAV | 10 m; 5 m/s; range 65 m theo khoảng cách 3D | Giữ paper |
| Năng lượng UAV | bay 150 W; hover 80 W; pin 1.600.000 J | Giữ paper |
| Pin thiết bị | random 50–80 kJ | Giữ cách lấy mẫu paper |
| Hardware, vision task | 5 × 5 loại, throughput/standby/active theo bảng paper | Giữ ánh xạ và giá trị trong code paper |
| Radio | 20 MHz, TX 0,1 W; noise −100 dBm; path-loss 4 | Giữ quy ước literal beta0 hiện tại; chưa giải quyết mơ hồ đơn vị beta0 của paper |
| Ảnh/task | synthetic uniform 2–4 MB, đơn vị MB thập phân | Gần workload synthetic paper; **không phải RescueNet inference** |
| Mất điện / kết nối | 0/12 có nguồn điện ngoài; 8/12 có kết nối | Một cấu hình availability cụ thể; không đại diện mọi trường hợp paper |
| Đến task | Poisson tổng 0,04 ảnh/s trong 600 s | Phần mở rộng; paper sinh task theo slot, không phải quá trình này |
| CPU local | bytes/s theo đúng hardware và vision task của paper | Local CPU FIFO; mỗi thiết bị giữ một loại vision task |
| CPU UAV | 2.000.000 bytes/s, CPU tăng thêm 20 W | **Giả định mở rộng**, không phải số đo phần cứng hay thông số paper xác nhận |
| Work unit | 1 normalized MI = 1.000 bytes công việc | Chỉ chuẩn hóa; không phải CPU instructions đo được |
| Deadline | primary 600 s; sensitivity 300 s | SLA giả định. Không đồng nhất slot cap 600 s hay tuổi dữ liệu 10 slot với deadline |
| Mobility | RR, dừng tối thiểu 60 s; được chờ chuyến bay đã chọn | RR theo thiết bị còn sống; upload pin giữ stop; không biết chuyến tương lai chưa chọn |
| Kết thúc | horizon 1.800 s / xử lý pin cạn theo kernel | Không dùng điều kiện network lifetime/age nguyên bản paper |
| Background | mặc định tắt; tùy chọn Alibaba 0,1 task/s | Proxy workload, không replay nguyên DAG, arrival hay cluster trace |

Cách chuẩn hóa bảo toàn thời gian local:
- work = input_bytes / 1.000;
- local_mips = paper_bytes_per_second(hardware, vision_task) / 1.000;
- local_compute_s = work / local_mips = input_bytes / paper_bytes_per_second.
- Năng lượng local = standby × thời gian sống + active × thời gian CPU busy, cùng cách cộng công suất trong nhánh paper.

Kết quả từ scenario này không sử dụng số đo DeepLab 0,524 s của cấu hình trước.
Không áp tốc độ DeepLab server vào các loại hardware/vision task khác trong bảng paper.

## Chỉnh tham số ở đâu?

Cấu hình mặc định: [offloading/near-paper-protocol.json](offloading/near-paper-protocol.json).

Có thể thay trên **bản sao JSON mới**:
- uavBytesPerSecond, uavCpuWatts: khả năng xử lý/chi phí compute của UAV.
- loads[].imageRate: tổng ảnh/s toàn mạng, không phải ảnh/s mỗi thiết bị.
- loads[].criticalDeadlineSeconds, imageDeadlineSeconds: ngân sách end-to-end kể từ task arrival.
- criticalFraction, estimateError: tỷ lệ task ưu tiên cao và sai số ước lượng công việc.
- dwellSeconds, allowContactWait: dừng phục vụ và chờ chuyến đã chọn.
- connectedDevices, layoutSeed: kết nối và cách lấy mẫu layout paper.
- taskSeeds, arrivalWindowSeconds, horizonSeconds: cỡ pilot và thời gian mô phỏng.
- loads[].backgroundRate, backgroundDeadlineSeconds, backgroundWorkScale: tải nền tùy chọn.
- policies: SELECTOR__OFFLOADING__SCHEDULER, phải dùng các baseline đã triển khai.

Các hằng vật lý paper không được scale để lấy kết quả đẹp.
poweredDevices phải bằng 0 vì kernel nghiên cứu này chưa mô hình hóa nguồn điện ngoài.
Nếu thay arrival window/deadline thì mọi deadline phải nằm trong horizon.
Dùng output mới; chương trình từ chối ghi đè run cũ.

## Baseline và thiết kế so sánh

8 arm dùng cùng workload/hash:
- ALL_LOCAL, ALL_UAV, SHORTEST_FINISH, DEADLINE_ENERGY, DELIVERY_AWARE: giữ EDF và RR.
- FIFO, EDF, SPT, RISK_EDF: giữ ALL_UAV và RR.

ALL_UAV nghĩa là offload khi có contact hợp lệ; ngoài current/known-flight contact thì fallback local.
Không có bảo đảm mọi task đều lên UAV.

30 seed là **workload seed**, không phải 30 lần train hoặc 30 layout.
Một layout seed 42; pilot exploratory, chưa có generalization/unseen-layout hoặc xác nhận bằng holdout.
Chạy primary trước; deadline/background là sensitivity khai báo trước, không chọn lại scenario theo arm thắng.

**Mục tiêu có thể đạt:** cho phép offloading làm thay đổi số ảnh giao đúng hạn/latency/energy efficiency.
Nếu scheduler ít task đồng thời ready hoặc không cải thiện, giữ nguyên kết luận đó.
Không thêm tải lớn chỉ để chứng minh scheduler phải thắng.

## Chạy và kiểm chứng

Tại gốc MECSim, Windows (đã có Java 17, Maven, .venv-drl):
~~~powershell
.\.venv-drl\Scripts\python.exe scripts/near-paper-study.py prepare --protocol target/near-smoke.json --smoke
.\.venv-drl\Scripts\python.exe scripts/near-paper-study.py run --protocol target/near-smoke.json --output target/near-smoke-run
~~~

Linux/server: dùng python của môi trường đã có; script pilot này chỉ dùng Python stdlib.
~~~bash
.venv-drl/bin/python scripts/near-paper-study.py prepare --protocol target/near-full.json --background
.venv-drl/bin/python scripts/near-paper-study.py run --protocol target/near-full.json --output target/near-full-run
.venv-drl/bin/python scripts/report-near-paper.py target/near-full-run
~~~

--background cần datasets/raw/alibaba2018/batch_task.csv sẵn có.
Không dùng flag này thì không cần dataset nào. Không tải dữ liệu tự động.
Maven chạy offline theo cache hiện có; máy mới cần resolve dependency một lần bằng Maven online trước.

RNG ảnh/Alibaba và RNG ước lượng compute được tách theo nguồn. Bật background giữ nguyên mọi trường của task ảnh, kể cả estimated MI; Java và Python đều có regression test cho điều này.

Mỗi run tự:
1. Lưu protocol, source snapshot + SHA-256, layout, source pool, workload + hash.
2. Chạy các arm xoay thứ tự theo seed; lưu task/energy/decision/trajectory/contact/update traces.
3. Dựng lại độc lập layout Java RNG, task RNG, hardware throughput/power.
4. Replay CPU/queue/routing, đường bay/contact/upload và kiểm tra bảo toàn năng lượng.
5. Chỉ sau PASS mới xuất core metrics.

Kết quả chính:
- core-metrics-summary.csv: từng scenario, compute DVR và delivered DVR, latency, năng lượng.
- paired-contrasts.csv: chênh lệch paired + bootstrap CI exploratory.
- queue-opportunities.csv: số lần CPU có ≥2 task ready.
- RESULTS.md: bảng tổng hợp có caveat.
- verification.json: trạng thái audit, số episode và outcome.

Delivered DVR là chỉ tiêu cần ưu tiên khi nói về kết quả có ích: xử lý xong ở thiết bị mất kết nối chưa được coi là đã giao.
Giữ cả compute DVR để thấy sự khác nhau.
Pin còn sống ở horizon là censored; không suy ra kéo dài lifetime.

## Giới hạn cần giữ khi báo cáo

- Không phải dữ liệu thực nghiệm RescueNet; background Alibaba là proxy CPU trên sample root single-instance.
- Không giả lập chất lượng dự đoán ảnh, memory/GPU contention, downlink cost, shared bandwidth/interference.
- Kết quả local của nguồn mất kết nối chưa có cơ chế thu gom về sau.
- Mỗi device có FIFO local; so sánh scheduler ở đây là scheduler CPU UAV.
- Dwell/RR/arrival/deadline/UAV compute là lựa chọn của nghiên cứu, không gán là thông số tác giả công bố.
- Không so trực tiếp DVR/giây của pilot này với reward/network lifetime/slot của paper.

Kết quả pilot đã chạy xem [NEAR_PAPER_RESULTS.md](NEAR_PAPER_RESULTS.md).
