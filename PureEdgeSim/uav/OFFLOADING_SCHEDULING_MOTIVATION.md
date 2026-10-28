# Motivation: từ duy trì mạng đến xử lý tác vụ thiên tai đúng hạn

Ngày: 28/10/2026. Bản làm việc để cùng phân tích phạm vi nghiên cứu; chưa phải tuyên bố novelty hoặc đề cương đã khóa.

## 1. Paper giải quyết vấn đề nào?

Sau thiên tai, một số thiết bị edge mất nguồn điện, mất kết nối hoặc cả hai. UAV hỗ trợ tính toán và chuyển tiếp dữ liệu để các thiết bị tiếp tục hoạt động. Câu hỏi điều khiển chính là: **UAV nên phục vụ thiết bị nào tiếp theo để kéo dài lifetime của hệ thống dưới ràng buộc pin và tuổi dữ liệu?**

Paper mô tả các slot có độ dài thay đổi theo thời gian di chuyển và xử lý; các thiết bị sinh workload ở đầu slot. Quyết định điểm đến ảnh hưởng coverage, offloading và năng lượng. Bài toán này có ý nghĩa đối với tính liên tục của hạ tầng: duy trì khả năng thu thập/cập nhật thông tin khi nguồn lực cứu hộ hạn chế. [S1, §3.1, §4, §6]

**Đây không phải một paper “không có offloading”.** Offloading là cơ chế UAV hỗ trợ thiết bị; đóng góp điều khiển tập trung vào lựa chọn thiết bị phục vụ. Paper không xây dựng bài toán chúng ta đang hướng tới: quyết định nơi thực thi từng task kết hợp lập lịch hàng đợi CPU hữu hạn theo deadline từng task. Đây là khác biệt phạm vi, không phải bằng chứng phương pháp paper sai.

## 2. Vì sao cần một bài toán bổ sung?

Giả thuyết ứng dụng của chúng ta là: **giữ thiết bị hoạt động và dữ liệu được cập nhật chưa đủ bảo đảm từng kết quả phân tích đến đúng lúc để sử dụng.**

Ví dụ, camera vẫn còn pin và liên lạc được, nhưng task phân tích ảnh phải chờ CPU UAV quá lâu. Kết quả có thể hoàn thành sau thời điểm cần ra quyết định. Ngược lại, gửi mọi task khẩn cấp lên UAV có thể tạo quá tải, trong khi một số thiết bị vẫn đủ khả năng tự xử lý.

Các tình huống này là motivation cho mô hình cần nghiên cứu; chúng ta chưa có bằng chứng thực địa hoặc yêu cầu nghiệp vụ xác nhận một deadline cụ thể. Các giá trị 20/60 giây hiện tại là giả định development, không được gọi là chuẩn phản ứng thiên tai.

| Mức độ dịch vụ | Câu hỏi | Chỉ số tương ứng |
| --- | --- | --- |
| Duy trì hạ tầng | Hệ thống còn hoạt động bao lâu? | Lifetime theo định nghĩa failure |
| Độ mới thông tin | Lần cập nhật mới nhất đã cũ bao lâu? | Tuổi dữ liệu/AoI theo định nghĩa đã công bố |
| Xử lý tác vụ | Từng task có kết quả trước hạn không? | Deadline violation, on-time completion/delivery |

Ba mức liên quan nhưng không thay thế nhau. Lifetime cao không mặc nhiên suy ra mọi deadline được đáp ứng; DVR thấp trên horizon cố định cũng chưa chứng minh lifetime tăng.

## 3. Vì sao offloading và scheduling phải được xét cùng nhau?

Offloading quyết định **task chạy ở đâu**; scheduling quyết định **task nào được CPU chạy trước**. Quyết định thứ nhất tạo queue; queue và scheduler lại thay đổi lợi ích của quyết định thứ nhất.

Một dự báo latency tối thiểu cần tính:

\[
L_i^{UAV}=T_i^{upload}+T_i^{queue,UAV}+T_i^{compute,UAV}+T_i^{return},
\]

\[
L_i^{local}=T_i^{queue,local}+T_i^{compute,local}+T_i^{delivery,local}.
\]

Thời gian return/delivery có thể được giả định tức thời ở bản đầu, nhưng phải ghi rõ. Nếu phải chờ UAV tiếp cận thì thời gian chờ cũng thuộc end-to-end latency; bản mobile hiện chọn local ngay khi ngoài coverage, chưa cho chờ UAV.

Ví dụ minh họa, không phải kết quả benchmark: task có ngân sách 20 s; local cần 12 s; UAV cần upload 1 s và compute 4 s nhưng queue chờ 18 s. Chọn UAV chỉ vì CPU nhanh sẽ dự báo thiếu 18 s và dẫn đến tổng 23 s. Nếu queue UAV rỗng, lựa chọn UAV lại có thể phù hợp. Nếu scheduler thay đổi thứ tự, cả completion forecast và routing có thể đổi theo.

