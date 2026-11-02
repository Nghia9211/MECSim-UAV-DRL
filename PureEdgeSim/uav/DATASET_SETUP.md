# Dataset đang sử dụng

Dữ liệu đã có sẵn, không cần tải lại:

```text
datasets/raw/
  rescuenet/validation/val-org-img/
  rescuenet/validation/val-label-img/
  alibaba2018/batch_task.csv
```

Đường dẫn và các giả định tính toán nằm trong `dataset_defaults` của
[`scenarios.json`](../../scenarios.json). Chạy từ MECSim:

```powershell
.\scripts\run-paper-datasets.ps1 -Mode single -Offline
.\scripts\run-paper-datasets.ps1 -Mode evaluate -Seeds 30 -Offline
```

Xem [DATASET_EVALUATION.md](DATASET_EVALUATION.md) để hiểu cách trộn và kết quả.
RescueNet dùng metadata ảnh, chưa chạy inference; Alibaba lấy mẫu task hợp lệ,
chưa replay toàn bộ cluster. MI/MIPS và công suất CPU là giả định khai báo trong
`scenarios.json`, được lưu trong `dataset-config.txt` mỗi lần chạy. Raw dataset không bị sửa.

Các entry point milestone chạy riêng trước đây đã được gỡ. Dùng chế độ dataset
trong `PaperSimulation` và runner `PaperDatasetEvaluation` cho đánh giá hiện tại.
