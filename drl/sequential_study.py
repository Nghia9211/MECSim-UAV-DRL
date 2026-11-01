"""Sequential calibrated study: prepare stage1, verify/review it, then prepare mobile stage2."""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from workload_rng import verify_rows,read
from .workload_protocol import load_seed_manifest

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False),encoding="utf-8")
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
def write_rows(path,rows):
    with Path(path).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def prepare_stage1(path,smoke=False):
    if path.exists():raise ValueError("Protocol exists")
    calpath=ROOT/"docs/calibration/workstation-cpu-20261101/calibration.json"
    cal=json.loads(calpath.read_text());fit=cal["fit"]
    plan=load_seed_manifest()
    p=json.loads((ROOT/"PureEdgeSim/uav/offloading/mobile-protocol.json").read_text())
    p.update(studyStage="hover",studySchema="sequential-study-v1",workloadGenerator="mixed-v2",
        taskSeeds=plan["development"][:1] if smoke else plan["development"],smoke=smoke,
        seedManifestSha256=plan["sha256"],calibrationSource=str(calpath.relative_to(ROOT)),
        calibrationSha256=sha(calpath),computeCalibrationId=cal["calibration_id"],
        localMips=fit["localMips"],uavMips=fit["uavMips"],imageFixedMi=fit["imageFixedMi"],
        imageRate=.24,estimateError=0,slantDistanceMetres=10,referenceSlantMetres=10,
        horizonSeconds=600,arrivalWindowSeconds=300,uavBatteryJ=1600000,devices=12,
        layouts=[dict(name="hover")],policies=["ALL_UAV__"+s for s in ("FIFO","EDF","SPT","PRIORITY")])
    source=read(ROOT/"target/workload-v2-inputs-20261030/source-pools/alibaba-pool.csv")
    bgmean=statistics.mean((float(r["end_s"])-float(r["start_s"]))*float(r["plan_cpu"])/100*p["referenceMips"]*p["backgroundWorkScale"]/p["uavMips"] for r in source)
    p["backgroundSourcePoolSha256"]=sha(ROOT/"target/workload-v2-inputs-20261030/source-pools/alibaba-pool.csv")
    p["backgroundServiceMeanSecondsProxy"]=bgmean;p["loads"]=[]
    for rho in (.3,.6,.9,1.2):
        for name,scale in (("tight",.5),("reference",1),("relaxed",2)):
            p["loads"].append(dict(name=f"rho{int(rho*100):03d}-{name}",targetRho=rho,imageRate=.24,
                backgroundRate=(rho-.24*fit["fitted_uav_seconds"])/bgmean,
                criticalDeadlineSeconds=20*scale,imageDeadlineSeconds=60*scale))
    path.parent.mkdir(parents=True,exist_ok=True);save(path,p)
    print("STAGE1_PROTOCOL",path,"episodes",len(p["loads"])*len(p["taskSeeds"])*4)

def queue_diagnostic(jobs,outcomes,cfg,window):
    airborne=[k for k,o in outcomes.items() if o["route"] in ("UAV","BACKGROUND")]
    def finite(o,key):
        try:return math.isfinite(float(o[key]))
        except (ValueError,KeyError):return False
    starts=[(float(outcomes[k]["start_s"]),k) for k in airborne if finite(outcomes[k],"start_s")]
    opportunities=[]
    for at,chosen in starts:
        ready=[k for k in airborne if float(jobs[k]["arrival_s"])<=at+1e-8 and
            float(outcomes[k]["ready_s"])<=at+1e-8 and float(jobs[k]["deadline_s"])>at+1e-8 and
            float(outcomes[k]["resolved_s"])>=at-1e-8 and (k==chosen or not finite(outcomes[k],"start_s") or float(outcomes[k]["start_s"])>at+1e-8)]
        opportunities.append(len(ready))
    images=[k for k in airborne if jobs[k]["source"]=="RESCUENET"]
    completed=[k for k in images if outcomes[k]["status"].startswith("COMPLETED")]
    waits=[float(outcomes[k]["start_s"])-float(outcomes[k]["ready_s"]) for k in completed]
    busy=sum(max(0,min(window,float(outcomes[k]["resolved_s"]))-max(0,at)) for at,k in starts)
    intrinsic=sum(float(outcomes[k]["ready_s"])-float(jobs[k]["arrival_s"])+float(jobs[k]["actual_mi"])/cfg["uavMips"]>
        float(jobs[k]["deadline_s"])-float(jobs[k]["arrival_s"])+1e-8 for k in images)
    return dict(uav_dispatches=len(starts),multi_ready_dispatches=sum(x>=2 for x in opportunities),
        max_ready=max(opportunities,default=0),uav_busy_fraction_arrival_window=busy/window,
        uav_routed_offered_work_per_window=sum(float(jobs[k]["actual_mi"])/cfg["uavMips"] for k in airborne)/window,
        completed_uav_images=len(completed),completed_image_mean_queue_wait_s=statistics.mean(waits) if waits else None,
        isolated_infeasible_offloaded_images=intrinsic,uav_offloaded_images=len(images))