**“Joint” ở đây là phối hợp routing với scheduling và trạng thái queue**, không bắt buộc một mạng RL xuất cả hai action. Có thể dùng heuristic kết hợp hoặc policy phân tầng. Chưa có cơ sở mặc định DRL sẽ tốt hơn EDF/SPT hoặc heuristic tốt.

## 4. Vai trò của năng lượng

UAV có pin hữu hạn, đồng thời phải duy trì bay/hover và xử lý. Thiết bị cũng tiêu thụ năng lượng compute, idle và upload. Lựa chọn giảm latency có thể chuyển chi phí từ ground sang UAV; năng lượng một node giảm không có nghĩa tổng hệ thống giảm.

Chỉ đổi thứ tự xử lý trên CPU công suất cố định thường không làm giảm năng lượng compute nếu hoàn thành đúng cùng lượng công việc. Vì vậy, động lực energy-aware mạnh hơn khi **kết hợp nơi thực thi, tài nguyên còn lại và giá trị phục vụ đúng hạn**, thay vì chỉ đổi FIFO thành EDF rồi kỳ vọng tiết kiệm điện.

Mục tiêu làm việc đề xuất: **tăng tỷ lệ tác vụ phân tích thiên tai được xử lý và chuyển kết quả đúng hạn dưới ngân sách năng lượng**, đồng thời báo latency, năng lượng và tác động lên background. Chưa chốt một weighted reward là objective cuối.

Không được tính việc hết pin sớm, drop nhiều task hoặc bỏ background là thành công chỉ vì tổng joule thấp. Cần báo cả số task được phục vụ, drop/miss và năng lượng trên mỗi kết quả hữu ích.

## 5. Dataset hỗ trợ motivation đến đâu?

| Nguồn | Vai trò trong benchmark hiện có | Giới hạn bằng chứng |
| --- | --- | --- |
| RescueNet | Payload/metadata ảnh thiên tai, tạo task phân tích | Chưa chạy inference thật; compute cost, priority và deadline không tự có từ ảnh |
| Alibaba trace | Tạo tải nền cạnh tranh CPU UAV | Ánh xạ workload cluster sang UAV là giả định; chưa replay đầy đủ timeline/DAG; không phải trace UAV thực tế |

Sự kết hợp giúp kiểm tra giả thuyết về **tranh chấp tài nguyên**. Nó chưa chứng minh UAV ngoài thực tế có đúng phân bố background đó. Cần giải thích nguồn background (dịch vụ đang chạy hoặc các task khác) và khảo sát từ không có tải nền đến quá tải. Không bắt buộc tải thêm Google/C2A trước khi mô hình hiện tại được hiệu chuẩn. [S2]

## 6. Chúng ta kế thừa gì và thay đổi gì?

| Thành phần | Kế thừa bối cảnh paper | Phần nghiên cứu bổ sung |
| --- | --- | --- |
| UAV hỗ trợ thiết bị trong thiên tai | Có | Xét tài nguyên compute hữu hạn và queue |
| Di chuyển, coverage, pin | Có thể tái sử dụng mô hình | Giữ policy phục vụ cố định ở thí nghiệm đầu để tách ảnh hưởng |
| Offloading | UAV hỗ trợ thiết bị trong coverage | Chọn local/UAV cho từng task dựa trên queue/deadline/pin |
| Thời gian | Tuổi dữ liệu và lifetime | Deadline end-to-end và thời gian chờ/xử lý từng task |
| Workload | Synthetic theo slot để reproduction | Arrival theo thời gian, workload ảnh + background |
| Đối chứng | DQN/PPO/A2C chọn thiết bị | Policy routing × FIFO/EDF/Priority/SPT trên cùng môi trường |

**Chưa thể so trực tiếp DQN lifetime với scheduler mới.** Muốn chứng minh lợi ích bổ sung, phải giữ cùng workload, vị trí/coverage, budget và quyền quyết định rồi thay từng thành phần.

`LOCAL_COMPLETION` chỉ là một sensitivity của nhánh paper: yêu cầu xử lý xong nhưng vẫn bỏ task dở cuối slot. Nó không phải benchmark offloading + scheduling hoàn chỉnh và thất bại của DQN ở đó không chứng minh novelty của hướng mới. State125 cũng chỉ là ablation thông tin cho policy chọn thiết bị. [S3]

## 7. Câu hỏi và giả thuyết cần kiểm chứng

**RQ chính:** Phối hợp offloading với scheduling có xét deadline và năng lượng có tăng khả năng cung cấp kết quả phân tích thiên tai đúng hạn dưới tải tính toán biến thiên không?

