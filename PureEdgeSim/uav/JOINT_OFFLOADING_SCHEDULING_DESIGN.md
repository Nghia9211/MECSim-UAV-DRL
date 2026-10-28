# Thiết kế v1: offloading và scheduling xét tác động lên hàng đợi

Ngày: 28/10/2026. Trạng thái: **thiết kế để implement và kiểm chứng**, chưa có kết quả cho thuật toán này, chưa xác nhận novelty bằng literature review.

Tên làm việc: **Queue Impact Offloading and Scheduling (QIOS)**. Tên chỉ để phân biệt prototype với các baseline hiện có.

## 1. Phạm vi và vấn đề cụ thể

Một UAV và nhiều thiết bị mặt đất phát sinh task ảnh; background cạnh tranh CPU UAV. Mỗi task ảnh chọn toàn bộ LOCAL hoặc UAV tại arrival; không migration/preemption. Local FIFO, CPU UAV có scheduler. Tầng phục vụ/di chuyển giữ cùng policy giữa các đối chứng; bản đầu kiểm tra trên UAV cố định để cô lập hai quyết định.

Code đã có DEADLINE_ENERGY: dự báo candidate có kịp deadline/đủ pin không rồi ưu tiên marginal energy thấp. Code cũng có FEASIBLE_AGING. Không coi việc ghép hai baseline này là thuật toán mới.

**Khoảng trống implementation cần thử:** forecast hiện chỉ trả completion/energy/feasibility của candidate. Chưa định lượng một quyết định offload làm thay đổi số task *đã tiếp nhận* còn có thể hoàn thành đúng hạn như thế nào. Scheduler hiện xếp điểm từng task, chưa trực tiếp đối chiếu tác động của lựa chọn đầu tiên lên toàn queue.

Giả thuyết: xét tác động lên hàng đợi giúp tránh offload hoặc dispatch một task có lợi riêng nhưng làm nhiều task quan trọng khác trễ. Hiệu quả phải được kiểm chứng; lookahead sai có thể làm thuật toán kém hơn EDF/SPT.

## 2. Objective và metric

Trong horizon cố định H, working objective:

\[
\max \sum_{i\in\mathcal I} w_i y_i + \rho\sum_{j\in\mathcal B}y_j,
\]

với y=1 nếu **kết quả được chuyển tới nơi nhận trước deadline**, ngược lại0. I là ảnh, B là background tính hoàn thành tại UAV. w lấy từ priority được biết tại arrival, không lấy từ ground-truth mask. Rho là giá trị dịch vụ background, không phải xác suất hay hằng số vật lý.

Ràng buộc vật lý: pin mỗi node, coverage, ready time, CPU đơn, horizon và execution kernel chung. Đây là mục tiêu hữu hạn dưới energy budget; không tự tuyên bố tối thiểu năng lượng hay kéo dài lifetime.

Đánh giá đồng thời: image/background compute DVR, delivery failure rate, priority-weighted on-time delivery, số task hoàn thành/drop, latency thành công và time-to-resolution mọi task, UAV/ground/total joules, joules trên mỗi delivery đúng hạn và runtime. Denominator bằng0 phải xuất NA, không0. Late/drop/expired/unfinished không được loại khỏi tỷ lệ thất bại dịch vụ.

Nếu chưa chốt nghiệp vụ cho w/rho, báo thêm count không trọng số và bảng từng lớp priority. Không dùng một scalar score để che đánh đổi. Đây là working objective của prototype, không phải yêu cầu ứng dụng đã đo.

## 3. Thông tin được dùng

- Task đã arrival: source, ID, arrival/ready/deadline, priority, payload, estimated remaining MI và trạng thái execution.
- Tài nguyên hiện tại: vị trí/coverage, pin còn lại, tốc độ CPU, công suất theo config, các upload đã admit.
- Không đọc danh sách FUTURE, actual remaining MI chưa quan sát, task seed, ảnh/mask hoặc workload sắp sinh.
- Local disconnected có thể compute thành công nhưng chưa delivered. Bản đầu không thêm cơ chế buffer kết quả/retry/relay mới.

Forecast là point estimate trên workload đã biết, **không phải bảo đảm deadline**. Sai số compute và arrival tương lai có thể làm nó sai. Tránh gọi mọi route không dự báo kịp hạn là physically infeasible: đó chỉ là forecast failure.

## 4. Projection chung: đánh giá cả hai node

Tại thời điểm t, tạo snapshot immutable của local queues, UAV queue, running tasks, uploads và pin. Không mutate kernel khi thử action. Projection mô phỏng tới khi mọi task đã biết terminal hoặc tới H, dùng estimated MI, cùng quy tắc expiration/depletion/tie với kernel.

Projection trả cho **từng task**: dự báo route, finish, delivered/on-time, status và năng lượng theo node; cùng tổng served value và incremental energy. Running task không bị preempt. Task chờ hết hạn trước dispatch bị expired. Task đã chạy có thể tiếp tục trễ theo kernel hiện tại; không âm thầm hủy để làm QIOS tiết kiệm điện hơn baseline.