def verify_study(root):
    root=Path(root);m=json.loads((root/"manifest.json").read_text());p=m["protocol"]
    if m["status"]!="COMPLETE":raise ValueError("Incomplete simulation")
    seeds=load_seed_manifest()
    partition=p.get("taskSeedPartition","development")
    if partition not in ("development","validation","evaluation"):raise ValueError("Unknown partition")
    if p["seedManifestSha256"]!=seeds["sha256"] or p["taskSeeds"]!=(seeds[partition][:1] if p["smoke"] else seeds[partition]):
        raise ValueError("Study seeds/partition drift")
    if partition!="development":
        from .heldout_admission import validate_lock,check_geometry
        validate_lock(p)
        for cfg in m["configs"].values():check_geometry(p,cfg)
    if sha(root/"source/study-protocol.json")!=m["protocol_sha256"]:raise ValueError("Protocol snapshot drift")
    if sha(root/"source/calibration.json")!=p["calibrationSha256"]:raise ValueError("Calibration drift")
    for name,h in m["source_sha256"].items():
        if sha(root/"source"/name)!=h:raise ValueError("Source snapshot drift "+name)
    fixed=module("study_fixed_audit","verify-uav-offloading.py")
    mobile=module("study_mobile_audit","verify-uav-mobile.py")
    images=read(root/"source-pools/rescuenet-pool.csv");bg=read(root/"source-pools/alibaba-pool.csv")
    if sha(root/"source-pools/alibaba-pool.csv")!=p["backgroundSourcePoolSha256"]:raise ValueError("Background pool changed")
    rows=read(root/"episodes.csv")
    expected={(scenario,seed,policy) for scenario in m["configs"] for seed in p["taskSeeds"] for policy in m["policies"]}
    if len(rows)!=3*len(expected) or m["episodes"]!=len(expected):raise ValueError("Count mismatch")
    grouped={}
    for r in rows:grouped.setdefault((r["scenario"],int(r["seed"]),r["policy"]),[]).append(r)
    if set(grouped)!=expected:raise ValueError("Missing/extra episode")
    diagnostics=[];tasks=0;paired={};source_hashes={};route_hashes={};last=None
    for index,(key,summary) in enumerate(grouped.items()):
        scenario,seed,policy=key;cfg=m["configs"][scenario];directory=root/scenario/f"seed-{seed}"
        if (scenario,seed)!=last:
            jobs_list=read(directory/"workload.csv");jobs={int(r["id"]):r for r in jobs_list}
            if len(jobs)!=len(jobs_list):raise ValueError("Duplicate job IDs")
            wp=dict(p,**cfg["load"]);verify_rows(jobs_list,images,bg,wp,seed)
            digest=sha(directory/"workload.csv");last=(scenario,seed)
        if any(r["workload_sha256"]!=digest for r in summary):raise ValueError("Workload digest")
        if paired.setdefault((scenario,seed),digest)!=digest:raise ValueError("Unpaired policy workload")
        outcomes_list=read(directory/(policy+"-tasks.csv"));outcomes={int(r["id"]):r for r in outcomes_list}
        if len(outcomes)!=len(jobs) or len(outcomes)!=len(outcomes_list) or set(jobs)!=set(outcomes):raise ValueError("Outcome IDs")
        energies=read(directory/(policy+"-energy.csv"));parts=policy.split("__")
        if m["study_stage"]=="hover":
            audit=fixed.Audit(jobs,outcomes,energies,cfg,parts[1],.75)
            if "BG_CAP" in parts[1]:audit.background_cap_seconds=cfg["load"]["backgroundBudgetSeconds"]
            audit.verify(read(directory/(policy+"-decisions.csv")),parts[0])
        else:
            audit=mobile.MobileAudit(jobs,outcomes,energies,cfg,parts[2],p,
                *[read(directory/(policy+"-"+suffix+".csv")) for suffix in ("visits","positions","coverage","updates","views")])
            if "BG_CAP" in parts[2]:audit.background_cap_seconds=cfg["load"]["backgroundBudgetSeconds"]
            selector=parts[0]
            if selector=="STATIC_FIRST":
                selector={float(v["at_s"]):min(d for d in range(len(cfg["devices"])) if audit.alive(d,float(v["at_s"]))) for v in audit.visits}
            audit.verify_mobile(selector,read(directory/(policy+"-decisions.csv")),parts[1])
            if parts[1]=="ALL_UAV":
                group=(scenario,seed,parts[0])
                geometry_digest=sha(directory/(policy+"-visits.csv"))
                if route_hashes.setdefault(group,geometry_digest)!=geometry_digest:
                    raise ValueError("Scheduler altered ALL_UAV service trajectory")
        if {r["source"] for r in summary}!={"ALL","RESCUENET","ALIBABA"}:raise ValueError("Source summary keys")
        for r in summary:
            os=[o for k,o in outcomes.items() if r["source"]=="ALL" or jobs[k]["source"]==r["source"]]
            if int(r["offered"])!=len(os) or int(r["on_time"])!=sum(o["status"]=="COMPLETED_ON_TIME" for o in os):raise ValueError("Summary count drift")
        diagnostic=queue_diagnostic(jobs,outcomes,cfg,p["arrivalWindowSeconds"])
        runtime=json.loads((directory/(policy+"-runtime.json")).read_text())
        scheduling=runtime["scheduling_ns"]
        diagnostic.update(scenario=scenario,seed=seed,policy=policy,workload_sha256=digest,
            scheduling_calls=len(scheduling),scheduling_mean_us=statistics.mean(scheduling)/1000 if scheduling else None,
            scheduling_p95_us=sorted(scheduling)[math.ceil(.95*len(scheduling))-1]/1000 if scheduling else None,
            episode_wall_ms=runtime["episode_wall_ms"])
        diagnostics.append(diagnostic);tasks+=len(jobs)
        if index%120==0:print("AUDITED",index+1,"/",len(expected),flush=True)
    proof=dict(status="PASS",episodes=len(expected),task_outcomes=tasks,paired_cases=len(paired),
        seed_partition=partition,independent_input_and_dispatch_replay=True,
        independent_physics_energy_and_routing_replay=True,unchanged_all_uav_trajectories_across_schedulers=True,
        calibration_status=m["calibration_status"],training=False)
    save(root/"verification.json",proof);write_rows(root/"queue-diagnostics.csv",diagnostics)
    # Mandatory standalone exporter is called after this verifier in the CLI.
    return proof

