# Thích nghi hai cơ chế từ paper disaster: kết quả đầu tiên

29/10/2026. Chạy local, không train agent, chưa push/server. Mục tiêu thực dụng: tìm phương pháp chạy đúng và tốt hơn baseline, không bắt buộc đóng góp mới. Protocol trước launch: [TWO_PAPER_ADAPTATION_PLAN.md](TWO_PAPER_ADAPTATION_PLAN.md).

## Áp dụng gì từ mỗi bài?

| Nguồn | Cơ chế được thử | Phần không tái hiện |
| --- | --- | --- |
| Fan et al.,2024, [MA-SDRC emergency monitoring](https://doi.org/10.1038/s41598-024-67886-x) | Guard tại dispatch: task UAV chưa chạy mà estimated finish sớm nhất đã vượt deadline bị hủy; vẫn tính failure | Không MARL, negotiation, multi-stage risk control hoặc resource allocation của bài gốc |
| Kalinagac et al.,2023, [prioritization-based UAV offloading](https://doi.org/10.3390/s23052375) | Ý ADP tránh giao thêm cho processor đang nhận transfer: một UAV đang upload thì task mới chạy LOCAL; lúc rảnh dùng DEADLINE_ENERGY | Không task waiting pool, nhiều processor xe/cloud hoặc oracle Q-OPT. Không gọi TRANSFER_AWARE là ADP reproduction |

Đây là **hai cơ chế lấy cảm hứng từ phương pháp**, chưa phải tái hiện hai thuật toán đầy đủ. Chuyển bài gốc sang topology khác cần kiểm chứng lại hiệu quả.

## Thiết lập

-2routing ×4scheduler(EDF,SPT,guard+EDF,guard+SPT),5seed93000–93004,3mức tải,2pin UAV.
-Estimate chính xác vàmultiplicative noise±40%: **480episode**, 31.648 kết quả task (có workload/policy/scenario lặp).
-Cùng actual workload giữa policy và hai mức error; kiểm tra1.978workload rows khớp mọi trường trừ estimated MI. Không tune threshold.
-RescueNet metadata + Alibaba background; fixed-hover UAV,4groundCPU500MIPS,UAV2000MIPS,horizon600s. Compute/power/deadline là giả định. Mọi source connected trong benchmark này; chưa có disaster outage/mobile scenario.
-Task early-drop tính failure; không preempt running hoặc hủy transfer. Ground luônFIFO.

## Kết quả chính: cùng scheduler EDF

Macro-average30case, không phải confidence interval. Dùng EDF để tách rõ hai cơ chế; SPT đầy đủ có trong CSV/REPORT của từng lượt.

### Estimate chính xác

| Phương án | Image DVR ↓ | Background DVR ↓ | Tổng năng lượng |
| --- | ---: | ---: | ---: |
| Baseline DEADLINE_ENERGY+EDF | **0,598%** | 0,000% | 43,217kJ |
| Cơ chế D1: +deadline guard | **0,598%** | 0,000% | 43,217kJ |
| Cơ chế D2: transfer-aware+EDF | 1,897% | 0,000% | 43,202kJ |
| Kết hợp D1+D2 | 1,897% | 0,000% | 43,202kJ |

Không có task bị risk-drop trong lượt này: routing và workload hiện tại khiến guard không có dịp tác động. Không được gọi kết quả bằng nhau là guard đã chứng minh có lợi.

### Estimate sai số ±40%

| Phương án | Image DVR ↓ | Background DVR ↓ | Tổng năng lượng |
| --- | ---: | ---: | ---: |
| Baseline DEADLINE_ENERGY+EDF | 3,309% | 0,000% | 43,200kJ |
| Cơ chế D1: +deadline guard | **3,217%** | 0,000% | 43,196kJ |
| Cơ chế D2: transfer-aware+EDF | 3,853% | 0,000% | 43,194kJ |
| Kết hợp D1+D2 | 3,762% | 0,000% | 43,190kJ |

D1 cải thiện0,092điểm phần trăm trong lượt này, rất nhỏ; chưa có kiểm định để nói tốt hơn đáng tin cậy. D2 và bản kết hợp kém baseline về imageDVR. Chênh energy nhỏ, không bù được việc phục vụ kém nếu deadline là tiêu chí chính.

Với SPT, baseline và guard giống nhau: imageDVR0,684% ở error0 và3,217% ở error40%; transfer-aware làm tăng tương ứng lên1,982% và3,762%. Chưa có bằng chứng gate tốt hơn SPT.

## Trace nói gì về transfer gate?

So TRANSFER_AWARE+EDF với DEADLINE_ENERGY+EDF trên1.424image cases (gồm lặp mức pin):

| Estimate | Arrival gặp gate đang đóng | Task đổi route | Baseline đúng hạn → gate trễ/miss | Baseline miss → gate đúng hạn |
| --- | ---: | ---: | ---: | ---: |
| Chính xác | 94 | 38 | 28 | 0 |
| Sai số±40% | 86 | 22 | 14 | 2 |

Đây là chênh outcome ghép cặp; không chứng minh từng task mất hạn chỉ do route riêng của nó, vì các quyết định khác cũng làm queue thay đổi.

Giải thích mô hình quan trọng: **radio hiện cho mỗi upload link rate độc lập, không contention**. Gate của ADP được đặt trong bài gốc có tài nguyên mạng hạn chế và lựa chọn processor/controller pool khác. Ở bản thích nghi này, chặn upload có thể không đem lợi ích tránh contention, trong khi buộc task về CPU local chậm. Đây là lời giải thích phù hợp với trace và mô hình, chưa phải thử nghiệm nhân quả đã cô lập network contention.

Không nên thêm contention chỉ để gate thắng. Nếu cần mô hình contention cho ứng dụng, phải định nghĩa bandwidth sharing thực tế, kiểm tra và chạy lại mọi baseline trên cùng radio model.

## Verification

-3test mới cho transfer gate: đang transfer thì route LOCAL, transfer hoàn thành đúng boundary mở gate, future upload không ảnh hưởng action hiện tại.
-Toàn bộ Java regression được chạy; số test và tình trạng cuối được đối chiếu với surefire reports.
-Python replay đủ480episode/31.648task: routing và active-upload predicate từ trace, candidate forecasts, EDF/SPT dispatch, deadline-risk predicate, work/energy/upload/status, same workload hash và source snapshot.
-Verifier chấp nhận gate trace gốc và từ chối khi giả định không có gate. Các corruption tests offloading và deadline guard tiếp tục được chạy.
-Lượt error0 có0risk drops; error40 có8risk drops trên các policy lặp. Không coi số này là8task độc lập hoặc hiệu quả lâm sàng/hiện trường.
-Giới hạn: generated workload replay, chưa độc lập tái dựng raw-pool sampling. Một cấu hình fixed-UAV,5seed, chưa mô hình outage/network congestion.

## Quyết định sau thử nghiệm

1. **Chưa thay baseline hiện tại bằng transfer-aware gate.** Cơ chế này không phù hợp tốt với radio độc lập và một UAV trong pilot.
2. Giữ DEADLINE_ENERGY+EDF/SPT làm mốc. Deadline guard đơn giản có thể giữ làm option, nhưng không khẳng định luôn tốt; pilot trước với seed khác đã có regression khi estimate sai.
3. Không cần thêm MARL để “cứu” cơ chế kém. Ưu tiên chốt đặc trưng disaster có ảnh hưởng thật: source outage, delivery path và compute/power calibration.
4. Nếu muốn tái hiện ADP đầy đủ, phải xây controller waiting pool và lựa chọn nhiều processor, nêu thay đổi topology/action rồi kiểm tra riêng; không coi LOCAL fallback là tương đương thuật toán gốc.

Hai paper vẫn là tài liệu tham khảo có ích. Kết quả âm ở bản thích nghi **không bác bỏ kết quả của tác giả**; nó cho thấy cơ chế phụ thuộc giả định hệ thống.

## Artifact và chạy lại

- `target/two-paper-adapt-e0-20261029/`
- `target/two-paper-adapt-e40-20261029/`

Mỗi thư mục có REPORT.md, episodes.csv, verification.json, source snapshots và task/decision/energy traces.

```powershell
mvn -o test
mvn -o compile exec:java "-Dexec.mainClass=uav.offloading.QueueImpactBenchmark" "-Dqios.output=target/two-paper-NEW" "-Dqios.paperInspired=true" "-Dqios.seeds=5" "-Dqios.firstSeed=93000" "-Dqios.estimateError=0"
python scripts/verify-deadline-risk.py target/two-paper-NEW
```

Error40 dùng output mới và`-Dqios.estimateError=0.4`. Tài liệu tham khảo/mức đọc: [DISASTER_OFFLOADING_SCHEDULING_LITERATURE.md](DISASTER_OFFLOADING_SCHEDULING_LITERATURE.md).
