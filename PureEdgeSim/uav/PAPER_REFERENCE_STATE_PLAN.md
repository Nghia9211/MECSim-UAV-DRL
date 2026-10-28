# Train lại state trên setting REFERENCE của nhánh paper

Ngày lập protocol: 2026-10-28, sau kết quả âm LOCAL_COMPLETION. Kế thừa state125 nhưng không thay dữ liệu hoặc xóa kết quả thí nghiệm trước.

## Câu hỏi

DQN24 có phục hồi lifetime khi quay lại delivery REFERENCE không? Trên cùng setting đó, state125 có cải thiện so với state24 không? Kết quả trước của LOCAL_COMPLETION không được coi là kết quả reproduction paper.

## Cấu hình khóa trước train

`drl/paper_reference_state_protocol.json` sao chép protocol state extension trước. Chỉ thay `paper.deliveryConvention` từ COMPLETED sang LEGACY trong các thông số môi trường; đổi tập đánh giá sang task seed 4.000.000–4.000.029 để reserve test mới. Các thông số còn lại giữ nguyên: layout0; 12 thiết bị, 8 có nguồn/8 có kết nối; synthetic 2–4 MB; cap600s; expiry >=10; reward BEFORE; state24 hoặc state125; DQN [64,64], lr0.0071, gamma0.98, batch16; 1 triệu bước/model.

LEGACY ở đây nghĩa là thiết bị connected hoặc upload thành công được reset tuổi. Đây là implementation REFERENCE đã công bố, không phải xác nhận tác giả cũng dùng mọi quy ước giống hệt. Các bất định channel, slot cuối và output-link trong PAPER_ALIGNMENT vẫn giữ nguyên.

6 model: 2 state × 3 learning seed (0,1,2), tối đa3 tiến trình CPU, một Torch thread/model. Không dùng lại checkpoint LOCAL_COMPLETION. Validation bắt đầu1.000.000; best validation và final đều được báo; test không dùng chọn checkpoint. Heuristic Round Robin/Oldest Data/Random cùng môi trường và task seed. Mẫu heuristic lặp lại qua learner/checkpoint không phải mẫu độc lập bổ sung.

## Điều kiện hoàn tất

Preflight Java/Python, smoke train/save/load/replay cả hai mode, sau đó mới full budget. Kiểm tra source hash, đủ1m bước và249.975 gradient updates, tái tính action checkpoint, state125 và toàn bộ physics/age/reward từ trace. Manifest COMPLETE, verification PASS và job exit0 mới gọi là hoàn tất.

Kết quả chỉ là một cấu hình/layout development của paper; chưa tái hiện đủ Table5/6, chưa SUMO, chưa chứng minh tổng quát trên layout mới. Tăng input125 cũng tăng số tham số; hidden architecture giữ nguyên.

## Chạy

```bash
PLAN_FILE=drl/paper_reference_state_protocol.json OUT_DIR=target/reference-state-UNIQUE bash scripts/train-state-extension-server.sh --dry-run
PLAN_FILE=drl/paper_reference_state_protocol.json OUT_DIR=target/reference-state-UNIQUE bash scripts/train-state-extension-server.sh
```

Đầu ra REPORT.md, summary.csv, manifest.json, verification.json và full trace nằm trong OUT_DIR mới. Báo cáo setting và checkpoint phải ghi riêng, không gộp lifetime REFERENCE và LOCAL_COMPLETION.
