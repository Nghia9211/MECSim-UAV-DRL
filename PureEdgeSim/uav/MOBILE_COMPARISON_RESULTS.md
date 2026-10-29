# Kết quả đưa thuật toán vào UAV di động

Run server 29/10/2026, commit `1bce0b9`. Round Robin chung cho mọi policy; 30 task seed95000..95029, 2 layout scale ×2load ×2pin, 9 cặp offloading/scheduling, 2 estimate error: 4320episode.

## Môi trường đã chạy

- UAV bay thật trong simulator: 5m/s, flight150W/hover80W, altitude10m, coverage65m, dwell30s. Không upload trong lúc bay; CPU vẫn chạy khi bay; upload dở có thể giữ stop.
- Task ngoài coverage chạy local ngay. ALL_UAV là ALL_UAV_WHEN_COVERED. ALL_LOCAL vẫn giữ UAV bay/background để dùng chung tầng phục vụ; không phải deployment không UAV.
- 12CPU local500MIPS, UAV2000MIPS, 8/12source connected. Vùng250/800m từ cùng normalized layout seed42; không phải30layout độc lập. Horizon600s, arrival[0,300)s.
- Cùng selector RR không có nghĩa trajectory giống hệt: upload pinning/depletion có thể làm lộ trình thực khác nhau.
- Compute DVR giữ định nghĩa cũ. Delivered DVR tính cả việc kết quả đã nhận được; local completion ở source disconnected không phải delivered success. Backhaul/output khi có đường truyền đang tức thời.
- Total energy đã gồm flight+hover+CPU+ground idle/compute/TX; không cộng propulsion lần hai. Latency là completed images, P95 trung bình per-episode; lifetime restricted min(T,600s) và có censoring.
- Không so trực tiếp số này với benchmark fixed4CPU để quy mọi khác biệt cho di chuyển. Không DQN training hoặc paper reproduction claim.

## Ước lượng chính xác

| Thuật toán (RR chung) | Compute DVR % | J/ảnh đúng hạn | Mean latency s | Mean P95 s | Restricted UAV time s | Delivered DVR % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 7.000 | 1342.215 | 23.261 | 36.781 | 415.228 | 36.937 |
| ALL_UAV__EDF | 9.762 | 1367.481 | 22.816 | 36.548 | 418.451 | 38.322 |
| ALL_UAV__FIFO | 9.762 | 1367.475 | 22.813 | 36.503 | 418.451 | 38.322 |
| ALL_UAV__SPT | 9.762 | 1367.388 | 22.809 | 36.494 | 418.454 | 38.322 |
| DEADLINE_ENERGY__EDF | 6.785 | 1338.541 | 23.225 | 36.767 | 415.242 | 36.722 |
| DEADLINE_ENERGY__FIFO | 6.802 | 1338.913 | 23.226 | 36.767 | 415.242 | 36.739 |
| DEADLINE_ENERGY__RISK_EDF | 6.785 | 1334.491 | 23.226 | 36.767 | 415.498 | 36.722 |
| DEADLINE_ENERGY__SPT | 6.799 | 1338.759 | 23.225 | 36.767 | 415.242 | 36.735 |
| SHORTEST_FINISH__EDF | 6.754 | 1337.491 | 22.811 | 36.437 | 414.946 | 36.554 |

| Thuật toán | Offloaded images/episode | Covered images/episode | Flight kJ | Hover kJ | Background DVR % |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 0.000 | 3.400 | 38.947 | 12.446 | 13.989 |
| ALL_UAV__EDF | 2.858 | 2.858 | 37.202 | 13.635 | 12.949 |
| ALL_UAV__FIFO | 2.858 | 2.858 | 37.202 | 13.635 | 12.909 |
| ALL_UAV__SPT | 2.858 | 2.858 | 37.203 | 13.635 | 12.641 |
| DEADLINE_ENERGY__EDF | 0.129 | 3.362 | 38.935 | 12.454 | 13.989 |
| DEADLINE_ENERGY__FIFO | 0.129 | 3.362 | 38.935 | 12.454 | 13.989 |
| DEADLINE_ENERGY__RISK_EDF | 0.113 | 3.379 | 38.960 | 12.461 | 12.793 |
| DEADLINE_ENERGY__SPT | 0.129 | 3.362 | 38.935 | 12.454 | 13.898 |
| SHORTEST_FINISH__EDF | 1.337 | 3.367 | 38.890 | 12.454 | 14.042 |

