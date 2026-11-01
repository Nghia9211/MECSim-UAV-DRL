"""Re-evaluate fixed baselines on the frozen mixed-v2 DEVELOPMENT seeds. No training."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import statistics
import shutil
import subprocess
import sys
import time
import torch

from .environment import ROOT
from .contact_environment import ContactEnv
from .contact_campaign import Predictor
from .joint_campaign import scenarios,evaluate_with_envs,import_metrics
from .mobile_environment import MobileEnv
from .mobile_run import save_json,snapshot
from .workload_protocol import load_seed_manifest
from .metric_recount import validate_recount

def policies():
    result=[(name,Predictor(name=name),0,None) for name in ("RR","DISCONNECTED_RR","CONTACT_GREEDY")]
    for name,pair in (
        ("RR_DELIVERY_RISK_EDF",("DELIVERY_AWARE","RISK_EDF")),
        ("RR_DEADLINE_RISK_EDF",("DEADLINE_ENERGY","RISK_EDF")),
        ("RR_DELIVERY_RISK_SPT",("DELIVERY_AWARE","RISK_SPT")),
        ("RR_DELIVERY_AGING",("DELIVERY_AWARE","FEASIBLE_AGING")),
        ("RR_ALL_LOCAL_EDF",("ALL_LOCAL","EDF")),
        ("RR_ALL_UAV_FIFO",("ALL_UAV","FIFO"))):
        result.append((name,None,0,pair))
    return result

def cases(smoke=False):
    items=list(scenarios().items())[:1] if smoke else list(scenarios().items())
    for _,cfg in items:
        cfg.control_mode="contact_policy";cfg.workloadGenerator="mixed-v2"
    return items

def validate_inputs():
    seed_plan=load_seed_manifest()
    p=ROOT/"target/workload-v2-inputs-20261030"
    manifest=json.loads((p/"manifest.json").read_text())
    verification=json.loads((p/"verification.json").read_text())
    assert verification["status"]=="PASS"
    assert manifest["seed_manifest_sha256"]==seed_plan["sha256"]
    expected={(c["load"],c["seed"]):c["sha256"] for c in manifest["cases"] if c["split"]=="development"}
    return seed_plan,expected

def write_report(out):
    metrics=import_metrics()
    summary=metrics.read(out/"core-metrics-summary.csv")
    rows=metrics.read(out/"core-metrics-episodes.csv")
    m=json.loads((out/"manifest.json").read_text())
    def f(x,scale=1):
        return "NA" if x in (None,"") else f"{float(x)*scale:.3f}"
    lines=["# Baseline mixed-v2: development rerun","",
        "Generator mixed-v2; source workload costs, deadlines, power, radio and geometry unchanged.",
        "Development seeds only. Validation/evaluation partitions were not used for algorithm outcomes.",
        f"Completed {m['episodes']} audited episodes = {len(m['policies'])} policies x {len(m['scenarios'])} scenarios x {len(m['task_seeds'])} task seeds.",
        "Same normalized layout42 scaled to250/800m; shared source pools, not real-device calibrated inference.",
        "All differences below are descriptive, not a statistical-significance or unseen-layout claim.","",
        "| Policy | Compute DVR % | Delivered DVR % | J/on-time image | J/on-time delivered | Completed mean/P95 s | Restricted UAV s | Censored/cases |",
        "|---|---:|---:|---:|---:|---|---:|---|"]
    for r in summary:
        if r["scenario"]!="ALL":continue
        values=[r["policy"],f(r["image_dvr"],100),f(r["delivered_image_dvr"],100),f(r["j_per_ontime_image"]),
            f(r["j_per_delivered_ontime_image"]),f(r["mean_image_latency_s"])+"/"+f(r["mean_episode_p95_s"]),
            f(r["mean_restricted_uav_lifetime_s"]),r["censored_cases"]+"/"+r["cases"]]
        lines.append("| "+" | ".join(values)+" |")
    lines+=["","Mean/P95 above concern completed images; P95 is mean of per-episode nearest-rank P95, not a pooled percentile.",
        "J/image is whole-system ratio-of-sums; drops and zero-success episodes are retained. Horizon600s survivors are right-censored.",
        "See core-metrics-summary.csv for every scenario, background DVR, counts, total/UAV energy and delivery latency.",
        "RR, DISCONNECTED_RR and CONTACT_GREEDY use DELIVERY_AWARE+EDF. RISK/AGING rows use fixed RR service.",
        "ALL_LOCAL still pays the common UAV mobility/hover costs: it is a routing baseline, not a no-UAV system.",
        "Risk policies have risk-drop capability; the contact heuristics use ordinary EDF. This is not an equal scheduler-action-space ablation.",
        "Historical tables use other generator/seed combinations: do not interpret their difference from this table as an algorithm improvement.",
        "DQN/PPO checkpoints were not retrained or included. The paper lifetime branch is unchanged.","",
        "## Per-scenario delivered DVR (%)","",
        "| Scenario | CONTACT_GREEDY | DISCONNECTED_RR | RR + DELIVERY/RISK_EDF |",
        "|---|---:|---:|---:|"]
    index={(r["scenario"],r["policy"]):r for r in summary}
    for name in m["scenarios"]:
        lines.append("| "+name+" | "+" | ".join(f(index[name,p]["delivered_image_dvr"],100)
            for p in ("CONTACT_GREEDY","DISCONNECTED_RR","RR_DELIVERY_RISK_EDF"))+" |")
    lines+=["","Runtime is end-to-end Python/Java episode plus CSV saving; audit time is separate, JVM/pool startup excluded.",
        "See runtime-summary.csv; these are host runtimes, not deployment decision latencies."]
    (out/"REPORT.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def run(out,smoke=False):
    seeds,expected=validate_inputs()
    task_seeds=seeds["development"][:1] if smoke else seeds["development"]
    configs=cases(smoke);defs=policies()
    out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1)
    m=dict(schema="workload-v2-baselines-v1",trace_format="gym-mobile-v1",status="RUNNING",
        smoke=smoke,partition="development",workloadGenerator="mixed-v2",task_seeds=task_seeds,
        seed_manifest_sha256=seeds["sha256"],policies=[p[0] for p in defs],
        scenarios={n:asdict(c) for n,c in configs},expected_episodes=len(defs)*len(configs)*len(task_seeds),
        protocol=dict(json.loads((ROOT/"PureEdgeSim/uav/offloading/mobile-protocol.json").read_text()),
                      workloadGenerator="mixed-v2",allowContactWait=True),
        base_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        training=False,source_holdout=False,unseen_layout=False,
        note="New development baseline table after seed repair. Costs/deadlines still uncalibrated; no PPO retraining.")
    m["source_sha256"]=snapshot(out)
    shutil.copy2(ROOT/"drl/workload_v2_seed_manifest.json",out/"seed-manifest.json")
    save_json(out/"manifest.json",m)
    started=time.monotonic()
    try:
        with ContactEnv() as env,MobileEnv() as fixed:
            proof=evaluate_with_envs(out,smoke,env,fixed,policy_override=defs,case_override=configs,seed_override=task_seeds)
        assert proof["traces"]==m["expected_episodes"]
        metrics=import_metrics()
        original=metrics.read(out/"core-metrics-episodes.csv")
        assert len(original)==m["expected_episodes"]
        expected_keys={(n,s,p[0]) for n,_ in configs for s in task_seeds for p in defs}
        assert {(r["scenario"],int(r["seed"]),r["policy"]) for r in original}==expected_keys
        common={}
        for r in original:
            cfg=m["scenarios"][r["scenario"]];load="light" if cfg["imageRate"]==.08 else "overload"
            key=(load,cfg["estimateError"],int(r["seed"]))
            assert common.setdefault(key,r["workload_sha256"])==r["workload_sha256"]
            if cfg["estimateError"]==0:
                assert r["workload_sha256"]==expected[load,int(r["seed"])],"Preflight/runtime workload mismatch"
        metrics.write_csv(out/"episodes.csv",original)
        runtimes=[]
        for policy in m["policies"]:
            group=[r for r in original if r["policy"]==policy]
            runtimes.append(dict(policy=policy,episodes=len(group),
                mean_episode_save_s=statistics.mean(float(r["simulation_wall_s"]) for r in group),
                p95_episode_save_s=metrics.p95([float(r["simulation_wall_s"]) for r in group]),
                mean_audit_s=statistics.mean(float(r["audit_wall_s"]) for r in group)))
        metrics.write_csv(out/"runtime-summary.csv",runtimes)
        proof["source_unchanged"]=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in m["source_sha256"].items())
        assert proof["source_unchanged"]
        proof.update(preflight_workloads_matched=True,partition="development",training=False,
                     heuristic_actions_replayed=True,checkpoint_actions_replayed=None)
        m.update(status="COMPLETE",episodes=proof["traces"])
        save_json(out/"verification.json",proof);save_json(out/"manifest.json",m)
        # Recount with the mandatory standalone exporter AFTER independent trace audits.
        subprocess.run([sys.executable,str(ROOT/"scripts/offloading_metrics.py"),str(out)],cwd=ROOT,check=True)
        recounted=metrics.read(out/"core-metrics-episodes.csv")
        comparison=validate_recount(original,recounted)
        save_json(out/"metric-recount-verification.json",comparison)
        proof.update(standalone_exporter_recount=True,metric_recount=comparison)
        save_json(out/"verification.json",proof)
        m["elapsed_s"]=time.monotonic()-started;save_json(out/"manifest.json",m)
        write_report(out)
    except BaseException as exc:
        m.update(status="FAILED",error=repr(exc));save_json(out/"manifest.json",m);raise
    print("MIXED_V2_BASELINES_COMPLETE_AND_VERIFIED",out,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--smoke",action="store_true");args=p.parse_args()
    run(args.output.resolve(),args.smoke)