def paired_statistics(root):
    metrics=read(root/"core-metrics-episodes.csv")
    result=[]
    import numpy as np
    for scenario in sorted({r["scenario"] for r in metrics}):
        subset=[r for r in metrics if r["scenario"]==scenario];policies={r["policy"] for r in subset}
        for policy in sorted(policies):
            prefix="__".join(policy.split("__")[:-1]);baseline=prefix+"__FIFO"
            if policy==baseline or baseline not in policies:continue
            a={r["seed"]:r for r in subset if r["policy"]==baseline};b={r["seed"]:r for r in subset if r["policy"]==policy}
            if set(a)!=set(b):raise ValueError("Unpaired statistics")
            seeds=sorted(a);field="delivered_image_dvr" if "delivered_image_dvr" in subset[0] else "image_dvr"
            delta=np.array([float(a[s][field])-float(b[s][field]) for s in seeds])
            rng=np.random.default_rng(20261101);indices=rng.integers(0,len(seeds),size=(2000,len(seeds)))
            draws=delta[indices].mean(axis=1)
            result.append(dict(scenario=scenario,baseline=baseline,candidate=policy,metric=field,
                cases=len(seeds),mean_dvr_reduction=float(delta.mean()),paired_bootstrap_95_low=float(np.quantile(draws,.025)),
                paired_bootstrap_95_high=float(np.quantile(draws,.975)),bootstrap_resamples=2000,
                interpretation="exploratory paired interval; no confirmatory multiplicity-adjusted test"))
    if result:write_rows(root/"paired-statistics.csv",result)
    return result

