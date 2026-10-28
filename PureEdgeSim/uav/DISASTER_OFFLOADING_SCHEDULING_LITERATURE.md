# Tham khảo phương pháp offloading–scheduling cho thiên tai

Ngày tra cứu: 29/10/2026. Mục tiêu theo yêu cầu người dùng: **chạy được, kiểm chứng được và cải thiện so với baseline; không bắt buộc novelty cao**. Đây là tìm kiếm có mục tiêu, chưa phải systematic review.

## 1. Kết luận lựa chọn

Không cần thiết kế một thuật toán hoàn toàn mới. Nên thích nghi một cơ chế đơn giản từ nghiên cứu emergency, giữ EDF/SPT và DEADLINE_ENERGY làm baseline mạnh. QIOS hiện là prototype có kết quả âm ở routing, không bắt buộc giữ làm phương pháp cuối.

Hai bài ưu tiên đọc phương pháp là **Fan et al. (2024)** về kiểm soát rủi ro deadline trong emergency monitoring và **Kalinagac et al. (2023)** về offloading có ưu tiên trong mạng UAV hậu thiên tai. Chúng gần bài toán ứng dụng hơn các bài UAV-MEC/DAG tổng quát.

“Tốt hơn” cần định nghĩa trước: nhiều ảnh được chuyển kết quả đúng hạn hơn dưới cùng ngân sách pin; báo cả năng lượng, background, drops và runtime. Không nhận giảm joule là thành công khi số task được phục vụ cũng giảm. Nếu baseline đơn giản đã tốt nhất thì dùng baseline đó, không cần ép QIOS thắng.

## 2. Tài liệu gắn trực tiếp với emergency/disaster

### D1 — Fan, Lin, Ai và Xu, 2024: ưu tiên cao nhất

