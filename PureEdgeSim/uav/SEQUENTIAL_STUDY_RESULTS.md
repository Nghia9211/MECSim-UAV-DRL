# Kết quả Giai đoạn 1 và 2 — 01/11/2026

**Đã chạy tuần tự và kiểm chứng cả hai giai đoạn.**
[Báo cáo đầy đủ, bảng theo scenario và biểu đồ](../../docs/experiments/sequential-study-20261101/README.md).

- Giai đoạn1: 1.440 episode, UAV hover/link10m/ALL_UAV; 4 load ×3 deadline ×4 scheduler ×30 development seeds.
- Đánh giá riêng trước giai đoạn2: input/physical/dispatch verifier PASS, không có ảnh intrinsic-infeasible,
  20,86% dispatch có >=2 ready tasks; giữ workload/radio và chốt mobile controls theo biên bản.
- Giai đoạn2: 1.200 episode, 2 scale của layout42 ×2 load ×10 policy arms ×30 development seeds.
  ALL_UAV so scheduler trên cùng service trajectory; DELIVERY_AWARE+EDF là routing arm riêng.
- Tổng2.640 full episode, 262.720 task outcomes được audit; 88 smoke episode không gộp thành thêm mẫu.
- 43 Java regression tests liên quan +3 Python study tests pass; không train RL, không chạy server trong task này.

## Đọc kết quả chính

Trong hover control, image DVR mean: FIFO11,671%, EDF10,192%, SPT10,169%, PRIORITY10,073%.
PRIORITY có background DVR cao hơn EDF/SPT; chưa chọn winner từ metric ảnh đơn lẻ.

Trong mobile/RR/ALL_UAV, delivered DVR: FIFO40,173% → EDF39,922%, chỉ giảm0,251 điểm phần trăm.
RR/DELIVERY_AWARE/EDF đạt32,887%, nhưng đây là thay đổi routing và có thể thay stop pinning;
không gọi lợi ích đó là do scheduler.

RR/ALL_UAV/EDF đã offload1.374 ảnh;832 ảnh có contact wait+upload+compute vượt deadline
ngay cả khi bỏ queue. DA/EDF offload54 ảnh,51 được UAV giao đúng hạn; phần lớn kết quả
đúng hạn còn lại đến từ local connected. Local disconnected compute xong chưa có delivery.
Vì vậy cơ chế mới cần xét contact/admission/offloading; thêm scheduler phức tạp đơn thuần
chưa chắc có leverage lớn trong mobile setting này.

Tất cả UAV còn pin ở horizon600s: chỉ báo lifetime>=600s, không kết luận kéo dài lifetime.
Compute còn provisional/random-weight architecture timing; power/deadline/Alibaba CPU là
giả định/proxy, source pools chung, chưa unseen-layout hay validation/evaluation outcomes.

## Source và artifact

- Runner Java: [SequentialStudyBenchmark.java](offloading/SequentialStudyBenchmark.java).
- Prepare/verify/review/gate: [drl/sequential_study.py](../../drl/sequential_study.py).
- Report tool: [review-sequential-study.py](../../scripts/review-sequential-study.py).
- Protocol, core metric mỗi episode/từng scenario, queue, paired bootstrap:
  [docs/experiments/sequential-study-20261101](../../docs/experiments/sequential-study-20261101/README.md).
- Full raw traces: target/sequential-study-20261101/stage1-full và stage2-full.
- Study không thay PaperParameters, OffloadingSimulation, MobileService hay default protocol.

## Chạy lại tuần tự

Từ gốc MECSim, với dataset có sẵn, JDK17/Maven và Python environment.
Dùng output mới; không copy gate path tuyệt đối từ máy khác.

~~~powershell
mvn -o compile
.\.venv-drl\Scripts\python.exe -m drl.sequential_study prepare-stage1 --output target/study-new/stage1.json
mvn -o exec:java -Dexec.mainClass=uav.offloading.SequentialStudyBenchmark -Dstudy.protocol=target/study-new/stage1.json -Dstudy.output=target/study-new/stage1
.\.venv-drl\Scripts\python.exe -u -m drl.sequential_study verify target/study-new/stage1
.\.venv-drl\Scripts\python.exe scripts/offloading_metrics.py target/study-new/stage1
.\.venv-drl\Scripts\python.exe -m drl.sequential_study review-stage1 target/study-new/stage1
~~~

**Đọc REPORT.md, queue-diagnostics.csv, paired-statistics.csv và STAGE1_REVIEW.json trước bước sau.**
Nếu cần đổi thiết kế, giữ run cũ và xuất protocol/output mới; không sửa kết quả cũ.

~~~powershell
.\.venv-drl\Scripts\python.exe -m drl.sequential_study prepare-stage2 --stage1 target/study-new/stage1 --output target/study-new/stage2.json
mvn -o exec:java -Dexec.mainClass=uav.offloading.SequentialStudyBenchmark -Dstudy.protocol=target/study-new/stage2.json -Dstudy.output=target/study-new/stage2
.\.venv-drl\Scripts\python.exe -u -m drl.sequential_study verify target/study-new/stage2
.\.venv-drl\Scripts\python.exe scripts/offloading_metrics.py target/study-new/stage2
~~~

Linux dùng .venv-drl/bin/python thay .venv-drl\Scripts\python.exe.
Thêm --smoke lúc prepare để kiểm tra pipeline một seed; smoke stage1 không được mở gate stage2.
prepare-stage2 kiểm tra stage1 manifest/verifier hashes; Java runner kiểm tra review hash và allow flag
trước khi chạy mobile. Các nhánh benchmark/paper cũ giữ protocol cũ.
