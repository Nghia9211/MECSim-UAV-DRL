"""Aggregate completed diagnostics without pooling repeated baselines as new samples."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import statistics as stat

import numpy as np


def read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def distribution(values):
    a = np.asarray(list(values), dtype=float)
    return dict(n=len(a), mean=float(a.mean()), median=float(np.median(a)),
                p95=float(np.percentile(a, 95)), min=float(a.min()), max=float(a.max()))


def analyze(root):
    for stage in ["evaluate", "runtime", "permutation", "sensitivity"]:
        assert json.loads((root/stage/"complete.json").read_text())["status"] == "COMPLETE", stage
    data = read(root/"evaluate/episodes.csv")
    parity = read(root/"evaluate/original_parity.csv")
    result = {"parity": dict(n=len(parity), all_match=all(r["slots_match"] == "True"
        and r["reason_match"] == "True" and abs(float(r["seconds_delta"])) < 1e-6 for r in parity))}
    unseen = [r for r in data if r["mode"] == "unseen"]
    dn = [r for r in unseen if r["policy"] == "DQN"]
    old = [r for r in unseen if r["policy"] == "OLDEST_DATA" and r["learning_seed"] == "0"]
    result["unseen_dqn"] = dict(episodes=len(dn), layouts=len({r["layout_seed"] for r in dn}),
        learning_seeds=len({r["learning_seed"] for r in dn}),
        age_failures=sum("DATA_AGE" in r["reason"] for r in dn),
        battery_failures=sum("BATTERY" in r["reason"] for r in dn),
        cap_slots=sum(int(r["cap_slots"]) for r in dn), total_slots=sum(int(r["slots"]) for r in dn))
    deltas = []
    for r in old:
        mean = stat.mean(int(d["slots"]) for d in dn if d["layout_seed"] == r["layout_seed"])
        deltas.append(mean - int(r["slots"]))
    # Conditional on these five trained policies. Resample layout/task pairs, NOT 150 episodes.
    boots = np.random.default_rng(123).choice(deltas, size=(10000, len(deltas))).mean(axis=1)
    result["paired_layout_difference"] = dict(mean_dqn_minus_oldest=stat.mean(deltas),
        percentile95=np.percentile(boots, [2.5, 97.5]).tolist(),
        wins=sum(d>0 for d in deltas), ties=sum(d==0 for d in deltas), losses=sum(d<0 for d in deltas),
        interpretation="Exploratory paired bootstrap of 30 layout/task pairs, conditional on five fixed checkpoints; not uncertainty over retraining or an untouched final test.")
    fatal = Counter()
    case_ids = sorted({2000000, 2000001, int(max(old, key=lambda r:int(r["slots"]))["layout_seed"])})
    cases = []
    for r in dn:
        trace = Path(r["trace"])
        ds, tasks = read(trace/"devices.csv"), read(trace/"dataset-tasks.csv")
        cpu = read(trace/"cpu-tasks.csv")
        slot_end = {s["slot"]:float(s["end_s"]) for s in read(trace/"slots.csv")}
        for device in re.findall(r"DEVICE_(\d+)_DATA_AGE", r["reason"]):
            history = [d for d in ds if d["device"] == device]
            images = [d for d in tasks if d["device"] == device]
            assert len(history) == 10 and not any(t["delivered"] == "true" for t in images)
            key = "never_in_coverage" if not any(d["offload_candidate"] == "true" for d in history) else "in_coverage_but_not_delivered"
            fatal[key] += 1
            fatal["connected" if history[0]["connected"] == "true" else "disconnected"] += 1
            for job in cpu:
                if job["source"] == "RESCUENET" and job["device"] == device:
                    fatal["candidate_slot_upload_exceeds_slot" if float(job["ready_s"]) > slot_end[job["slot"]]+1e-6
                          else "candidate_slot_cpu_incomplete"] += 1
            if int(r["learning_seed"]) == 0 and int(r["layout_seed"]) in case_ids:
                cases.append(dict(layout=int(r["layout_seed"]), fatal_device=int(device), category=key,
                    connected=history[0]["connected"], min_local_required_s=min(float(t["local_required_s"]) for t in images)))
    result["fatal_device_instances"] = dict(fatal)
    result["case_failures_seed0"] = cases
    result["case_policies_seed0"] = [{k:r[k] for k in ["policy", "layout_seed", "slots", "seconds", "reason", "actions", "cap_slots", "capped_work_items"]}
        for r in unseen if r["learning_seed"] == "0" and r["policy"] in ["DQN", "OLDEST_DATA"] and int(r["layout_seed"]) in case_ids]
    perm = read(root/"permutation/episodes.csv")
    result["permutation"] = []
    for layout in [42, 2000000, 2000001]:
        rows = [r for r in perm if int(r["layout_seed"]) == layout and r["permutation"] != "identity"]
        result["permutation"].append(dict(layout=layout, trials=len(rows),
            mean_slots=stat.mean(int(r["slots"]) for r in rows),
            mean_delta=stat.mean(int(r["delta_slots"]) for r in rows),
            min_slots=min(int(r["slots"]) for r in rows), max_slots=max(int(r["slots"]) for r in rows),
            changed_actions=sum(r["same_actions"] == "False" for r in rows)))
    calls, steps, episodes = [read(root/"runtime"/name) for name in ["calls.csv", "step_times.csv", "episode_times.csv"]]
    result["runtime"] = {}
    for policy in ["DQN", "ROUND_ROBIN", "OLDEST_DATA", "RANDOM"]:
        result["runtime"][policy] = dict(
            inference_us=distribution(float(r["ns"])/1000 for r in calls if r["policy"] == policy),
            bridge_step_ms=distribution(float(r["bridge_step_ns"])/1e6 for r in steps if r["policy"] == policy),
            java_handlers_ms=distribution(float(r["java_handlers_ns"])/1e6 for r in steps if r["policy"] == policy),
            episode_with_reset_ms=distribution(float(r["episode_with_reset_ms"]) for r in episodes if r["policy"] == policy))
    sens = read(root/"sensitivity/episodes.csv")
    result["sensitivity"] = []
    for setting in dict.fromkeys(r["setting"] for r in sens):
        for layout in [42, 2000000, 2000001]:
            for policy in ["DQN", "OLDEST_DATA"]:
                group=[r for r in sens if r["setting"] == setting and int(r["layout_seed"]) == layout and r["policy"] == policy]
                result["sensitivity"].append(dict(setting=setting, layout=layout, policy=policy,
                    mean_slots=stat.mean(int(r["slots"]) for r in group),
                    mean_seconds=stat.mean(float(r["seconds"]) for r in group),
                    delivery_fraction=sum(int(r["images_delivered"]) for r in group)/sum(int(r["images_submitted"]) for r in group),
                    mean_compute_j=stat.mean(float(r["uav_compute_j"]) for r in group),
                    capped_slots=sum(int(r["cap_slots"]) for r in group), slots=sum(int(r["slots"]) for r in group)))
    result["pilot_status"] = "COMPLETE" if (root/"pilot/complete.json").exists() else "PENDING"
    result["pilot"] = read(root/"pilot/summary.csv") if result["pilot_status"] == "COMPLETE" else []
    (root/"analysis.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ["pilot","sensitivity"]},indent=2))


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path)
    analyze(p.parse_args().output)
