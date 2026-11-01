# Chẩn đoán và kiểm tra admission background

Ngày01/11/2026. [Báo cáo đầy đủ](../../docs/experiments/admission-final-20261101/README.md),
[development review](../../docs/experiments/admission-development-20261101/README.md).

## Trình tự đã thực hiện

1. Phân loại194.392 image outcomes từ hai campaign cũ trước khi đổi thuật toán.
2. Chọn background admission từ dấu hiệu blocking; test, forecast/verifier parity.
3. Smoke/full hover → đánh giá tradeoff → smoke/full mobile.
4. Khóa source/candidate/threshold/metric/protocol trước validation rồi evaluation,
   dùng task seed partitions và geometry mới. Không tuning sau lock.

Đây là thử nghiệm cơ chế có đánh đổi, chưa claim novelty/SOTA.
Không train RL, không chỉnh radio/payload/power để tạo chiến thắng.

## Cơ chế thử

BackgroundBudgetScheduler chỉ được wire opt-in trong OffloadingSimulation qua
SequentialStudyBenchmark. Chưa expose Gym/DQN/PPO/paper; SchedulingSimulation đơn lẻ
không có admission hook này.

- BG_CAP_EDF: idle dispatch drop background nếu estimated runtime>B, rồi EDF.
- RISK_BG_CAP_EDF: thêm deadline-risk guard; risk drop có precedence.
- Status DROPPED_BACKGROUND_BUDGET riêng, tính failure, không phải completion.
- Không đọc future arrivals/actual work, không preempt.
- B=critical image deadline−max JPEG upload ở10m−reference image compute.
  Tight/reference/relaxed khoảng5,212/15,212/35,212s; không tuning từ score.
- B không bảo đảm mọi radio/queue/estimate-error scenario đều feasible.

Independent verifier kiểm tra predicate/drop/precedence/CPU-busy/work/energy,
và forecast giữ cùng semantics. Baseline control cũ giữ CSV byte-identical:
720hover episodes và480mobile episodes.

## Kết luận

Giữ RISK_EDF làm đối chứng chính; EDF chưa đủ mạnh.
Cap cải thiện ảnh nhưng làm background DVR/rejected CPU work xấu hơn RISK_EDF.
Không chọn cap làm phương pháp cuối chỉ từ image metric.

Hướng scheduling tiếp theo có thể là pause/resume background với work conservation,
context-switch overhead và background service constraint. Đây là đề xuất, chưa implement.
Contact/offloading vẫn chi phối mobile; scheduling không tự sửa disconnected delivery.

Compute vẫn provisional/random-weight architecture timing; power/deadline giả định;
Alibaba CPU proxy. Task-seed holdout không đồng nghĩa source-image/Alibaba holdout.
Hai geometry mỗi partition, scale hai mức; không phải120layout độc lập.
Nếu dùng holdout hiện tại để phát triển tiếp, cần holdout mới cho đánh giá cuối.

## Tái lập

Chạy từ gốc repo, output phải mới, kiểm tra status/exit code từng bước.
Cần stage1/stage2 đã verified theo SEQUENTIAL_STUDY_RESULTS.md.

~~~powershell
mvn -o test
.\.venv-drl\Scripts\python.exe scripts/test_study_failures.py
.\.venv-drl\Scripts\python.exe scripts/test_background_budget_verifier.py
.\.venv-drl\Scripts\python.exe -m unittest drl.test_heldout_admission drl.test_sequential_study

.\.venv-drl\Scripts\python.exe -m drl.admission_study --base-protocol target/sequential-study-20261101/stage1-full.json --output target/budget-new/hover.json
mvn -o exec:java -Dexec.mainClass=uav.offloading.SequentialStudyBenchmark -Dstudy.protocol=target/budget-new/hover.json -Dstudy.output=target/budget-new/hover
.\.venv-drl\Scripts\python.exe -m drl.sequential_study verify target/budget-new/hover
.\.venv-drl\Scripts\python.exe scripts/offloading_metrics.py target/budget-new/hover
~~~

Đọc background DVR/rejected work trước mobile. Dùng protocol stage2 để prepare/simulation/
verify/export tương tự. Verifier mới là drl.sequential_study verify, không CLI benchmark cũ.

Held-out tool drl/heldout_admission.py trong receipt này đọc development ở
target/admission-study-20261101/mobile-full. Tái lập với thư mục/máy khác cần chuẩn bị
protocol/gate mới trước run và công khai thay đổi đường dẫn; không đổi source sau lock.
Không copy gate Windows tuyệt đối lên server rồi coi là portable.

Raw traces giữ trong target/admission-study-20261101. Báo cáo gọn ở docs/experiments.
120smoke episode không gộp vào6480full episode; không xóa report/campaign đời trước.

## Verify và runtime

Full Java139/139, Python70/70 pass ở bước cơ chế. Sau lock wiring chạy lại39Java
và5Python bị ảnh hưởng; thêm2diagnosis và3negative admission-verifier tests pass.
Java từ chối protocol sửa ngưỡng sau lock trước khi tạo output.

Admission scan O(N), EDF min O(K); không suy ra whole-simulator complexity.
Scheduling timer chỉ đo choose(), không gồm guard scan; host episode wall time
không phải deployment decision latency. Lifetime>=600s/censored không phải exhaustion time.
