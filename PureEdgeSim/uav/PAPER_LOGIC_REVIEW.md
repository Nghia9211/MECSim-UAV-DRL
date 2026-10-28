# Rà soát logic nhánh paper / LOCAL_COMPLETION

Ngày 2026-10-28. Phạm vi chính: `PaperSimulation`, `PaperConventions`, `PaperGymBridge`, `drl/environment.py`, đường chọn baseline và cập nhật state/reward. Đã đọc thêm UAV motion/energy, CPU plan và một số đường mobile/offloading; không phải audit toàn bộ MECSim hoặc chứng nhận mọi nhánh đều không lỗi.

## Kết luận

Chưa xác nhận được bug implementation trong đường synthetic LOCAL_COMPLETION giải thích việc DQN dừng sớm. Không sửa thuật toán khi chưa có ca tái hiện chứng minh sai. Kết quả âm của DQN là thật trong semantics hiện tại, nhưng semantics và biểu diễn RL có hạn chế đáng kể.

## Các invariant đã rà trực tiếp

- Local time = bytes / rate / localRateScale; active energy chỉ tính trong phần thời gian đã chạy, cộng standby xuyên slot.
- Coverage được xét theo khoảng cách 3D đến đích; truyền bắt đầu sau flight; slot dừng ở pin cạn sớm nhất và cap. Đây là abstraction phục vụ tại điểm đến, không phải upload dọc đường bay.
- LOCAL_COMPLETION chỉ reset tuổi khi upload/compute tương ứng hoàn thành hoặc local ngoài coverage hoàn thành và connected. Không reset chỉ vì có kết nối.
- Tuổi tăng một lần ở cuối slot; expiry `AT_LIMIT` là >=10, `ABOVE_LIMIT` là >10.
- Tuổi dùng cho reward BEFORE được chụp trước action; AFTER dùng tuổi sau cập nhật. Epsilon tránh log(0); không đọc task tương lai trong observation.
- Gym reset tạo manager/engine mới; step dùng observation trước/sau đúng thứ tự; action DQN là integer 0..11. Physical termination và safety truncation tách nhau.
- Powered device không bị trừ pin dự phòng, nhưng energy tiêu thụ vẫn được báo; đây là quy ước nguồn ngoài.
- UAV flight/hover không bị cộng hai lần trong synthetic; trong dataset CPU load được tích phân qua các mốc job.

## Các vấn đề thiết kế chưa nên gọi là bug

### 1. Không tích lũy tiến độ local qua slot — ảnh hưởng rất lớn

`beginSlot` lấy task mới; cuối slot bỏ phần chưa xong. Các thiết bị có min local time >600s không bao giờ hoàn thành local dù nhiều slot liên tiếp. Điều này giải thích vì sao COMPLETED làm 5 thiết bị connected trở thành phụ thuộc UAV. Nếu chủ đích là xử lý task đến khi xong, semantics này phải đổi sang queue/progress bền. Nếu chủ đích là workload độc lập theo slot với hard cap thì code hiện tại đúng. Không sửa âm thầm vì sẽ tạo môi trường khác và làm kết quả train cũ không còn trực tiếp so sánh.

### 2. State 24D không biểu diễn đủ trạng thái môi trường

Không có vị trí UAV, UAV battery, hardware/task, connected/powered flags hoặc thời gian/slot. Vị trí ảnh hưởng flight/energy; slot ảnh hưởng reward. Do đó cùng observation 24D không đảm bảo cùng transition/reward distribution. Đây là hạn chế observability đối với MLP DQN. Chưa có can thiệp chứng minh nó là nguyên nhân chính; Oldest Data vẫn thành công trên layout đang xét. Thêm state phải gọi là biến thể, không còn giữ nguyên state paper.

### 3. Reward không phản ánh trực tiếp failure của thiết bị khác

Reward có thành phần tuổi selected/oldest và slot, không terminal-age penalty riêng. Có terminal step vẫn được reward dương. Termination vẫn loại bỏ future return, nên không suy ra objective luôn ưu tiên chết sớm. Cần ablation reward chứ không tự sửa theo kết quả test.

### 4. Trong coverage không có fallback local

Kernel gán covered device sang upload; nếu upload chậm/chưa xong, không chạy local song song hoặc quay về local, kể cả thiết bị connected có CPU nhanh. Đây là hạn chế action/routing trong nhánh paper. Nhánh offloading mới có lựa chọn riêng. Nếu yêu cầu là joint local/UAV theo từng task, không nên dùng nhánh paper để đại diện khả năng đó.

### 5. Slot cuối bị dở vẫn được tính một slot

`slot++` trước khi phát hiện failure; reward/lifetime đếm cả attempted slot cuối. Cần đọc lifetime theo slot cùng giây và completed-slot diagnostic. Đây là quy ước metric đã công bố, chưa có bằng chứng khác tác giả. Không gọi attempted slots là số slot hoàn thành trọn vẹn.

## Chứng cứ

- 46 production files liên quan khớp checksum snapshot dùng để train; không có thay đổi code hậu nghiệm giải thích score thấp.
- Đợt kiểm tra liền trước: full Java 109 test, Python paper 11, corruption verifier 9 đạt. Full replay 540 episode, 12 checkpoint, 130.788 device rows đạt.
- Lần rà logic này chạy lại analysis trên 270 trace: 3.465 slot reward, 41.580 chuyển tuổi, 3.465 age-termination checks đạt. Chạy lại test Java/Python tập trung các nhánh paper/completion.
- Classpath ổ C cũ đã được build lại ở đợt trước; lỗi đó chặn startup, không âm thầm thay kết quả của model.

Chi tiết hành vi thất bại và experiment tiếp theo: [LOCAL_COMPLETION_DIAGNOSIS.md](LOCAL_COMPLETION_DIAGNOSIS.md).

## Quyết định

Giữ nguyên reproduction. Với phiên bản nghiên cứu mới, ưu tiên chốt có cho carry-over task hay không và tách semantics đó khỏi reward. Thử mỗi thay đổi trên protocol validation cố định; dùng test mới cho xác nhận. Không tăng ngân sách train chỉ để che một mô hình hoặc state chưa phù hợp.
