"""Independent stdlib verifier: source mapping, causal dispatch, work/energy, DVR and pairing."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from collections import defaultdict


def read(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def close(actual, expected, tolerance=1e-6):
    assert math.isclose(float(actual), expected, rel_tol=1e-9, abs_tol=tolerance), (actual, expected)


def finite_mean(values):
    values = [v for v in values if math.isfinite(v)]
    return statistics.mean(values) if values else math.nan


def optional(actual, expected):
    assert (actual == "") == (not math.isfinite(expected)), (actual, expected)
    if actual:
        close(actual, expected)


def dispatch_id(candidates, policy, options, now, battery, params):
    """Independent reconstruction of selection rules; never calls Java policy code."""
    def fifo(t):
        return (float(t["ready_s"]), float(t["arrival_s"]), int(t["id"]))
    def seconds(t):
        return float(t["compute_mi"]) / params["mips"]
    if policy in ("FIFO", "EDF", "PRIORITY", "SPT"):
        def order(t):
            return ((float(t["deadline_s"]),) if policy == "EDF" else
                    (-int(t["priority"]),) if policy == "PRIORITY" else
                    (float(t["compute_mi"]),) if policy == "SPT" else ()) + fifo(t)
        return int(min(candidates, key=order)["id"])
    assert options and set(options) == {"aging_fraction", "aging", "energy_guard", "deadline_guard"}
    eligible = [t for t in candidates if now + seconds(t) <= params["horizon_s"] + 1e-8
                and (not options["deadline_guard"] or now + seconds(t) <= float(t["deadline_s"]) + 1e-8)
                and (not options["energy_guard"] or seconds(t) * (params["cpu_w"] + params["hover_w"]) <= battery + 1e-8)]
    if not eligible:
        chosen = min(candidates, key=lambda t: (seconds(t),) + fifo(t))
    else:
        aged = [t for t in eligible if options["aging"] and now - float(t["ready_s"])
                >= options["aging_fraction"] * (float(t["deadline_s"]) - float(t["ready_s"]))]
        if aged:
            chosen = min(aged, key=lambda t: (float(t["deadline_s"]),) + fifo(t))
        else:
            def order(t):
                slack = max(0, float(t["deadline_s"]) - now - seconds(t)) / max(1e-9, float(t["deadline_s"]) - float(t["ready_s"]))
                score = max(1, int(t["priority"])) / (max(1e-9, seconds(t)) * (1 + slack))
                return (-score,) + fifo(t)
            chosen = min(eligible, key=order)
    return int(chosen["id"])


def verify(root):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] in ("uav-cpu-scheduling-v1", "uav-cpu-scheduling-v2") and manifest["status"] == "COMPLETE"
    base_params, cost = manifest["parameters"], manifest["cost_model"]
    pools = root if manifest["schema"] == "uav-cpu-scheduling-v1" else root.parent
    images = {int(r["index"]): r for r in read(pools / "source-pools/rescuenet-pool.csv")}
    background = {int(r["source_line"]): r for r in read(pools / "source-pools/alibaba-pool.csv")}
    scenarios = {s["name"]: s for s in manifest["scenarios"]}
    rows = read(root / "episodes.csv")
    groups = defaultdict(list)
    for row in rows:
        groups[row["scenario"], row["seed"], row["policy"]].append(row)
    expected_cases = len(manifest["scenarios"]) * manifest["seeds"]
    assert len(groups) == expected_cases * len(manifest["policies"]) == manifest["episodes"]
    cases = defaultdict(list)
    due = defaultdict(list)
    verified_tasks = 0
    for (scenario, seed, policy), metrics in groups.items():
        assert scenario in scenarios and manifest["first_seed"] <= int(seed) < manifest["first_seed"] + manifest["seeds"]
        params = {**base_params, "battery_j": scenarios[scenario].get("battery_j", base_params["battery_j"])}
        assert len(metrics) == 3
        assert {r["source"] for r in metrics} == {"ALL", "RESCUENET", "ALIBABA"}
        trace = Path(metrics[0]["trace"])
        assert not trace.is_absolute() and ".." not in trace.parts
        workload_file = root / trace.parent / "workload.csv"
        digest = hashlib.sha256(workload_file.read_bytes()).hexdigest()
        assert all(r["workload_sha256"] == digest for r in metrics)
        cases[scenario, seed].append((policy, digest))
        workload = read(workload_file)
        tasks = {int(t["id"]): t for t in workload}
        assert len(tasks) == len(workload)
        outcomes = {int(t["id"]): t for t in read(root / trace)}
        assert set(tasks) == set(outcomes)
        for task in tasks.values():
            arrival, ready, deadline, mi = (float(task[k]) for k in ("arrival_s", "ready_s", "deadline_s", "compute_mi"))
            assert 0 <= arrival < params["arrival_window_s"] and ready >= arrival and arrival < deadline <= params["horizon_s"]
            if task["source"] == "RESCUENET":
                image = images[int(task["source_index"])]
                assert task["input_bytes"] == image["bytes"]
                close(mi, int(image["width"]) * int(image["height"]) / 1e6 * cost["image_mi_per_megapixel"])
                d = cost["slant_distance_m"]
                rate = 20_000_000 * math.log2(1 + .1 * 1e-8 * d**-4 / 1e-13)
                close(ready - arrival, int(image["bytes"]) * 8 / rate)
                assert int(task["priority"]) in (2, 3)
                close(deadline - arrival, params["critical_deadline_s"] if task["priority"] == "3" else params["image_deadline_s"])
            else:
                assert task["source"] == "ALIBABA"
                job = background[int(task["source_index"])]
                close(mi, (float(job["end_s"]) - float(job["start_s"])) * float(job["plan_cpu"]) / 100 * cost["reference_mips"] * cost["background_work_scale"])
                close(ready, arrival)
                assert task["priority"] == "1"
                close(deadline - arrival, params["background_deadline_s"])
        all_metrics = next(r for r in metrics if r["source"] == "ALL")
        stop = float(all_metrics["stop_s"])
        assert 0 <= stop <= params["horizon_s"] + 1e-7
        close(all_metrics["hover_j"], stop * params["hover_w"])
        work = sum(float(o["executed_mi"]) for o in outcomes.values())
        close(all_metrics["compute_j"], work / params["mips"] * params["cpu_w"])
        close(all_metrics["total_uav_j"], float(all_metrics["hover_j"]) + float(all_metrics["compute_j"]))
        close(float(all_metrics["total_uav_j"]) + float(all_metrics["remaining_battery_j"]), params["battery_j"])
        assert float(all_metrics["remaining_battery_j"]) >= -1e-7
        if all_metrics["reason"] == "BATTERY":
            close(all_metrics["remaining_battery_j"], 0)
        else:
            assert all_metrics["reason"] == "HORIZON"
            close(stop, params["horizon_s"])
        started = sorted((o for o in outcomes.values() if o["cpu_start_s"]), key=lambda o: float(o["cpu_start_s"]))
        already_started = set()
        previous_end = 0.
        previous_work = 0.
        for outcome in started:
            start, end = float(outcome["cpu_start_s"]), float(outcome["resolved_s"])
            ident = int(outcome["id"])
            candidates = [t for i, t in tasks.items() if i not in already_started
                          and float(t["ready_s"]) <= start + 1e-8 and float(t["deadline_s"]) > start + 1e-8]
            assert candidates and start >= previous_end - 1e-8
            # No future access, no artificial idle gap when an eligible task could run.
            feasible_starts = [max(previous_end, float(t["ready_s"])) for i, t in tasks.items()
                               if i not in already_started and max(previous_end, float(t["ready_s"])) < float(t["deadline_s"]) - 1e-8]
            close(start, min(feasible_starts))
            assert policy in manifest["policies"]
            battery = params["battery_j"] - start * params["hover_w"] - previous_work / params["mips"] * params["cpu_w"]
            assert dispatch_id(candidates, policy, manifest.get("policy_options", {}).get(policy), start, battery, params) == ident, (scenario, seed, policy, ident)
            close(float(outcome["executed_mi"]), (end - start) * params["mips"])
            already_started.add(ident)
            previous_end = end
            previous_work += float(outcome["executed_mi"])
        for ident, outcome in outcomes.items():
            task = tasks[ident]
            executed, remaining = float(outcome["executed_mi"]), float(outcome["remaining_mi"])
            assert executed >= -1e-7 and remaining >= -1e-7
            close(executed + remaining, float(task["compute_mi"]))
            status, end = outcome["status"], float(outcome["resolved_s"])
            if status.startswith("COMPLETED"):
                close(remaining, 0)
                assert bool(outcome["cpu_start_s"])
                assert (end <= float(task["deadline_s"]) + 1e-8) == (status == "COMPLETED_ON_TIME")
            elif status == "EXPIRED_WAITING":
                assert not outcome["cpu_start_s"] and executed == 0
                close(end, float(task["deadline_s"]))
            else:
                assert status in ("DROPPED_BATTERY", "UNFINISHED_HORIZON")
                close(end, stop)
        for row in metrics:
            for column in ("hover_j", "compute_j", "total_uav_j", "remaining_battery_j", "stop_s", "simulation_wall_ms", "reason", "max_queue", "trace"):
                assert row[column] == all_metrics[column]
            selected = [i for i, t in tasks.items() if row["source"] == "ALL" or t["source"] == row["source"]]
            on = sum(outcomes[i]["status"] == "COMPLETED_ON_TIME" for i in selected)
            assert int(row["offered"]) == len(selected) and int(row["on_time"]) == on
            for column, status in [("late", "COMPLETED_LATE"), ("expired", "EXPIRED_WAITING"), ("battery_dropped", "DROPPED_BATTERY"), ("unfinished", "UNFINISHED_HORIZON")]:
                assert int(row[column]) == sum(outcomes[i]["status"] == status for i in selected)
            optional(row["dvr"], (len(selected) - on) / len(selected) if selected else math.nan)
            latencies = [float(outcomes[i]["resolved_s"]) - float(tasks[i]["arrival_s"]) for i in selected if outcomes[i]["status"].startswith("COMPLETED")]
            waits = [float(outcomes[i]["cpu_start_s"]) - float(tasks[i]["ready_s"]) for i in selected if outcomes[i]["cpu_start_s"]]
            optional(row["mean_completed_latency_s"], finite_mean(latencies))
            optional(row["mean_started_wait_s"], finite_mean(waits))
            due[scenario, policy, row["source"]].append(row)
        if manifest["schema"] == "uav-cpu-scheduling-v2":
            by_source = {r["source"]: r for r in metrics}
            primary = sum(weight * float(by_source[source]["dvr"] or 0) for source, weight in manifest["primary_weights"].items())
            for row in metrics:
                close(row["primary_loss"], primary)
        verified_tasks += len(tasks)
    for case in cases.values():
        assert {p for p, h in case} == set(manifest["policies"]) and len({h for p, h in case}) == 1
    for row in read(root / "summary.csv"):
        group = due[row["scenario"], row["policy"], row["source"]]
        assert int(row["seeds"]) == len(group) == manifest["seeds"]
        offered = sum(int(r["offered"]) for r in group)
        on = sum(int(r["on_time"]) for r in group)
        assert int(row["offered_total"]) == offered and int(row["on_time_total"]) == on
        optional(row["pooled_dvr"], 1 - on / offered if offered else math.nan)
        dvr = [float(r["dvr"]) for r in group if r["dvr"]]
        optional(row["mean_dvr"], finite_mean(dvr))
        optional(row["sd_dvr"], statistics.stdev(dvr) if len(dvr) > 1 else math.nan)
        optional(row["mean_completed_latency_s"], finite_mean([float(r["mean_completed_latency_s"]) for r in group if r["mean_completed_latency_s"]]))
        close(row["mean_uav_energy_j"], statistics.mean(float(r["total_uav_j"]) for r in group))
        if "mean_primary_loss" in row:
            close(row["mean_primary_loss"], statistics.mean(float(r["primary_loss"]) for r in group))
            optional(row["j_per_on_time_task"], sum(float(r["total_uav_j"]) for r in group) / on if on else math.nan)
    report = dict(status="PASS",verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  paired_workloads=len(cases),episodes=len(groups),task_outcomes=verified_tasks,
                  checks=["input SHA256 pairing", "dataset-to-task costs", "independent baseline/mechanism dispatch", "work-conserving nonpreemptive CPU", "work and battery conservation", "deadline/drop denominator", "summary recomputation"])
    (root / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
