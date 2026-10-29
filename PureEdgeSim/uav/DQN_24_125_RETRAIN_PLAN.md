# Train lại DQN24D và125D sau benchmark contact-wait

Yêu cầu29/10/2026, triển khai tiếp sang30/10: hoàn tất benchmark mới rồi train cả hai state và tạo lệnh tắt
máy Windows sau khi training được kiểm chứng. Không tự chạy lệnh shutdown.

## Phạm vi và cấu hình

Theo tên model sẵn có trong repo, dùng `paper24` và `extended125` của **nhánh paper
REFERENCE**, không gắn nhầm vào mobile129D/contact-wait. Đây là retrain riêng để
đối chiếu state, không phải DQN học offloading/scheduling trong môi trường mới.
Nếu chuyển sang mobile phải định nghĩa và kiểm chứng state/reward riêng trước.

- Protocol giữ nguyên `drl/paper_reference_state_protocol.json`.
- 6model =2state ×3learning seed0/1/2, mỗi model1.000.000step, tối đa3CPU worker,
  Torch1thread/model; không nạp checkpoint cũ, không tune hyperparameters.
- Layout0,12device,power8/comms8,synthetic2–4MB,slot cap600s,deliveryLEGACY,
  rewardBEFORE,expiryAT_LIMIT,radioLITERAL_DBM. DQN[64,64],lr0.0071,gamma0.98,batch16.
- Validation5seed từ1.000.000,eval mỗi10kstep; best theo validation và final đều báo.
  Test30seed4.000.000..4.000.029 đã là tập development dùng trước, không gọi fresh holdout.
- Campaign trước cùng protocol mất khoảng2h15 trên server; đây chỉ là tham chiếu.

## Trình tự và điều kiện hoàn tất

1. Contact-wait full run phải exit0, manifestCOMPLETE và audit/testPASS.
2. Publish/pull source; giữ remote executable mode tùy chỉnh của train-paper-server.sh.
3. `scripts/train-state-extension-server.sh`: Java/Python preflight, smoke cả2mode,
   train6model và replay checkpoint/physics/state/reward.
4. ManifestCOMPLETE, verificationPASS,1440evaluation traces, đủ12best/final checkpoint;
   mỗi final1mstep và249.975gradient update, source không đổi. Smoke phảiPASS32trace.
5. Job control giữ commit/protocol/PID/log/exit-code/timestamps và completion marker.

Không có task queue/deadline ảnh trong paper environment; offloading image DVR,
J/ảnh đúng hạn và image latency **không áp dụng** ở campaign này. Báo lifetime
slots/seconds và energy theo paper, không so trực tiếp với metric contact-wait.

## Tải kết quả và lệnh tắt máy

`scripts/wait-dqn-24-125.ps1` chạy hidden trên Windows, poll đúng task đã tạo trên
aiotlab_92; không dừng process người khác. Sau exit0 mới tải summary, metadata,
config, validation curves và12checkpoint. Kiểm tra state/seed/steps, protocol và
checkpoint SHA256, smoke/full PASS rồi ghi completion-checked.json.

Chỉ sau các bước đó mới tạo `Tat_may_sau_train.cmd` với:

```cmd
"%SystemRoot%\System32\shutdown.exe" /s /t 0
```

Lệnh dành cho máy Windows local, không phải server. Người dùng chạy thủ công;
không force-close ứng dụng. Nếu job/network/download/validation lỗi, watcher ghi
watcher-failed.json và không tạo lệnh mới. Có timeout12h và có thể chạy lại watcher.

Local gate tests không gọi SSH/shutdown:5case complete/running/corrupt checkpoint/
wrong state/wrong source. `-ValidateOnly` chỉ kiểm tra artifact, không tạo lệnh.
