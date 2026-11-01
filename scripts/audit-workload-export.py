"""Independently audit exported inputs, without training or evaluating an algorithm."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
from workload_rng import read, verify_rows

def audit(root):
    root=Path(root)
    m=json.loads((root/"manifest.json").read_text())
    p=json.loads((root/"protocol.json").read_text())
    assert m["status"]=="COMPLETE" and not m["algorithm_evaluation"]
    assert hashlib.sha256((root/"seed-manifest.json").read_bytes()).hexdigest()==m["seed_manifest_sha256"]
    plan=json.loads((root/"seed-manifest.json").read_text())
    assert plan["schema"]=="uav-workload-seeds-v2" and plan["master"]=="uav-workload-v2-20261030"
    for split in ("development","validation","evaluation"):
        expected=[1000000000+int.from_bytes(hashlib.sha256(f"{plan['master']}/{split}/{i}".encode()).digest()[:4],"big")%1000000000 for i in range(30)]
        assert plan[split]==expected,"Frozen partition changed: "+split
    assert plan["workloadGenerator"]==p["workloadGenerator"]==m["workloadGenerator"]
    splits=("development","validation","evaluation")
    pairs={(split,load["name"],seed) for split in splits for seed in plan[split] for load in p["loads"]}
    assert len(pairs)==sum(len(plan[s]) for s in splits)*len(p["loads"])
    all_seeds=[s for split in splits for s in plan[split]]
    assert len(set(all_seeds))==len(all_seeds)
    images=read(root/"source-pools/rescuenet-pool.csv");bg=read(root/"source-pools/alibaba-pool.csv")
    groups={};tasks=0;seen=set()
    for case in m["cases"]:
        key=(case["split"],case["load"],case["seed"]);assert key in pairs and key not in seen;seen.add(key)
        path=(root/case["path"]).resolve();assert path.is_relative_to(root.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==case["sha256"]
        rows=read(path)
        cfg=dict(p);cfg.update(next(x for x in p["loads"] if x["name"]==case["load"]))
        tasks+=verify_rows(rows,images,bg,cfg,case["seed"])
        assert len(rows)==case["tasks"]
        im=[r for r in rows if r["source"]=="RESCUENET"];back=[r for r in rows if r["source"]=="ALIBABA"]
        groups.setdefault(case["split"]+"/"+case["load"],[]).append(dict(images=len(im),background=len(back),
            first_image=min((float(r["arrival_s"]) for r in im),default=None),
            first_critical=next((int(r["priority"])==3 for r in im),None)))
    assert seen==pairs
    stats={}
    for k,rows in groups.items():
        first=[r["first_image"] for r in rows if r["first_image"] is not None]
        stats[k]=dict(cases=len(rows),mean_images=statistics.mean(r["images"] for r in rows),
            mean_background=statistics.mean(r["background"] for r in rows),
            first_image_min_s=min(first),first_image_max_s=max(first),first_image_sd_s=statistics.stdev(first),
            first_image_critical_fraction=statistics.mean(r["first_critical"] for r in rows if r["first_critical"] is not None))
    return dict(status="PASS",cases=len(seen),task_rows=tasks,workloadGenerator=m["workloadGenerator"],
                independent_seed_reconstruction=True,algorithm_evaluation=False,statistics=stats)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("root",type=Path);a=p.parse_args()
    result=audit(a.root);(a.root/"verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
