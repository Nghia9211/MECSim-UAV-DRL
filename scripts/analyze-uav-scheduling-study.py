"""Verify both phases and validation-only selection; descriptive paired seed-cluster intervals."""
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import sys
from collections import defaultdict


def read(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        out = csv.DictWriter(stream, fieldnames=list(rows[0]))
        out.writeheader()
        out.writerows(rows)


def quantile(values, fraction):
    values = sorted(values)
    pos = (len(values) - 1) * fraction
    lo, hi = math.floor(pos), math.ceil(pos)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def analyze(root):
    checker = Path(__file__).with_name("verify-uav-scheduling.py")
    spec = importlib.util.spec_from_file_location("scheduling_checker", checker)
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    parent = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    selected = json.loads((root / "selected.json").read_text(encoding="utf-8"))
    assert parent["status"] == "COMPLETE"
    digest = hashlib.sha256((root / "protocol.json").read_bytes()).hexdigest()
    assert parent["protocol_sha256"] == digest
    manifests = {}
    for phase in ("validation", "evaluation"):
        manifests[phase] = json.loads((root / phase / "manifest.json").read_text(encoding="utf-8"))
        manifest = manifests[phase]
        assert manifest["phase"] == phase and manifest["protocol_sha256"] == digest
        assert manifest["first_seed"] == protocol[f"{phase}_first_seed"]
        assert manifest["seeds"] == protocol[f"{phase}_seeds"]
        assert manifest["primary_weights"] == protocol["primary_weights"]
        verifier.verify(root / phase)
    validation = read(root / "validation/episodes.csv")
    by_policy = defaultdict(list)
    for row in validation:
        if row["source"] == "ALL":
            by_policy[row["policy"]].append(float(row["primary_loss"]))
    alpha_scores = []
    for row in read(root / "validation-grid.csv"):
        mean = statistics.mean(by_policy[row["policy"]])
        assert math.isclose(mean, float(row["mean_primary_loss"]), abs_tol=1e-12)
        assert int(row["episodes"]) == len(by_policy[row["policy"]])
        alpha_scores.append((mean, float(row["aging_fraction"]), row["policy"]))
    assert sorted(a for loss, a, name in alpha_scores) == protocol["aging_fraction_candidates"]
    best_value = min(x[0] for x in alpha_scores)
    winner = min((x for x in alpha_scores if abs(x[0] - best_value) <= 1e-12), key=lambda x: x[1])
    assert selected["selected_before_evaluation"] and selected["selected_policy"] == winner[2]
    assert selected["aging_fraction"] == winner[1]
    assert math.isclose(selected["validation_primary_loss"], winner[0], abs_tol=1e-12)
    # Fixed-alpha ablations: change exactly one mechanism switch.
    opts = manifests["evaluation"]["policy_options"]
    full = dict(aging_fraction=winner[1], aging=True, energy_guard=True, deadline_guard=True)
    assert opts["FEASIBLE_AGING"] == full
    for policy, switch in [("NO_AGING", "aging"), ("NO_ENERGY_GUARD", "energy_guard"), ("NO_DEADLINE_GUARD", "deadline_guard")]:
        assert opts[policy] == {**full, switch: False}
    va = set(range(protocol["validation_first_seed"], protocol["validation_first_seed"] + protocol["validation_seeds"]))
    ev = set(range(protocol["evaluation_first_seed"], protocol["evaluation_first_seed"] + protocol["evaluation_seeds"]))
    assert va.isdisjoint(ev)
    rows = read(root / "evaluation/episodes.csv")
    groups = defaultdict(list)
    for row in rows:
        groups[row["policy"], row["source"]].append(row)
    macro = []
    for (policy, source), group in groups.items():
        offered = sum(int(r["offered"]) for r in group)
        on_time = sum(int(r["on_time"]) for r in group)
        energy = sum(float(r["total_uav_j"]) for r in group)
        macro.append(dict(policy=policy, source=source, cases=len(group), offered=offered, on_time=on_time,
            mean_dvr=statistics.mean(float(r["dvr"] or 0) for r in group),
            pooled_dvr=1-on_time/offered if offered else "",
            mean_primary_loss=statistics.mean(float(r["primary_loss"]) for r in group),
            mean_uav_j=energy/len(group), j_per_on_time_task=energy/on_time if on_time else ""))
    write(root / "macro.csv", macro)
    # Average the six fixed load/battery scenarios within each seed, then resample seeds.
    # This preserves pairing and does not treat six variants of one RNG seed as independent replicates.
    all_rows = { (r["scenario"], int(r["seed"]), r["policy"]): r for r in rows if r["source"] == "ALL" }
    scenarios = [s["name"] for s in manifests["evaluation"]["scenarios"]]
    paired = []
    for baseline in manifests["evaluation"]["policies"]:
        if baseline == "FEASIBLE_AGING":
            continue
        differences = [statistics.mean(float(all_rows[scenario, seed, "FEASIBLE_AGING"]["primary_loss"])
                                       -float(all_rows[scenario, seed, baseline]["primary_loss"]) for scenario in scenarios)
                       for seed in sorted(ev)]
        rng = random.Random(20261021)
        bootstrap = [sum(rng.choice(differences) for _ in differences)/len(differences) for _ in range(10000)]
        paired.append(dict(reference=baseline, seeds=len(differences), mean_delta_primary=statistics.mean(differences),
            descriptive_ci_low=quantile(bootstrap,.025), descriptive_ci_high=quantile(bootstrap,.975),
            seed_wins=sum(d < -1e-12 for d in differences), seed_ties=sum(abs(d) <= 1e-12 for d in differences),
            seed_losses=sum(d > 1e-12 for d in differences)))
    write(root / "paired.csv", paired)
    with (root / "REPORT.md").open("w",encoding="utf-8") as stream:
        stream.write("# Feasible aging development study\n\nValidation-selected aging fraction: "+str(winner[1])+".\n\n")
        stream.write("Primary loss = 0.75 image DVR + 0.25 background DVR; lower is better. Fixed source pools/cost assumptions; no novelty or confirmatory claim.\n\n")
        stream.write("| Policy | Image DVR | Background DVR | Primary loss | Mean UAV J |\n|---|---:|---:|---:|---:|\n")
        index = {(r["policy"],r["source"]):r for r in macro}
        for policy in manifests["evaluation"]["policies"]:
            im,bg,all_ = (index[policy,s] for s in ("RESCUENET","ALIBABA","ALL"))
            stream.write(f"| {policy} | {im['mean_dvr']:.4f} | {bg['mean_dvr']:.4f} | {all_['mean_primary_loss']:.4f} | {all_['mean_uav_j']:.1f} |\n")
        stream.write("\npaired.csv: unadjusted descriptive 95% seed-cluster bootstrap intervals, 10,000 resamples. Not a final significance test.\n")
    audit = dict(status="PASS",selection="validation-only",aging_fraction=winner[1],fixed_alpha_ablations=True,
                 disjoint_task_seeds=True,bootstrap_cluster="task seed across six fixed scenarios",
                 bootstrap_resamples=10000,source_holdout=False)
    (root / "study-verification.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print(json.dumps(audit,indent=2))
    print((root / "REPORT.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    analyze(Path(sys.argv[1]))