Tổng năng lượng projection gồm baseline power theo thời gian, compute và TX; không đếm lại flight/hover giữa các node. Energy của task bị drop/depletion vẫn được tính. So route phải chiếu cùng tập task và cùng horizon, không chỉ chiếu tới completion của candidate.

Nếu mobile có chọn đích tương lai phụ thuộc state, projection không được biết trước decision đó. Bản đầu chỉ bảo đảm dự báo mobility cho điều kiện cố định; mobile adaptation cần protocol riêng và ghi giả định hover sau current stop.

## 5. CPU scheduler QIOS

Scheduler dùng bounded one-step lookahead, tránh recursive optimization:

1. Khi CPU UAV rảnh, lấy các task ready/unexpired.
2. Cho mỗi candidate k, giả sử k chạy trước.
3. Sau k, rollout các task còn lại bằng **EDF cố định** (tie: ready, arrival, ID), tính U_k và E_k cho queue đã admit. Upload đang dở chỉ ready khi truyền xong; không lấy future arrivals.
4. Chọn action theo quy tắc ở mục7; kernel thực thi đúng một task rồi quyết định lại tại dispatch sau.

Không dùng chính scheduler QIOS làm tail trong lookahead: điều đó gây lồng projection và tăng chi phí khó kiểm soát. EDF là tail policy đã khóa, không phải lịch tối ưu toàn cục. Nếu không có candidate dự báo hoàn thành đúng hạn, vẫn chọn best-effort theo cùng phép so sánh, không reject task ngoài quyền kernel.

Aging chưa đưa vào v1 vì ablation cũ chưa xác nhận lợi ích trên objective tổng hợp. Background có rho và được báo riêng; **không có bảo đảm chống starvation**. Nếu cần hard fairness, phải định nghĩa constraint và variant riêng.

## 6. Offloading QIOS

Tại arrival của task i:

1. Kiểm tra route vật lý: LOCAL nếu source còn sống; UAV nếu source/UAV còn sống và đủ điều kiện upload. Ngoài coverage dùng LOCAL theo kernel hiện tại.
2. Tạo hai bản snapshot, thêm i vào route tương ứng. Background luôn tại UAV.
3. Rollout cả hệ thống local+UAV đã biết. Local dùng FIFO; UAV dùng chính QIOS mục5 tại các mốc dispatch dự báo. Tail trong mỗi lần lookahead vẫn EDF nên không recursion vô hạn.
4. Tính tổng U_r và incremental E_r của **candidate và mọi task đã admit**. Có thể ghi delta so với projection không có i để giải thích ngoại tác; phép chọn route dựa trên hai projection cùng snapshot.
5. Chọn route theo mục7. Không có quyền từ chối task: nếu cả hai forecast xấu thì best-effort; task vẫn được tính failure nếu thực tế không kịp.

Đây là mối nối thuật toán: routing biết scheduler sẽ xử lý queue ra sao, scheduler dùng cùng định nghĩa giá trị đúng hạn và ngân sách pin. Nó không cần agent DRL.

## 7. Quy tắc chọn và tham số

V1 dùng thứ tự lexicographic để tránh trộn tùy tiện đơn vị joule với task:

1. Tổng giá trị served đúng hạn U **cao nhất**.
2. Khi U hòa trong tolerance số học đã cố định: tổng incremental energy thấp hơn.
3. Nếu tiếp tục hòa: tổng priority-weighted completion latency của task delivered đúng hạn thấp hơn.
4. Tie cuối: route LOCAL; với scheduler là ready time, arrival, ID tăng dần.

Energy tham gia qua depletion/feasibility của projection và tie-break, **không phải objective energy ngang hàng**. Nếu cần chủ động đổi một ít service lấy giảm energy, đó là variant epsilon-constraint, phải chốt trước bằng validation, chưa đưa vào v1.

Working rho=1, image weight=priority (2 hoặc3 theo generator hiện tại). Đây là default dễ giải thích, không tối ưu theo test; chạy sensitivity rho∈{0,0.5,1,2} trên validation và công bố toàn bộ. Không đổi default sau khi xem test. Không thêm penalty/bonus chọn thiết bị hoặc số lần offload.

## 8. Pseudocode

```text
QIOS_SCHEDULE(snapshot):
    for task k in ready_queue:
        result[k] = project_known_queue(first=k, tail=EDF,
                                        estimated_work, current_batteries)
    return lexicographic_argmax(result.U, -result.energy,
                                -result.delivered_latency, stable_tie)

QIOS_ROUTE(task i, snapshot):
    routes = physically_available_routes(i, snapshot)
    for route r in routes:
        copy = snapshot.with_task(i, r)
        result[r] = project_system(copy,
                                  local_scheduler=FIFO,
                                  uav_scheduler=QIOS_SCHEDULE)
    return lexicographic_argmax(result.U, -result.energy,
                                -result.delivered_latency, prefer_LOCAL)
```

## 9. Thay đổi code cần thực hiện