| Giả thuyết làm việc | Đối chứng cần có | Khi nào không được nhận là thành công? |
| --- | --- | --- |
| H1: Dự báo queue giúp routing tốt hơn chỉ so compute/link | Cùng scheduler, thay routing có/không xét queue | Chỉ tốt do biết actual compute tương lai hoặc workload khác |
| H2: Scheduler có ích sau khi routing đã được kiểm soát | Cùng routing, FIFO/EDF/SPT và cơ chế đề xuất | Lợi ích chỉ do thay routing hoặc bỏ task khó |
| H3: Cơ chế energy-aware giữ dịch vụ tốt hơn khi pin thấp | Cùng budget, báo on-time delivery và năng lượng | Joule giảm nhưng mức dịch vụ giảm không được định lượng |
| H4: Bảo vệ ảnh không làm background bị bỏ đói ngoài mức cho phép | Báo riêng hai nguồn, waiting time và drop | Chỉ báo ảnh và giấu background failures |

H1–H4 chưa phải kết luận. Cần ablation tách queue prediction, urgency/priority và energy; thử sai số estimate và nhiều mức tải/pin. Thêm nhiều thành phần không tự tạo novelty: cần rà literature offloading–scheduling để xác định khoảng trống cụ thể trước khi viết claim đóng góp.

## 8. Phạm vi đề xuất để cùng chốt

1. Một UAV; local/UAV execution; CPU hữu hạn, queue bền, task không chia nhỏ; không migration/preemption ở bản đầu.
2. Giữ policy phục vụ/di chuyển cố định và giống nhau giữa các đối chứng. Tối ưu trajectory, cache, DVFS và multi-UAV để ngoài phạm vi trước mắt.
3. Chốt dịch vụ cần tối ưu là **compute đúng hạn** hay **delivery đúng hạn**. Đề xuất ưu tiên delivery cho ứng dụng ra quyết định; báo compute riêng để không che lỗi kết nối.
4. Chốt quy tắc với task đã trễ: tiếp tục chạy hay hủy. Đo cả lợi ích và compute đã lãng phí; không thay quy tắc giữa các thuật toán.
5. Hiệu chuẩn một model inference và phần cứng đại diện, hoặc công bố cost model và sensitivity nếu chưa đo được. Deadline cần có luận cứ ứng dụng hoặc thang tương đối rõ ràng.

Phần kernel/offloading/scheduler/mobile đã có để thử các giả thuyết này. **Phần còn thiếu để thành nghiên cứu vững là objective và workload được khóa/hiệu chuẩn, khoảng trống literature, thuật toán có lý do rõ và thực nghiệm đối chứng**, không chỉ thêm một agent RL. [S2, S4]

## 9. Đoạn motivation có thể dùng làm bản nháp

Các hệ thống UAV-assisted edge computing trong thiên tai cần duy trì khả năng hoạt động của thiết bị khi nguồn điện và kết nối bị gián đoạn. Bài toán của Azfar và cộng sự tập trung lựa chọn thiết bị được UAV hỗ trợ nhằm kéo dài thời gian sống của mạng dưới ràng buộc pin và tuổi dữ liệu. Trong một phạm vi bổ sung, khi UAV phải xử lý các tác vụ phân tích ảnh trên CPU hữu hạn, duy trì liên lạc chưa đủ bảo đảm kết quả được cung cấp trước deadline. Quyết định offloading làm thay đổi tải hàng đợi, trong khi thứ tự xử lý quyết định thời gian chờ và khả năng hoàn thành của các task đã offload. Vì vậy, nghiên cứu này đề xuất khảo sát sự phối hợp giữa offloading và task scheduling dưới giới hạn năng lượng và tải nền biến thiên. Mục tiêu là xác định khi nào sự phối hợp đó cải thiện tỷ lệ kết quả được cung cấp đúng hạn, cùng các đánh đổi về latency, năng lượng và dịch vụ background.

Đoạn trên là định hướng, chưa tuyên bố phương pháp mới hoặc ưu thế thực nghiệm đã được chứng minh.

## Nguồn và ranh giới bằng chứng

- **[S1]** [Bản trích xuất paper Azfar](../../../2501.15305v1.md), §3.1 (mô hình theo slot/lifetime), §4 (implementation), §5–6 (thực nghiệm/kết luận). Paper là nguồn cho mô tả bài toán gốc; không suy từ giả định simulator của chúng ta thành phát biểu của tác giả.
- **[S2]** [OFFLOADING_SCHEDULING.md](OFFLOADING_SCHEDULING.md): mô hình, dataset và các giả định development của nhánh mới.
- **[S3]** [REFERENCE_VS_RESEARCH_SETTING.md](REFERENCE_VS_RESEARCH_SETTING.md) và [PAPER_ALIGNMENT.md](PAPER_ALIGNMENT.md): phân biệt setting và quy ước implementation.
- **[S4]** [MOBILE_DRL.md](MOBILE_DRL.md): policy chọn thiết bị đang giữ offloading/scheduler cố định; chưa phải joint-learning agent.

Tài liệu này dựa trên paper và code/tài liệu nội bộ đã đọc, chưa phải systematic literature review để xác nhận khoảng trống toàn lĩnh vực.
