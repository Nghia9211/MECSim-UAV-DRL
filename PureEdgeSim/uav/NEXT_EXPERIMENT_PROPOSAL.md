# Đề xuất thí nghiệm tiếp theo: độ nhạy reward và freshness của DQN

Ngày 24/10/2026. Người dùng đã yêu cầu: sau khi run xong, viết đề xuất `.md` rồi
chạy luôn. **Đề xuất này được ghi sau khi đối chứng seed hoàn tất và trước khi
khởi chạy các model bên dưới.** Đây là kiểm chứng implementation paper, chưa
phải đề xuất thuật toán offloading hoặc scheduler mới.

## Bằng chứng làm cơ sở

Trên layout 0 cố định, ba learning seed đều tìm được best-validation checkpoint
đạt 32 slot. Tuy nhiên final checkpoint đạt 30; 30,367; và 10 slot. Cả 270 trace
đã replay độc lập, model/source/runtime đã được kiểm tra. Seed 2 cuối training
vi phạm tuổi dữ liệu ở cả 30 case dù best của nó kết thúc do pin UAV.

Do đó, **không thể kết luận chỉ cần giữ layout cố định thì DQN ổn định**. Cần
kiểm tra những lựa chọn reward/freshness còn chưa được paper mô tả đủ chi tiết.
Chưa biết nguyên nhân suy giảm có phải reward, optimizer, target update hoặc
yếu tố khác; đợt này không thay tất cả chúng cùng lúc.

## Câu hỏi và giả thuyết có thể kiểm chứng

1. **Reward timing:** chụp tuổi dữ liệu A/O trước hay sau cập nhật age có thay
   đổi lifetime, số episode hết hạn dữ liệu và khoảng cách best–final không?
   Giả thuyết H1 là có ảnh hưởng; không giả định AFTER tốt hơn. Khi reset age
   về 0, logarithm/clamp có thể làm reward AFTER rất khác.
2. **Completion semantics:** yêu cầu local xử lý xong mới cập nhật age có làm
   thay đổi bottleneck, hành vi phục vụ và lifetime không? H2 là có ảnh hưởng.
   Đây là thay đổi model, không tự coi là sửa đúng code tác giả.

## Thiết kế khóa trước khi chạy

| Nhóm | Thay đổi so với REFERENCE | Learning seed | Model train mới |
| --- | --- | --- | ---: |
| REFERENCE | Không đổi; dùng lại bộ fixed-layout đã audit | 0/1/2 | 0 |
| REWARD_AFTER | `paper.rewardSnapshot=AFTER` thay `BEFORE` | 0/1/2 | 3 |
| LOCAL_COMPLETION | `paper.deliveryConvention=COMPLETED` thay `LEGACY` | 0/1/2 | 3 |

Mỗi nhóm chỉ đổi **một property**; không tạo nhóm đổi cả hai. Mỗi model mới
train **1.000.000 bước**, cùng DQN hyperparameters đã công bố và lựa chọn SB3
cũ. Không hạ learning rate, thay network, buffer hoặc target-update trong đợt này.

Giữ layout 0, hardware/task/capacity/masks, power 8/comms 8, synthetic 2–4 MB,
slot cap 600 giây, kênh literal dBm, age≥10 và epsilon 1e−6. Learning seed được
ghép cặp với REFERENCE; training task-seed stream có thể đi qua số episode khác
nhau do transition/termination khác. Không gọi là cùng toàn bộ training trajectory.

Best checkpoint chọn theo mean lifetime của 5 validation case, giữ checkpoint
đầu khi hòa. Final đúng 1m là diagnostic riêng. Đánh giá 30 task seed như bộ
development hiện tại; không gọi là final-test chưa từng mở. Không chọn biến thể
vì nó cho số gần 18,3 slot của paper.

## Metrics và tiêu chí kết luận

- Primary: mean lifetime slots của best-validation checkpoint, từng learning
  seed và mean/SD giữa ba run means; báo cáo thêm seconds và fully elapsed slots.
- Secondary: final1m lifetime, best–final gap, tần suất failure do data age/pin,
  diễn biến validation và runtime/optimizer loss hữu hạn.
- So reward curves trong từng định nghĩa; **không so tổng reward giữa hai
  công thức như thể cùng thang objective**. Không dùng raw reward để chọn winner.
- Mỗi profile chạy RR/Oldest/Random một lần/case trong bảng chính. Không nhân
  baseline theo learner. Dự kiến **540 trace mới**: 2 profile ×(90 best DQN +
  90 final DQN + 90 heuristic), ngoài 270 trace REFERENCE dùng lại đã audit.
- Replay độc lập từng trace theo đúng profile: action, RNG/layout, duration,
  energy/battery, age/expiry/reward; kiểm tra source/checkpoint/runtime hashes.
- Khác biệt không tự chứng minh convention nào là code tác giả. Mẫu ba seed
  trên một layout không đủ để tuyên bố superiority, generalization hoặc phân
  rã phương sai. Kết quả âm hoặc suy giảm vẫn được báo cáo.

## Thực thi và giới hạn

Run tối đa 3 learner/JVM độc lập cùng lúc, Torch CPU một thread; hai đợt cho
6 model mới. Dùng thư mục output mới, giữ nguyên model và log REFERENCE. Không
cần GPU hoặc dataset mới. Phải kiểm tra test/preflight trước khi launch.

Sau đợt này mới quyết định cần kiểm tra optimizer/learning rate, mở rộng layout,
Table 5/6 hay quay lại nghiên cứu offloading+scheduling. Chưa tự động triển khai
thêm cache, joint algorithm hoặc workload dataset thật trong các đối chứng này.
