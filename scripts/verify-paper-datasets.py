"""Independent trace/aggregation checks for PaperDatasetEvaluation (Python stdlib only)."""
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

root = Path(sys.argv[1])

def read(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))

episodes = read(root / "episodes.csv")
groups = defaultdict(list)
paired = defaultdict(list)
for e in episodes:
    directory = root / e["trace_directory"]
    slots = read(directory / "slots.csv")
    devices = read(directory / "devices.csv")
    assert len(slots) == int(e["slots"]) and len(devices) == len(slots) * 12
    assert slots[-1]["reason"] == e["reason"]
    assert slots[-1]["terminated"] == "true" or slots[-1]["truncated"] == "true"
    assert abs(float(slots[-1]["end_s"]) - float(e["seconds"])) < 1e-6
    for s in slots:
        assert 0 <= float(s["duration_s"]) <= 600.000001
        assert float(s["uav_battery_j"]) >= 0 and math.isfinite(float(s["reward"]))
    assert all(float(d["battery_j"]) >= 0 for d in devices)
    groups[e["mode"], e["policy"]].append(e)
    paired[e["seed"]].append((e, directory))
    if e["mode"] == "synthetic":
        continue
    tasks = read(directory / "dataset-tasks.csv")
    cpu = read(directory / "cpu-tasks.csv")
    pool = read(directory / "rescuenet-pool.csv")
    assert len(tasks) == int(e["images_submitted"]) == len(slots) * 12
    assert sum(t["delivered"] == "true" for t in tasks) == int(e["images_delivered"])
    assert len(cpu) == int(e["cpu_submitted"])
    assert sum(t["status"] == "COMPLETED" for t in cpu) == int(e["cpu_completed"])
    config = (directory / "dataset-config.txt").read_text(encoding="utf-8").splitlines()[0]
    import re
    mips = float(re.search(r"uavMips=([^,\]]+)", config)[1])
    watts = float(re.search(r"cpuPowerW=([^,\]]+)", config)[1])
    expected_j = sum(float(t["executed_mi"]) / mips * watts for t in cpu)
    assert abs(expected_j - float(e["uav_compute_j"])) < 1e-4
    last_finish = {}
    for t in cpu:
        slot = int(t["slot"])
        begin, finish, ready = (float(t[k]) for k in ("planned_start_s", "planned_finish_s", "ready_s"))
        assert begin + 1e-7 >= ready and begin + 1e-7 >= last_finish.get(slot, 0)
        last_finish[slot] = finish
        actual_end = float(slots[slot-1]["end_s"])
        executed = min(float(t["requested_mi"]), max(0, min(actual_end, finish)-begin)*mips)
        assert abs(executed-float(t["executed_mi"])) < 1e-4
        assert 0 <= float(t["executed_mi"]) <= float(t["requested_mi"]) + 1e-6
        if t["status"] == "COMPLETED":
            assert finish <= actual_end + 1e-7
    for t in tasks:
        assert int(t["input_bytes"]) == int(pool[int(t["image_index"])]["bytes"])
        if t["delivered"] == "true":
            assert 0 <= float(t["latency_s"]) <= float(slots[int(t["slot"])-1]["duration_s"]) + 1e-6
    if e["mode"] == "rescuenet":
        assert not any(t["source"] == "ALIBABA" for t in cpu)
    else:
        assert any(t["source"] == "ALIBABA" for t in cpu)

for seed, group in paired.items():
    assert len(group) == 9
    assert len({(p / "layout.csv").read_bytes() for _, p in group}) == 1
    task_sets = [read(p / "dataset-tasks.csv") for e, p in group if e["mode"] != "synthetic"]
    common = min(map(len, task_sets))
    assert len({tuple((r["image_index"], r["input_bytes"], r["uav_compute_mi"]) for r in tasks[:common]) for tasks in task_sets}) == 1

for s in read(root / "summary.csv"):
    group = groups[s["mode"], s["policy"]]
    assert len(group) == int(s["n"])
    for target, source, fn in (("mean_slots", "slots", statistics.mean), ("sd_slots", "slots", statistics.stdev),
                                ("mean_seconds", "seconds", statistics.mean), ("mean_compute_j", "uav_compute_j", statistics.mean)):
        assert abs(float(s[target]) - fn(float(e[source]) for e in group)) < 1e-6
    count = sum(int(e["images_submitted"]) for e in group)
    if count:
        assert abs(float(s["pooled_delivery_fraction"])-sum(int(e["images_delivered"]) for e in group)/count) < 1e-8

message = f"Verified {len(episodes)} episodes, {len(paired)} paired seeds: source mapping, queue timing, work/energy conservation, delivery counts, slot limits, summaries."
print(message)
(root / "verification.txt").write_text(message + "\n", encoding="utf-8")
