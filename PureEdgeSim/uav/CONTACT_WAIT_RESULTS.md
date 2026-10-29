# Kết quả hàng đợi chờ tiếp xúc đã biết

Protocol: [CONTACT_WAIT_PLAN.md](CONTACT_WAIT_PLAN.md). Source commit `36fd35d`. 4320episode =9policy ×8case ×30task seed ×2estimate error; không train DQN trong benchmark này.

**Kết luận:** hàng đợi đã hoạt động và được audit độc lập, nhưng lợi ích phụ thuộc
admission. DELIVERY_AWARE+RISK_EDF cải thiện delivery nhỏ; ALL_UAV nhận nhiều task
chờ nhưng làm delivered DVR tệ hơn. Chưa có thuật toán thắng tất cả metric.

- Cùng có quyền chờ, DELIVERY_AWARE+RISK_EDF đạt delivered DVR36,399% ở e0 và36,531%
  ở e40; DEADLINE_ENERGY+RISK_EDF là36,688% và36,797%. J/delivered đúng hạn thấp hơn.
- So với SHORTEST_FINISH+EDF: tốt hơn nhẹ về delivered DVR ở e0 (36,399% so36,466%),
  tệ hơn ở e40 (36,531% so36,495%). SHORTEST_FINISH vẫn có mean/P95 latency thấp hơn.
- Bật chờ cho cùng DELIVERY_AWARE+RISK_EDF giảm delivered DVR từ36,509% xuống36,399%
  và từ36,621% xuống36,531%. Đây là ablation capability, không phải so baseline khác quyền.
- ALL_UAV+FIFO tăng delivered DVR từ38,322% lên40,951%: nhận raw-task chờ mà không
  kiểm tra deadline/pin tốt có thể làm giảm chất lượng dịch vụ.
- Chưa có kiểm định significance; các cải thiện của candidate còn nhỏ. Lifetime pin
  lớn chỉ biết>=600s, không suy diễn kéo dài lifetime thực.

## Luật mới và cách so sánh

allowContactWait=true cho toàn bộ baseline/candidate. Task có thể reserve upload tại endpoint của chuyến bay UAV đang thực hiện nếu endpoint trong range và ETA trước deadline. Không nhìn stop chưa chọn, không reset deadline hoặc migration/retry. TX chỉ bắt đầu tại contact, source trả idle/compute trong lúc chờ. Upload chưa xong giữ UAV tại stop.
Mọi thuật toán trong bảng chính đều có cùng quyền chờ. ALL_UAV có thể buộc nhận task mà upload/CPU dự báo không kịp hoặc pin không đủ; failure vẫn được tính. DELIVERY_AWARE xét source disconnected và forecast pin/deadline; SHORTEST_FINISH cũng được chọn contact có chờ.
RR,12source500MIPS,UAV2000MIPS,2layout scale từseed42,2load,2pin,flight150W/hover80W,v5m/s,range65m,dwell30s,horizon600s/arrival300s. Không phải30layout độc lập; CPU/power/deadline là giả định, không calibrated inference.
Giữ compute và delivered DVR tách riêng. J/ảnh =tổng system J/tổng success đúng hạn. Mean/P95 chỉ trên completed hoặc delivered ảnh theo cột; P95 là trung bình percentile từng episode. Lifetime=min(T,600s), không phải lifetime mạng. Backhaul/output delay hiện0 khi có đường delivery; không có radio contention.
Offloaded là số route commits, gồm reservations có thể thất bại; không đồng nghĩa đã upload thành công. Bảng reservation phân biệt các bước này.

## Ước lượng chính xác

