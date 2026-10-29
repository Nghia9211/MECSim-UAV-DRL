# Phân tích DQN mới nhất và kế hoạch RL cho offloading + scheduling

Ngày: 2026-10-30. Paper campaign: `target/dqn-24-125-retrain-20261030-v1` trên aiotlab_92.
Source: `d3a75cee0dd9529337e018b1a2d84eec22100caf`. Sáu model, mỗi model 1.000.000 bước,
12 checkpoint best/final, 1.440 evaluation traces. Exit 0, independent verification PASS,
370.848 device rows; checkpoint/action replay và source guard PASS. Đã tải checkpoint và
xác minh hash tại local `target/dqn-24-125-server-results-20261030/completion-checked.json`.

## Kết quả đã có

Các số dưới là trung bình số slot của từng learner trên 30 task seed giống nhau,
sau đó trung bình trên 3 learning seed; SD giữa 3 learner, không phải 90 mẫu độc lập.
Best được chọn bằng validation, không chọn bằng test.

| State | Best: mean ± SD slot | Final: mean ± SD slot | Best từng seed | Final từng seed |
|---|---:|---:|---|---|
| 24D | 31,556 ± 0,509 | 30,333 ± 1,155 | 31,667; 31; 32 | 29; 31; 31 |
| 125D | 31,667 ± 0,577 | 22,889 ± 11,241 | 31; 32; 32 | 28; 30,667; 10 |
| OLDEST_DATA | 29 | 29 | Chung workload | Chung workload |
| ROUND_ROBIN | 16,5 | 16,5 | Chung workload | Chung workload |
| RANDOM | 11,233 | 11,233 | Chung workload | Chung workload |

125D-best chỉ hơn 24D-best 0,111 slot (~0,35%): chưa có bằng chứng tăng state giúp tốt rõ.
Tính theo thời gian vật lý, best24D đạt18.574,21s và best125D18.492,55s: 125D thấp hơn
khoảng81,66s (~0,44%). Slot có thời lượng khác nhau; hơn slot không đồng nghĩa hơn giây.
Cả hai best hơn OLDEST_DATA khoảng 8,8–9,2% về slot ở setting này. Final 125D seed2
rơi xuống 10 slot dù từng có checkpoint đạt 32 slot. Đó là dấu hiệu policy cuối kém đi;
chưa đủ dữ liệu để khẳng định nguyên nhân là overfitting, replay hay Q-value divergence.
Muốn phân biệt cần kiểm tra learning curves/Q-values và thử lại hyperparameters.
Bắt buộc giữ best và final riêng, validation độc lập với test.

Các best DQN dùng xấp xỉ hết 1,6 MJ UAV. Lifetime dài hơn không tự chứng minh tổng năng lượng
nhỏ hơn: có thể UAV phục vụ lâu hơn và tiêu thụ nhiều hơn. Không suy ra J/ảnh từ bảng này.

## Giới hạn chuyển kết luận sang đề tài

24D/125D là PaperSimulation REFERENCE/LEGACY, chọn thiết bị phục vụ tiếp theo, một layout0,
workload synthetic 2–4 MB, slot cap600s. Đây không phải mobile contact-wait RescueNet+Alibaba.
Episode lifetime của paper có thể kết thúc vì tuổi dữ liệu hoặc pin; không đồng nhất với
UAV battery service lifetime của bài toán mới. Không có image deadline queue tương ứng,
nên image DVR, completed-image latency và J/on-time image ở campaign paper là NA.
30 test seed paper đã dùng trong phát triển; không gọi là fresh holdout hoặc tổng quát nhiều layout.

## Hướng triển khai lần này

Thử PPO policy selector, đồng thời train DQN mới làm đối chứng trong cùng môi trường.
Chưa khẳng định PPO sẽ tốt hơn DQN. Chọn PPO để kiểm tra một phương pháp policy-gradient
với clipped update và KL guard, thay vì chỉ tăng state và kéo dài DQN cũ.
Tài liệu triển khai: https://stable-baselines3.readthedocs.io/en/v2.6.0/modules/ppo.html

Giữ trajectory ROUND_ROBIN. Mỗi service boundary, agent chọn 1 trong 9 cặp:

- Offload: DELIVERY_AWARE, DEADLINE_ENERGY, SHORTEST_FINISH.
- UAV CPU scheduler: EDF, SPT, FIFO; local CPU vẫn FIFO.

Action `3*route_index + scheduler_index` có hiệu lực tới boundary tiếp theo. Task arrival
được route theo cặp đang chọn; CPU dispatch và queue forecast dùng cùng scheduler.
Forecast đóng băng cặp hiện tại, không giả định biết action tương lai của agent.
Không RPC/học trong counterfactual forecast. Không preemption/migration/retry/drop rule mới.
Đây là RL chọn chính sách theo trạng thái; chưa phải học trực tiếp route từng task hay priority từng job.
Không gọi là full joint trajectory-offloading-scheduling.

