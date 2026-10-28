# Chẩn đoán thất bại LOCAL_COMPLETION

Ngày: 2026-10-28. Phân tích hậu nghiệm, không đổi simulator/reward, không train thêm. Phạm vi: layout 0, synthetic, 3 learning seed; không suy rộng sang mọi layout hoặc môi trường mobile.

## Kết luận

Nguyên nhân trực tiếp là policy DQN bỏ sót các thiết bị cần được UAV cập nhật trước 10 slot. Môi trường khó hơn đáng kể khi connected không còn đồng nghĩa tự cập nhật thành công. Không có bằng chứng môi trường bất khả thi: Oldest Data đạt 29 slot và dừng vì UAV cạn pin, trong khi toàn bộ 180 episode DQN best/final dừng vì tuổi dữ liệu.

Chưa chứng minh được nguyên nhân tối ưu hóa (reward, observation, exploration hay optimizer) bằng can thiệp. Các mục bên dưới tách bằng chứng trực tiếp khỏi giả thuyết.

## Dữ liệu và cách kiểm tra

Nguồn: `target/paper-convention-retrain-20261024/episodes.csv`, các trace LOCAL_COMPLETION và snapshot source cùng campaign. Đã đọc 270 episode: 180 DQN best/final + 90 heuristic. Best/final dùng cùng case, không coi là 180 mẫu độc lập. 30 task seed dùng chung một layout; không phải 30 bố trí độc lập.

Chạy lại từ MECSim:

```powershell
.\.venv-drl\Scripts\python.exe scripts/analyze-local-completion.py
```

Evidence: `target/local-completion-diagnosis/evidence.json`. Script tính lại reward từ tuổi trước action, tính lại delivery/age từ bytes, rate, coverage flags, completion và duration, rồi kiểm tra failure tuổi dữ liệu. Đạt 3.465 slot reward, 41.580 chuyển tuổi thiết bị và 3.465 kiểm tra termination. Đây là kiểm tra logic tuổi/reward từ trace; không thay thế replay physics hoặc xác minh checkpoint đã làm ở campaign. Bảng rate đọc từ source snapshot của experiment, có checksum khớp source hiện tại.

## 1. Quy ước mới tăng số thiết bị phụ thuộc UAV từ 4 lên 9

REFERENCE synthetic reset tuổi cho thiết bị connected ngay cả khi local chưa xử lý xong. LOCAL_COMPLETION yêu cầu local hoàn tất trong slot hoặc được UAV phục vụ thành công. Trong cả hai chế độ, upload chưa xong không được cập nhật.

Trên layout 0 có 4 thiết bị disconnected: 2, 5, 8, 10. Thêm 5 thiết bị connected không thể hoàn thành task local dù task nhỏ nhất 2 MB:

| ID | Hardware / task | Local time cho 2–4 MB | Có kết nối |
| --- | --- | ---: | --- |
| 1 | Firefly / DNN | 2.107–4.213 s | Có |
| 3 | NanoPC T4 / DNN | 2.055–4.111 s | Có |
| 6 | Raspberry Pi 3B / HAAR | 725–1.450 s | Có |
| 7 | Firefly / YOLOv3 | 732–1.463 s | Có |
| 11 | Firefly / DNN | 2.107–4.213 s | Có |

Dấu chấm trong bảng là phân tách hàng nghìn. Cap chỉ 600 s; công việc local chưa xong không giữ tiến độ qua slot. Vì vậy năm thiết bị trên không tự cứu được qua các slot tiếp theo. Tổng cộng 9 thiết bị cần UAV trực tiếp hoặc coverage lân cận để cập nhật. Phải phục vụ đủ trước khi tuổi đạt 10; việc chỉ phủ một nhóm quen thuộc sẽ thất bại.

Đây là thay đổi bài toán thực sự, không chỉ thay tên metric hoặc độ lớn reward.

## 2. Kết quả hành vi

