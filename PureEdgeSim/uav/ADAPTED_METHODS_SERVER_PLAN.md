# Áp dụng phương pháp vào setting hiện tại: đợt server

29/10/2026. Theo yêu cầu người dùng, không tái hiện topology/agent của tác giả. Giữ fixed UAV, local/UAV routing và CPU scheduling hiện tại. Không cần train DRL cho hai cơ chế heuristic này.

So DEADLINE_ENERGY với TRANSFER_AWARE (ý tưởng điều tiết transfer từ Kalinagac2023); mỗi routing ghép EDF/SPT và bản có deadline-risk guard (cảm hứng Fan2024). Cơ chế, sự khác biệt với paper và giới hạn ở [TWO_PAPER_ADAPTATION_RESULTS.md](TWO_PAPER_ADAPTATION_RESULTS.md).

Đợt mới:30seed94000–94029,3mức tải,2mức pin,8policy,estimate error0/±40% =2880episode. Các seed này được chốt sau pilot5seed, không dùng để tune cơ chế trong đợt chạy. Không gọi là final deployment validation vì hardware/cost/dataset mapping còn giả định. Mọi policy nhận cùng actual workload/hash và pin. Không thêm radio contention hoặc cho thêm quyền chờ/retry chỉ để gate thắng.

Server aiotlab_92, repo `/mnt/disk1/nghialt2/MECSim-UAV-DRL`. Runner `scripts/run-adapted-methods-server.sh`, output prefix riêng trong target, job tmux riêng. Chạy Java tests rồi benchmark/replay cả2mức error; require exit0,2manifestCOMPLETE,2verificationPASS và completion marker. Không coi tmux launch là hoàn tất.

Sau khi hoàn tất: tải manifest,verification,summary/REPORT/log về local; ghi biên bản. Người dùng đã yêu cầu tắt máy Windows sau khi thiết lập/chạy/verify/lưu xong. Không tắt server hoặc job của người khác.