| Task | Đầu ra | Tiêu chí hoàn thành |
| --- | --- | --- |
| T1: Projection API | Snapshot immutable, task-level predicted outcomes và energy ledger | Không đọc FUTURE/actual MI; fixed workload projection khớp kernel khi không có future arrivals và estimate đúng |
| T2: Queue-impact scheduler | Class riêng, không đổi FEASIBLE_AGING/EDF | Ca task dài làm nhiều task ngắn miss; expiry/ready/depletion tie; deterministic; no recursive tail |
| T3: Queue-impact routing | Route projection đánh giá cả local và UAV | Ca candidate kịp nhưng làm queue khác miss phải thay quyết định so candidate-only; disconnected delivery được tính đúng |
| T4: Trace/verifier | Ghi snapshot, hai route/candidate score, selected action | Verifier tính lại quyết định; phát hiện cố ý sửa score, route, ready, pin và weight |
| T5: Benchmark | Baseline/ablation cùng workload hash | Manifest config, test split, runtime, independent audit và negative results |

`OffloadingPolicy.Context` và `TaskScheduler.ReadyTask` hiện chưa đủ cho projection đầy đủ (thiếu queue-level outcomes/upload context/source connectivity). Cần API mới hoặc optional extension, giữ nguyên contract baseline cũ. Không giấu actual task object trong interface.

## 10. Protocol đánh giá trước mắt

1. **Mechanical phase:** workload nhỏ được dựng tay, estimate=actual, không future arrivals; chứng minh forecast/counterfactual đúng. Thử input mutation và permutation để kiểm tra alias/tie.
2. **Development:** cùng generator RescueNet+Alibaba hiện có; 3 mức tải, 2 mức pin; fixed UAV và horizon600s. Arrival/noise/source assignment giữ RNG stream riêng, mọi policy nhận cùng task hash. Chạy zero-background riêng để kiểm tra motivation tranh chấp.
3. **Đối chứng:** routing ALL_LOCAL/ALL_UAV/SHORTEST_FINISH/DEADLINE_ENERGY × FIFO/EDF/SPT; thêm DEADLINE_ENERGY+FEASIBLE_AGING và PRIORITY để thấy trade-off.
4. **Ablation:** QIOS routing+EDF; DEADLINE_ENERGY+QIOS scheduler; full QIOS; candidate-only forecast; energy tie-break tắt. Baseline chỉ dùng ít thông tin hơn phải được ghi rõ; bổ sung cùng thông tin để phân biệt lợi ích policy với quyền quan sát.
5. **Robustness:** estimate error0/±20%/±40%, nhiều pin/local CPU/deadline load; giữ actual workload không đổi khi chỉ thay estimate. Chưa gọi uniform noise là mô hình dự báo đã hiệu chuẩn.
6. **Validation/test:** trước launch ghi manifest dải seed riêng, không tái dùng task seed đã xem làm final test. Chọn rho trên validation nếu có; test khóa trước khi chạy. Chưa chỉ định một dải seed là “chưa dùng” nếu chưa audit lịch sử run.
7. **Thống kê:** paired difference theo cùng scenario/task seed, báo mean và dispersion/CI phù hợp. Không coi mỗi task là một episode độc lập. Một layout chỉ hỗ trợ kết luận conditional; sau pilot mở rộng cấu hình thiết bị/layout.
8. **Runtime:** đo projection+routing+scheduling cùng nhau, p50/p95/max, queue size và số rollout. Với queue n, một dispatch lookahead đã cần n rollout; full route projection có thể đắt hơn nhiều. Chưa giới hạn top-K âm thầm; nếu runtime không đạt thì thêm bounded variant và báo ablation.

Điều kiện tiến tiếp: projection đúng cơ học, có lợi ích hoặc trade-off rõ so baseline mạnh, runtime phù hợp và kết quả không chỉ nhờ loại task khó. Nếu EDF/SPT ngang hoặc tốt hơn thì báo kết quả âm và thu hẹp giả thuyết; không mặc định train DRL để thay thế.

## 11. Giới hạn cần giữ rõ

- Chưa có bảo đảm tối ưu, fairness hoặc deadline khi estimate sai/future load tới.
- Lookahead có thể overfit current queue, bỏ qua lợi ích của reserve tài nguyên cho arrivals tương lai.
- Forecast dùng scheduler lồng rollout nên chi phí có thể lớn; phải đo trước experiment lớn.
- Không thay mô hình radio contention, output link, cache, DVFS hoặc task rejection ở đợt này.
- CPU/power/deadline hiện chưa hiệu chuẩn phần cứng. Thuật toán tốt trong benchmark giả định chưa chứng minh hiệu quả ngoài thực tế.
- Novelty cần đối chiếu literature queue-aware offloading/lookahead scheduling; tên QIOS không phải claim đóng góp đã mới.

Nguồn nội bộ: [Motivation](OFFLOADING_SCHEDULING_MOTIVATION.md), [mô hình hiện có](OFFLOADING_SCHEDULING.md), [phân biệt setting](REFERENCE_VS_RESEARCH_SETTING.md). Source đã rà: `OffloadingPolicy`, `OffloadingSimulation.predict`, `TaskScheduler`, `FeasibleAgingScheduler`.