RISK_EDF so với DEADLINE_ENERGY+EDF, image_dvr: tốt hơn/bằng/tệ hơn = 0/240/0 case.

RISK_EDF so với DEADLINE_ENERGY+EDF, delivered_image_dvr: tốt hơn/bằng/tệ hơn = 0/240/0 case.

| Pin UAV | EDF: UAV time s | RISK_EDF: UAV time s | Censor |
| --- | ---: | ---: | --- |
| 30000J | 230.483 | 230.995 | Không, quan sát hết pin |
| 1600000J | 600.000 | 600.000 | Toàn bộ >=600s |

Từng layout/load/pin: `target/mobile-metrics-server-results-20261029/e0/core-metrics-summary.csv`.

## Sai số ước lượng ±40%

| Thuật toán (RR chung) | Compute DVR % | J/ảnh đúng hạn | Mean latency s | Mean P95 s | Restricted UAV time s | Delivered DVR % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 7.000 | 1342.215 | 23.261 | 36.781 | 415.228 | 36.937 |
| ALL_UAV__EDF | 9.762 | 1367.481 | 22.816 | 36.548 | 418.451 | 38.322 |
| ALL_UAV__FIFO | 9.762 | 1367.475 | 22.813 | 36.503 | 418.451 | 38.322 |
| ALL_UAV__SPT | 9.769 | 1367.518 | 22.809 | 36.494 | 418.454 | 38.329 |
| DEADLINE_ENERGY__EDF | 6.870 | 1339.689 | 23.221 | 36.767 | 415.208 | 36.801 |
| DEADLINE_ENERGY__FIFO | 6.887 | 1340.073 | 23.222 | 36.767 | 415.211 | 36.818 |
| DEADLINE_ENERGY__RISK_EDF | 6.877 | 1336.237 | 23.221 | 36.767 | 415.290 | 36.807 |
| DEADLINE_ENERGY__SPT | 6.877 | 1339.786 | 23.220 | 36.767 | 415.208 | 36.807 |
| SHORTEST_FINISH__EDF | 6.780 | 1337.979 | 22.812 | 36.457 | 414.923 | 36.579 |

| Thuật toán | Offloaded images/episode | Covered images/episode | Flight kJ | Hover kJ | Background DVR % |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 0.000 | 3.400 | 38.947 | 12.446 | 13.989 |
| ALL_UAV__EDF | 2.858 | 2.858 | 37.202 | 13.635 | 12.949 |
| ALL_UAV__FIFO | 2.858 | 2.858 | 37.202 | 13.635 | 12.909 |
| ALL_UAV__SPT | 2.858 | 2.858 | 37.203 | 13.635 | 12.672 |
| DEADLINE_ENERGY__EDF | 0.150 | 3.404 | 38.939 | 12.449 | 13.989 |
| DEADLINE_ENERGY__FIFO | 0.142 | 3.404 | 38.940 | 12.449 | 13.989 |
| DEADLINE_ENERGY__RISK_EDF | 0.150 | 3.404 | 38.944 | 12.453 | 12.858 |
| DEADLINE_ENERGY__SPT | 0.150 | 3.404 | 38.939 | 12.449 | 13.918 |
| SHORTEST_FINISH__EDF | 1.342 | 3.375 | 38.895 | 12.450 | 14.063 |

RISK_EDF so với DEADLINE_ENERGY+EDF, image_dvr: tốt hơn/bằng/tệ hơn = 0/239/1 case.

RISK_EDF so với DEADLINE_ENERGY+EDF, delivered_image_dvr: tốt hơn/bằng/tệ hơn = 0/239/1 case.

| Pin UAV | EDF: UAV time s | RISK_EDF: UAV time s | Censor |
| --- | ---: | ---: | --- |
| 30000J | 230.416 | 230.581 | Không, quan sát hết pin |
| 1600000J | 600.000 | 600.000 | Toàn bộ >=600s |