| Policy/checkpoint | Seed | Mean slot | Pin UAV còn khi dừng |
| --- | ---: | ---: | ---: |
| DQN best | 0 | 10,50 | 1.001 kJ |
| DQN best | 1 | 14,00 | 815 kJ |
| DQN best | 2 | 12,00 | 957 kJ |
| DQN final | 0 | 10,00 | 1.093 kJ |
| DQN final | 1 | 10,00 | 1.016 kJ |
| DQN final | 2 | 10,00 | 1.056 kJ |
| Oldest Data | — | 29,00 | 0 kJ |
| Round Robin | — | 10,00 | 1.037 kJ |
| Random | — | 10,00 | 1.051 kJ |

Mức pin cao khi DQN dừng không phải tiết kiệm năng lượng thành công: hệ thống ngừng sớm do dữ liệu quá cũ. Mean best DQN 12,17 slot thấp hơn 29 slot của Oldest Data khoảng 58,0%.

DQN final seed 0 không phục vụ thành công thiết bị 1, 6, 8 lần nào trong mọi episode test. Cả ba đạt tuổi 10 ở cuối episode. Final seed 1 không phục vụ 1, 7, 8; final seed 2 không phục vụ 2, 7, 10, 11. Đây là bằng chứng trực tiếp về bỏ sót thiết bị; không chỉ suy ra từ score thấp.

Round Robin đi qua ID 0–9 trước khi kết thúc, không cập nhật được ID 11; cycle 12 thiết bị không phù hợp với hạn 10 khi vẫn ghé các thiết bị tự xử lý tốt. Oldest Data bỏ qua nhiều lượt phục vụ không cần thiết bằng cách chọn tuổi lớn nhất và có tie-breaking quay vòng.

## 3. Một trace cụ thể

Best seed 0, task seed 2000000:

```text
Action: 3 → 9 → 8 → 11 → 6 → 7 → 1 → 10 → 11 → 3
Slot:   1   2   3    4   5   6   7    8    9  10
```

Thiết bị 5 không được phục vụ thành công lần nào và đạt tuổi 10. UAV còn 1.039.578 J. Policy quay lại 11 và 3, trong khi thiết bị 5 đang sắp hết hạn. Task seed này chỉ là ví dụ, không phải phép chứng minh tất cả seed đi cùng action sequence.

## 4. Reward phản ánh nguy cơ chưa trực tiếp

Reward hiện dùng `slot + log(max(epsilon, age_selected_before) / max(epsilon, max_age_before))`, không có penalty riêng khi một thiết bị khác đạt tuổi giới hạn.

Trong ví dụ trên, slot 9 được +8,307 và slot cuối vẫn +9,749 dù ID 5 hết hạn. Reward phạt chọn thiết bị trẻ hơn oldest nhưng không ràng buộc trực tiếp mọi thiết bị phải được phục vụ. Nếu có nhiều thiết bị cùng già, chọn một trong số đó nhận log-ratio bằng 0, dù bỏ thiết bị khác đến hạn.

Tuy nhiên, termination loại bỏ reward tương lai và Oldest Data đạt return cao hơn. Do đó không kết luận reward khuyến khích chết sớm hoặc objective hoàn toàn sai. Giả thuyết hợp lý là tín hiệu dài hạn khó học hơn khi số thiết bị phụ thuộc UAV tăng và nhiều task phải chờ nhiều slot.

Tỷ lệ chọn một thiết bị đồng tuổi với oldest: best seeds 0/1/2 là 74,3% / 67,9% / 72,2%; final là 50,0% / 55,3% / 38,0%. Tỷ lệ này không phải tỷ lệ action đúng tối ưu; chọn không-oldest đôi khi có lợi do coverage, pin hoặc đường bay.

## 5. Observation và bất ổn học: các giả thuyết cần thử

State paper chỉ có 12 battery fraction + 12 age. Nó không chứa vị trí UAV, hardware/task, connected flag hoặc slot index, dù các yếu tố này ảnh hưởng transition hoặc reward. Vì vậy không nên coi 24D này là biểu diễn Markov đầy đủ trong simulator. Fixed layout cho phép học một phần ý nghĩa ID, nhưng không loại bỏ hoàn toàn thông tin vị trí hiện tại bị ẩn.