def review_stage1(root):
    root=Path(root);m=json.loads((root/"manifest.json").read_text());v=json.loads((root/"verification.json").read_text())
    if m["study_stage"]!="hover" or m["protocol"]["smoke"] or v["status"]!="PASS":raise ValueError("Full verified stage1 required")
    diagnostics=read(root/"queue-diagnostics.csv");metrics=read(root/"core-metrics-summary.csv")
    dispatches=sum(int(r["uav_dispatches"]) for r in diagnostics)
    choices=sum(int(r["multi_ready_dispatches"]) for r in diagnostics)
    intrinsic=sum(int(r["isolated_infeasible_offloaded_images"]) for r in diagnostics)
    if len(diagnostics)!=1440 or intrinsic!=0:raise ValueError("Stage1 intrinsic feasibility/count gate failed")
    review=dict(status="PASS",stage1_run=str(root),stage1_verification_sha256=sha(root/"verification.json"),
        simulation_manifest_sha256=sha(root/"manifest.json"),stage1_episodes=1440,
        allow_stage2=choices>0,dispatches=dispatches,multi_ready_dispatches=choices,
        multi_ready_dispatch_fraction=choices/dispatches if dispatches else 0,
        isolated_infeasible_offloaded_images=intrinsic,
        conclusion="Measurement valid; scheduling opportunities exist. Mobile stage needs fixed trajectory/route controls.",
        limitations=["Provisional random-weight architecture compute; synthetic deadlines/power",
            "Alibaba CPU proxy and shared source pools, development seeds only",
            "No RL training, no novelty or real energy/lifetime claim"],
        stage2_adjustments=["Keep four schedulers under ALL_UAV to isolate ordering with audited identical service trajectories",
            "Add STATIC_FIRST against ROUND_ROBIN, reference deadline only, two area scales",
            "Use heavy offered loads rho0.9 and1.2; actual UAV load falls when images run locally",
            "DELIVERY_AWARE+EDF is a separate routing arm, not an order-only comparison",
            "Use same radio/whole JPEG/compute; report radio-infeasible offloads, coverage vs delivery separately"])
    save(root/"STAGE1_REVIEW.json",review)
    return review

