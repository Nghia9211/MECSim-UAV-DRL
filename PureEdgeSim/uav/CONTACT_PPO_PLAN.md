# Contact-aware MaskablePPO: thiết kế và pilot

Ngày2026-10-30. Đây là adaptation cho bài toán, không phải thuật toán PPO mới.
Dùng MaskablePPO chuẩn từ sb3-contrib2.6.0, cùng stable-baselines3. Không tự viết framework RL.
Tài liệu: https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html

## Cơ sở lựa chọn

PPO143D trước chỉ chọn9 cặp policy trong khi service rule là Round Robin cố định; nó không
điều khiển được UAV đến nơi có nhu cầu gửi kết quả. Trên160 case của baseline
DELIVERY_AWARE/RISK_EDF trong joint-RL-v2, chỉ101/7840 ảnh (1,29%) được offload. Trong2234
lần UAV CPU dispatch,251 lần (11,24%) có>=2 ready tasks. Đây là diagnostic offline từ trace,
không phải feature đưa cho agent. Mean UAV compute khoảng1,28% tổng UAV energy trong run đó.

Đợt simple-scheduling6240 episodes đã hoàn tất và PASS trước khi triển khai pilot này.
Ở error0, delivered DVR DA/RISK_EDF36,399%; DA/RISK_SPT36,413%; DA/FEASIBLE_AGING36,424%.
Thay scheduler chưa giải quyết được nút thắt contact. Không tăng tải/giảmCPU để tạo kết quả thuận lợi.

## State/action/reward

Action108 =12 destination devices x3 route policies x3 schedulers.
Encoding: `9*target + 3*route + scheduler`.
Route: DELIVERY_AWARE, DEADLINE_ENERGY, SHORTEST_FINISH.
Scheduler: EDF, SPT, FIFO. Local CPUs vẫn FIFO.
Agent chọn tại service boundary, giữ cặp policy đến boundary tiếp theo. Route từng arrival
và CPU dispatch vẫn do cặp policy đang chọn thực hiện. Đây là học service scheduling và
policy selection, chưa phải học trực tiếp destination từng task hay priority từng ready job.
Giữ giới hạn này khi viết kết luận offloading+scheduling.

State179 =129 causal mobile features +5scenario features +9 previous-policy onehot +36
candidate features (3/device): estimated travel time/horizon, flight cost/current UAV battery
clipped[0,1], số live disconnected devices trong slant coverage của destination /12.
Thông tin vị trí/connectivity/queue/slack/pin đã quan sát, không actual MI, future arrivals,
image labels/masks hoặc task seed. Biết geometry/connectivity toàn mạng là giả định kế thừa.
Các physics constants của feature là speed5m/s, flight150W, altitude10m, range65m của setting này.

Mask chỉ loại destination devices đã chết. Không loại connected devices, không mask theo
future tasks hay xác suất deadline thực. Prediction/evaluation bắt buộc truyền action_masks.
Có thể chọn lại vị trí hiện tại, vẫn dwell30s; không có quyết định thời gian0 lặp vô hạn.

Giữ reward của joint-RL-v2 để kiểm tra tác dụng điều khiển contact thay vì đổi nhiều thứ:
`2*delivered_on_time - images_seen - .25*background_misses - .1*energy_j/10000`.
Step reward là delta cumulative, gamma1 và GAE lambda1 cho episode có boundary duration khác nhau.
Failure delivery (kể cả local compute nhưng source disconnected) vẫn nằm trong images_seen.
Latency và lifetime được đo độc lập, chưa có reward penalty trực tiếp cho latency.
Không thêm bonus tiếp cận thiết bị để agent được thưởng dù không giao được kết quả.

## Protocol

- Cùng mobile contact-wait physics, RescueNet449 + Alibaba1000 workload mapper; không train vision model.
-16 scenarios:area250/800m xpin30k/1,6MJ xlight/overload xestimate error0/40%; layout42.
-3 learning seeds0,1,2;32768 decision steps/model;CPU1Torch thread/model,3model đồng thời.
-MLP64x64,lr.0003,rollout256,batch64,epochs5,clip.2,targetKL.02,entropy.01.
-Train task seeds[0,999999]; validation1900000 trên16scenarios mỗi4096steps; chọnbest bằng mean reward.
-Test2800000..2800009, giống joint-RL-v2 để so sánh paired. Đây là development-used seeds,
  cùng raw pools và layout; không fresh-holdout/source-holdout/unseen-layout claim.
-Best/final đều đánh giá; không lấy test chọn best; budget bước bằng PPO143D cũ.
-Counter sb3_n_updates của PPO là epoch counter, không phải số optimizer minibatches.

Đối chứng:4 RR fixed pairs (DA/RISK_EDF,DE/RISK_EDF,DA/RISK_SPT,DA/FEASIBLE_AGING),
3 heuristic cùng action space (RR,DISCONNECTED_RR,CONTACT_GREEDY với DA/EDF),3 oldPPO-RR best,
6 newPPO best/final =16 policies x160cases =2560 episodes.
CONTACT_GREEDY chọn số disconnected live được phủ / (travel time + dwell), tie theo RR order.
DISCONNECTED_RR luân phiên các live disconnected sites; fallbackRR khi không có.
Hai heuristic là đối chứng mạnh đơn giản; không chỉ so với RR để claim RL tốt.
Các baseline RISK có risk-drop rule mà action space RL chưa bao gồm; báo rõ khác biệt này.

Smoke1024steps seed0,1case,9episodes; full chỉ chạy sau smoke PASS. Mọi eval action được
replay từ checkpoint hoặc heuristic. OldPPO được nạp143D đầu, chọn mode; target vẫn RR,
để giữ đúng policy cũ trên cùng workloads. Hash old checkpoints phải khớp verification cũ.

## Verify và metrics

Java tests, Gym contract, state ban đầu không phụ thuộc future task seed, target action thay
đổi trajectory, mask loại đúng dead destinations, reward telescoping, negative audits cho
candidate coverage features/target/policy/reward. Regression tests cho mobile/joint cũ.
Independent audit mỗi trace tái tạo state179, geometry, energy, coverage, upload waiting,
chosen target và route/scheduler hiện hành. Cùng workload hashes trên mọi policy/case.
Reuse shared audited metrics.calculate/summarize từ scripts/offloading_metrics.py:
compute/delivered image DVR, whole-system J/on-time image và delivered image, completed mean/P95
latency, delivery latency, UAV battery service time với censoring, UAV/total energy,
background DVR, on-time counts; giữ per-scenario và ALL.
Survivors600s chỉ có lifetime>=600; zero delivered thì J/delivered NA.

COMPLETE cần exit0, completion marker, COMPLETE manifest, PASS full audit2560 traces và
source_unchanged. Phải hơn CONTACT_GREEDY và strongest fixed policies trên tradeoff metrics
mới có bằng chứng RL đáng dùng. Pilot32k không bảo đảm hội tụ hoặc cải thiện.
Không chọn seed đẹp, không gộp best/final thành sample độc lập.

Entrypoint: scripts/train-contact-server.sh.
Remote tmux:uav-contact-ppo-20261030-v1.
Output:target/contact-ppo-20261030-v1; control:target/contact-ppo-control-20261030-v1.
Dependencies thêm sb3-contrib2.6.0 trong project .venv-drl; không đổi shared Conda/GPU setup.
