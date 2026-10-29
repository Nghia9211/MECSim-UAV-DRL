# Delivery-aware offloading: kết quả current-contact

Protocol trước launch: [DELIVERY_AWARE_PLAN.md](DELIVERY_AWARE_PLAN.md). Source commit `97a98a5`. Không train model; không thay power/CPU/range/layout/deadline để làm policy mới thắng.

**Kết luận:** DELIVERY_AWARE sửa được một phần sự lệch mục tiêu compute/delivery,
nhưng mức cải thiện nhỏ. Chưa giải quyết các task sinh ra ngoài vùng phục vụ UAV.

- Với RISK_EDF, delivered DVR giảm từ36,722% xuống36,509% khi estimate chính xác,
  và từ36,807% xuống36,621% khi sai số±40%, so với DEADLINE_ENERGY+RISK_EDF.
  J/ảnh delivered đúng hạn giảm lần lượt0,456% và0,378%.
- So với baseline mạnh SHORTEST_FINISH+EDF: delivered DVR tốt hơn nhẹ ở e0
  (36,509% so với36,554%), nhưng tệ hơn ở e40 (36,621% so với36,579%).
  SHORTEST_FINISH vẫn có latency trung bình/P95 thấp hơn rõ rệt.
- P95 delivery của policy mới cao hơn bản cũ. So với DEADLINE_ENERGY cùng scheduler,
  lifetime pin30kJ tăng dưới1giây;
  pin1.6MJ chưa hết ở600s, không suy diễn tuổi thọ thực.
- Lợi ích không đồng đều: RISK_EDF mới tốt hơn/bằng/tệ hơn về delivered DVR
  ở25/214/1case của e0 và21/219/0case của e40. Chưa có kiểm định significance.
- Số ảnh offload tăng từ khoảng0,1–0,15 lên0,24–0,25ảnh/episode nhưng vẫn rất thấp.
  Đây chưa phải bằng chứng đã giải quyết hiệu quả bài toán disaster analytics đầy đủ.

## Đã thay gì?

Policy DELIVERY_AWARE nhận boolean localDeliveryAvailable từ connected flag hiện tại. Nếu local không chuyển được kết quả về và forecast UAV available, đủ pin, kịp deadline, chọn UAV; còn lại dùng DEADLINE_ENERGY. Contact availability được kernel tính từ trajectory và stop. Không biết future task/actual MI/outage tương lai.
Đây là current-contact routing: chưa có buffer chờ UAV, planner dự báo điểm ghé hoặc upload kết quả local đã tính. Task ngoài coverage vẫn local ngay. ALL_UAV nghĩa là ALL_UAV_WHEN_COVERED; ALL_LOCAL vẫn giữ tầng RR/flight/background chung.

## Thiết lập và metric

30 task seed95000..95029, 8case (2scale layout ×2load ×2pin), 9policy, 2estimate error0/±40%: 4320episode. RR, 12local CPU500MIPS, UAV2000MIPS, v5m/s, range65m, dwell30s, flight150W/hover80W, horizon600s/arrival300s. 8/12source connected; các CPU/power/deadline là giả định. Không có radio contention.
Bảng delivery đánh giá kết quả đã tới trung tâm; compute DVR giữ nguyên định nghĩa cũ và báo riêng. Mean/P95 delivery chỉ trên ảnh đã delivered, gồm late; P95 trung bình per-episode. Return/backhaul tức thời khi có đường delivery, không mô phỏng output TX/RX.
Energy là UAV + tất cả source, bao gồm propulsion/background/idle. J/ảnh là tỷ số tổng J trên tổng thành công đúng hạn, không phải trung bình tỷ số. Lifetime bảng là min(T,600s), không phải lifetime mạng; một nửa case bị censor ở600s. Không có kiểm định significance.

## Ước lượng chính xác

| Thuật toán (RR chung) | Delivered DVR % | J/ảnh delivered đúng hạn | Mean delivery latency s | Mean delivery P95 s | Restricted UAV time s |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 36.937 | 1986.842 | 23.164 | 36.803 | 415.228 |
| ALL_UAV__EDF | 38.322 | 2005.835 | 22.567 | 36.119 | 418.451 |
| ALL_UAV__FIFO | 38.322 | 2005.827 | 22.565 | 36.044 | 418.451 |
| ALL_UAV__SPT | 38.322 | 2005.699 | 22.560 | 36.041 | 418.454 |
| DEADLINE_ENERGY__EDF | 36.722 | 1978.786 | 23.108 | 36.748 | 415.242 |
| DEADLINE_ENERGY__RISK_EDF | 36.722 | 1972.799 | 23.111 | 36.748 | 415.498 |
| DELIVERY_AWARE__EDF | 36.516 | 1970.030 | 23.114 | 37.010 | 415.348 |
| DELIVERY_AWARE__RISK_EDF | 36.509 | 1963.797 | 23.112 | 37.010 | 415.599 |
| SHORTEST_FINISH__EDF | 36.554 | 1971.818 | 22.478 | 35.883 | 414.946 |

