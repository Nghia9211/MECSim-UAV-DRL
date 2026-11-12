"""Gates G1-G6 of docs/v2/CALIBRATION.md, computed from uav.mec run directories.

  python scripts/mec_gates.py g5 RUN            # queueing theory
  python scripts/mec_gates.py g1 RUN            # CPU speed sensitivity
  python scripts/mec_gates.py g234 RUN          # scheduler effect, offloading trade-off, energy spread
  python scripts/mec_gates.py g6 RUN            # gap between best heuristic and the rollout oracle
Writes RUN/gates-<name>.json and prints it. Exit code 1 if a gate fails.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    return float(x) if x not in ("", None) else math.nan


def mean(values):
    values = [v for v in values if not math.isnan(v)]
    return sum(values) / len(values) if values else math.nan


def summary(run):
    """(variant, policy) -> mean DVR over episodes and pooled marginal J per on-time task."""
    groups = defaultdict(list)
    for r in rows(run / "episodes.csv"):
        groups[(r["variant"], r["policy"])].append(r)
    out = {}
    for key, g in groups.items():
        on_time = sum(num(r["on_time"]) for r in g)
        marginal = sum(num(r["marginal_j"]) for r in g)
        out[key] = dict(n=len(g), dvr=mean([num(r["dvr"]) for r in g]), marginal_j=marginal,
                        j_per_on_time=marginal / on_time if on_time else math.nan,
                        offload_ratio=mean([num(r["offload_ratio"]) for r in g]))
    return out


def g5(run):
    cells = {}
    model = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in (run / "models").glob("*.json")}
    for trace in sorted((run / "traces").glob("*/L*/S*/*")):
        variant = trace.parts[-4]
        m = model[variant]
        lam = m["arrival_rate_per_s"]
        cyc = m["classes"][0]["cycles_g"]
        mean_cycles = cyc["mean"] if isinstance(cyc, dict) else cyc
        mu = m["uav"]["speed_gcps"] / mean_cycles
        rho = lam / mu
        theory = rho / (mu - lam) if variant.startswith("mm1") else rho / (2 * mu * (1 - rho))
        waits = [num(t["cpu_start"]) - num(t["uav_ready"]) for t in rows(trace / "tasks.csv") if t["cpu_start"]]
        observed = sum(waits) / len(waits)
        err = abs(observed - theory) / theory
        cells[variant] = dict(tasks=len(waits), rho=rho, theory_wq_s=theory, observed_wq_s=observed,
                              relative_error=err, pass_=err <= 0.03)
    return dict(gate="G5", cells=cells, passed=bool(cells) and all(c["pass_"] for c in cells.values()))


def g1(run):
    s = summary(run)
    by_speed = {}
    for (variant, policy), v in s.items():
        if policy == "ALL_UAV+EDF+NONE":
            by_speed[float(variant.split("cpu")[1])] = v["dvr"]
    speeds = sorted(by_speed)
    dvr = [by_speed[x] for x in speeds]
    monotone = all(a > b for a, b in zip(dvr, dvr[1:]))
    drop = dvr[0] - dvr[-1]
    return dict(gate="G1", uav_speed_gcps=speeds, dvr=dvr, dvr_drop_points=100 * drop, monotone=monotone,
                passed=monotone and drop >= 0.10)


def divergence(trace):
    tasks = [t for t in rows(trace / "tasks.csv") if t["route"] == "UAV" and t["uav_ready"]]
    for t in tasks:
        t.update(ready=num(t["uav_ready"]), start=num(t["cpu_start"]), res=num(t["resolved"]),
                 dl=num(t["deadline"]), est=num(t["est_cycles_g"]), arr=num(t["arrival"]), i=int(t["id"]))
    starts = sorted((t for t in tasks if not math.isnan(t["start"])), key=lambda t: t["start"])
    differ = match = queue2 = 0
    for d in starts:
        now = d["start"]
        q = [t for t in tasks if t["ready"] <= now + 1e-9 and t["res"] > now + 1e-9
             and (math.isnan(t["start"]) or t["start"] >= now - 1e-9)]
        fifo = lambda t: (t["ready"], t["arr"], t["i"])
        picks = {min(q, key=fifo)["i"], min(q, key=lambda t: (t["dl"],) + fifo(t))["i"],
                 min(q, key=lambda t: (t["est"],) + fifo(t))["i"]}
        match += min(q, key=lambda t: (t["dl"],) + fifo(t))["i"] == d["i"]
        queue2 += len(q) >= 2
        differ += len(picks) > 1
    return len(starts), differ, match, queue2


def g234(run):
    s = summary(run)
    variants = sorted({v for v, _ in s})
    loads = sorted({v.split("-")[0] for v in variants})
    schedulers = ["FIFO", "EDF", "SRPT", "LLF", "PRIORITY_EDF"]
    g2 = {}
    for v in variants:
        d = {x: s[(v, f"ALL_UAV+{x}+NONE")]["dvr"] for x in schedulers if (v, f"ALL_UAV+{x}+NONE") in s}
        if len(d) == len(schedulers):
            g2[v] = dict(dvr=d, spread_points=100 * (max(d.values()) - min(d.values())))
    traces = sorted((run / "traces").glob("*-np/L*/S*/ALL_UAV__EDF__NONE"))
    n = differ = match = queue2 = 0
    for t in traces:
        a, b, c, q = divergence(t)
        n += a; differ += b; match += c; queue2 += q
    g2b = dict(traced_episodes=len(traces), dispatches=n, share_queue_at_least_2=queue2 / n if n else None,
               share_fifo_edf_spt_differ=differ / n if n else None,
               reconstruction_check_edf_matches_dispatch=f"{match}/{n}")
    g2_pass = any(c["spread_points"] >= 5 for k, c in g2.items() if k.split("-")[0] in ("medium", "overload")) \
        and n > 0 and differ / n >= 0.30 and match == n

    offload = ["ALL_LOCAL", "ALL_UAV", "RANDOM", "SHORTEST_FINISH", "DEADLINE_ENERGY", "THRESHOLD_5"]
    g3, g4 = {}, {}
    for v in variants:
        if not v.endswith("-np"):
            continue
        d = {o: s[(v, f"{o}+EDF+NONE")] for o in offload if (v, f"{o}+EDF+NONE") in s}
        if len(d) != len(offload):
            continue
        mixed = {o: x["dvr"] for o, x in d.items() if o not in ("ALL_LOCAL", "ALL_UAV")}
        best = min(mixed, key=mixed.get)
        local, uav = d["ALL_LOCAL"], d["ALL_UAV"]
        g3[v] = dict(dvr={o: x["dvr"] for o, x in d.items()}, j_per_on_time={o: x["j_per_on_time"] for o, x in d.items()},
                     best_mixed=best, mixed_beats_both=mixed[best] < min(local["dvr"], uav["dvr"]),
                     local_wins=local["dvr"] < uav["dvr"] or local["j_per_on_time"] < uav["j_per_on_time"],
                     uav_wins=uav["dvr"] < local["dvr"] or uav["j_per_on_time"] < local["j_per_on_time"])
        energies = [x["marginal_j"] for x in d.values()]
        g4[v] = dict(marginal_j={o: x["marginal_j"] for o, x in d.items()}, max_over_min=max(energies) / min(energies))
    g3_pass = any(c["mixed_beats_both"] for c in g3.values()) and any(c["local_wins"] for c in g3.values()) \
        and any(c["uav_wins"] for c in g3.values())
    g4_pass = bool(g4) and all(c["max_over_min"] >= 1.20 for c in g4.values())
    return dict(G2=dict(cells=g2, divergence=g2b, passed=g2_pass), G3=dict(cells=g3, passed=g3_pass),
                G4=dict(cells=g4, passed=g4_pass), passed=g2_pass and g3_pass and g4_pass, loads=loads)


def g6(run):
    s = summary(run)
    cells = {}
    oracle_rows = defaultdict(list)
    for r in rows(run / "episodes.csv"):
        oracle_rows[(r["variant"], r["layout"], r["seed"])].append(r)
    for (variant, policy), v in s.items():
        if not policy.startswith("ORACLE:"):
            continue
        base = policy[len("ORACLE:"):]
        # compare on exactly the episodes the oracle ran
        keys = [(k, g) for k, g in oracle_rows.items() if k[0] == variant and any(r["policy"] == policy for r in g)]
        pick = lambda p, f: [num(r[f]) for _, g in keys for r in g if r["policy"] == p]
        dvr_b, dvr_o = mean(pick(base, "dvr")), mean(pick(policy, "dvr"))
        on_b, on_o = sum(pick(base, "on_time")), sum(pick(policy, "on_time"))
        jb = sum(pick(base, "marginal_j")) / on_b if on_b else math.nan
        jo = sum(pick(policy, "marginal_j")) / on_o if on_o else math.nan
        cells[variant] = dict(episodes=len(keys), base=base, dvr_base=dvr_b, dvr_oracle=dvr_o,
                              dvr_gap_points=100 * (dvr_b - dvr_o), j_per_on_time_base=jb, j_per_on_time_oracle=jo,
                              energy_gap_relative=(jb - jo) / jb if jb else math.nan)
    passed = any(c["dvr_gap_points"] >= 5 or c["energy_gap_relative"] >= 0.10 for c in cells.values())
    return dict(gate="G6", cells=cells, passed=passed)


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("g1", "g5", "g234", "g6"):
        raise SystemExit(__doc__)
    run = Path(sys.argv[2])
    result = {"g1": g1, "g5": g5, "g234": g234, "g6": g6}[sys.argv[1]](run)
    text = json.dumps(result, indent=2, default=lambda x: None)
    (run / f"gates-{sys.argv[1]}.json").write_text(text, encoding="utf-8")
    print(text)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
