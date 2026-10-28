# Retrain đối chứng reward/freshness: đã khởi chạy

Cập nhật lúc **10:05 ngày 24/10/2026**, trên máy local. **Đang chạy, chưa có
kết quả cuối của đợt này.**

Đề xuất đã ghi trước launch:
[NEXT_EXPERIMENT_PROPOSAL.md](NEXT_EXPERIMENT_PROPOSAL.md).
Protocol máy đọc được:
[paper_convention_retrain_protocol.json](../../drl/paper_convention_retrain_protocol.json).

Run:
[paper-convention-retrain-20261024](../../target/paper-convention-retrain-20261024/).

| Nhóm | Trạng thái tại thời điểm kiểm tra | Ngân sách |
| --- | --- | --- |
| REFERENCE | Dùng lại 3 model fixed-layout đã audit; không train lại | Đủ 1m/model |
| REWARD_AFTER, seed 0/1/2 | Đã chạy và qua mốc validation 10.000 bước/model | 1m/model |
| LOCAL_COMPLETION, seed 0/1/2 | Trong hàng đợi, tự chạy khi worker trống | 1m/model |

Chạy tối đa 3 learner/JVM độc lập cùng lúc, Torch CPU một thread. Không thay
hyperparameter ngoài một property của từng nhóm. Không cần dataset mới.

Trước launch đã đạt 5 integration/protocol tests và 9 verifier tests. Kiểm tra
coverage tối ưu lạc quan cho thấy REFERENCE cần ít nhất 3 điểm phục vụ để phủ
các thiết bị luôn phụ thuộc UAV; LOCAL_COMPLETION cần ít nhất 7 điểm. Cả hai
không vi phạm cận cần thiết 10 slot ở phép kiểm tra này, nhưng đây **không phải
bằng chứng hệ thống có policy khả thi dài hạn**: còn flight, battery, work size
và thứ tự phục vụ. Không dùng cận này thay cho kết quả mô phỏng.

Controller tự chạy đủ 6 model, kiểm tra checkpoint/validation/source/runtime,
đánh giá và replay **540 trace mới** theo đúng profile. 270 reference rows được
dùng lại, không gọi là model hoặc case độc lập mới. `verification.json` và
`REPORT.md` cuối chỉ xuất sau các bước kiểm chứng; xem `manifest.json` trước khi
gọi đợt chạy là hoàn tất.

Theo dõi từ thư mục repo, PowerShell:

```powershell
Get-Content target/paper-convention-retrain-20261024/REWARD_AFTER/seed-0.log -Tail 10
Get-Content target/paper-convention-retrain-20261024.log -Tail 20
Get-Content target/paper-convention-retrain-20261024.err.log -Tail 20
Get-Content target/paper-convention-retrain-20261024/manifest.json -Raw
```

Chạy một campaign mới, không ghi đè:

```bash
python -u -m drl.paper_convention_retrain train --workers 3 --output target/paper-convention-retrain-new
```

Đợt này không tự mở rộng sang Table 5/6 đầy đủ, optimizer ablation, cache hoặc
joint algorithm. Source và kết quả ở local; chưa push hoặc đồng bộ server.
