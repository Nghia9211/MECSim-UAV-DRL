"""P1 development study: validation-only weight selection, paired P0 cases, ablations.

python -m drl.service_experiment --output target/p1-new
No training, no final test, no oracle task samples. Refuses output overwrites.
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import itertools
import json
from pathlib import Path
import platform
import statistics
import time

import numpy as np
import torch

from .diagnostics import Policy
from .environment import DATASET_PROPERTIES, EnvConfig, PaperEnv
from .run import snapshot, write_csv
from .service_policy import ServiceOptions, ServicePolicy, VARIANTS

TUNED=VARIANTS[:5]
BASELINES=("OLDEST_DATA","ROUND_ROBIN","RANDOM")


def episode(env, name, weights, layout, task, mode="legacy", shift=0, trace=None, decisions=None, case_id=""):
    obs,info=env.reset(seed=task,options=dict(layout_seed=layout,task_seed=task,scenario_mode=mode,
                       shift_seed=shift,decision_state=True,trace=trace is not None))
    initial=info["decision_state"]
    policy=Policy(name,task) if name in BASELINES else ServicePolicy(name,ServiceOptions(**weights),seed=task+2)
    actions=[]; refreshes=0; fallbacks=0; errors=0; tp=fp=fn=tn=0; duration_error=energy_error=0.
    wall_start=time.perf_counter_ns()
    while True:
        t0=time.perf_counter_ns();packet=env.service_estimates();t1=time.perf_counter_ns()
        action=policy.choose(obs) if name in BASELINES else policy.choose(packet)
        t2=time.perf_counter_ns()
        pred=packet["candidates"][action]
        before=info["decision_state"]
        obs,_,terminated,truncated,info=env.step(action)
        after=info["decision_state"]
        actual=[d["data_age_slots"]==0 for d in after["devices"]]
        refreshes+=sum(actual);actions.append(action)
        for a,p in zip(actual,pred["delivered"],strict=True):
            tp+=int(a and p);fp+=int(not a and p);fn+=int(a and not p);tn+=int(not a and not p)
            errors+=int(a!=p)
        actual_time=after["time_s"]-before["time_s"]
        actual_energy=before["uav"]["battery_j"]-after["uav"]["battery_j"]
        duration_error+=abs(pred["duration_s"]-actual_time)
        energy_error+=abs(pred["uav_energy_j"]-actual_energy)
        fallback=getattr(policy,"last_reason","").startswith("NO_POSITIVE")
        fallbacks+=fallback
        if decisions is not None:
            # Forecast RPC is diagnostic-only for baselines/urgency/nearest. Do not charge it to their policy.
            needs_estimator=name in TUNED
            decisions.append(dict(case_id=case_id,policy=name,slot=info["slots"],action=action,
                estimator_rpc_us=(t1-t0)/1000,selection_us=(t2-t1)/1000,
                operational_policy_us=((t2-t0) if needs_estimator else (t2-t1))/1000,
                forecast_required=needs_estimator,fallback=fallback,predicted_duration_s=pred["duration_s"],
                actual_duration_s=actual_time,predicted_uav_j=pred["uav_energy_j"],actual_uav_j=actual_energy,
                completion_errors=sum(a!=p for a,p in zip(actual,pred["delivered"]))))
        if terminated or truncated:break
    wall_ms=(time.perf_counter_ns()-wall_start)/1e6
    if trace is not None:env.save_trace(trace)
    battery_j=initial["uav"]["battery_j"]-after["uav"]["battery_j"]+sum(
        a["battery_j"]-b["battery_j"] for a,b in zip(initial["devices"],after["devices"],strict=True))
    return dict(policy=name,layout_seed=layout,task_seed=task,mode=mode,shift_seed=shift,
        slots=info["slots"],seconds=info["seconds"],reason=info["reason"],truncated=truncated,
        battery_energy_j=battery_j,age_refreshes=refreshes,uav_compute_j=info["uav_compute_j"],
        images_submitted=info["images_submitted"],images_delivered=info["images_delivered"],
        delivered_latency_s=info["mean_delivered_latency_s"],fallbacks=fallbacks,
        completion_errors=errors,tp=tp,fp=fp,fn=fn,tn=tn,
        duration_absolute_error_s=duration_error,uav_energy_absolute_error_j=energy_error,
        wall_ms_with_diagnostic_rpc=wall_ms,actions=" ".join(map(str,actions)))


def aggregate(rows, keys):
    groups={}
    for r in rows:groups.setdefault(tuple(r[k] for k in keys),[]).append(r)
    out=[]
    for key,g in groups.items():
        slots=sum(r["slots"] for r in g);updates=sum(r["age_refreshes"] for r in g)
        submitted=sum(r["images_submitted"] for r in g)
        out.append(dict(zip(keys,key),episodes=len(g),mean_slots=statistics.mean(r["slots"] for r in g),
            mean_seconds=statistics.mean(r["seconds"] for r in g),mean_battery_j=statistics.mean(r["battery_energy_j"] for r in g),
            battery_j_per_refresh=sum(r["battery_energy_j"] for r in g)/updates if updates else None,
            image_delivery_fraction=sum(r["images_delivered"] for r in g)/submitted if submitted else None,
            age_failures=sum("DATA_AGE" in r["reason"] for r in g),battery_failures=sum("BATTERY" in r["reason"] for r in g),
            truncated=sum(r["truncated"] for r in g),fallback_fraction=sum(r["fallbacks"] for r in g)/slots,
            completion_error_fraction=sum(r["completion_errors"] for r in g)/(12*slots),
            duration_mae_s=sum(r["duration_absolute_error_s"] for r in g)/slots,
            uav_energy_mae_j=sum(r["uav_energy_absolute_error_j"] for r in g)/slots))
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(1)
    protocol=json.loads(Path(__file__).with_name("protocol_p0.json").read_text())
    study=dict(schema="service-study-v1",status="RUNNING",validation_layouts=list(range(1100000,1100005)),
        validation_tasks=[1200000,1200001],grid=[0.,.1,1.],selection="max mean validation slots; ties smallest energy then time weight",
        development_protocol=protocol,variants=list(VARIANTS),baselines=list(BASELINES),
        forecast="point forecast at mean payload/MI of declared shared source pool; no sample access",
        primary="lifetime slots at cap600",seed_units="paired development cases; no independent training seeds",
        python=platform.python_version(),cpu=platform.processor(),torch_threads=1,
        energy="UAV plus unpowered-device battery draw; excludes grid energy",
        timing="operational policy includes forecast RPC for estimator-based variants; excludes diagnostic-only RPC for others; excludes env.step/reset/trace")
    (out/"protocol.json").write_text(json.dumps(study,indent=2));snapshot(out)
    selections={};validation=[];gridrows=[];evalrows=[];decisions=[];priors={};started=time.monotonic()
    for workload in protocol["workloads"]:
        config=EnvConfig(decision_state=True,properties=dict(DATASET_PROPERTIES) if workload=="datasets" else {})
        with PaperEnv(config) as env:
            env.reset(seed=0);priors[workload]=env.service_estimates()["prior"]
            selections[workload]={}
            for variant in TUNED:
                grid=list(itertools.product([0.] if variant=="NO_ENERGY" else study["grid"],
                                            [0.] if variant=="NO_TIME" else study["grid"]))
                scores=[]
                for e,t in grid:
                    weights=dict(energy_weight=e,time_weight=t);batch=[]
                    for layout in study["validation_layouts"]:
                        for task in study["validation_tasks"]:
                            row=episode(env,variant,weights,layout,task)
                            row.update(workload=workload,**weights);batch.append(row);validation.append(row)
                    score=statistics.mean(r["slots"] for r in batch)
                    gridrows.append(dict(workload=workload,policy=variant,**weights,mean_slots=score,episodes=len(batch)))
                    scores.append((score,-e,-t,weights))
                selected=max(scores,key=lambda r:r[:3]);selections[workload][variant]=selected[3]
                write_csv(out/"validation.csv",validation);write_csv(out/"validation-grid.csv",gridrows)
                print(f"validation {workload} {variant}: {selected[3]}, slots={selected[0]:.3f}",flush=True)
            # Freeze weights BEFORE reading development outcomes for this workload.
            (out/"selected.json").write_text(json.dumps(selections,indent=2))
            for mode in protocol["modes"]:
                for shift in ([0] if mode=="legacy" else protocol["shift_seeds"]):
                    for task in protocol["task_seeds"]:
                        case=f"{workload}-{mode}-{shift}-{task}"
                        for name in [*BASELINES,*VARIANTS]:
                            trace=(out/"traces"/case/name) if task==protocol["task_seeds"][0] and shift in (0,protocol["shift_seeds"][0]) and name in ("SERVICE_AWARE","OLDEST_DATA") else None
                            row=episode(env,name,selections[workload].get(name,{}),protocol["base_layout_seed"],task,mode,shift,trace,decisions,case)
                            row.update(workload=workload);evalrows.append(row)
                write_csv(out/"episodes.csv",evalrows)
                print(f"development {workload} {mode} done",flush=True)
    references={(r["workload"],r["mode"],r["shift_seed"],r["task_seed"]):r for r in evalrows if r["policy"]=="OLDEST_DATA"}
    for r in evalrows:
        ref=references[r["workload"],r["mode"],r["shift_seed"],r["task_seed"]]
        r["delta_slots_vs_oldest"]=r["slots"]-ref["slots"]
    write_csv(out/"episodes.csv",evalrows);write_csv(out/"summary.csv",aggregate(evalrows,["workload","policy"]))
    write_csv(out/"by-mode.csv",aggregate(evalrows,["workload","mode","policy"]))
    write_csv(out/"decisions.csv",decisions)
    timing=[]
    for name in [*BASELINES,*VARIANTS]:
        # Exclude first two decisions in each episode as warm-up; data remains in raw CSV.
        g=[r for r in decisions if r["policy"]==name and r["slot"]>2]
        for key in ["operational_policy_us","estimator_rpc_us","selection_us"]:
            values=[r[key] for r in g]
            timing.append(dict(policy=name,metric=key,n=len(values),median_us=float(np.median(values)),p95_us=float(np.percentile(values,95))))
    write_csv(out/"timing.csv",timing)
    (out/"priors.json").write_text(json.dumps(priors,indent=2))
    study.update(status="COMPLETE",validation_episodes=len(validation),development_episodes=len(evalrows),elapsed_s=time.monotonic()-started)
    (out/"manifest.json").write_text(json.dumps(study,indent=2))
    print(f"P1 complete: validation={len(validation)}, development={len(evalrows)}; {out}",flush=True)


if __name__=="__main__":main()
