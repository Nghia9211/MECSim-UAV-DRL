"""P0 controlled development fixtures and frozen-policy checks. No training.

python -m drl.scenarios --output target/p0-new --runs result/target
Omit --runs to run only Oldest Data and Round Robin. Never opens final-test seeds.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import time

import torch
from stable_baselines3 import DQN

from .diagnostics import Policy, rollout, summarize
from .environment import DATASET_PROPERTIES, EnvConfig, PaperEnv, ROOT
from .run import snapshot, write_csv


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_fixture(base, changed, mode):
    allowed={"legacy":set(),"position":{"x_m","y_m"},
        "hardware_task":{"hardware","vision_task","local_rate_bytes_s","active_w","standby_w"},
        "capacity":{"capacity_j","battery_j"},"power":{"powered"},
        "connectivity":{"connected"},"outage":{"powered","connected"}}
    allowed["full"]=set.union(*allowed.values())
    assert {k:v for k,v in base.items() if k!="devices"} == {k:v for k,v in changed.items() if k!="devices"}
    differences=0
    for before,after in zip(base["devices"],changed["devices"],strict=True):
        assert before.keys()==after.keys()
        for key in before:
            if before[key]!=after[key]:
                assert key in allowed[mode], (mode,key)
                differences+=1
    assert sum(d["powered"] for d in base["devices"])==sum(d["powered"] for d in changed["devices"])
    assert sum(d["connected"] for d in base["devices"])==sum(d["connected"] for d in changed["devices"])
    return differences


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--runs",type=Path)
    args=p.parse_args();torch.set_num_threads(1)
    protocol_path=Path(__file__).with_name("protocol_p0.json")
    protocol=json.loads(protocol_path.read_text())
    models=[]
    if args.runs is not None:
        for run in sorted(args.runs.glob("drl-server-*")):
            if not (run/"best_model.zip").exists():continue
            config=json.loads((run/"config.json").read_text())
            assert config["algorithm"]=="DQN"
            models.append((f"DQN_s{config['seed']}",DQN.load(run/"best_model.zip",device="cpu"),
                dict(run=str(run),sha256=sha(run/"best_model.zip"),training_config=config)))
        if not models:raise ValueError("No DQN server checkpoints found")
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    snapshot(out)
    (out/"protocol.json").write_text(json.dumps(protocol,indent=2))
    manifest=dict(schema="p0-run-v1",protocol_sha256=sha(protocol_path),python=platform.python_version(),
        torch=torch.__version__,threads=1,checkpoint_provenance=[m[2] for m in models],
        note="Development only. Mixed-trained checkpoints on synthetic are workload-transfer probes, not synthetic-trained controls.",
        configurations={})
    rows=[];fixtures=[];start=time.monotonic()
    for workload in protocol["workloads"]:
        conf=EnvConfig(layout_seed=protocol["base_layout_seed"],powered=protocol["powered"],
            connected=protocol["connected"],max_slots=protocol["max_slots"],
            properties=dict(DATASET_PROPERTIES) if workload=="datasets" else {})
        manifest["configurations"][workload]=asdict(conf)
        with PaperEnv(conf) as env:
            _,info=env.reset(seed=0,options={"task_seed":protocol["task_seeds"][0],"decision_state":True})
            base=info["decision_state"]
            for mode in protocol["modes"]:
                for shift in ([0] if mode=="legacy" else protocol["shift_seeds"]):
                    options=dict(scenario_mode=mode,shift_seed=shift)
                    _,info=env.reset(seed=0,options={**options,"task_seed":protocol["task_seeds"][0],"decision_state":True})
                    decision=info["decision_state"]
                    differences=check_fixture(base,decision,mode)
                    fixture=out/"fixtures"/workload/f"{mode}-{shift}";fixture.mkdir(parents=True)
                    (fixture/"decision_state.json").write_text(json.dumps(decision,indent=2))
                    fixtures.append(dict(workload=workload,mode=mode,shift_seed=shift,changed_fields=differences,
                        untouched_fields_match=True,path=str(fixture)))
                    for task in protocol["task_seeds"]:
                        for name,model in [("OLDEST_DATA",None),("ROUND_ROBIN",None),*[(m[0],m[1]) for m in models]]:
                            trace=fixture/"trace" if task==protocol["task_seeds"][0] and name=="OLDEST_DATA" else None
                            row,_=rollout(env,Policy(name,task,model),conf.layout_seed,task,trace,
                                          reset_options=options)
                            for key in ["cap_slots","capped_work_items","trace"]:row.pop(key,None)
                            row.update(workload=workload,mode=mode,shift_seed=shift)
                            rows.append(row)
                write_csv(out/"episodes.csv",rows)
                print(f"completed {workload}: {mode}",flush=True)
    # Case-level differences to the same task sequence on unchanged layout42.
    references={(r["workload"],r["policy"],r["task_seed"]):r for r in rows if r["mode"]=="legacy"}
    for r in rows:
        ref=references[r["workload"],r["policy"],r["task_seed"]]
        r["delta_slots_vs_legacy"]=r["slots"]-ref["slots"]
        r["delta_seconds_vs_legacy"]=r["seconds"]-ref["seconds"]
    write_csv(out/"episodes.csv",rows)
    write_csv(out/"summary.csv",summarize(rows,["workload","mode","policy"]))
    write_csv(out/"fixture-checks.csv",fixtures)
    manifest.update(status="COMPLETE",episodes=len(rows),fixtures=len(fixtures),elapsed_s=time.monotonic()-start)
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(f"P0 complete: {len(fixtures)} fixtures; {len(rows)} episodes; {out}",flush=True)


if __name__=="__main__":main()