| Thuật toán, cùng có quyền chờ | Delivered DVR % | J/ảnh delivered đúng hạn | Mean delivery s | Mean delivery P95 s | Restricted UAV time s |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 36.937 | 1986.842 | 23.164 | 36.803 | 415.228 |
| ALL_UAV__EDF | 40.919 | 2084.446 | 22.704 | 38.124 | 418.684 |
| ALL_UAV__FIFO | 40.951 | 2085.959 | 22.705 | 38.056 | 418.685 |
| ALL_UAV__SPT | 40.945 | 2085.573 | 22.719 | 38.152 | 418.689 |
| DEADLINE_ENERGY__EDF | 36.688 | 1977.138 | 23.098 | 36.748 | 415.231 |
| DEADLINE_ENERGY__RISK_EDF | 36.688 | 1971.153 | 23.101 | 36.748 | 415.490 |
| DELIVERY_AWARE__EDF | 36.411 | 1966.256 | 23.098 | 37.004 | 415.340 |
| DELIVERY_AWARE__RISK_EDF | 36.399 | 1959.768 | 23.099 | 37.004 | 415.597 |
| SHORTEST_FINISH__EDF | 36.466 | 1968.184 | 22.342 | 35.743 | 414.723 |

| Thuật toán | Compute DVR % | J/ảnh compute đúng hạn | Mean compute s | Mean compute P95 s | Background DVR % |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 7.000 | 1342.215 | 23.261 | 36.781 | 13.989 |
| ALL_UAV__EDF | 14.542 | 1435.249 | 22.886 | 37.049 | 12.786 |
| ALL_UAV__FIFO | 14.574 | 1435.955 | 22.885 | 37.077 | 12.655 |
| ALL_UAV__SPT | 14.568 | 1435.756 | 22.896 | 37.109 | 12.409 |
| DEADLINE_ENERGY__EDF | 6.752 | 1337.790 | 23.218 | 36.767 | 13.989 |
| DEADLINE_ENERGY__RISK_EDF | 6.752 | 1333.741 | 23.220 | 36.767 | 12.793 |
| DELIVERY_AWARE__EDF | 6.737 | 1337.136 | 23.211 | 36.885 | 13.958 |
| DELIVERY_AWARE__RISK_EDF | 6.737 | 1333.096 | 23.212 | 36.885 | 12.763 |
| SHORTEST_FINISH__EDF | 6.722 | 1336.693 | 22.718 | 36.371 | 14.127 |

| Thuật toán | Reservations/ep | Đã upload/ep | Reserved delivered đúng hạn/ep | Tổng wait thực s/ep | Offload commits/ep |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| ALL_UAV__EDF | 3.521 | 3.442 | 1.062 | 64.897 | 6.329 |
| ALL_UAV__FIFO | 3.521 | 3.442 | 1.042 | 64.897 | 6.329 |
| ALL_UAV__SPT | 3.521 | 3.442 | 1.046 | 64.897 | 6.329 |
| DEADLINE_ENERGY__EDF | 0.037 | 0.037 | 0.025 | 0.438 | 0.167 |
| DEADLINE_ENERGY__RISK_EDF | 0.025 | 0.025 | 0.025 | 0.223 | 0.138 |
| DELIVERY_AWARE__EDF | 0.079 | 0.079 | 0.058 | 0.828 | 0.325 |
| DELIVERY_AWARE__RISK_EDF | 0.062 | 0.062 | 0.062 | 0.630 | 0.304 |
| SHORTEST_FINISH__EDF | 0.662 | 0.662 | 0.642 | 6.295 | 1.979 |

### Ablation capability: cùng policy trước/sau bật chờ

Bảng này thay capability cho toàn môi trường; không coi nó là so candidate với baseline bị tước quyền chờ.

| Policy | Delivered DVR không chờ % | Có chờ % | J/delivered không chờ | Có chờ |
| --- | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 36.937 | 36.937 | 1986.842 | 1986.842 |
| ALL_UAV__EDF | 38.322 | 40.919 | 2005.835 | 2084.446 |
| ALL_UAV__FIFO | 38.322 | 40.951 | 2005.827 | 2085.959 |
| ALL_UAV__SPT | 38.322 | 40.945 | 2005.699 | 2085.573 |
| DEADLINE_ENERGY__EDF | 36.722 | 36.688 | 1978.786 | 1977.138 |
| DEADLINE_ENERGY__RISK_EDF | 36.722 | 36.688 | 1972.799 | 1971.153 |
| DELIVERY_AWARE__EDF | 36.516 | 36.411 | 1970.030 | 1966.256 |
| DELIVERY_AWARE__RISK_EDF | 36.509 | 36.399 | 1963.797 | 1959.768 |
| SHORTEST_FINISH__EDF | 36.554 | 36.466 | 1971.818 | 1968.184 |