def report(root):
    root=Path(root);m=json.loads((root/"manifest.json").read_text())
    summary=read(root/"core-metrics-summary.csv");diag=read(root/"queue-diagnostics.csv");stats=paired_statistics(root)
    fmt=lambda x:"NA" if x in ("",None) else f"{float(x):.3f}"
    lines=[f"# Sequential study: {m['study_stage']}","",
        f"Completed and independently verified {m['episodes']} episodes, {m.get('partition','development')} seeds only.",
        "Provisional architecture timing/random weights. Synthetic deadlines and power; Alibaba CPU proxy. No RL training.",
        "Completed-only latency must be read with DVR; horizon survivors are censored, not observed lifetime exhaustion.","",
        "| Policy | Image DVR % | J/on-time image | Mean/P95 s | Background DVR % | Censored/cases |",
        "|---|---:|---:|---:|---:|---|"]
    for r in summary:
        if r["scenario"]!="ALL":continue
        lines.append(f"| {r['policy']} | {100*float(r['image_dvr']):.3f} | {fmt(r['j_per_ontime_image'])} | {fmt(r['mean_image_latency_s'])}/{fmt(r['mean_episode_p95_s'])} | {100*float(r['background_dvr']):.3f} | {r['censored_cases']}/{r['cases']} |")
    lines+=["","Per-scenario core-metrics-summary.csv and paired-statistics.csv retain load/deadline effects.",
        "Intervals are exploratory, paired by seed; no multiple-testing-adjusted confirmatory significance claim.",
        "queue-diagnostics.csv reports CPU busy fraction over the arrival window and actual multi-ready dispatch opportunities.",
        "Scheduling runtime records measured selection calls, not entire episode time; pure host timings, no deployment claim."]
    if m["study_stage"]=="mobile":
        lines+=["","ALL_UAV still falls back to local outside contact. Only its within-selector scheduler comparison has audited identical service trajectories.",
            "DELIVERY_AWARE+EDF changes routing: treat it as a separate arm. STATIC_FIRST chooses ID0 before seeing tasks and is not an optimized placement.",
            "Read delivered DVR/energy separately from compute DVR in CORE_METRICS.md. Layout42 at two scales is not unseen-layout evaluation."]
    (root/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def prepare_stage2(stage1,path,smoke=False):
    review_path=stage1/"STAGE1_REVIEW.json";review=json.loads(review_path.read_text())
    if review["status"]!="PASS" or not review["allow_stage2"]:raise ValueError("Stage1 gate not passed")
    if sha(stage1/"verification.json")!=review["stage1_verification_sha256"] or sha(stage1/"manifest.json")!=review["simulation_manifest_sha256"]:
        raise ValueError("Stage1 gate stale")
    if path.exists():raise ValueError("Stage2 protocol exists")
    p=json.loads((stage1/"manifest.json").read_text())["protocol"]
    p.update(studyStage="mobile",smoke=smoke,stage1Review=str(review_path.resolve()),
        stage1ReviewSha256=sha(review_path),layouts=[dict(name="compact",areaMetres=250),dict(name="wide",areaMetres=800)],
        allowContactWait=True,policies=[f"{sel}__ALL_UAV__{sched}" for sel in ("STATIC_FIRST","ROUND_ROBIN") for sched in ("FIFO","EDF","SPT","PRIORITY")]+
            [f"{sel}__DELIVERY_AWARE__EDF" for sel in ("STATIC_FIRST","ROUND_ROBIN")])
    p["taskSeeds"]=load_seed_manifest()["development"][:1] if smoke else load_seed_manifest()["development"]
    p["loads"]=[l for l in p["loads"] if l["targetRho"] in (.9,1.2) and l["name"].endswith("-reference")]
    path.parent.mkdir(parents=True,exist_ok=True);save(path,p)
    print("STAGE2_PROTOCOL",path,"episodes",len(p["loads"])*2*len(p["taskSeeds"])*10)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("prepare-stage1");a.add_argument("--output",type=Path,required=True);a.add_argument("--smoke",action="store_true")
    a=sub.add_parser("prepare-stage2");a.add_argument("--stage1",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--smoke",action="store_true")
    a=sub.add_parser("verify");a.add_argument("run",type=Path)
    a=sub.add_parser("review-stage1");a.add_argument("run",type=Path)
    args=parser.parse_args()
    if args.cmd=="prepare-stage1":prepare_stage1(args.output,args.smoke)
    elif args.cmd=="prepare-stage2":prepare_stage2(args.stage1,args.output,args.smoke)
    elif args.cmd=="verify":
        print(json.dumps(verify_study(args.run),indent=2))
        exporter=module("study_metrics","offloading_metrics.py");exporter.export(args.run);report(args.run)
        if json.loads((args.run/"manifest.json").read_text())["study_stage"]=="hover":
            print("Stage1 verified; review is a separate required step before preparing stage2.")
    elif args.cmd=="review-stage1":print(json.dumps(review_stage1(args.run),indent=2))
if __name__=="__main__":main()
