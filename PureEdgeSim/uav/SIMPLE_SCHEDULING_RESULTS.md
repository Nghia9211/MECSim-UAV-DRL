# Kết quả thử scheduling đơn giản

Source5088e3a; server control target/simple-scheduling-control-20261030-v1. Exit0 và marker SIMPLE_SCHEDULING_COMPLETE_AND_VERIFIED.
6.240 episodes,3120/error; independent audits PASS ở cả0% và40%. Hai summary CSV đã đối chiếu SHA256 server/local.
Development seeds95000..95029;8scenarios/error; cùng13policies và workload hashes. Không fresh holdout.

| Error | Offloading / Scheduler | Delivered DVR % ↓ | J/on-time delivered ↓ | Completed mean s | Completed P95 s | UAV restricted s | Censored/cases |
|---|---|---:|---:|---:|---:|---:|---:|
|e0|DELIVERY_AWARE / EDF|36.4110|1966.2564|23.2112|36.8848|415.3400|120/240|
|e0|DELIVERY_AWARE / RISK_EDF|36.3995|1959.7677|23.2118|36.8848|415.5969|120/240|
|e0|DELIVERY_AWARE / RISK_SPT|36.4127|1960.2447|23.2116|36.8848|415.5969|120/240|
|e0|DELIVERY_AWARE / FEASIBLE_AGING|36.4243|1966.6656|23.2104|36.8848|415.3400|120/240|
|e40|DELIVERY_AWARE / EDF|36.5464|1971.2953|23.2075|36.8997|415.2573|120/240|
|e40|DELIVERY_AWARE / RISK_EDF|36.5305|1965.1878|23.2085|36.8997|415.3563|120/240|
|e40|DELIVERY_AWARE / RISK_SPT|36.5305|1965.1403|23.2076|36.8997|415.3563|120/240|
|e40|DELIVERY_AWARE / FEASIBLE_AGING|36.5597|1971.6943|23.2069|36.8997|415.2620|120/240|

Delivered DVR là kết quả thực sự được nhận đúng hạn; compute DVR khác và vẫn có trong CSV đầy đủ.
P95 là trung bình P95 từng case, không phải percentile pooled. UAV survivors600s là right-censored, không phải đã hết pin.
ALL gộp compact/wide,light/overload,low/high battery; xem per-scenario CSV trước khi kết luận.

RISK_SPT không cải thiện delivered DVR so với RISK_EDF; ở error0 còn kém nhẹ. Error40 energy thấp hơn chỉ khoảng0,048J/ảnh (~0,0024%), chưa phải lợi ích thực tế đáng kể.
FEASIBLE_AGING kém hơn về delivered DVR và J/ảnh ở cảhai error. Không có bằng chứng từ đợt này để thay RISK_EDF bằng hai scheduler vừa thử.
Không có significance test hay claim tối ưu; test này chỉ loại bớt hướng ít hứa hẹn trong setting hiện tại.

Chẩn đoán riêng trên baseline joint-RL-v2 (160case, không phải6240episode này):101/7840ảnh offload(1,29%),251/2234CPU dispatch có>=2ready jobs(11,24%),compute khoảng1,28% UAV energy.
Đây là cơ sở thử contact-aware RL điều khiển destination thay vì chỉ chọn scheduler trong RR cố định; không là oracle feature.
Kế hoạch tiếp theo: CONTACT_PPO_PLAN.md. Artifacts đầy đủ trên server; local chỉ tải summary/metadata, không đủ tự rerun toàn bộ trace audit.