State143D = 129 feature causal của mobile kernel + area, initial UAV battery, hai arrival rates,
estimate error + one-hot mode trước (9). Không đưa actual MI, future arrivals, source labels,
mask ground-truth hay task seed vào observation. Task cost ước lượng và queue/slack đã quan sát
được dùng trong kernel. State hiện tại chưa có histogram priority/deadline; có thể là hạn chế tiếp theo.

Reward cumulative: `2*delivered_on_time - images_seen - .25*background_misses - .1*energy_j/10000`.
Step reward là chênh lệch cumulative. Cuối episode tương đương `on-time delivered - failed delivery`
trừ background/energy penalty, đếm cả local hoàn thành nhưng không gửi được là delivery failure.
Không dùng J/task ratio làm step reward. Gamma1 cho các boundary có thời lượng không bằng nhau;
PPO GAE lambda1. Latency/lifetime được đo độc lập, chưa tối ưu trực tiếp bằng reward này.
Weights là development choices, không phải paper hay được hiệu chỉnh từ dữ liệu thực địa.

## Protocol pilot đã định trước

- Dữ liệu: cùng RescueNet pool449 ảnh + Alibaba1000 row, mapper mô phỏng hiện có; không train vision model.
- Kernel: contact wait bật cho mọi policy; chỉ đợi điểm đến đã chọn, không biết các stop tương lai.
- 16 scenario: area250/800m × pin30k/1,6MJ × light/overload × estimate error0/40%.
- Layout seed42, hai area dùng cùng tọa độ normalized; chưa thử unseen layouts.
- Train task seed [0,999999]; validation1800000, test2800000..2800009; cùng raw pools, không source holdout.
- PPO và DQN: mỗi loại 3 learning seed0/1/2; 32.768 decision steps/model, CPU1thread, tối đa3 model đồng thời.
- MLP64×64; lr0,0003. PPO rollout256, batch64, epochs5, clip0,2, entropy0,01, targetKL0,02.
- DQN batch64, replay100k, learning starts128, update mỗi4 step, target500, epsilon1→0,05.
- Validation mỗi4096 bước, đủ16 scenario với seed đã cố định; chọn best bằng mean reward,
  ghi cả final. Không dùng test để chọn checkpoint.
- Smoke: PPO+DQN seed0,1024step/model,1case,15 evaluation episodes; bắt buộc PASS trước full.
- Full evaluation:160 paired cases × (12 learned best/final policies +9 fixed pairs +ALL_LOCAL/EDF
  +ALL_UAV/FIFO) =3.680 episodes; các baseline chia sẻ, không lặp để tăng cỡ mẫu.

## Verify và tiêu chí đánh giá

Java tests, Gym contract, thay đổi mode thực sự ảnh hưởng route/energy, future-task independence,
reproducible reset, reward telescoping, adversarial action/observation/reward/route tests.
Mỗi evaluation trace được independent audit physics, battery/TX, contact plans, causal observations,
mode-selected routing/scheduling và reward. Learned actions được đối chiếu lại checkpoint.
Workload hash phải giống giữa policies ở mỗi case; source phải không đổi trong campaign.

Dùng `scripts/offloading_metrics.py` qua các hàm calculate/summarize trên audited traces:
image compute DVR, delivered DVR (primary disaster outcome), whole-system J/on-time image
và J/on-time delivered image, completed-image mean/P95 latency, delivery latency, UAV battery
service time với right censoring, background DVR, UAV/total energy, số on-time images.
Ghi cả per-scenario và ALL; ALL là hỗn hợp scenario, không thay thế bảng riêng.
Zero successes → efficiency NA. Survives horizon600s → lifetime>=600, không phải exhaustion600.

Chỉ kết luận RL có ích nếu cải thiện trên cặp fixed mạnh nhất với cùng budget vật lý,
không chỉ thắng ALL_UAV/FIFO; xem tradeoff delivered DVR/energy/latency/background.
Pilot32k không thể chứng minh hội tụ hoặc SOTA. Nếu không thắng: đọc action frequencies,
validation-vs-final và từng scenario; sau đó cân nhắc state priority/slack histogram hoặc
per-task action bridge. Không tự tăng budget hay claim thắng từ vài seed.

## Entrypoint và artifacts

`python -m drl.joint_campaign campaign --smoke --output target/<fresh-smoke>`

`python -m drl.joint_campaign campaign --output target/<fresh-full>`

Artifacts: manifest/source snapshots, models/config/validation/best/final, process receipts,
all evaluation traces, verification.json, core-metrics-episodes/summary.csv, CORE_METRICS.md,
delivery-summary.csv. COMPLETE chỉ sau toàn bộ audit và source guard.

Lệnh tắt máy manual của đợt24D/125D đã tạo ở
`target/dqn-24-125-server-results-20261030/Tat_may_sau_train.cmd`; không tự chạy.
Job RL mới nằm trong tmux trên server và tiếp tục sau khi máy local tắt.