Đây là hạn chế cấu trúc, chưa chứng minh nó gây ra thất bại đã thấy. Oldest Data chỉ cần tuổi vẫn giải tốt layout này, nên cũng chưa có bằng chứng bắt buộc phải tăng state mới cứu được DQN.

Best > final ở cả ba seed LOCAL_COMPLETION cho thấy chất lượng policy bị suy giảm theo training; không chỉ thiếu thời gian train. Các run vẫn có đủ gradient updates theo audit đã lưu. Chưa đo Q-value, gradient stability hoặc replay distribution trong đợt phân tích này; không kết luận learning rate hoặc exploration là nguyên nhân đã được xác nhận.

## 6. Thử nghiệm tiếp theo đề xuất, chưa chạy

1. Giữ nguyên LOCAL_COMPLETION, train reward AFTER trên cùng layout/seed/ngân sách, đối chiếu reward BEFORE đã có. Đây là kiểm tra tương tác vì REWARD_AFTER trước đó chỉ được thử với delivery REFERENCE, chưa chứng minh giúp LOCAL_COMPLETION.
2. Thử thêm đúng một penalty termination do tuổi dữ liệu hoặc biến thể reward freshness, với magnitude được chốt bằng validation. Không thay reward, observation và optimizer cùng lúc. Reward mới là thuật toán mở rộng, không gọi là reproduction nguyên bản.
3. Nếu vẫn thất bại, đối chứng thêm thông tin trạng thái hiện tại (vị trí, cờ availability, service cost) hoặc kiểm tra hyperparameter từng yếu tố. Không dùng test hiện có để chọn tiếp config; các case đã phân tích là development, cần reserve test mới cho xác nhận.
4. Giữ Oldest Data làm mốc feasibility, báo cả best/final, missed-device counts, age trajectory, coverage và remaining battery. Không chỉ báo mean lifetime hoặc energy.

Không cần train nhiều bước hơn ngay. Ưu tiên chốt protocol cho phép thử reward interaction trước; reproduction REFERENCE giữ nguyên và báo khác biệt semantics công khai.

## 7. Xác minh code bổ sung ngày 2026-10-28

- Build và chạy toàn bộ Maven tests: 109 test, không failure/error (gồm 2 ca biên bổ sung). Hai ca biên được tách sang `PaperCompletionBoundaryTest.java` để giữ nguyên checksum file test thuộc snapshot thí nghiệm.
- 11 Python paper integration/protocol tests đạt; 9 corruption tests của verifier đạt.
- Replay lại 540 episode của REWARD_AFTER và LOCAL_COMPLETION từ artifact đã lưu: 130.788 hàng thiết bị, 12 checkpoint. Action được tính lại từ checkpoint theo state trong trace; physics, RNG, tuổi, termination và reward được đối chiếu bằng verifier Python độc lập. 90 checksum snapshot đạt. Receipt: `target/local-completion-diagnosis/full-reverification.json`.
- Lỗi vận hành phát hiện: classpath Python–Java chứa đường dẫn ổ C cũ sau khi chuyển workspace. Đã chạy lại `scripts/build-drl.ps1 -Offline`; chỉ cập nhật artifact runtime, không thay simulator/checkpoint.

Kết luận giới hạn: chưa tìm thấy sai lệch implementation đối với quy ước đã công bố trong các kiểm tra trên. Không đồng nghĩa đã xác nhận đúng toàn bộ ý tác giả. Cap bỏ công việc dở, không fallback local khi đang offload, output link tức thời và reset tuổi connected của REFERENCE vẫn là giả định mô hình; LOCAL_COMPLETION cố ý thay delivery semantics. Mọi thay đổi các quy tắc này phải chạy thành đối chứng mới, không sửa âm thầm kết quả cũ.