| Policy | Lifetime pin30kJ s | Flight kJ | Hover kJ | Quãng đường m |
| --- | ---: | ---: | ---: | ---: |
| SHORTEST_FINISH__EDF | 229.445 | 38.874 | 12.445 | 1295.788 |
| DEADLINE_ENERGY__EDF | 230.462 | 38.934 | 12.454 | 1297.809 |
| DELIVERY_AWARE__EDF | 230.680 | 38.871 | 12.496 | 1295.715 |
| DELIVERY_AWARE__RISK_EDF | 231.194 | 38.897 | 12.503 | 1296.557 |

Pin1.6MJ: mọi case sống>=600s, chưa biết exhaustion thật. Từng layout/load/pin xem core-metrics-summary.csv.

## Sai số ước lượng ±40%

| Thuật toán, cùng có quyền chờ | Delivered DVR % | J/ảnh delivered đúng hạn | Mean delivery s | Mean delivery P95 s | Restricted UAV time s |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 36.937 | 1986.842 | 23.164 | 36.803 | 415.228 |
| ALL_UAV__EDF | 40.919 | 2084.446 | 22.704 | 38.124 | 418.684 |
| ALL_UAV__FIFO | 40.951 | 2085.959 | 22.705 | 38.056 | 418.685 |
| ALL_UAV__SPT | 40.953 | 2085.879 | 22.711 | 38.114 | 418.690 |
| DEADLINE_ENERGY__EDF | 36.801 | 1981.302 | 23.073 | 36.730 | 415.171 |
| DEADLINE_ENERGY__RISK_EDF | 36.797 | 1975.702 | 23.075 | 36.730 | 415.268 |
| DELIVERY_AWARE__EDF | 36.546 | 1971.295 | 23.081 | 37.097 | 415.257 |
| DELIVERY_AWARE__RISK_EDF | 36.531 | 1965.188 | 23.082 | 37.099 | 415.356 |
| SHORTEST_FINISH__EDF | 36.495 | 1969.532 | 22.343 | 35.785 | 414.716 |

| Thuật toán | Compute DVR % | J/ảnh compute đúng hạn | Mean compute s | Mean compute P95 s | Background DVR % |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 7.000 | 1342.215 | 23.261 | 36.781 | 13.989 |
| ALL_UAV__EDF | 14.542 | 1435.249 | 22.886 | 37.049 | 12.786 |
| ALL_UAV__FIFO | 14.574 | 1435.955 | 22.885 | 37.077 | 12.655 |
| ALL_UAV__SPT | 14.575 | 1435.900 | 22.890 | 37.052 | 12.412 |
| DEADLINE_ENERGY__EDF | 6.884 | 1339.949 | 23.203 | 36.754 | 14.024 |
| DEADLINE_ENERGY__RISK_EDF | 6.880 | 1336.222 | 23.204 | 36.754 | 12.858 |
| DELIVERY_AWARE__EDF | 6.891 | 1339.357 | 23.207 | 36.900 | 13.993 |
| DELIVERY_AWARE__RISK_EDF | 6.887 | 1335.641 | 23.208 | 36.900 | 12.827 |
| SHORTEST_FINISH__EDF | 6.752 | 1337.309 | 22.718 | 36.413 | 14.189 |

| Thuật toán | Reservations/ep | Đã upload/ep | Reserved delivered đúng hạn/ep | Tổng wait thực s/ep | Offload commits/ep |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| ALL_UAV__EDF | 3.521 | 3.442 | 1.062 | 64.897 | 6.329 |
| ALL_UAV__FIFO | 3.521 | 3.442 | 1.042 | 64.897 | 6.329 |
| ALL_UAV__SPT | 3.521 | 3.442 | 1.046 | 64.897 | 6.329 |
| DEADLINE_ENERGY__EDF | 0.125 | 0.125 | 0.087 | 1.421 | 0.275 |
| DEADLINE_ENERGY__RISK_EDF | 0.092 | 0.092 | 0.079 | 1.015 | 0.242 |
| DELIVERY_AWARE__EDF | 0.183 | 0.183 | 0.129 | 1.895 | 0.433 |
| DELIVERY_AWARE__RISK_EDF | 0.146 | 0.146 | 0.125 | 1.506 | 0.400 |
| SHORTEST_FINISH__EDF | 0.637 | 0.637 | 0.613 | 6.316 | 1.954 |

