# Kế hoạch đối chứng quy ước sau khi tách learning seed

> **Cập nhật 24/10:** đối chứng seed đã hoàn tất; đề xuất được chốt trong
> [NEXT_EXPERIMENT_PROPOSAL.md](NEXT_EXPERIMENT_PROPOSAL.md) và 6 model mới đã
> được đưa vào hàng đợi chạy. Trạng thái và cách theo dõi ở
> [PAPER_CONVENTION_RETRAIN_STATUS.md](PAPER_CONVENTION_RETRAIN_STATUS.md).
> Phần dưới là bản kế hoạch trước khi khởi chạy.

Ngày24/10/2026. **Đây là kế hoạch; chưa khởi chạy các model trong bảng dưới.**
Thí nghiệm đang chạy ở [PAPER_SEED_ISOLATION.md](PAPER_SEED_ISOLATION.md) phải
được kiểm chứng trước khi dùng các model đó làm baseline cho bước tiếp theo.

Mục đích là kiểm tra mức độ phụ thuộc của kết quả DQN vào chi tiết còn mơ hồ
trong paper. Không đổi môi trường mobile/offloading/scheduler và không tìm một
quy ước chỉ vì nó cho số gần18,3slot hơn.

| Nhóm | Thay đổi duy nhất | Seed huấn luyện | Ngân sách dự kiến |
| --- | --- | --- | --- |
| REFERENCE | Không đổi; dùng lại3model đủ1m trên layout0 đã audit | 0/1/2 | Không train lại |
| REWARD_AFTER | Chụp A/O sau cập nhật age thay vì trước; reward vẫn gọi cuối step | 0/1/2 | 3model ×1m |
| LOCAL_COMPLETION | Connected local chỉ reset age sau khi thực sự xử lý xong | 0/1/2 | 3model ×1m |

Giữ cố định layout0, source hardware/task/capacity/outage masks, hyperparameters,
1mstep/model, validation/task-seed ranges, rule chọn checkpoint và toàn bộ yếu
tố khác. So REWARD_AFTER với REFERENCE và LOCAL_COMPLETION với REFERENCE riêng,
không thay hai yếu tố đồng thời. Đây là adaptation sensitivity, không tự nhận
biến thể nào đúng như code tác giả.

Hai nhóm được ưu tiên vì convention audit đã thấy reward có thể đổi mạnh mà
physics heuristic không đổi, còn completion/freshness làm lifetime heuristic
đổi đáng kể. Điều này mới cho biết nên kiểm tra, chưa chứng minh tác động DQN.

Nếu thực hiện, phải báo cáo:

- Best-validation và final1m riêng; không dùng test để đổi checkpoint.
- Lifetime slots và seconds, failure causes, cap frequency, completion/age,
  reward curves và runtime; không so tổng reward trực tiếp giữa hai định nghĩa
  reward như thể cùng một objective scale.
- Chênh lệch ghép cặp theo learning seed và cùng task cases. Với3learning seed,
  ưu tiên mô tả từng run và bất định, chưa đưa tuyên bố superiority chắc chắn.
- Trace replay theo đúng profile của từng run, source/model/config hashes và
  tham số môi trường. Các output trung gian hoặc run thiếu ngân sách phải ghi rõ.
- Kết luận chỉ có điều kiện trên layout0 development. Muốn tổng quát hóa, cần
  nhiều layout độc lập với nhiều learning seed/layout và protocol mới đã khóa.

Sau bước này mới có căn cứ quyết định cần mở rộng Table5/6 hay quay lại mục tiêu
offloading+scheduling. Không cần tải dataset mới cho các đối chứng synthetic.