**Adaptive task migration strategy with delay risk control and reinforcement learning for emergency monitoring.** Scientific Reports14,17606. DOI: [10.1038/s41598-024-67886-x](https://doi.org/10.1038/s41598-024-67886-x). [Full text nhà xuất bản](https://www.nature.com/articles/s41598-024-67886-x).

Đã đọc mô hình, MA-SDRC và thiết lập thực nghiệm. Bài mô phỏng sau động đất: UAV thu ảnh/video, sensor mặt đất và UAV edge. Phương pháp kết hợp MARL với kiểm tra rủi ro trễ qua các giai đoạn truyền, queue và compute; có early discard để thu hồi tài nguyên. Đây là liên quan emergency thực sự trong mô hình mô phỏng, không phải chứng cứ triển khai cứu hộ thực địa. Xem mục “Emergency monitoring network architecture”, “MA-SDRC algorithm design”, “Experimental setup”.

**Áp dụng đề xuất của chúng ta, chưa phải tái hiện nguyên bản:** thử deadline-risk guard với EDF/SPT trước; chưa cần MARL. Không chép deadline của bài sang RescueNet khi chưa hiệu chuẩn compute/link. Quyền early-drop mới phải áp dụng đồng đều cho mọi đối chứng trong thí nghiệm riêng; drop vẫn tính failure.

### D2 — Kalinagac, Gür và Alagöz, 2023: ưu tiên cao

**Prioritization Based Task Offloading in UAV-Assisted Edge Networks.** Sensors23(5),2375. DOI: [10.3390/s23052375](https://doi.org/10.3390/s23052375). [Full text PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10007597/).

Đã đọc §3–5 và discussion. Bối cảnh là vận hành hậu thiên tai, nhưng UAV chủ yếu làm access/network; processor là xe và cloud. Có priority-weighted deadline penalty, AGG-1/AGG-2 và ADP. ADP tránh giao thêm vào processor đang nhận transfer; Q-OPT dùng dữ liệu đã ghi kiểu oracle, không phải online baseline công bằng. AGG-1/2 khác nhau ở thứ tự assignment và hoàn thành transmission.

**Áp dụng đề xuất:** thử hạn chế dồn offload theo backlog/transfer và so thứ tự ready với assignment. Vì chiều offloading/topology khác, phải ghi là adapted heuristic. Nếu cho phép chờ trong controller pool thì đó là action mới so với quyết định ngay tại arrival; không âm thầm thêm cho riêng phương pháp đề xuất.

### D3 — Zhu, Zhao, Wei, Ma và Lv, 2023: liên quan disaster nhưng khác topology

**Unmanned Aerial Vehicle Computation Task Scheduling Based on Parking Resources in Post-Disaster Rescue.** Applied Sciences13(1),289. DOI: [10.3390/app13010289](https://doi.org/10.3390/app13010289). [Trang nhà xuất bản](https://www.mdpi.com/2076-3417/13/1/289).

Đã xác minh metadata và mô tả publisher; truy cập full page trực tiếp gặp HTTP429, nên chưa phân tích chi tiết pseudocode. UAV giao task cho các xe đỗ còn hoạt động; DRL chọn tài nguyên thực thi, xét completion và execution cost. Có mô hình hậu thiên tai, nhưng không đồng nhất với UAV làm compute server trong code hiện tại.

**Cân nhắc:** tham khảo cách mô hình hóa tài nguyên còn sống sau thiên tai; chưa ưu tiên triển khai vì cần thêm vehicle/server pool và đổi chiều offloading.

### D4 — Wang và Jiao, 2024: related work, không phải lựa chọn đầu

**Multi-Agent Reinforcement Learning-Based Computation Offloading for Unmanned Aerial Vehicle Post-Disaster Rescue.** Sensors24(24),8014. DOI: [10.3390/s24248014](https://doi.org/10.3390/s24248014). [Publisher PDF](https://www.mdpi.com/1424-8220/24/24/8014/pdf?version=1734349193).

Xác minh metadata/abstract từ publisher. CER-MADDPG dùng phối hợp agent và phân loại experience replay; UAV có workload cần offload sang edge. Liên quan rescue nhưng khác chiều tính toán, chưa có kiểm tra full scheduling implementation. **Chưa đề xuất bê MARL sang code** vì thêm training/credit assignment trước khi heuristic được chốt sẽ khó kiểm soát.

## 3. Ứng viên đúng tên đề tài nhưng chưa đủ full text để chọn thuật toán

| Bài | Bằng chứng đã kiểm tra | Trạng thái |
| --- | --- | --- |
| Sun et al., *Optimal Task Offloading and Trajectory Planning Algorithms for Collaborative Video Analytics With UAV-Assisted Edge in Disaster Rescue*, IEEE TVT73(5),6811–6828,2024, DOI[10.1109/TVT.2023.3344281](https://doi.org/10.1109/TVT.2023.3344281) | [Danh mục nhóm tác giả](https://www.srislab.org/publications), có metadata và DOI | Rất đáng lấy bản author manuscript để đọc; chưa gán tên thuật toán hoặc kết luận kỹ thuật khi IEEE chặn truy cập |
| Zhou et al., *Delay-Aware UAV Computation Offloading and Communication Assistance for Post-Disaster Rescue*, IEEE TWC23(12),19110–19125,2024, DOI[10.1109/TWC.2024.3479709](https://doi.org/10.1109/TWC.2024.3479709) | [Danh mục nhóm Waterloo](https://uwaterloo.ca/broadband-communications-research-lab/publication/journalmagazine-papers) | Metadata xác nhận, chưa đủ full text để chọn phương pháp |

Không xếp hai bài này thành “đã đọc sâu” chỉ vì có disaster trong tiêu đề. DOI chứa2023 hoặc2024 không tự xác định năm volume; giữ năm xuất bản journal được đối chiếu.

## 4. Bài phương pháp tổng quát — chỉ làm nền, không gọi là disaster baseline

| Bài | Phương pháp đã xác minh | Có thể học gì / khác code hiện tại |
| --- | --- | --- |
| Zhang et al., *Stochastic Computation Offloading and Trajectory Scheduling for UAV-Assisted Mobile Edge Computing*, IEEE IoTJ6(2),3688–3699,2019; DOI[10.1109/JIOT.2018.2890133](https://doi.org/10.1109/JIOT.2018.2890133) | Lyapunov và tách bài toán queue/resource/trajectory; metadata/abstract publisher và đoạn author PDF | Học quản lý năng lượng/backlog qua thời gian; scheduling ở đây không đồng nghĩa EDF task-order. Không có bằng chứng disaster-specific. [Publisher](https://ieeexplore.ieee.org/document/8594571/) |
| Mao, Zhang và Letaief, *Dynamic Computation Offloading for Mobile-Edge Computing With Energy Harvesting Devices*, IEEE JSAC34(12),3590–3605,2016; DOI[10.1109/JSAC.2016.2611964](https://doi.org/10.1109/JSAC.2016.2611964) | LODCO, Lyapunov; phối hợp offloading/CPU frequency/TX power, chi phí latency và task failure; đã đọc preprint | Cách cân đối pin hiện tại/tương lai. Energy harvesting/DVFS khác pin hữu hạn công suất cố định của ta; không sao chép guarantee. [Preprint](https://arxiv.org/abs/1605.05488) |
| Cao và Deng, *Dependent Task Offloading in Edge Computing Using GNN and Deep Reinforcement Learning*, IEEE IoTJ11(12),21632–21646,2024; DOI[10.1109/JIOT.2024.3374969](https://doi.org/10.1109/JIOT.2024.3374969) | GAT+DRL, action chọn subtask và location; đã đọc preprint §§4.2–4.3 | Tham khảo action liên kết và reward theo cải thiện completion forecast. DAG khác task ảnh độc lập; chưa cần GNN. [Preprint](https://arxiv.org/abs/2303.17100) |
| Park et al., *Two-Stage Computation Offloading Scheduling Algorithm for Energy-Harvesting Mobile Edge Computing*, Energies12(22),4367,2019; DOI[10.3390/en12224367](https://doi.org/10.3390/en12224367) | Greedy admission + Lyapunov CPU-frequency scheduling; đọc author PDF | Tách admission/resource control, không phải scheduler task-order hiện tại. [Author PDF](https://uclab.re.kr/publications_openaccesspdf/lhpark_energies2019_open.pdf) |

Không cần chỉ đọc paper disaster để học thuật toán; nhưng phải kiểm tra khả năng chuyển phương pháp và bổ sung scenario disaster phù hợp. Dùng nhãn disaster cho một queue benchmark tổng quát không làm nó trở thành đánh giá cứu hộ thực tế.

## 5. Cân nhắc cho hệ thống của chúng ta

Các mục dưới là **đề xuất của chúng ta**, không phải kết quả đã chứng minh trong các paper kể trên.

1. **Giữ hướng dữ liệu rõ ràng:** thiết bị hiện trường phát sinh task ảnh → local hoặc UAV compute. Không vô tình chuyển sang UAV thu ảnh rồi offload xuống xe. RescueNet đang là payload đại diện; chưa có source positions/arrival/deadline thực từ dataset.
2. **Giữ yếu tố emergency có ảnh hưởng thật:** source mất nguồn/kết nối, pin giới hạn, deadline/priority biết trước xử lý, kết quả phải về được nơi nhận. Tải nền Alibaba là giả định stress-test compute, không phải trace tải nền đo trong thiên tai.
3. **Tách compute và delivery:** local xong ở source disconnected không đủ để chỉ huy nhận kết quả. Không dùng compute DVR một mình nếu tuyên bố hỗ trợ thông tin cứu hộ.
4. **Giữ quy tắc so sánh công bằng:** cùng arrival/compute/link/energy budget và cùng quyền chờ/drop. Thử nghiệm drop phải báo drop trong denominator của failure.
5. **Không hứa giảm đồng thời mọi metric:** ưu tiên on-time delivery dưới budget, báo latency và energy cùng background. Chọn phương pháp đơn giản nếu hiệu quả tương đương.

## 6. Phép thử kế tiếp đề xuất

**Không sửa QIOS hoặc chạy train mới trong đợt tìm tài liệu này.** Phương án gần hạn để thử:

- Mốc giữ nguyên: DEADLINE_ENERGY+EDF/SPT, không early-drop mới.
- Variant A: cùng routing, bổ sung deadline-risk check ở dispatch; khi forecast cho thấy task không thể kịp thì hủy theo quy tắc công bố. So cùng cơ chế hủy với EDF và SPT để phân biệt lợi ích drop với order.
- Variant B: giới hạn backlog/nhận offload mới bằng ngưỡng validation; task không offload phải xử lý local hoặc nhận failure đúng quy tắc, không biến mất.
- Giữ pin, workload và source connectivity giống nhau giữa policy; validation/test tách riêng, không chỉnh ngưỡng theo các case QIOS đã xem.
- Bắt đầu với case dựng tay và fixed-UAV; chỉ sau khi đúng mới kiểm tra coverage/mobile, estimate error và nhiều mức tải/pin.

Variant A là **deadline-risk heuristic lấy cảm hứng** từ D1, không gọi là MA-SDRC reproduction. Variant B lấy ý tưởng điều tiết tiếp nhận từ D2, không gọi là ADP nguyên bản. Không cần bổ sung MARL, multi-UAV, DAG, cache hoặc DVFS để đạt mục tiêu trước mắt.

## 7. Giới hạn tra cứu và bằng chứng

Tra cứu theo nhóm từ khóa UAV/edge + offloading/scheduling/queue/deadline và disaster/post-disaster/emergency monitoring; ưu tiên full text nhà xuất bản, PMC, arXiv hoặc nhóm tác giả. Không có academic-search MCP trong session nên dùng web search và nguồn primary; không có lỗi MCP call được che đi.

Một số IEEE yêu cầu JavaScript, ScienceDirect trả403, MDPI trả429; các bài chỉ truy cập metadata/abstract được đánh dấu. Không sử dụng số phần trăm cải thiện của bài khác làm dự đoán cho code hiện tại. Không khẳng định danh sách bao phủ toàn bộ literature hoặc có dữ liệu thực địa chỉ dựa vào scenario mô phỏng.
