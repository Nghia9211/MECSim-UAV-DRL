"""H3 exploration (docs/v2/CALIBRATION_V21.md section 1): write configs and compute gates G6-G9.

  python scripts/h3.py heuristics ROUND CELLS_JSON      -> experiments/h3-ROUND-heuristics.json
  python scripts/h3.py oracle ROUND HEUR_RUN            -> experiments/h3-ROUND-oracle.json (base = best heuristic per cell)
  python scripts/h3.py gates HEUR_RUN ORACLE_RUN        -> HEUR_RUN/h3-gates.json, prints the table
CELLS_JSON maps a cell name to its model patch (relative to v2.0 overload, CIRCLE, exact estimates).
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFLOAD = ["ALL_LOCAL", "ALL_UAV", "RANDOM", "THRESHOLD_5", "SHORTEST_FINISH", "DEADLINE_ENERGY"]
BASE = {"rho_uav": 1.3}

ROUND1 = {
    "R1-base": {},
    "R1-L1": {"radio": {"mode": "PLOS", "carrier_hz": 2e9, "xi_los_db": 1, "xi_nlos_db": 20, "plos_a": 9.6, "plos_b": 0.28}},
    "R1-L2a": {"radio": {"uplink_hz": 5e6, "downlink_hz": 2.5e6}},
    "R1-L2b": {"radio": {"uplink_hz": 2e6, "downlink_hz": 1e6}},
    "R1-L3a": {"area_m": 1200},
    "R1-L3b": {"area_m": 2000},
    "R1-L4": {"hotspots": {"device_share": 0.3, "task_share": 0.7}},
    "R1-L5": {"bursts": {"high_rate": 3, "low_rate": 0.5, "high_mean_s": 20, "low_mean_s": 80}},
    "R1-L6a": {"rho_uav": None, "rho_system": 0.8},
    "R1-L6b": {"rho_uav": None, "rho_system": 1.0},
    "R1-L7": {"initial_charge": 0.05},
}


def merge(a, b):
    out = dict(a)
    for k, v in b.items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def area_of(patch):
    return patch.get("area_m", 600)


def trajectories(area):
    return {"circle": {"trajectory": {"type": "CIRCLE", "radius_m": area / 3, "speed_mps": 10}},
            "static-centre": {"trajectory": {"type": "STATIC"}},
            "static-quarter": {"trajectory": {"type": "STATIC", "x_m": area / 4, "y_m": area / 4}}}


def heuristics(rnd, cells):
    levels = []
    for name, patch in cells.items():
        for traj, tp in trajectories(area_of(patch)).items():
            levels.append({"name": f"{name}~{traj}", "model": merge(merge(BASE, patch), tp)})
    cfg = {"name": f"h3-{rnd}-heuristics",
           "hypothesis": f"H3 {rnd}: which v2.1 levers open headroom (G6) and make the UAV position matter (G7).",
           "threshold": "G6, G7, G8, G9 as pre-registered in docs/v2/CALIBRATION_V21.md section 1.3",
           "model_file": "experiments/base-model.json",
           "axes": {"cell": levels, "cpu": [{"name": "np"}, {"name": "pre", "model": {"preemptive": True}}]},
           "policies": [f"{o}+EDF+NONE" for o in OFFLOAD], "partition": "development", "trace_tasks": 1,
           "trace_layouts": 1, "engine": "loop", "threads": 16}
    path = ROOT / f"experiments/h3-{rnd}-heuristics.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(path, len(levels) * 2 * len(OFFLOAD) * 150, "episodes")


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(run):
    g = defaultdict(list)
    for r in rows(Path(run) / "episodes.csv"):
        g[(r["variant"], r["policy"])].append(r)
    out = {}
    for (variant, policy), rs in g.items():
        cell_traj, cpu = variant.rsplit("-", 1)
        cell, traj = cell_traj.split("~")
        on = sum(float(r["on_time"]) for r in rs)
        out[(cell, traj, cpu, policy)] = dict(
            n=len(rs), dvr=sum(float(r["dvr"]) for r in rs) / len(rs),
            j=sum(float(r["marginal_j"]) for r in rs) / on if on else math.nan,
            deaths=sum(int(r["device_deaths"]) > 0 for r in rs) / len(rs))
    return out


def best(s, cell):
    """Best heuristic of a cell on CIRCLE over both CPU modes: lowest DVR, then lowest J per on-time task."""
    cands = [(v["dvr"], v["j"], cpu, pol) for (c, traj, cpu, pol), v in s.items() if c == cell and traj == "circle"]
    return min(cands)


def oracle(rnd, heur_run):
    s = summarize(heur_run)
    cfg_h = json.loads((Path(heur_run) / "config.json").read_text(encoding="utf-8"))
    cells = sorted({c for c, *_ in s})
    levels, policies = [], set()
    for cell in cells:
        dvr, j, cpu, pol = best(s, cell)
        lvl = next(l for l in cfg_h["axes"]["cell"] if l["name"] == f"{cell}~circle")
        model = dict(lvl["model"]); model["preemptive"] = cpu == "pre"
        levels.append({"name": f"{cell}~circle-{cpu}", "model": model})
        policies.add(pol)
    # one policy list for all cells; each cell is scored only on its own best heuristic (gates step)
    cfg = {"name": f"h3-{rnd}-oracle", "hypothesis": f"H3 {rnd} G6: ORACLE_ITER of each cell's best heuristic.",
           "threshold": "G6: >= 5 DVR points or >= 10% marginal J per on-time task (CALIBRATION_V21.md 1.3)",
           "model_file": "experiments/base-model.json", "axes": {"cell": levels},
           "policies": sorted(policies) + [f"ORACLE_ITER:{p}" for p in sorted(policies)],
           "seeds": {"layouts": [0, 1, 2], "tasks": [0, 1]}, "trace_tasks": 1, "trace_layouts": 1,
           "engine": "loop", "threads": 16}
    path = ROOT / f"experiments/h3-{rnd}-oracle.json"
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(path, {c: best(s, c)[2:] for c in cells})


def gates(heur_run, oracle_run):
    s = summarize(heur_run)
    o = defaultdict(list)
    for r in rows(Path(oracle_run) / "episodes.csv"):
        o[(r["variant"].split("~")[0], r["policy"])].append(r)
    table = {}
    for cell in sorted({c for c, *_ in s}):
        dvr, j, cpu, pol = best(s, cell)
        trajs = {t: s[(cell, t, cpu, pol)] for t in ("circle", "static-centre", "static-quarter")}
        g7_dvr = 100 * (max(v["dvr"] for v in trajs.values()) - min(v["dvr"] for v in trajs.values()))
        g7_j = max(v["j"] for v in trajs.values()) / min(v["j"] for v in trajs.values()) - 1
        base_rows, orc_rows = o.get((cell, pol), []), o.get((cell, "ORACLE_ITER:" + pol), [])
        pair = lambda rs, f: sum(float(r[f]) for r in rs)
        g6_dvr = 100 * (pair(base_rows, "dvr") - pair(orc_rows, "dvr")) / max(1, len(orc_rows))
        jb = pair(base_rows, "marginal_j") / max(1e-9, pair(base_rows, "on_time"))
        jo = pair(orc_rows, "marginal_j") / max(1e-9, pair(orc_rows, "on_time"))
        local_deaths = s[(cell, "circle", cpu, "ALL_LOCAL+EDF+NONE")]["deaths"]
        row = dict(best=f"{pol} [{cpu}]", dvr_pct=100 * dvr, j=j, oracle_episodes=len(orc_rows),
                   g6_dvr_pts=g6_dvr, g6_energy=(jb - jo) / jb if jb else math.nan,
                   g7_dvr_pts=g7_dvr, g7_energy=g7_j, local_death_share=local_deaths,
                   traj_dvr_pct={t: 100 * v["dvr"] for t, v in trajs.items()})
        row["G6"] = row["g6_dvr_pts"] >= 5 or row["g6_energy"] >= 0.10
        row["G7"] = row["g7_dvr_pts"] >= 3 or row["g7_energy"] >= 0.10
        row["G8"] = 2 <= row["dvr_pct"] <= 40
        row["G9"] = (0.10 <= local_deaths <= 0.90) if "L7" in cell else None
        table[cell] = row
    (Path(heur_run) / "h3-gates.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    print(f"{'cell':9s} {'best heuristic':34s} {'DVR%':>6s} {'G6 pts':>7s} {'G6 E':>6s} {'G7 pts':>7s} {'G7 E':>6s} G6 G7 G8 G9")
    for c, r in table.items():
        print(f"{c:9s} {r['best']:34s} {r['dvr_pct']:6.2f} {r['g6_dvr_pts']:7.2f} {100*r['g6_energy']:5.1f}% "
              f"{r['g7_dvr_pts']:7.2f} {100*r['g7_energy']:5.1f}%  {'Y' if r['G6'] else '-'}  {'Y' if r['G7'] else '-'}  "
              f"{'Y' if r['G8'] else '-'}  {'' if r['G9'] is None else ('Y' if r['G9'] else '-')} (local deaths {100*r['local_death_share']:.0f}%)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "heuristics":
        heuristics(sys.argv[2], ROUND1 if sys.argv[3] == "round1" else json.loads(Path(sys.argv[3]).read_text()))
    elif cmd == "oracle":
        oracle(sys.argv[2], sys.argv[3])
    elif cmd == "gates":
        gates(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
