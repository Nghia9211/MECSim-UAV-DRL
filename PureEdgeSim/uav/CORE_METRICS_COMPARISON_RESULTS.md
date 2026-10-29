# So sánh các thuật toán theo bộ metric chính

Run ngày 29/10/2026. 30 seed 94000–94029, 3 mức tải × 2 pin, cùng workload và kernel. Không train, không tune.
9 baseline mới (3.240 episode) ghép với 8 cấu hình adapted (2.880 episode); 2 cấu hình trùng phải cho kết quả giống nhau. Sau loại trùng: 15 cấu hình × 180 case × 2 estimate error = 5.400 episode.

## Cách đọc

- DVR ảnh: tất cả ảnh được tạo đều nằm trong mẫu số; mọi drop là failure.
- J/ảnh đúng hạn: tổng năng lượng toàn hệ thống, gồm hover/background, chia tổng ảnh đúng hạn.
- Mean/P95 latency: ảnh hoàn thành, gồm cả ảnh trễ; P95 từng episode rồi lấy trung bình. Chưa có truyền kết quả về.
- UAV time: thời gian hoạt động giới hạn bởi horizon; không phải lifetime toàn mạng. 90/180 case pin lớn bị censor tại 600s cho mỗi thuật toán.
- Đây là kết quả mô tả; chưa có kiểm định ý nghĩa thống kê. Chi tiết quy ước ở [EVALUATION_METRICS.md](EVALUATION_METRICS.md).

## Các nhóm thuật toán

- ALL_LOCAL: ảnh xử lý local; background vẫn chạy trên UAV và hover vẫn tiêu thụ năng lượng.
- ALL_UAV: ảnh luôn gửi lên UAV; SHORTEST_FINISH: chọn nơi có dự báo hoàn thành sớm hơn.
- DEADLINE_ENERGY: routing xét deadline và năng lượng; FIFO/EDF/SPT/PRIORITY là cách xếp hàng UAV. Local giữ FIFO.
- RISK_EDF/RISK_SPT: loại task chưa chạy nếu dự báo không thể kịp deadline; task bị loại vẫn tính thất bại.
- TRANSFER_AWARE: hạn chế offload khi đang upload. Đây là bản thích nghi cơ chế, không tái hiện đầy đủ paper.

## Ước lượng chính xác

| Thuật toán | DVR ảnh % ↓ | J/ảnh đúng hạn ↓ | Mean latency s ↓ | Mean P95 s ↓ | UAV time giới hạn s ↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 26.864 | 1360.346 | 33.183 | 57.784 | 478.454 |
| ALL_UAV__EDF | 20.661 | 1276.161 | 20.545 | 36.362 | 458.152 |
| ALL_UAV__FIFO | 23.247 | 1314.803 | 20.803 | 35.189 | 458.361 |
| ALL_UAV__SPT | 17.145 | 1157.600 | 18.421 | 30.944 | 458.345 |
| DEADLINE_ENERGY__EDF | 3.352 | 961.288 | 25.406 | 48.325 | 472.717 |
| DEADLINE_ENERGY__FIFO | 3.988 | 970.806 | 25.622 | 48.390 | 472.885 |
| DEADLINE_ENERGY__PRIORITY | 3.279 | 960.076 | 25.382 | 48.317 | 472.724 |
| DEADLINE_ENERGY__RISK_EDF | 1.390 | 928.902 | 24.817 | 47.276 | 474.313 |
| DEADLINE_ENERGY__RISK_SPT | 1.815 | 934.844 | 24.967 | 47.334 | 474.469 |
| DEADLINE_ENERGY__SPT | 3.768 | 967.535 | 25.535 | 48.357 | 472.809 |
| SHORTEST_FINISH__EDF | 2.976 | 949.347 | 14.860 | 28.148 | 458.555 |
| TRANSFER_AWARE__EDF | 5.094 | 985.933 | 25.769 | 48.790 | 473.239 |
| TRANSFER_AWARE__RISK_EDF | 3.535 | 957.708 | 25.280 | 48.333 | 474.895 |
| TRANSFER_AWARE__RISK_SPT | 3.827 | 961.861 | 25.394 | 48.295 | 475.027 |
| TRANSFER_AWARE__SPT | 5.343 | 989.637 | 25.855 | 48.748 | 473.304 |

So với DEADLINE_ENERGY+EDF, RISK_EDF:
- DVR ảnh: giảm tương đối 58.53%.
- J/ảnh đúng hạn: giảm tương đối 3.37%.
- Mean latency: giảm tương đối 2.32%.
- Mean episode P95: giảm tương đối 2.17%.

| Pin UAV | EDF: UAV time s | RISK_EDF: UAV time s | Censoring |
| --- | ---: | ---: | --- |
| 30000 J | 345.435 | 348.626 | Không; quan sát hết pin |
| 1600000 J | 600.000 | 600.000 | Toàn bộ >=600s, chưa biết lifetime thật |

CSV từng load/pin: `target/core-metrics-results-20261029/compare-e0/core-metrics-summary.csv`.

## Sai số ước lượng ±40%

