"""P0 diagnosis of the frozen v1 mobile kernel from existing traces (read-only).

D1  why the UAV stays at one site (re-selection vs. departure held by uploads)
D2  slant distance of offloaded images that finished on time
D3  energy spread between policies on the same seed, and propulsion share
D4  how often FIFO / EDF / SPT would pick different tasks at a real UAV dispatch
D5  UAV ready-queue length at dispatch

Usage: python scripts/diagnose_v1.py RUN_DIR [--dwell 30] [--output FILE.json]
RUN_DIR is a workload-v2 baselines run (gym-mobile-v1 trace format).
"""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    return float(x) if x not in ("", None) else math.nan


def quantiles(values):
    if not values:
        return None
    v = sorted(values)
    pick = lambda q: v[min(len(v) - 1, max(0, math.ceil(q * len(v)) - 1))]
    return dict(n=len(v), p10=pick(.1), median=pick(.5), p90=pick(.9), max=v[-1], mean=statistics.fmean(v))


def d1_visits(episode, dwell):
    visits = rows(episode / "episode-visits.csv")
    same = sum(1 for v in visits[1:] if v["previous"] == v["target"])
    holds = []
    for prev, nxt in zip(visits, visits[1:]):
        depart = num(prev["planned_arrival_s"]) + dwell
        holds.append(max(0., num(nxt["at_s"]) - depart))
    return dict(visits=len(visits), reselect_same=same, distinct_targets=len({v["target"] for v in visits}),
                holds=holds)


def d2_slant(episode):
    cov = {r["id"]: r for r in rows(episode / "episode-coverage.csv")}
    out = []
    for t in rows(episode / "episode-tasks.csv"):
        if t["route"] == "UAV" and t["status"] == "COMPLETED_ON_TIME" and t["id"] in cov:
            c = cov[t["id"]]
            planned = num(c["planned_slant_m"])
            out.append(planned if math.isfinite(planned) and num(c["planned_upload_start_s"]) > num(c["at_s"]) else num(c["slant_m"]))
    return out


def d4_d5(episode):
    work = {r["id"]: r for r in rows(episode / "workload.csv")}
    tasks = [t for t in rows(episode / "episode-tasks.csv") if t["route"] in ("UAV", "BACKGROUND")]
    for t in tasks:
        w = work[t["id"]]
        t.update(ready=num(t["ready_s"]), start=num(t["start_s"]), end=num(t["resolved_s"]),
                 deadline=num(w["deadline_s"]), mi=num(w["estimated_mi"]), arrival=num(w["arrival_s"]))
    queue_lengths, differs, comparable = [], 0, 0
    for d in sorted((t for t in tasks if math.isfinite(t["start"])), key=lambda t: t["start"]):
        now = d["start"]
        queue = [t for t in tasks if t["ready"] <= now + 1e-9 and t["end"] > now + 1e-9
                 and not (math.isfinite(t["start"]) and t["start"] < now - 1e-9)]
        if d not in queue:
            queue.append(d)
        queue_lengths.append(len(queue))
        if len(queue) >= 2:
            comparable += 1
            fifo = min(queue, key=lambda t: (t["ready"], t["arrival"], int(t["id"])))
            edf = min(queue, key=lambda t: (t["deadline"], t["ready"], t["arrival"], int(t["id"])))
            spt = min(queue, key=lambda t: (t["mi"], t["ready"], t["arrival"], int(t["id"])))
            differs += len({fifo["id"], edf["id"], spt["id"]}) > 1
    return queue_lengths, differs, comparable


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", type=Path)
    p.add_argument("--dwell", type=float, default=30.)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    root = a.run / "evaluation"
    report = {}

    # D1: CONTACT_GREEDY trajectories.
    holds, visits, same, single_site = [], 0, 0, 0
    episodes = sorted(root.glob("*/seed-*/CONTACT_GREEDY"))
    for e in episodes:
        r = d1_visits(e, a.dwell)
        holds += r["holds"]; visits += r["visits"]; same += r["reselect_same"]; single_site += r["distinct_targets"] == 1
    held = [h for h in holds if h > 1e-6]
    report["D1"] = dict(episodes=len(episodes), episodes_single_site=single_site, visits=visits,
                        reselections_of_same_site=same, departures_after_dwell=len(holds),
                        departures_held_by_upload=len(held), hold_seconds=quantiles(held))

    # D2: offloaded on-time images (all policies that offload).
    slants = []
    for e in sorted(root.glob("*/seed-*/*")):
        if e.is_dir() and (e / "episode-coverage.csv").exists():
            slants += d2_slant(e)
    report["D2"] = dict(offloaded_ontime_images=len(slants), slant_m=quantiles(slants),
                        share_below_15m=sum(s < 15 for s in slants) / len(slants) if slants else None,
                        share_below_20m=sum(s < 20 for s in slants) / len(slants) if slants else None)

    # D3: energy spread per (scenario, seed) across policies.
    groups = defaultdict(list)
    shares = []
    for r in rows(a.run / "core-metrics-episodes.csv"):
        groups[(r["scenario"], r["seed"])].append(num(r["total_energy_j"]))
        total = num(r["total_energy_j"])
        if total > 0:
            shares.append((num(r["flight_j"]) + num(r["hover_j"])) / total)
    cvs = [statistics.pstdev(v) / statistics.fmean(v) for v in groups.values() if len(v) > 1 and statistics.fmean(v) > 0]
    spread = [(max(v) - min(v)) / min(v) for v in groups.values() if len(v) > 1 and min(v) > 0]
    report["D3"] = dict(groups=len(groups), energy_cv_between_policies=quantiles(cvs),
                        max_over_min_minus_one=quantiles(spread), propulsion_share_of_total=quantiles(shares))

    # D4/D5: scheduler divergence on the EDF delivery policy and the FIFO all-UAV policy.
    for policy in ("RR_DELIVERY_RISK_EDF", "RR_ALL_UAV_FIFO"):
        lengths, differs, comparable = [], 0, 0
        for e in sorted(root.glob(f"*/seed-*/{policy}")):
            q, d, c = d4_d5(e)
            lengths += q; differs += d; comparable += c
        report[f"D4_D5_{policy}"] = dict(dispatches=len(lengths), queue_length=quantiles(lengths),
            share_queue_at_least_2=comparable / len(lengths) if lengths else None,
            share_fifo_edf_spt_differ_given_queue_2=differs / comparable if comparable else None,
            share_differ_of_all_dispatches=differs / len(lengths) if lengths else None)

    text = json.dumps(report, indent=2)
    print(text)
    if a.output:
        a.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
