# Thử cơ chế từ hai bài disaster, protocol trước launch

29/10/2026. Mục tiêu thực dụng: thích nghi phương pháp đã có, kiểm tra khi nào tốt hơn baseline; không yêu cầu novelty. Không train MARL hoặc tuyên bố tái hiện nguyên bản hai paper.

1. Fan et al.,2024, DOI10.1038/s41598-024-67886-x: thích nghi **deadline-risk guard tại UAV dispatch**. Giữ EDF/SPT, không ngắt running task; task dropped vẫn failure. Không có multi-stage negotiation, resource allocation hoặc MA-SDRC agent của bài gốc.
2. Kalinagac et al.,2023, DOI10.3390/s23052375: thích nghi ý ADP **tránh giao thêm cho processor đang nhận upload**. Với một UAV duy nhất, task mới chuyển LOCAL nếu UAV đang nhận bất kỳ upload nào; nếu không thì dùng DEADLINE_ENERGY. Không thêm controller waiting pool, xe hoặc cloud như paper. Bản này gọi TRANSFER_AWARE, không gọi ADP reproduction.

2routing(DEADLINE_ENERGY/TRANSFER_AWARE) ×4scheduler(EDF/SPT/guard+EDF/guard+SPT) =8policy. Dùng5seed93000–93004,3loads,2pin UAV,estimate error0 và±40%:480episode. Không fit threshold, rho hoặc reward. Các baseline cùng arrival/actual workload/pin/link. Source admission/upload có cùng quy tắc vật lý; gate là quyết định policy, không thay bandwidth model. Không thêm radio contention chỉ cho một phương pháp.

Các seed mới cho lượt này là development được chỉ định trước launch, không tuyên bố final niêm phong hoặc generalization. Horizon600s,4groundCPU500MIPS,UAV2000MIPS, raw pools/cost/deadline theo benchmark cũ. Fixed UAV và mọi source connected; mức phù hợp disaster mới ở payload ứng dụng và resource limits, chưa có outage scenario trong lượt này. Phải kiểm tra mobile/outage trước kết luận cứu hộ thực tế.

Đánh giá chính: image/background DVR và priority-weighted on-time service; energy tổng/runtime và mức dùng local/UAV báo cùng. Không chọn winner chỉ bằng joule. Hủy nhầm do estimate, gate khiến source yếu phải local và lợi ích giả do loại task đều phải báo nếu xuất hiện.

Verifier độc lập tái tính forecasts, EDF/SPT order, guard predicate, active-upload gate, deadline/status, work/energy/upload. Test hand-case cho upload boundary và future arrivals. Giữ snapshots/source/hash và full traces. Sau experiment không đổi cơ chế theo test vừa xem rồi gọi đó là cùng protocol.
