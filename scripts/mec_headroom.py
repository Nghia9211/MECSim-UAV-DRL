"""H0 headroom analysis for a uav.mec run (docs/v2/HEADROOM.md).

  python scripts/mec_headroom.py RUN [--base "DEADLINE_ENERGY+EDF+NONE"]

1. Violation breakdown of the base policy, from its traces. Each task that is not DONE falls in exactly one group:
   infeasible   cannot meet its deadline even alone: min(local alone, uplink alone + UAV CPU + downlink alone) with the
                actual work and the channel at arrival exceeds the deadline (a floor no policy can beat)
   queueing     feasible alone, and the forecast of the chosen route already predicted a miss at decision time
   forecast     feasible alone, the chosen route was forecast on time, but the task still missed
2. Oracle ladder on the oracle episodes: base, ORACLE, ORACLE_ITER, ORACLE_BEST, and the infeasible floor;
   checks ORACLE_BEST >= ORACLE_ITER >= ORACLE on every episode (on-time count, then marginal energy).
Writes RUN/headroom.json.
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_mec import Model, num, rows  # noqa: E402


def isolated_best(t, dev, model):
    a = num(t["arrival"])
    local = num(t["cycles_g"]) / num(dev["speed_gcps"])
    if model.ideal:
        return min(local, num(t["cycles_g"]) / model.uav_speed)
    blk = model.r["block_s"]
    x, y, z = model.position(math.floor((a + 1e-9) / blk) * blk)
    d = math.sqrt((x - num(dev["x"])) ** 2 + (y - num(dev["y"])) ** 2 + z * z)
    up = num(t["input_bytes"]) * 8 / model.rate(True, 1, d) if num(t["input_bytes"]) > 0 else 0
    down = num(t["result_bytes"]) * 8 / model.rate(False, 1, d) if num(t["result_bytes"]) > 0 else 0
    return min(local, up + num(t["cycles_g"]) / model.uav_speed + down)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", type=Path)
    p.add_argument("--base", default="DEADLINE_ENERGY+EDF+NONE")
    a = p.parse_args()
    models = {f.stem: Model(json.loads(f.read_text(encoding="utf-8"))) for f in (a.run / "models").glob("*.json")}
    base_dir = a.base.replace("+", "__")
    breakdown = {}
    floor = {}
    for variant in sorted(models):
        groups = defaultdict(lambda: defaultdict(int))
        for ep in sorted((a.run / "traces" / variant).glob(f"L*/S*/{base_dir}")):
            devices = {d["id"]: d for d in rows(ep / "devices.csv")}
            ep_key = (ep.parts[-3][1:], ep.parts[-2][1:])
            infeasible = 0
            tasks = rows(ep / "tasks.csv")
            for t in tasks:
                cls = t["class"]
                groups[cls]["offered"] += 1
                slack = num(t["deadline"]) - num(t["arrival"])
                alone_ok = isolated_best(t, devices[t["device"]], models[variant]) <= slack + 1e-9
                infeasible += not alone_ok
                if t["status"] == "DONE":
                    continue
                if not alone_ok:
                    g = "infeasible"
                else:
                    fc = num(t["fc_local_finish"] if t["route"] == "LOCAL" else t["fc_uav_finish"])
                    g = "forecast" if fc <= num(t["deadline"]) + 1e-9 else "queueing"
                groups[cls][g] += 1
            floor[(variant,) + ep_key] = infeasible / len(tasks)
        total = defaultdict(int)
        for c in groups.values():
            for k, v in c.items():
                total[k] += v
        breakdown[variant] = dict(all=dict(total), **{k: dict(v) for k, v in groups.items()})

    eps = rows(a.run / "episodes.csv")
    by = defaultdict(dict)
    for r in eps:
        by[(r["variant"], r["layout"], r["seed"])][r["policy"]] = r
    names = [a.base, "ORACLE:" + a.base, "ORACLE_ITER:" + a.base, "ORACLE_BEST:" + a.base.split("+")[0]]
    ladder, violations = {}, []
    for (variant, layout, seed), g in sorted(by.items()):
        if not all(n in g for n in names):
            continue
        s = [(num(g[n]["on_time"]), -num(g[n]["marginal_j"])) for n in names]
        for i in (2, 3):
            if s[i] < s[i - 1]:
                violations.append(f"{variant} L{layout} S{seed}: {names[i]} worse than {names[i-1]}")
        cell = ladder.setdefault(variant, defaultdict(list))
        for n in names:
            cell[n].append(num(g[n]["dvr"]))
            cell[n + " J/on"].append((num(g[n]["marginal_j"]), num(g[n]["on_time"])))
        cell["floor_infeasible"].append(floor.get((variant, layout, seed), math.nan))
        cell["best_choice"].append(g[names[3]]["resolved_policy"].split("=")[-1])
    summary = {}
    for v, c in ladder.items():
        out = dict(episodes=len(c["floor_infeasible"]))
        for n in names:
            out[n + " dvr_pct"] = 100 * sum(c[n]) / len(c[n])
            mj, on = map(sum, zip(*c[n + " J/on"]))
            out[n + " j_per_on_time"] = mj / on if on else math.nan
        out["floor_dvr_pct"] = 100 * sum(c["floor_infeasible"]) / len(c["floor_infeasible"])
        counts = defaultdict(int)
        for b in c["best_choice"]:
            counts[b] += 1
        out["best_scheduler_choices"] = dict(counts)
        summary[v] = out
    report = dict(base=a.base, breakdown=breakdown, oracle_ladder=summary, ladder_order_violations=violations,
                  ladder_order_ok=not violations)
    (a.run / "headroom.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(dict(ladder_order_ok=report["ladder_order_ok"], violations=violations[:5]), indent=2))


if __name__ == "__main__":
    main()
