"""Predeclared background-blocking ablation, parameters derived from SLA and frozen input pool."""
import argparse,hashlib,json,math
from pathlib import Path
from .workload_protocol import load_seed_manifest
ROOT=Path(__file__).resolve().parents[1]
POLICIES=("EDF","PRIORITY","RISK_EDF","RISK_SPT","BG_CAP_EDF","RISK_BG_CAP_EDF")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-protocol",type=Path,required=True);ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--smoke",action="store_true")
    a=ap.parse_args()
    if a.output.exists():ap.error("Output exists")
    p=json.loads(a.base_protocol.read_text())
    p["ablation"]="background-budget-v1"
    p["ablationProtocolBaseSha256"]=sha(a.base_protocol)
    p["smoke"]=a.smoke
    p["taskSeeds"]=load_seed_manifest()["development"][:1] if a.smoke else load_seed_manifest()["development"]
    import csv
    pool=ROOT/"target/workload-v2-inputs-20261030/source-pools/rescuenet-pool.csv"
    with pool.open(encoding="utf-8")as f:sizes=[int(r["bytes"])for r in csv.DictReader(f)]
    max_upload=max(sizes)*8/20e6
    image_service=p["imageFixedMi"]/p["uavMips"]
    p["backgroundBudgetDerivation"]=dict(rule="critical deadline - max frozen JPEG upload at10m - reference compute",
        max_source_bytes=max(sizes),reference_rate_bps=20e6,reference_compute_seconds=image_service,
        source_pool_sha256=sha(pool),no_future_tasks_or_policy_scores=True,
        guarantee="isolated reference10m head-of-line blocking budget only; not global schedulability")
    for load in p["loads"]:
        cap=load["criticalDeadlineSeconds"]-max_upload-image_service
        if not math.isfinite(cap)or cap<=0:raise ValueError("No positive blocking budget")
        load["backgroundBudgetSeconds"]=cap
    if p["studyStage"]=="hover":p["policies"]=["ALL_UAV__"+s for s in POLICIES]
    else:p["policies"]=[selector+"__ALL_UAV__"+s for selector in ("STATIC_FIRST","ROUND_ROBIN") for s in POLICIES]
    p["policyOrdering"]="Rotate by seed index; no result-based policy selection"
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(p,indent=2),encoding="utf-8")
    print("ADMISSION_ABLATION_PROTOCOL",a.output,"episodes",len(p["loads"])*len(p["layouts"])*len(p["taskSeeds"])*len(p["policies"]))
if __name__=="__main__":main()
