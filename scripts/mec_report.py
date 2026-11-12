"""Summary tables for a uav.mec run (metric conventions: docs/v2/MODEL.md section 7, AGENTS.md).

  python scripts/mec_report.py RUN [--reference "DEADLINE_ENERGY+EDF+NONE"]
Writes RUN/summary.csv (every variant x policy) and RUN/paired.csv (difference to the reference, paired by
(layout, seed), bootstrap 95% CI over pairs, 2000 resamples, seed 0).
Episode means for DVR and latency; ratio of sums for energy per on-time task (NA when nothing is on time).
UAV lifetime is min(death, horizon); survivors are right-censored and counted.
"""
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    return float(x) if x not in ("", None) else math.nan


def ratio(a, b):
    return a / b if b else math.nan


def bootstrap(stat, n, rng, reps=2000):
    if n < 2:
        return math.nan, math.nan
    idx = rng.integers(0, n, size=(reps, n))
    values = np.array([stat(i) for i in idx])
    values = values[~np.isnan(values)]
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))) if len(values) else (math.nan, math.nan)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("run", type=Path)
    p.add_argument("--reference", default="DEADLINE_ENERGY+EDF+NONE")
    a = p.parse_args()
    eps = rows(a.run / "episodes.csv")
    classes = sorted(k[4:] for k in eps[0] if k.startswith("dvr_"))
    by = defaultdict(dict)
    for r in eps:
        by[(r["variant"], r["policy"])][(r["layout"], r["seed"])] = r
    rng = np.random.default_rng(0)
    summary, paired = [], []
    for (variant, policy), g in sorted(by.items()):
        keys = sorted(g)
        R = [g[k] for k in keys]
        col = lambda f: np.array([num(r[f]) for r in R])
        dvr, on, mj, tj = col("dvr"), col("on_time"), col("marginal_j"), col("total_j")
        row = dict(variant=variant, policy=policy, episodes=len(R), dvr_pct=100 * np.nanmean(dvr))
        lo, hi = bootstrap(lambda i: np.mean(dvr[i]), len(R), rng)
        row.update(dvr_ci_lo=100 * lo, dvr_ci_hi=100 * hi)
        for c in classes:
            row[f"dvr_{c}_pct"] = 100 * np.nanmean(col("dvr_" + c))
        row["marginal_j_per_on_time"] = ratio(mj.sum(), on.sum())
        lo, hi = bootstrap(lambda i: ratio(mj[i].sum(), on[i].sum()), len(R), rng)
        row.update(mj_ci_lo=lo, mj_ci_hi=hi, total_j_per_on_time=ratio(tj.sum(), on.sum()),
                   zero_success_episodes=int((on == 0).sum()),
                   latency_mean_s=float(np.nanmean(col("latency_mean_s"))), latency_p95_s=float(np.nanmean(col("latency_p95_s"))),
                   offload_ratio=float(np.nanmean(col("offload_ratio"))), uav_queue_mean=float(np.nanmean(col("uav_queue_mean"))),
                   uav_lifetime_restricted_s=float(np.mean(col("uav_lifetime_s"))),
                   uav_censored=f"{int((col('uav_death_observed') == 0).sum())}/{len(R)}",
                   dropped_admission=float(np.mean(col("drop_admission"))), background_dvr="unavailable")
        summary.append(row)
        ref = by.get((variant, a.reference))
        if ref and policy != a.reference:
            common = [k for k in keys if k in ref]
            d = np.array([num(g[k]["dvr"]) - num(ref[k]["dvr"]) for k in common])
            pm, po = np.array([num(g[k]["marginal_j"]) for k in common]), np.array([num(g[k]["on_time"]) for k in common])
            rm, ro = np.array([num(ref[k]["marginal_j"]) for k in common]), np.array([num(ref[k]["on_time"]) for k in common])
            rel = lambda i: ratio(pm[i].sum(), po[i].sum()) / ratio(rm[i].sum(), ro[i].sum()) - 1
            lo, hi = bootstrap(lambda i: d[i].mean(), len(common), rng)
            elo, ehi = bootstrap(rel, len(common), rng)
            paired.append(dict(variant=variant, policy=policy, reference=a.reference, pairs=len(common),
                               delta_dvr_pts=100 * d.mean(), delta_ci_lo=100 * lo, delta_ci_hi=100 * hi,
                               wins=int((d < 0).sum()), losses=int((d > 0).sum()),
                               energy_rel=rel(np.arange(len(common))), energy_ci_lo=elo, energy_ci_hi=ehi))
    for name, data in (("summary.csv", summary), ("paired.csv", paired)):
        with open(a.run / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(data)
    print(f"wrote {len(summary)} summary rows and {len(paired)} paired rows to {a.run}")


if __name__ == "__main__":
    main()
