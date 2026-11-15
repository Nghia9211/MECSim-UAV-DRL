"""H5d-2 trade-off front (experiments/h5d-offload-ext.json): DVR vs marginal J per offered task on evaluation-v21.

  python scripts/h5d_front.py OUT.json RUN [RUN ...]
Each RUN is a uav.mec run directory (episodes.csv). Rows of variant e0-pre-circle are used.
Heuristic = any policy without "RL_" in its name. RL points are grouped by energy weight (RL_PPO_w<W>_s<S>): the mean
over seeds of the episode-mean DVR and of the pooled marginal J per offered task. A heuristic is dominated when some RL
weight has DVR <= and J/offered <= with at least one strict. Duplicate (policy, layout, seed) rows across runs must agree.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

VARIANT = "e0-pre-circle"


def main():
    out, runs = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    rows = {}
    for run in runs:
        with open(run / "episodes.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["variant"] != VARIANT:
                    continue
                key = (r["policy"], r["layout"], r["seed"])
                if key in rows and (rows[key]["dvr"], rows[key]["marginal_j"]) != (r["dvr"], r["marginal_j"]):
                    raise SystemExit(f"conflicting rows for {key}")
                rows[key] = r
    by = defaultdict(list)
    for (policy, _, _), r in rows.items():
        by[policy].append(r)
    points = {}
    for policy, rs in by.items():
        points[policy] = dict(episodes=len(rs), dvr=100 * sum(float(r["dvr"]) for r in rs) / len(rs),
                              j_per_offered=sum(float(r["marginal_j"]) for r in rs) / sum(float(r["offered"]) for r in rs),
                              j_per_on_time=sum(float(r["marginal_j"]) for r in rs) / sum(float(r["on_time"]) for r in rs))
    rl = defaultdict(list)
    for policy, p in points.items():
        m = re.match(r"RL_PPO_w([0-9.]+)_s(\d+)\+", policy)
        if m:
            rl[float(m.group(1))].append(p)
    front = {w: dict(seeds=len(ps), dvr=sum(p["dvr"] for p in ps) / len(ps), dvr_min=min(p["dvr"] for p in ps),
                     dvr_max=max(p["dvr"] for p in ps), j_per_offered=sum(p["j_per_offered"] for p in ps) / len(ps),
                     j_min=min(p["j_per_offered"] for p in ps), j_max=max(p["j_per_offered"] for p in ps))
             for w, ps in sorted(rl.items())}
    heur = {k: v for k, v in points.items() if "RL_" not in k}
    dominated = {}
    for name, h in heur.items():
        by_w = [w for w, f in front.items() if f["dvr"] <= h["dvr"] and f["j_per_offered"] <= h["j_per_offered"]
                and (f["dvr"] < h["dvr"] or f["j_per_offered"] < h["j_per_offered"])]
        dominated[name] = by_w
    result = dict(variant=VARIANT, rl_front=front, heuristics=heur, dominated_by=dominated,
                  dominated_share=sum(bool(v) for v in dominated.values()) / len(dominated))
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("RL front (mean over seeds):")
    for w, f in front.items():
        print(f"  w={w:<5g} seeds {f['seeds']}  DVR {f['dvr']:.2f}% [{f['dvr_min']:.2f}, {f['dvr_max']:.2f}]  "
              f"J/offered {f['j_per_offered']:.3f} [{f['j_min']:.3f}, {f['j_max']:.3f}]")
    print("Heuristics:")
    for name, h in sorted(heur.items(), key=lambda kv: kv[1]["dvr"]):
        print(f"  {name:45s} DVR {h['dvr']:6.2f}%  J/offered {h['j_per_offered']:.3f}  dominated by w={dominated[name] or '-'}")
    print(f"dominated share {100 * result['dominated_share']:.0f}% of {len(heur)} heuristics")


if __name__ == "__main__":
    main()