| Thuật toán | Compute DVR % | J/ảnh compute đúng hạn | Mean compute latency s | Mean compute P95 s | Offload/episode | Background DVR % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 7.000 | 1342.215 | 23.261 | 36.781 | 0.000 | 13.989 |
| ALL_UAV__EDF | 9.762 | 1367.481 | 22.816 | 36.548 | 2.858 | 12.949 |
| ALL_UAV__FIFO | 9.762 | 1367.475 | 22.813 | 36.503 | 2.858 | 12.909 |
| ALL_UAV__SPT | 9.762 | 1367.388 | 22.809 | 36.494 | 2.858 | 12.641 |
| DEADLINE_ENERGY__EDF | 6.785 | 1338.541 | 23.225 | 36.767 | 0.129 | 13.989 |
| DEADLINE_ENERGY__RISK_EDF | 6.785 | 1334.491 | 23.226 | 36.767 | 0.113 | 12.793 |
| DELIVERY_AWARE__EDF | 6.759 | 1337.594 | 23.220 | 36.885 | 0.246 | 13.958 |
| DELIVERY_AWARE__RISK_EDF | 6.759 | 1333.548 | 23.219 | 36.885 | 0.242 | 12.763 |
| SHORTEST_FINISH__EDF | 6.754 | 1337.491 | 22.811 | 36.437 | 1.337 | 14.042 |

DELIVERY_AWARE+EDF so với DEADLINE_ENERGY+EDF: delivered DVR giảm 0.206 điểm phần trăm; J/ảnh delivered đúng hạn giảm 0.442%. Tốt hơn/bằng/tệ hơn về delivered DVR: 24/215/1 case.

DELIVERY_AWARE+RISK_EDF so với DEADLINE_ENERGY+RISK_EDF: delivered DVR giảm 0.213 điểm phần trăm; J/ảnh delivered đúng hạn giảm 0.456%. Tốt hơn/bằng/tệ hơn về delivered DVR: 25/214/1 case.

| Thuật toán | Lifetime pin30kJ s | Flight kJ | Hover kJ | Distance m |
| --- | ---: | ---: | ---: | ---: |
| SHORTEST_FINISH__EDF | 229.892 | 38.890 | 12.454 | 1296.323 |
| DEADLINE_ENERGY__EDF | 230.483 | 38.935 | 12.454 | 1297.835 |
| DELIVERY_AWARE__EDF | 230.696 | 38.873 | 12.496 | 1295.755 |
| DELIVERY_AWARE__RISK_EDF | 231.199 | 38.897 | 12.503 | 1296.570 |

Pin1.6MJ: mọi thuật toán sống ít nhất600s, chưa đo exhaustion thật.
Chi tiết từng layout/load/pin: `target/delivery-aware-server-results-20261029/e0/core-metrics-summary.csv`.

## Sai số ước lượng ±40%

| Thuật toán (RR chung) | Delivered DVR % | J/ảnh delivered đúng hạn | Mean delivery latency s | Mean delivery P95 s | Restricted UAV time s |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 36.937 | 1986.842 | 23.164 | 36.803 | 415.228 |
| ALL_UAV__EDF | 38.322 | 2005.835 | 22.567 | 36.119 | 418.451 |
| ALL_UAV__FIFO | 38.322 | 2005.827 | 22.565 | 36.044 | 418.451 |
| ALL_UAV__SPT | 38.329 | 2005.981 | 22.559 | 36.041 | 418.454 |
| DEADLINE_ENERGY__EDF | 36.801 | 1981.015 | 23.100 | 36.741 | 415.208 |
| DEADLINE_ENERGY__RISK_EDF | 36.807 | 1976.001 | 23.100 | 36.741 | 415.290 |
| DELIVERY_AWARE__EDF | 36.621 | 1973.791 | 23.094 | 36.869 | 415.271 |
| DELIVERY_AWARE__RISK_EDF | 36.621 | 1968.523 | 23.093 | 36.869 | 415.354 |
| SHORTEST_FINISH__EDF | 36.579 | 1972.892 | 22.480 | 35.884 | 414.923 |

| Thuật toán | Compute DVR % | J/ảnh compute đúng hạn | Mean compute latency s | Mean compute P95 s | Offload/episode | Background DVR % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 7.000 | 1342.215 | 23.261 | 36.781 | 0.000 | 13.989 |
| ALL_UAV__EDF | 9.762 | 1367.481 | 22.816 | 36.548 | 2.858 | 12.949 |
| ALL_UAV__FIFO | 9.762 | 1367.475 | 22.813 | 36.503 | 2.858 | 12.909 |
| ALL_UAV__SPT | 9.769 | 1367.518 | 22.809 | 36.494 | 2.858 | 12.672 |
| DEADLINE_ENERGY__EDF | 6.870 | 1339.689 | 23.221 | 36.767 | 0.150 | 13.989 |
| DEADLINE_ENERGY__RISK_EDF | 6.877 | 1336.237 | 23.221 | 36.767 | 0.150 | 12.858 |
| DELIVERY_AWARE__EDF | 6.842 | 1338.856 | 23.214 | 36.825 | 0.250 | 13.958 |
| DELIVERY_AWARE__RISK_EDF | 6.849 | 1335.410 | 23.213 | 36.825 | 0.254 | 12.827 |
| SHORTEST_FINISH__EDF | 6.780 | 1337.979 | 22.812 | 36.457 | 1.342 | 14.063 |