Từng layout/load/pin: `target/mobile-metrics-server-results-20261029/e40/core-metrics-summary.csv`.

## Verification

Exit0 + completion marker; COMPLETE manifests; independent mobile audit PASS cả4320episode. 124Java tests, 4metric tests, 8mobile verifier tests/error và3guard verifier tests/error. Guard negative tests dùng recorded drop khi có; nếu guard không kích hoạt dùng hand fixture in-flight, không đổi benchmark workload.

Task outcomes: 283968. SHA256 đã đối chiếu12file tải về. Local/server parity: 432episode chung, hashes workload trùng, metric numeric tolerance abs1e-6/rel1e-9; không đo parity wall-time.

Remote outputs: `aiotlab_92:/mnt/disk1/nghialt2/MECSim-UAV-DRL/target/mobile-metrics-20261029-v1-{e0,e40}`; control `target/mobile-metrics-control-20261029-v1`. Raw trajectories/tasks/source snapshots ở server; bản local chỉ có metric/metadata/log.

## Giới hạn và bước tiếp

Các kết quả chỉ xác nhận mô hình đã khai báo, chưa hiệu chuẩn thực tế; workload dùng metadata RescueNet và Alibaba-derived background, không chạy inference. Đọc coverage/offload và delivered DVR trước khi kết luận scheduler mới có giá trị. Nếu UAV hỗ trợ quá ít task, phải xem lại policy phục vụ và điều kiện ứng dụng trước khi train dài; không chỉnh setting chỉ để guard thắng.

## Kết luận thực nghiệm

**Đã tích hợp và chạy đúng môi trường di động; chưa chứng minh RISK_EDF cải thiện
workload ảnh trong môi trường này.**

- Estimate chính xác: RISK_EDF có compute/delivered DVR giống EDF ở cả240case.
  J/ảnh đúng hạn giảm khoảng0,30%; UAV pin30kJ hoạt động thêm khoảng0,51s.
- Estimate sai số±40%: không có case nào cải thiện DVR ảnh; 239case bằng và1case
  tệ hơn. J/ảnh đúng hạn giảm khoảng0,26%; lifetime pin nhỏ chỉ tăng khoảng0,16s.
  Chưa có kiểm định cho các chênh lệch nhỏ này.
- Guard thực sự loại21background task ở e0; e40 loại16background task và1task ảnh.
  Drop luôn tính failure. Lợi ích hiện chủ yếu ở background DVR, không phải ảnh.
- SHORTEST_FINISH+EDF tốt hơn RISK_EDF về compute/delivered DVR và latency trong
  các trung bình này; không loại baseline mạnh này khỏi các lần đánh giá sau.
- DEADLINE_ENERGY chỉ offload khoảng0,1–0,15ảnh/episode. Tổng năng lực local là
  12×500=6000MIPS, còn UAV2000MIPS. CPU energy biên local3/500=0,006J/MI,
  UAV20/2000=0,010J/MI chưa tính TX/propulsion. Khi local kịp deadline, policy thường
  giữ ảnh tại nguồn. Những con số này là giả định model, chưa phải measurement.
- Delivered DVR khoảng36–38% cao hơn compute DVR khoảng7–10%: local completion tại
  source disconnected không được chuyển về; task ngoài coverage không chờ UAV.
  Routing hiện chưa xét trực tiếp khả năng delivery của source. Đây là hạn chế
  cần giải quyết trước khi dùng kết quả để khẳng định hiệu quả disaster analytics.

Bước tiếp hợp lý là thiết kế delivery/contact-aware offloading (phân biệt local
compute và kết quả tới trung tâm, cân nhắc hàng đợi chờ lượt UAV), với giả định được
chốt trước và các baseline cùng luật vật lý. Chưa triển khai cơ chế chờ hoặc train
policy mới trong đợt này; không thay setting chỉ để tăng số offload hoặc làm guard thắng.

Biên nhận: `target/mobile-metrics-server-results-20261029/receipt.json`;
diagnostics kiểm tra240case actual workloads khớp giữa e0/e40 tại
`target/mobile-metrics-server-results-20261029/control/diagnostics.json`.