| Thuật toán | DVR ảnh % ↓ | J/ảnh đúng hạn ↓ | Mean latency s ↓ | Mean P95 s ↓ | UAV time giới hạn s ↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 26.864 | 1360.346 | 33.183 | 57.784 | 478.454 |
| ALL_UAV__EDF | 20.661 | 1276.161 | 20.545 | 36.362 | 458.152 |
| ALL_UAV__FIFO | 23.247 | 1314.803 | 20.803 | 35.189 | 458.361 |
| ALL_UAV__SPT | 17.293 | 1156.909 | 13.631 | 32.941 | 458.397 |
| DEADLINE_ENERGY__EDF | 5.708 | 989.240 | 24.534 | 47.833 | 471.923 |
| DEADLINE_ENERGY__FIFO | 6.532 | 1002.747 | 24.739 | 47.799 | 472.085 |
| DEADLINE_ENERGY__PRIORITY | 5.708 | 989.221 | 24.516 | 47.833 | 471.923 |
| DEADLINE_ENERGY__RISK_EDF | 4.084 | 960.062 | 23.998 | 46.824 | 473.289 |
| DEADLINE_ENERGY__RISK_SPT | 4.664 | 968.714 | 24.088 | 46.816 | 473.543 |
| DEADLINE_ENERGY__SPT | 6.158 | 996.428 | 24.635 | 47.814 | 472.022 |
| SHORTEST_FINISH__EDF | 3.289 | 952.131 | 14.635 | 27.894 | 458.795 |
| TRANSFER_AWARE__EDF | 7.584 | 1017.525 | 25.031 | 49.022 | 472.502 |
| TRANSFER_AWARE__RISK_EDF | 6.118 | 989.088 | 24.501 | 48.047 | 473.961 |
| TRANSFER_AWARE__RISK_SPT | 6.382 | 993.370 | 24.582 | 48.098 | 474.078 |
| TRANSFER_AWARE__SPT | 7.776 | 1020.433 | 25.106 | 48.953 | 472.559 |

So với DEADLINE_ENERGY+EDF, RISK_EDF:
- DVR ảnh: giảm tương đối 28.44%.
- J/ảnh đúng hạn: giảm tương đối 2.95%.
- Mean latency: giảm tương đối 2.18%.
- Mean episode P95: giảm tương đối 2.11%.

| Pin UAV | EDF: UAV time s | RISK_EDF: UAV time s | Censoring |
| --- | ---: | ---: | --- |
| 30000 J | 343.846 | 346.578 | Không; quan sát hết pin |
| 1600000 J | 600.000 | 600.000 | Toàn bộ >=600s, chưa biết lifetime thật |

CSV từng load/pin: `target/core-metrics-results-20261029/compare-e40/core-metrics-summary.csv`.

## Kết luận so sánh

- RISK_EDF cải thiện so với DEADLINE_ENERGY+EDF ở cả hai mức sai số, nhưng không thắng
  tất cả baseline trên mọi metric. Với estimate chính xác, DVR ảnh và J/ảnh đúng hạn
  của RISK_EDF thấp nhất trong 15 cấu hình đã chạy.
- SHORTEST_FINISH+EDF có latency thấp hơn rõ rệt. Khi estimate sai số ±40%, phương án
  này còn có DVR ảnh tốt hơn (3,289% so với 4,084%) và J/ảnh đúng hạn thấp hơn
  (952,131 so với 960,062). Phải giữ đây là baseline mạnh trong các thử nghiệm sau.
- Đổi lại, background DVR của SHORTEST_FINISH+EDF là 11,599% / 10,794% ở e0/e40,
  so với 0,862% / 1,122% của RISK_EDF. UAV cũng hết pin sớm hơn trong nhóm pin nhỏ.
  Không tự gộp các đánh đổi này thành tuyên bố có một thuật toán thắng tuyệt đối.
- So từng case với DEADLINE_ENERGY+EDF: RISK_EDF cải thiện/bằng/tệ hơn về DVR ảnh
  là 24/156/0 ở e0 và 26/150/4 ở e40. Không suy diễn cải thiện đồng đều mọi workload.
- ALL_UAV có completed-only latency thấp nhưng bỏ lỡ nhiều ảnh hơn. Không đọc riêng
  latency để kết luận tốt hơn. ALL_LOCAL vẫn tiêu thụ UAV hover/background trong setting này.
- Lifetime cải thiện nhẹ; không có bằng chứng kéo dài lifetime vượt 600s ở nhóm pin lớn.

## Kiểm chứng và tái sử dụng

- Baseline mới: 123 Java tests PASS; 1620 episode/error được independent audit PASS;
  7 adversarial verifier tests PASS cho từng mức error. Hai metric tests chạy trên server;
  test bổ sung từ chối protocol khác nhau nâng tổng metric tests local lên 3, đều PASS.
- Ghép lại với 2880 adapted episode đã PASS trước đó; 720 episode trùng phải khớp
  toàn bộ metric. Bảng cuối có 5400 episode duy nhất, 15 cấu hình × 180 case × 2 error.
- Manifest protocol, seed, workload hash và shared kernel source hashes khớp giữa hai đợt.
  Đã đối chiếu SHA256 của 22 file tải về; remote job exit 0 và có completion marker.
- Experiment baseline commit: `09c8d82`; adapted input commit: `1d5049c`. Thay đổi entrypoint
  chỉ lọc baseline được chọn; không đổi kernel, workload generator hoặc thuật toán.
- Biên nhận local: `target/core-metrics-results-20261029/receipt.json`.
  Remote control: `target/core-metrics-control-20261029-v1` dưới repo aiotlab_92.
- Đã gắn exporter vào CLI verifier chuẩn và PowerShell runner; quy ước bắt buộc
  được lưu tại repo `AGENTS.md` và `EVALUATION_METRICS.md` để dùng cho mọi thuật toán mới.

## Phạm vi kết luận

Giữ fixed-UAV, 4 CPU local 500 MIPS, UAV 2000 MIPS, arrival window 300s, horizon 600s. RescueNet metadata + Alibaba-derived background; chi phí tính toán, deadline và power là giả định. Upload độc lập, chưa có tranh chấp radio hoặc đường truyền kết quả về. Không chứng minh tái hiện Azfar hoặc hiệu quả ngoài hiện trường.

Mọi run mới phải xuất cùng bộ metric qua verifier. Source, task và energy traces đầy đủ ở server; bản local có bảng, metadata và log.
