# Thêm PPO và A2C trong setting REFERENCE

Protocol lập trước khi chạy, 2026-10-28. Bổ sung các RL baseline sẵn có, không đổi mô hình để làm thuật toán nào thắng.

## REFERENCE là gì?

Implementation theo bài Azfar: một UAV chọn thiết bị đến phục vụ, 12 thiết bị trong vùng800×800m, 8 có nguồn ngoài và8 còn kết nối. Mỗi slot phát sinh task synthetic2–4MB/thiết bị; slot tối đa600s; UAV bay5m/s,150W khi bay,80W khi hover, pin1,6MJ. Thiết bị mất nguồn dùng pin50–80kJ. Coverage theo slant range65m, UAV cao10m.

Delivery LEGACY: connected hoặc được UAV upload thành công thì tuổi dữ liệu reset, không đòi local phải hoàn thành trong600s. Thiết bị mất kết nối cần UAV phục vụ để cập nhật. Episode dừng khi UAV/thiết bị hết pin hoặc tuổi đạt10slot; slot cuối dở vẫn đếm một slot. Safety cap200slot. Reward paper BEFORE; state24 là12 battery fractions +12 tuổi theo slot. Synthetic coi compute UAV không đáng kể, chưa finite task queue/deadline task. Không dùng RescueNet/Alibaba trong lượt này.

LOCAL_COMPLETION trước đó chỉ reset local khi có kết nối và xử lý xong; vì task dở không carry over nên làm tăng số thiết bị cần UAV. Hai setting là hai bài toán khác nhau, không gộp kết quả.

Các quy ước radio, output-link, cap và age còn bất định vẫn theo PAPER_ALIGNMENT; REFERENCE là nhãn implementation, không khẳng định mọi chi tiết giống code tác giả hoặc đã reproduce toàn bộ Tables5/6.

## Đối chứng

- Round Robin, Oldest Data, Random đã chạy trong campaign REFERENCE. Kết quả lần trước:16,50;29,00;11,23slot trên30task seed của layout0.
- DQN24 đã train3seed đủ1m; dùng lại kết quả/checkpoint đã replay PASS của `target/reference-state-20261028-v1`. Best31,56, final30,33slot. Không gọi việc tái dùng này là train thêm3DQN.
- Train mới **PPO và A2C**, mỗi thuật toán3learning seed(0/1/2), state24, reward/môi trường giữ nguyên. Không cần125D cho đối chứng thuật toán.
- Mỗi model yêu cầu1.000.000 environment steps. PPO rollout2048 làm actual steps=1.001.472 (489 rollout); A2C rollout5 đạt1.000.000. Báo actual budget; không coi số optimizer updates hay wall time bằng nhau.
- Gamma0,98, hidden layers[64,64]. PPO lr0,0003,10epochs,batch64,GAE0,95,clip0,2; A2C lr0,0007,rollout5,RMSProp. Đây là lựa chọn implementation đã có trong `drl/run.py`, không phải hyperparameter PPO/A2C do tác giả công bố. Không tune theo test.
- Tối đa3model đồng thời, CPU một Torch thread/model, venv server hiện tại; xác nhận package/Python khớp campaign DQN.

## Đánh giá và verification

Validation5task seed bắt đầu1.000.000, mỗi10.000step; best là mean lifetime cao nhất đầu tiên sau khi đã có optimizer update. Báo cả final. Test30seed4.000.000–4.000.029, giống DQN để ghép cặp. Các case này đã quan sát cho DQN; đây là đối chiếu development, không gọi là final unseen benchmark cho thuật toán mới.

PPO/A2C best/final và ba heuristic đều lưu trace; mô hình predict lại action từ state trước bước, verifier replay physics, RNG, pin, tuổi/reward. Kiểm tra checkpoint finite, actual rollout/update budget, source hashes và provenance checkpoint/summary DQN dùng lại. Heuristic lặp theo model/checkpoint là cùng case, không phải thêm mẫu độc lập.

Smoke train/save/load/replay trước full budget. Chỉ báo hoàn tất khi manifestCOMPLETE, verifierPASS, exit0. Xuất REPORT.md, summary.csv, verification.json và per-model logs/config/checkpoint. Một layout và3learning seed chưa chứng minh generalization hoặc superiority so với tác giả.

```bash
REFERENCE_DIR=target/reference-state-20261028-v1 OUT_DIR=target/reference-baselines-UNIQUE bash scripts/train-reference-baselines-server.sh --dry-run
REFERENCE_DIR=target/reference-state-20261028-v1 OUT_DIR=target/reference-baselines-UNIQUE bash scripts/train-reference-baselines-server.sh
```
