# Scenario registry: `scenarios.json`

`scenarios.json` ở thư mục gốc project là **nơi duy nhất** định nghĩa scenario,
workload, quy ước seed và các bộ thực nghiệm (suite). Java đọc qua
`uav.ScenarioRegistry`, Python đọc qua `drl/registry.py`. Muốn thêm hoặc đổi thực
nghiệm thì sửa file này, không hard-code danh sách trong runner hay script.

Phạm vi hiện tại: **nhánh paper/lifetime** (`PaperSimulation`, `PaperBaselines`,
`PaperDatasetEvaluation`, `PaperGymBridge`, `drl.run`, `drl.experiments`). Phân biệt với:

- `scenario_mode`/`shift_seed` (`PaperScenario.java`, `drl/scenarios.py`): can thiệp lên
  layout (position, outage…) của một scenario, không phải danh sách scenario ở đây.
- Các file `*-protocol.json` của nhánh offloading/scheduling/mobile: chưa chuyển vào registry.

Mỗi lần chạy đều chép `scenarios.json` vào thư mục kết quả (`target/uav-*`,
`source/` của run DRL) để đọc lại đúng cấu hình đã dùng.

## Các phần của file

| Khóa | Ý nghĩa |
| --- | --- |
| `scenarios` | Mức sẵn sàng: `powered`/`connected` = **số thiết bị còn** nguồn/liên lạc (0–12). Id dạng `p{P}c{C}`. |
| `workloads` | `synthetic` (mô hình paper), `rescuenet` (ảnh, CPU hữu hạn, không tải nền), `mixed` (ảnh + Alibaba). `fixed` là giá trị định danh workload, không bị override. |
| `workload_aliases` | Tên cũ còn chấp nhận: `datasets` = `mixed`. Suite phải dùng id chuẩn. |
| `dataset_defaults` | Đường dẫn raw data và các giả định MIPS/W/MI dùng chung cho mọi workload dataset. |
| `seed_protocol` | Java: layout = seed, task = seed+1, policy = seed+2. DRL: train task seed `[0,1e6)`, validation từ `1e6`, test từ `2e6`. |
| `defaults` | Mặc định khi chạy một episode/một model: `p8c8`, `synthetic`, seed 42, layout 42, `OLDEST_DATA`, 200 slot. |
| `suites` | Bộ thực nghiệm. `runner: java` chạy bằng `PaperBaselines`/`PaperDatasetEvaluation`; `runner: drl` chạy bằng `python -m drl.experiments`. |

Thứ tự ưu tiên khi resolve thuộc tính dataset (Java và Python giống nhau):
`dataset_defaults` < `-Dkey=value` hoặc `--property key=value` < `fixed` của workload.
Java in cảnh báo khi một `-D` bị `fixed` che; Python báo lỗi.

Với cùng một seed, `PaperSimulation.layout` cho vị trí/phần cứng/pin giống nhau ở
mọi scenario, và tập thiết bị còn nguồn/liên lạc lồng nhau giữa các mức. Nhờ vậy
các ô của lưới so sánh được theo cặp. Không đổi thứ tự RNG trong `layout()`.

## Suite hiện có

| Suite | Runner | Nội dung |
| --- | --- | --- |
| `heuristic_baselines` | java (`uav.PaperBaselines`) | 12/12, 6/6, 8/8, 10/8 × 3 heuristic × 30 seed, synthetic |
| `dataset_evaluation` | java (`uav.PaperDatasetEvaluation`) | 8/8 × synthetic/rescuenet/mixed × 3 heuristic × 30 seed |
| `table5` | drl | Lưới 5×5 power/comms, DQN, reward `paper`, 3 seed |
| `table6` | drl | 6/6, 8/8, 10/8 × DQN/PPO/A2C × 11 reward, 3 seed |

Giới hạn hiện tại của runner (kiểm tra khi chạy, báo lỗi rõ ràng):

- `PaperBaselines` chỉ chạy suite synthetic.
- `PaperDatasetEvaluation` chỉ chạy **một** scenario mỗi lần (trace chưa có tầng scenario).
- `drl.experiments` dùng một workload cho cả suite (`--workload` để chọn).

## Cách chạy

```powershell
# Java: suite mặc định của runner, hoặc chọn suite/scenario khác
mvn -o compile exec:java "-Dexec.mainClass=uav.PaperBaselines" "-Dexec.classpathScope=compile"
mvn -o compile exec:java "-Dexec.mainClass=uav.PaperDatasetEvaluation" "-Dexec.classpathScope=compile" "-Dpaper.scenario=p6c6"
mvn -o compile exec:java "-Dexec.mainClass=uav.PaperSimulation" "-Dexec.classpathScope=compile" "-Dpaper.scenario=p10c8" "-Dpaper.workload=rescuenet"

# Python
python -m drl.run train --scenario p6c6 --workload mixed --steps 10000
python -m drl.experiments --suite table6 --output target/table6 --plan-only
```

Các cờ Java:

- `-Dpaper.suite`, `-Dpaper.seeds`, `-Dpaper.firstSeed`, `-Dpaper.maxSlots` override giá trị suite/defaults.
- `-Dpaper.scenario=<id>` thay danh sách scenario của suite bằng một scenario.
- `-Dpaper.powered`/`-Dpaper.connected` override số lượng; với suite nhiều scenario phải đặt cả hai.
- `-Dpaper.registry=<path>` dùng file registry khác.

Phía Python, `--scenario` chọn mức sẵn sàng; `--powered`/`--connected` override
số lượng. `drl.experiments` vẫn truyền số lượng cụ thể cho từng run như trước.

## Thêm scenario hoặc suite

1. Thêm entry vào `scenarios` hoặc `suites`. Không cần sửa code nếu runner đã hỗ trợ dạng suite đó.
2. Chạy `mvn test` và `python -m unittest drl.test_drl`. Cả hai bên đều validate
   file: id không tồn tại, field gõ sai, giá trị ngoài 0–12 đều làm test fail.
3. Một workload chỉ được `fixed` các khóa cấu hình CPU/tải nền
   (`ScenarioRegistry.CONFIG_KEYS`), không được pin đường dẫn hay giới hạn pool.
