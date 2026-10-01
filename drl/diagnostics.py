"""Reproducible week 1-2 diagnostics. No training and no checkpoint modification.

Run stages sequentially (do not benchmark while training/building):
python -m drl.diagnostics --output target/week12 --stage evaluate
Stages: evaluate, runtime, permutation, sensitivity, pilot. Outputs refuse overwrites.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import time

import numpy as np
import torch
from stable_baselines3 import DQN

from .environment import EnvConfig, PaperEnv, ROOT
from .run import write_csv, snapshot, train, evaluate

BASELINES = ("ROUND_ROBIN", "OLDEST_DATA", "RANDOM")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    import csv
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def permute_observation(obs, order):
    """order[new ID] = canonical physical ID; Java/workload never change labels."""
    return np.concatenate((obs[:12][order], obs[12:][order]))


class Policy:
    def __init__(self, name, seed, model=None, order=None):
        self.name, self.model = name, model
        self.rng, self.next_device = np.random.default_rng(seed + 2), 0
        self.order = order

    def choose(self, obs):
        if self.model is not None:
            viewed = obs if self.order is None else permute_observation(obs, self.order)
            action = int(self.model.predict(viewed, deterministic=True)[0])
            return action if self.order is None else int(self.order[action])
        if self.name == "RANDOM":
            return int(self.rng.integers(12))
        if self.name == "ROUND_ROBIN":
            action = self.next_device
            self.next_device = (action + 1) % 12
            return action
        if self.name == "OLDEST_DATA":
            order = [(self.next_device + k) % 12 for k in range(12)]
            action = max(order, key=lambda i: obs[12 + i])
            self.next_device = (action + 1) % 12
            return action
        raise ValueError(self.name)


def rollout(env, policy, layout_seed, task_seed, trace=None, measured=False, states=None):
    started = time.perf_counter_ns()
    obs, info = env.reset(seed=task_seed, options={"layout_seed": layout_seed,
        "task_seed": task_seed, "trace": trace is not None})
    reset_ns = time.perf_counter_ns() - started
    loop_start = time.perf_counter_ns()
    steps, actions, total_reward = [], [], 0.
    while True:
        if states is not None:
            states.append(obs.copy())
        before = time.perf_counter_ns()
        action = policy.choose(obs)
        selected = time.perf_counter_ns()
        previous_kernel = info.get("kernel_nanos", 0)
        obs, reward, terminated, truncated, info = env.step(action)
        after = time.perf_counter_ns()
        actions.append(action)
        total_reward += reward
        if measured:
            steps.append(dict(policy_ns=selected-before, bridge_step_ns=after-selected,
                              java_handlers_ns=info["kernel_nanos"]-previous_kernel))
        if terminated or truncated:
            break
    episode_ns = time.perf_counter_ns() - loop_start
    if trace is not None:
        env.save_trace(trace)
    row = dict(policy=policy.name, layout_seed=layout_seed, task_seed=task_seed,
        slots=info["slots"], seconds=info["seconds"], reward=total_reward, reason=info["reason"],
        truncated=truncated, uav_battery_j=info["uav_battery_j"],
        uav_compute_j=info["uav_compute_j"], images_submitted=info["images_submitted"],
        images_delivered=info["images_delivered"], cpu_submitted=info["cpu_submitted"],
        cpu_completed=info["cpu_completed"], mean_delivered_latency_s=info["mean_delivered_latency_s"],
        actions=" ".join(map(str, actions)))
    if measured:
        row.update(reset_ms=reset_ns/1e6, episode_no_reset_ms=episode_ns/1e6,
                   episode_with_reset_ms=(reset_ns+episode_ns)/1e6)
    if trace is not None:
        slots = read_csv(Path(trace)/"slots.csv")
        cap = float(env.config.properties.get("paper.slotCapSeconds", 600))
        row.update(cap_slots=sum(float(s["duration_s"]) >= cap-1e-6 for s in slots),
                   capped_work_items=sum(int(s["capped_work_items"]) for s in slots), trace=str(trace))
    return row, steps


def summarize(rows, keys):
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(row[k] for k in keys)].append(row)
    result = []
    for key, group in grouped.items():
        values = [r["slots"] for r in group]
        submitted = sum(r["images_submitted"] for r in group)
        result.append(dict(zip(keys,key), episodes=len(group), mean_slots=statistics.mean(values),
            sd_slots=statistics.stdev(values) if len(values)>1 else 0,
            mean_seconds=statistics.mean(r["seconds"] for r in group),
            mean_compute_j=statistics.mean(r["uav_compute_j"] for r in group),
            delivery_fraction=sum(r["images_delivered"] for r in group)/submitted if submitted else None,
            truncated=sum(r["truncated"] for r in group),
            reasons=json.dumps(dict(Counter(r["reason"] for r in group)))))
    return result


def metadata(runs, output):
    cpu = platform.processor()
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0]
    import psutil
    data = dict(platform=platform.platform(), cpu=cpu, logical_cpus=os.cpu_count(),
        physical_cpus=psutil.cpu_count(logical=False), ram_bytes=psutil.virtual_memory().total,
        python=platform.python_version(), packages={n:importlib.metadata.version(n) for n in
        ["torch","numpy","stable-baselines3","gymnasium"]}, threads=torch.get_num_threads(),
        java_command=(ROOT/"target/drl-java.txt").read_text().strip(),
        note="Local experiments, not original server output. Server checkpoints frozen for evaluation; pilot trains separate models. Layouts previously inspected are diagnostic/development cases, not a fresh final test.",
        checkpoints=[dict(run=str(p),sha256=digest(p/"best_model.zip"),
                    training_config=json.loads((p/"config.json").read_text())) for p in runs])
    (output/"manifest.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    snapshot(output)


def run_evaluation(runs, out):
    rows, states, checks = [], [], []
    for run in runs:
        config=json.loads((run/"config.json").read_text())
        seed=config["seed"]
        model=DQN.load(run/"best_model.zip",device="cpu")
        with PaperEnv(EnvConfig(**config["environment"])) as env:
            # Matched same-layout verification against copied original episodes.
            old_dirs=sorted(run.glob("evaluation-*"))
            old=next(p for p in old_dirs if not json.loads((p/"evaluation.json").read_text())["unseen_layouts"])
            original=read_csv(old/"episodes.csv")
            for mode in ["same", "unseen"]:
                for i in range(30):
                    task_seed=2_000_000+i
                    layout=42 if mode=="same" else task_seed
                    for name in ["DQN", *BASELINES]:
                        trace=out/"traces"/f"s{seed}"/mode/f"{i:03d}-{name}"
                        policy=Policy(name,task_seed,model if name=="DQN" else None)
                        row,_=rollout(env,policy,layout,task_seed,trace,
                            states=states if seed==0 and len(states)<1024 else None)
                        row.update(learning_seed=seed,mode=mode)
                        rows.append(row)
                        if mode=="same":
                            ref=next(r for r in original if int(r["task_seed"])==task_seed and r["policy"]==name)
                            checks.append(dict(learning_seed=seed,task_seed=task_seed,policy=name,
                                slots_match=int(ref["slots"])==row["slots"],reason_match=ref["reason"]==row["reason"],
                                seconds_delta=row["seconds"]-float(ref["seconds"])))
                write_csv(out/"episodes.csv",rows)
                write_csv(out/"summary.csv",summarize(rows,["learning_seed","mode","policy"]))
                print(f"evaluation seed={seed} mode={mode} completed",flush=True)
    write_csv(out/"original_parity.csv",checks)
    np.save(out/"observations.npy",np.asarray(states[:1024],dtype=np.float32))
    assert all(r["slots_match"] and r["reason_match"] and abs(r["seconds_delta"])<1e-6 for r in checks), "Original server parity failed; inspect CSV before interpreting unseen results"


def run_runtime(runs,out):
    rows, steps, calls, init = [],[],[],[]
    pool_path=out.parent/"evaluate/observations.npy"
    pool=np.load(pool_path)[:512]
    # Every policy sees precisely the same observation sequence. Timer overhead is uncorrected.
    for run in runs:
        config=json.loads((run/"config.json").read_text()); seed=config["seed"]
        load_start=time.perf_counter_ns()
        model=DQN.load(run/"best_model.zip",device="cpu")
        load_ms=(time.perf_counter_ns()-load_start)/1e6
        names=["DQN",*BASELINES] if seed==0 else ["DQN"]
        for name in names:
            policy=Policy(name,123,model if name=="DQN" else None)
            for obs in pool[:128]: policy.choose(obs)
            for block in range(7):
                for idx in np.random.default_rng(700+block).permutation(len(pool)):
                    started=time.perf_counter_ns(); policy.choose(pool[idx]); ns=time.perf_counter_ns()-started
                    calls.append(dict(learning_seed=seed,policy=name,block=block,ns=ns))
        props={**config["environment"]["properties"],"paper.measureRuntime":"true"}
        with PaperEnv(replace(EnvConfig(**config["environment"]),properties=props)) as env:
            cold=time.perf_counter_ns(); env.reset(seed=0); cold_ms=(time.perf_counter_ns()-cold)/1e6
            init.append(dict(learning_seed=seed,model_load_ms=load_ms,first_reset_including_jvm_and_dataset_ms=cold_ms))
            for name in names:
                for i in range(12):
                    layout=42 if i%2==0 else 2_000_000+i
                    task_seed=2_000_000+i
                    row,timings=rollout(env,Policy(name,task_seed,model if name=="DQN" else None),layout,task_seed,measured=True)
                    if i<2: continue  # warm-up episodes, including JVM JIT
                    row.update(learning_seed=seed); rows.append(row)
                    for t in timings: steps.append(dict(learning_seed=seed,policy=name,**t))
        print(f"runtime seed={seed} completed",flush=True)
    write_csv(out/"calls.csv",calls); write_csv(out/"episode_times.csv",rows)
    write_csv(out/"step_times.csv",steps); write_csv(out/"startup.csv",init)
    summary=[]
    for seed,name in sorted({(r["learning_seed"],r["policy"]) for r in calls}):
        group=[r for r in calls if r["learning_seed"]==seed and r["policy"]==name]
        values=np.array([r["ns"] for r in group])/1000
        summary.append(dict(learning_seed=seed,policy=name,calls=len(values),median_us=float(np.median(values)),
                            p95_us=float(np.percentile(values,95))))
    write_csv(out/"policy_summary.csv",summary)


def run_permutation(runs,out):
    rows=[]
    orders={"identity":np.arange(12),"reverse":np.arange(11,-1,-1)}
    orders.update({f"shuffle{s}":np.random.default_rng(s).permutation(12) for s in [101,102,103,104]})
    (out/"orders.json").write_text(json.dumps({k:v.tolist() for k,v in orders.items()},indent=2))
    for run in runs:
        c=json.loads((run/"config.json").read_text()); seed=c["seed"]
        model=DQN.load(run/"best_model.zip",device="cpu")
        with PaperEnv(EnvConfig(**c["environment"])) as env:
            for layout in [42,2_000_000,2_000_001]:
                canonical,_=rollout(env,Policy("DQN",2_000_000,model),layout,2_000_000)
                for name,order in orders.items():
                    trace=out/"traces"/f"s{seed}"/f"layout{layout}"/name
                    row,_=rollout(env,Policy("DQN",2_000_000,model,order),layout,2_000_000,trace)
                    row.update(learning_seed=seed,permutation=name,canonical_slots=canonical["slots"],
                        delta_slots=row["slots"]-canonical["slots"],same_actions=row["actions"]==canonical["actions"])
                    if name=="identity": assert row["actions"]==canonical["actions"] and row["seconds"]==canonical["seconds"]
                    rows.append(row)
        write_csv(out/"episodes.csv",rows)
        print(f"permutation seed={seed} completed",flush=True)


def run_sensitivity(runs,out):
    rows=[]
    settings={"default":{},"cap300":{"paper.slotCapSeconds":"300"},"cap900":{"paper.slotCapSeconds":"900"},
        "local_half":{"paper.localRateScale":"0.5"},"local_double":{"paper.localRateScale":"2"},
        "uav_image_half":{"paper.imageMiPerMegapixel":"416.6666666666667"},
        "uav_image_double":{"paper.imageMiPerMegapixel":"1666.6666666666667"},
        "background_zero":{"paper.backgroundScale":"0"},"background_x5":{"paper.backgroundScale":"5"}}
    (out/"settings.json").write_text(json.dumps(settings,indent=2))
    for run in runs:
        c=json.loads((run/"config.json").read_text()); seed=c["seed"]
        model=DQN.load(run/"best_model.zip",device="cpu")
        for setting,change in settings.items():
            conf=replace(EnvConfig(**c["environment"]),properties={**c["environment"]["properties"],**change})
            with PaperEnv(conf) as env:
                for layout in [42,2_000_000,2_000_001]:
                    for task_seed in [2_000_000,2_000_001,2_000_002]:
                        names=["DQN",*BASELINES] if seed==0 else ["DQN"]
                        for name in names:
                            trace=out/"traces"/f"s{seed}"/setting/f"l{layout}-t{task_seed}-{name}"
                            row,_=rollout(env,Policy(name,task_seed,model if name=="DQN" else None),layout,task_seed,trace)
                            row.update(learning_seed=seed,setting=setting); rows.append(row)
            write_csv(out/"episodes.csv",rows)
            print(f"sensitivity seed={seed} setting={setting} completed",flush=True)
    write_csv(out/"summary.csv",summarize(rows,["setting","policy"]))


def run_pilot(runs, out):
    """Matched exploratory budget, not a replication of the paper's million steps."""
    protocol = dict(steps=20_000, learning_seeds=[0,1,2], layout_seed=42,
        powered=8, connected=8, eval_freq=5000, validation_episodes=5,
        test_episodes=30, test_first_seed=2_000_000,
        note="Synthetic and mixed differ in workload AND completion/CPU conventions. "
             "20k is a pilot budget; epsilon decays over 35% of 20k, not 1m. "
             "Best checkpoint chosen on validation only. No hyperparameter search.")
    (out/"protocol.json").write_text(json.dumps(protocol,indent=2))
    rows=[]
    for seed in protocol["learning_seeds"]:
        for workload in ["synthetic", "datasets"]:
            run=out/f"{workload}-s{seed}"
            args=argparse.Namespace(algorithm="DQN", steps=protocol["steps"], seed=seed,
                layout_seed=42, powered=8, connected=8, max_slots=200, workload=workload,
                reward="paper", property=[], output=str(run), eval_freq=5000,
                validation_episodes=5, eval_episodes=30, threads=1, device="cpu", save_replay=False)
            train(args)
            evaluate(run,30,2_000_000,"best_model.zip",True,False,"cpu")
            for evaluation in sorted(run.glob("evaluation-*")):
                mode="unseen" if json.loads((evaluation/"evaluation.json").read_text())["unseen_layouts"] else "same"
                for row in read_csv(evaluation/"summary.csv"):
                    rows.append(dict(learning_seed=seed,workload=workload,mode=mode,**row))
            write_csv(out/"summary.csv",rows)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runs",type=Path,default=ROOT/"result/target")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--stage",choices=["evaluate","runtime","permutation","sensitivity","pilot"],required=True)
    args=p.parse_args(); torch.set_num_threads(1)
    runs=sorted(p for p in args.runs.glob("drl-server-*") if (p/"best_model.zip").is_file())
    if not runs: raise SystemExit("No server checkpoint folders found")
    args.output.mkdir(parents=True,exist_ok=True)
    out=args.output/args.stage; out.mkdir(exist_ok=False)
    metadata(runs,out)
    start=time.monotonic()
    {"evaluate":run_evaluation,"runtime":run_runtime,"permutation":run_permutation,
     "sensitivity":run_sensitivity,"pilot":run_pilot}[args.stage](runs,out)
    (out/"complete.json").write_text(json.dumps(dict(status="COMPLETE",elapsed_s=time.monotonic()-start)))


if __name__=="__main__": main()
