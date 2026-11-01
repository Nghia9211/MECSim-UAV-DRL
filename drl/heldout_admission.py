"""Freeze candidates/configuration before validation/evaluation. No outcome-based tuning."""
import argparse,hashlib,json,copy
from pathlib import Path
from .workload_protocol import load_seed_manifest
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source_paths():
    paths=list((ROOT/"PureEdgeSim/uav/offloading").glob("*.java"))+list((ROOT/"PureEdgeSim/uav/scheduling").glob("*.java"))
    paths+=[ROOT/x for x in ("PureEdgeSim/uav/PaperParameters.java","scripts/verify-uav-offloading.py","scripts/verify-uav-mobile.py",
        "scripts/workload_rng.py","scripts/offloading_metrics.py","drl/sequential_study.py","drl/heldout_admission.py",
        "drl/admission_study.py","drl/workload_v2_seed_manifest.json")]
    return sorted(set(paths))
def validate_lock(p,check_sources=True):
    path=Path(p["experimentLock"])
    if sha(path)!=p["experimentLockSha256"]:raise ValueError("Experiment lock changed")
    lock=json.loads(path.read_text())
    normalized={k:v for k,v in p.items()if k not in("experimentLock","experimentLockSha256")}
    if normalized!=lock["protocols"][p["taskSeedPartition"]]:raise ValueError("Heldout protocol changed")
    if check_sources:
        for name,h in lock["source_sha256"].items():
            if sha(ROOT/name)!=h:raise ValueError("Frozen source changed: "+name)
    return lock
def check_geometry(p,cfg):
    from workload_rng import JavaRandom
    layout=cfg["layout"];seed=layout["seed"];area=layout["areaMetres"];rng=JavaRandom(seed)
    xy=[(area*(.1+.8*rng.double()),area*(.1+.8*rng.double())) for _ in range(p["devices"])]
    ids=list(range(p["devices"]));mask_rng=JavaRandom(seed^0x9CA72F)
    for i in range(len(ids),1,-1):
        k=mask_rng.integer(i);ids[i-1],ids[k]=ids[k],ids[i-1]
    connected=set(ids[:p["connectedDevices"]])
    for i,(site,(x,y))in enumerate(zip(cfg["sites"],xy)):
        if abs(site["x"]-x)>1e-9 or abs(site["y"]-y)>1e-9 or site["connected"]!=(i in connected):
            raise ValueError("Layout/connection seed reconstruction mismatch")
    if len(cfg["sites"])!=p["devices"]:raise ValueError("Sites")
def freeze(base_protocol,root):
    if root.exists():raise ValueError("Lock output exists")
    p=json.loads(base_protocol.read_text())
    dev=ROOT/"target/admission-study-20261101/mobile-full"
    if json.loads((dev/"verification.json").read_text())["status"]!="PASS":raise ValueError("Development not verified")
    root.mkdir(parents=True)
    seeds=load_seed_manifest();protocols={}
    for split,layouts in (("validation",(104729,104743)),("evaluation",(130363,130367))):
        q=copy.deepcopy(p);q.update(taskSeedPartition=split,taskSeeds=seeds[split],smoke=False,
            policies=[f"{sel}__ALL_UAV__{s}"for sel in ("STATIC_FIRST","ROUND_ROBIN")for s in("EDF","RISK_EDF","BG_CAP_EDF")])
        q["layouts"]=[dict(name=f"layout{seed}-{name}",seed=seed,areaMetres=area)
            for seed in layouts for name,area in (("compact",250),("wide",800))]
        q["heldoutPurpose"]="Frozen characterization of image/background tradeoff; no automatic winner or tuning"
        protocols[split]=q
    lock=dict(schema="admission-heldout-lock-v1",status="FROZEN_BEFORE_HELDOUT_ALGORITHM_OUTCOMES",
        source_sha256={str(x.relative_to(ROOT)).replace("\\","/"):sha(x)for x in source_paths()},
        development_verification_sha256=sha(dev/"verification.json"),protocols=protocols,
        candidates=("EDF","RISK_EDF","BG_CAP_EDF"),primary_metrics=["delivered_image_dvr","j_per_delivered_ontime_image","background_dvr"],
        threshold_tuned=False,checkpoint_selection=False,
        layout_interpretation="Two independent geometries per split, each scaled twice; not 120 independent layouts",
        no_promote_rule="No overall superiority if background regression; report tradeoff and restrict claim")
    lockpath=root/"EXPERIMENT_LOCK.json";lockpath.write_text(json.dumps(lock,indent=2),encoding="utf-8")
    for split,p in protocols.items():
        q=dict(p,experimentLock=str(lockpath.resolve()),experimentLockSha256=sha(lockpath))
        validate_lock(q)
        (root/(split+".json")).write_text(json.dumps(q,indent=2),encoding="utf-8")
    print("HELDOUT_FROZEN",root,"episodes_per_split",4*2*6*30)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--base-protocol",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
    a=p.parse_args();freeze(a.base_protocol,a.output)
if __name__=="__main__":main()
