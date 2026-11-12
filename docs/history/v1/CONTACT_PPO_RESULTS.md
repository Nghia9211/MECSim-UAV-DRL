# Contact-aware PPO: kết quả

Run target/contact-ppo-20261030-v1, source22cf0bf. Exit0 + completion markers; COMPLETE/PASS2560 episodes, source unchanged, checkpoint actions replayed.
Full campaign elapsed1258,48s (~20m58s), chưa bao gồm preflight/smoke.3 learning seed x32768 steps.16 policies x160paired cases.
Đã kiểm tra SHA256 của7 file tải về và tái tính summary từ2560episode rows. Raw trace audit chạy trên server, không rerun local vì không tải toàn bộ raw traces.

## Metric chính

RL là trung bình chỉ số của3 learner; best chọn bằng validation, final tách riêng. J/ảnh là ratio-of-sums trong từng learner rồi lấy trung bình các learner, không phải coi480case trùng workload là independent samples.
Các ratio DVR/latency là macro-average trên16scenarios x10 task seeds. P95 là trung bình P95 từng episode, không phải pooled percentile.

| Method | Compute DVR % | Delivered DVR % | J/compute on-time image | J/delivered on-time image | Completed mean/P95 s | Restricted UAV time s |
|---|---:|---:|---:|---:|---:|---:|
|RR + DA/RISK_EDF|6.115|37.092|1293.48|1930.49|23.059/35.621|415.949|
|PPO cũ/RR|6.115|37.092|1296.21|1934.56|23.064/35.642|415.842|
|DISCONNECTED_RR|6.086|32.326|1258.29|1743.38|22.688/36.411|419.626|
|CONTACT_GREEDY|5.763|30.311|1064.83|1438.27|22.178/35.621|449.015|
|Contact PPO best|6.330|32.439|1090.24|1509.39|22.516/35.716|441.029|
|Contact PPO final|5.791|31.697|1068.07|1472.67|22.347/35.567|448.228|

Mỗi policy có80/160case sống tới horizon600s: đây là right censoring, lifetime thật chỉ biết>=600. Không gọi restricted mean là tuổi thọ thực không giới hạn.
Pin30kJ thì các case hết pin có quan sát; bảng dưới tránh trộn horizon survivors với exhaustion.

| Method | Observed lifetime,30kJ s | Background DVR % | Mean total J | Mean UAV J | Delivered latency mean/P95 s |
|---|---:|---:|---:|---:|---:|
|RR + DA/RISK_EDF|231.898|17.626|58554.28|52086.45|23.096/38.175|
|PPO cũ/RR|231.683|18.014|58677.65|52209.83|23.103/38.196|
|DISCONNECTED_RR|239.253|15.720|57008.51|50684.80|22.630/37.645|
|CONTACT_GREEDY|298.030|3.621|48469.56|42202.20|21.956/35.830|
|Contact PPO best|282.057|8.727|49221.49|42890.41|22.311/36.664|
|Contact PPO final|296.455|4.950|48584.78|42277.08|22.060/35.876|

## Mỗi learner và checkpoint

| Policy | Delivered DVR % | J/delivered | Completed mean/P95 s | Restricted UAV s |
|---|---:|---:|---:|---:|
|CONTACT_PPO_s0_best|33.205|1519.09|22.630/35.766|440.709|
|CONTACT_PPO_s0_final|33.205|1519.09|22.630/35.766|440.709|
|CONTACT_PPO_s1_best|33.207|1519.14|22.626/35.734|440.703|
|CONTACT_PPO_s1_final|30.862|1446.74|22.189/35.467|451.979|
|CONTACT_PPO_s2_best|30.906|1489.95|22.291/35.648|441.674|
|CONTACT_PPO_s2_final|31.025|1452.19|22.221/35.467|451.995|

## Kết luận

Contact-aware PPO tốt hơn RR/PPO cũ về delivered DVR và J/delivered; compute DVR best hơi xấu hơn RR. Không kết luận tốt hơn mọi metric.
CONTACT_GREEDY tốt hơn trung bình PPO-best/final về DVR, J/ảnh, mean latency và restricted lifetime trong setting này. PPO-final có completed P95 thấp hơn nhẹ (35,567s so với35,621s), nên không gọi là Greedy vượt mọi metric. PPO có một số scenario/seed tốt hơn Greedy, nhưng chưa thắng tổng thể.
Không lấy final tốt hơn trên test để thay best hậu nghiệm. Validation hiện chỉ1task seed/scenario có thể thiếu đại diện; đây là giả thuyết cần thử độc lập, không phải nguyên nhân đã chứng minh.
Như vậy chọn điểm phục vụ contact-aware có ích thực nghiệm; chưa có bằng chứng cần RL thay heuristic đơn giản. Nếu cần bản dùng được ngay trong setting này, ưu tiên CONTACT_GREEDY làm ứng viên hiện tại.
Same layout42 scaled250/800m, cùng source pools và development-used seeds2800000..9. Không unseen-layout/source-holdout/fresh-test hoặc statistical-significance claim.

## Per-scenario

| Scenario | RR delivered DVR % | Contact PPO-best mean DVR % | Greedy DVR % |
|---|---:|---:|---:|
|a250-light-b1600000-e0|32.221|29.629|27.837|
|a250-light-b1600000-e40|32.748|29.629|27.837|
|a250-light-b30000-e0|35.465|29.629|27.837|
|a250-light-b30000-e40|35.991|29.629|27.837|
|a250-overload-b1600000-e0|37.128|32.234|30.396|
|a250-overload-b1600000-e40|37.384|32.479|30.396|
|a250-overload-b30000-e0|38.723|32.552|30.693|
|a250-overload-b30000-e40|39.132|32.797|30.693|
|a800-light-b1600000-e0|36.616|31.086|28.830|
|a800-light-b1600000-e40|36.616|31.086|29.187|
|a800-light-b30000-e0|36.616|32.954|28.830|
|a800-light-b30000-e40|36.616|32.954|29.604|
|a800-overload-b1600000-e0|39.355|34.577|33.176|
|a800-overload-b1600000-e40|39.355|34.577|33.435|
|a800-overload-b30000-e0|39.750|36.608|34.151|
|a800-overload-b30000-e40|39.750|36.608|34.232|