DELIVERY_AWARE+EDF so với DEADLINE_ENERGY+EDF: delivered DVR giảm 0.180 điểm phần trăm; J/ảnh delivered đúng hạn giảm 0.365%. Tốt hơn/bằng/tệ hơn về delivered DVR: 20/220/0 case.

DELIVERY_AWARE+RISK_EDF so với DEADLINE_ENERGY+RISK_EDF: delivered DVR giảm 0.187 điểm phần trăm; J/ảnh delivered đúng hạn giảm 0.378%. Tốt hơn/bằng/tệ hơn về delivered DVR: 21/219/0 case.

| Thuật toán | Lifetime pin30kJ s | Flight kJ | Hover kJ | Distance m |
| --- | ---: | ---: | ---: | ---: |
| SHORTEST_FINISH__EDF | 229.845 | 38.895 | 12.450 | 1296.486 |
| DEADLINE_ENERGY__EDF | 230.416 | 38.939 | 12.449 | 1297.976 |
| DELIVERY_AWARE__EDF | 230.542 | 38.899 | 12.475 | 1296.649 |
| DELIVERY_AWARE__RISK_EDF | 230.707 | 38.904 | 12.479 | 1296.808 |

Pin1.6MJ: mọi thuật toán sống ít nhất600s, chưa đo exhaustion thật.
Chi tiết từng layout/load/pin: `target/delivery-aware-server-results-20261029/e40/core-metrics-summary.csv`.

## Verification

Exit0 + completion marker, COMPLETE manifest, independent audit PASS cả4320episode/283968task outcomes. 125Java tests, 4metric tests, mỗi error8mobile verifier +3risk verifier +5delivery verifier tests PASS. Delivery test chọn episode thật sự override local rẻ sang UAV vì disconnected; false connectivity/missing flag/old route/missing update phải bị từ chối.
Local/server parity 432episode: workload hash trùng, metric abs1e-6/rel1e-9, không so wall-time. Legacy pilot parity 336episode. Full server legacy parity3360episode gồm task, energy, decisions, visits, positions, coverage, updates, views, mọi cột cũ: unchanged. Trace mới thêm local_delivery_available, không sửa baseline.
Actual workload giữa e0/e40 khớp240case khi bỏ estimated_mi; source snapshots chỉ khác test âm delivery, kernel/algorithm/verifier/metric code giữ nguyên. SHA256 của12file tải về khớp. Raw traces/source snapshots ở server; local chỉ metric/metadata/log.

Remote outputs: `aiotlab_92:/mnt/disk1/nghialt2/MECSim-UAV-DRL/target/delivery-aware-20261029-v1-e0` và `target/delivery-aware-20261029-v2-e40`; control `target/delivery-aware-control-20261029-v2`. Biên nhận `target/delivery-aware-server-results-20261029/receipt.json`.

Recovery: launcher v1 dừng sau audit e0 PASS vì test âm xóa update chờ sai thông báo lỗi. Verifier đã phát hiện corruption sớm ở freshness snapshot. Commit `0bbb90c` chỉ sửa expected assertion của test; chạy lại test trên e0 PASS, giữ dữ liệu e0 đã audit và chạy e40 trong v2. Source hashes xác nhận không đổi kernel/algorithm. Log thất bại ban đầu được giữ để audit; không rerun simulation e0 không cần thiết.

## Phạm vi

Không gọi đây là full contact planner hay tái hiện paper Azfar. Phương pháp chưa giải quyết task sinh ngoài coverage hoặc chờ UAV, nên có giới hạn mức cải thiện delivery. Không thay setting để tăng offload, không tune threshold, không dùng actual work hoặc future route làm oracle. Không khẳng định thắng mọi metric hoặc significance từ trung bình.

Bước tiếp theo phù hợp là hàng đợi chờ tiếp xúc có điều kiện deadline/pin. Một phạm vi
có thể kiểm chứng là chỉ đợi UAV đang bay tới điểm phục vụ đã được quyết định,
không giả định các chuyến bay tương lai chưa chọn. Khi triển khai phải cho baseline
cùng quyền chờ và cùng luật admission/expiry/energy, rồi mới so sánh thuật toán.
Chưa thực hiện bước này hoặc train policy mới trong đợt hiện tại.