### Ablation capability: cùng policy trước/sau bật chờ

Bảng này thay capability cho toàn môi trường; không coi nó là so candidate với baseline bị tước quyền chờ.

| Policy | Delivered DVR không chờ % | Có chờ % | J/delivered không chờ | Có chờ |
| --- | ---: | ---: | ---: | ---: |
| ALL_LOCAL__FIFO | 36.937 | 36.937 | 1986.842 | 1986.842 |
| ALL_UAV__EDF | 38.322 | 40.919 | 2005.835 | 2084.446 |
| ALL_UAV__FIFO | 38.322 | 40.951 | 2005.827 | 2085.959 |
| ALL_UAV__SPT | 38.329 | 40.953 | 2005.981 | 2085.879 |
| DEADLINE_ENERGY__EDF | 36.801 | 36.801 | 1981.015 | 1981.302 |
| DEADLINE_ENERGY__RISK_EDF | 36.807 | 36.797 | 1976.001 | 1975.702 |
| DELIVERY_AWARE__EDF | 36.621 | 36.546 | 1973.791 | 1971.295 |
| DELIVERY_AWARE__RISK_EDF | 36.621 | 36.531 | 1968.523 | 1965.188 |
| SHORTEST_FINISH__EDF | 36.579 | 36.495 | 1972.892 | 1969.532 |

| Policy | Lifetime pin30kJ s | Flight kJ | Hover kJ | Quãng đường m |
| --- | ---: | ---: | ---: | ---: |
| SHORTEST_FINISH__EDF | 229.431 | 38.878 | 12.442 | 1295.937 |
| DEADLINE_ENERGY__EDF | 230.342 | 38.936 | 12.448 | 1297.857 |
| DELIVERY_AWARE__EDF | 230.515 | 38.886 | 12.482 | 1296.189 |
| DELIVERY_AWARE__RISK_EDF | 230.713 | 38.892 | 12.486 | 1296.387 |

Pin1.6MJ: mọi case sống>=600s, chưa biết exhaustion thật. Từng layout/load/pin xem core-metrics-summary.csv.

## Verification

COMPLETE manifests, PASS audit4320episode/283968task outcomes, exit0 + completion marker. 129Java tests;4metric tests; mỗi error8mobile+3risk+5delivery+5contact-wait adversarial tests PASS.
No-wait compatibility432episode trên code mới: task, energy, decisions, visits, positions, coverage, updates, views và metric khớp mọi cột cũ với bản trước trong tolerance. Đây là regression3seed/error, không phải chạy mới30seed no-wait.
Parity local/server432episode mới PASS (abs1e-6/rel1e-9; không so wall-time); workload hashes trùng. Raw actual workloads240case khớp giữa2mức error khi bỏ estimated_mi. Metadata xác nhận run trước/sau chờ chỉ đổi capability, geometry/CPU/power/workload giữ nguyên. Mọi source snapshot trong2run mới khớp nhau. SHA256 của12file tải về khớp.

Remote: aiotlab_92:/mnt/disk1/nghialt2/MECSim-UAV-DRL/target/contact-wait-20261029-v1-{e0,e40}; control target/contact-wait-control-20261029-v1. Raw traces/source snapshots ở server; local target/contact-wait-server-results-20261029 có bảng/metadata/log/receipt.

## Giới hạn

Chỉ biết leg hiện tại, không dự báo các stop tương lai chưa chọn. Forecast pin/deadline dựa trên estimated work, admitted queues, observed source CPU load và phần bay đã biết; future arrivals/noise có thể làm task thất bại. Chưa có chờ kết quả local để relay, migration, multi-UAV hoặc backhaul TX/RX. Trung bình mô tả, chưa kiểm định significance; không khẳng định tái hiện paper hoặc hiệu quả thực địa.
