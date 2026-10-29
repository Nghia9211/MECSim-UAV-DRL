"""Train/diagnose device-selection DQN in the adapted mobile environment (not paper reproduction)."""
import argparse
from dataclasses import asdict, replace
from datetime import datetime
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import statistics
import time

import numpy as np
import torch
from stable_baselines3 import DQN
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor

from .environment import ROOT
from .mobile_environment import (DEVICE_FEATURES, GLOBAL_FEATURES, REWARD_SPEC, MobileConfig,
                                 MobileEnv, heuristic_action)
from .run import write_csv


def parameters():
    # Development choices. gamma=1 preserves this finite-horizon physical-cost objective
    # despite unequal durations between service decisions. Not the paper hyperparameters.
    return dict(learning_rate=.0003, gamma=1., batch_size=64, buffer_size=100_000,
                learning_starts=128, train_freq=4, gradient_steps=1, target_update_interval=500,
                exploration_initial_eps=1., exploration_final_eps=.05, exploration_fraction=.5,
                policy_kwargs=dict(net_arch=[64, 64], activation_fn=torch.nn.ReLU))


def episode(env, seed, policy="DQN", model=None, *, layout_seed=None, trace=None):
    start = time.perf_counter()
    obs, info = env.reset(seed=seed, options=dict(task_seed=seed, layout_seed=env.config.layout_seed if layout_seed is None else layout_seed))
    rng, reward, decisions, predict_ns, remapped = np.random.default_rng(seed + 7), 0., 0, [], 0
    while True:
        begin = time.perf_counter_ns()
        if model is None:
            action = heuristic_action(policy, obs, info, rng)
        else:
            action = int(model.predict(obs, deterministic=True)[0])
        predict_ns.append(time.perf_counter_ns() - begin)
        obs, r, terminated, truncated, info = env.step(action)
        reward += r
        decisions += 1
        remapped += info["requested_action"] != info["executed_action"]
        if terminated or truncated:
            break
    if trace is not None:
        env.save_trace(trace)
    return dict(policy=policy, task_seed=seed, layout_seed=env.config.layout_seed if layout_seed is None else layout_seed,
                reward=reward, decisions=decisions, remapped=remapped, images=info["images_seen"],
                delivered_on_time=info["delivered_on_time"], image_misses=info["image_misses"],
                image_dvr=info["image_misses"] / info["images_seen"] if info["images_seen"] else 0.,
                background_misses=info["background_misses"], image_resolution_latency_s=info["image_latency_s"],
                total_energy_j=info["energy_j"], offloaded=info["offloaded"], local=info["local"], covered=info["covered"],
                seconds=info["seconds"], wall_s=time.perf_counter()-start,
                mean_predict_us=statistics.mean(predict_ns)/1000, p95_predict_us=float(np.quantile(predict_ns,.95))/1000)


def summarize(rows):
    summaries = []
    for policy in dict.fromkeys(r["policy"] for r in rows):
        group = [r for r in rows if r["policy"] == policy]
        s = dict(policy=policy, episodes=len(group))
        for k in ("reward", "image_dvr", "delivered_on_time", "total_energy_j", "offloaded", "covered", "background_misses", "mean_predict_us", "wall_s"):
            vals = [r[k] for r in group]
            s["mean_"+k], s["sd_"+k] = statistics.mean(vals), statistics.stdev(vals) if len(vals)>1 else 0.
        summaries.append(s)
    return summaries


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def snapshot(output):
    files = [*ROOT.glob("drl/*.py"), *ROOT.glob("PureEdgeSim/uav/**/*.java"), *ROOT.glob("src/test/java/uav/*.java")]
    files += [ROOT / x for x in ("pom.xml", "drl/requirements.txt", "PureEdgeSim/uav/offloading/mobile-protocol.json",
              "PureEdgeSim/com/mechalikh/pureedgesim/simulationengine/PureEdgeSim.java",
              "scripts/verify-uav-mobile.py", "scripts/verify-uav-offloading.py", "scripts/verify-uav-mobile-trace.py",
              "scripts/offloading_metrics.py")]
    hashes = {}
    for p in files:
        target = output / "source" / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        hashes[p.relative_to(ROOT).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def audit_trace(path):
    spec=importlib.util.spec_from_file_location("mobile_trace_audit",ROOT/"scripts/verify-uav-mobile-trace.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result=module.verify(path)
    save_json(path/"verification.json",result)
    return result


class Validation(BaseCallback):
    def __init__(self, cfg, out, frequency, count):
        super().__init__()
        self.env, self.out, self.frequency, self.count = MobileEnv(cfg), out, frequency, count
        self.rows, self.best = [], -float("inf")

    def evaluate(self):
        rows = [episode(self.env, 1_000_000 + i, model=self.model) for i in range(self.count)]
        value = statistics.mean(r["reward"] for r in rows)
        self.rows.append(dict(steps=self.num_timesteps, updates=self.model._n_updates, mean_reward=value,
                             mean_image_dvr=statistics.mean(r["image_dvr"] for r in rows)))
        write_csv(self.out / "validation.csv", self.rows)
        if self.model._n_updates > 0 and value > self.best:
            self.best = value
            self.model.save(self.out / "best_model")
        self.model.save(self.out / "checkpoint")
        print(f"steps={self.num_timesteps} updates={self.model._n_updates} validation_reward={value:.3f}", flush=True)

    def _on_step(self):
        if self.n_calls % self.frequency == 0:
            self.evaluate()
        return True

    def _on_training_end(self):
        self.evaluate()


def evaluate(run, count, first_seed=2_000_000, unseen=False):
    cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
    if cfg["schema"] != "mobile-dqn-v1" or cfg["status"] != "COMPLETE":
        raise ValueError("Completed mobile DQN run required; paper checkpoints are incompatible")
    env = MobileEnv(MobileConfig(**cfg["environment"]))
    model = DQN.load(run / "best_model.zip", device="cpu")
    out = run / ("evaluation-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    out.mkdir()
    rows = []
    protocol=dict(first_seed=first_seed, episodes=count, unseen_layouts=unseen,
                  checkpoint="best_model.zip", training_run=str(run), seed_pairing=True, source_holdout=False, status="RUNNING")
    save_json(out/"protocol.json",protocol)
    try:
        for i in range(count):
            for policy in ("DQN", "ROUND_ROBIN", "OLDEST_DATA", "RANDOM"):
                rows.append(episode(env, first_seed+i, policy, model if policy == "DQN" else None,
                                    layout_seed=first_seed+i if unseen else None,
                                    trace=out / ("trace-"+policy) if i == 0 else None))
    finally:
        env.close()
    write_csv(out / "episodes.csv", rows)
    write_csv(out / "summary.csv", summarize(rows))
    try:
        audits=[audit_trace(p) for p in sorted(out.glob("trace-*"))]
        protocol.update(status="COMPLETE",trace_audits=audits)
    except BaseException as e:
        protocol.update(status="AUDIT_FAILED",error=repr(e))
        save_json(out/"protocol.json",protocol)
        raise
    save_json(out/"protocol.json",protocol)
    print(f"Evaluation: {out}", flush=True)
    for r in summarize(rows):
        print(f"{r['policy']}: reward={r['mean_reward']:.3f}; image DVR={r['mean_image_dvr']:.3f}; offloaded={r['mean_offloaded']:.2f}", flush=True)
    return out


def train(args):
    if args.steps < 256:
        raise ValueError("Use at least 256 steps to exercise actual gradient updates")
    cfg = MobileConfig(layout_seed=args.layout_seed, offloading=args.offloading, scheduler=args.scheduler,
                       localMips=args.local_mips, areaMetres=args.area)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema="mobile-dqn-v1", status="RUNNING", seed=args.seed, requested_steps=args.steps,
                    environment=asdict(cfg), reward=REWARD_SPEC, hyperparameters=parameters(),
                    global_features=GLOBAL_FEATURES, device_features=DEVICE_FEATURES,
                    observation_size=129, action="next device 0..11; dead IDs map cyclically to next live ID",
                    validation_seeds=[1_000_000+i for i in range(args.validation_episodes)],
                    training_seed_range=[0,999999], test_seed_start=2_000_000,
                    paper_reproduction=False, source_holdout=False, device="cpu", threads=1,
                    python=platform.python_version(), packages={p:importlib.metadata.version(p) for p in
                    ("torch","numpy","gymnasium","stable-baselines3")})
    manifest["source_sha256"] = snapshot(out)
    save_json(out / "config.json", manifest)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    env = Monitor(MobileEnv(cfg), str(out / "train.monitor.csv"))
    validation = Validation(cfg, out, args.eval_freq, args.validation_episodes)
    begin = time.monotonic()
    try:
        model = DQN("MlpPolicy", env, seed=args.seed, device="cpu", **parameters())
        model.set_logger(configure(str(out), ["csv"]))
        model.learn(args.steps, callback=validation)
        model.save(out / "final_model")
        manifest.update(status="COMPLETE", actual_steps=model.num_timesteps, gradient_updates=model._n_updates,
                        elapsed_s=time.monotonic()-begin, java_command=env.unwrapped.command)
        save_json(out / "config.json", manifest)
    except BaseException as e:
        manifest.update(status="INTERRUPTED", error=repr(e), elapsed_s=time.monotonic()-begin)
        save_json(out / "config.json", manifest)
        raise
    finally:
        env.close()
        validation.env.close()
    print(f"Training complete: {out}", flush=True)
    evaluate(out, args.eval_episodes)


def diagnose(args):
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    # Prespecified sensitivity grid; do not silently replace the inherited default.
    grid = [(m,r) for m in (500,125,50) for r in ("ALL_UAV","DEADLINE_ENERGY","ALL_LOCAL")]
    for mips, route in grid:
        env = MobileEnv(replace(MobileConfig(), localMips=mips, offloading=route))
        try:
            for i in range(args.seeds):
                for policy in ("ROUND_ROBIN","OLDEST_DATA","RANDOM"):
                    row = episode(env, 70000+i, policy, trace=out / f"trace-m{mips}-{route}-{policy}" if i==0 else None)
                    row.update(local_mips=mips, offloading=route)
                    rows.append(row)
        finally:
            env.close()
        print(f"Diagnosed localMips={mips} route={route}", flush=True)
        write_csv(out / "episodes.csv", rows)
    summaries = []
    for mips, route in grid:
        for r in summarize([r for r in rows if r["local_mips"]==mips and r["offloading"]==route]):
            r.update(local_mips=mips, offloading=route)
            summaries.append(r)
    write_csv(out / "summary.csv", summaries)
    save_json(out / "protocol.json", dict(schema="mobile-signal-diagnostic-v1", status="COMPLETE",
              seeds=[70000+i for i in range(args.seeds)], grid=grid, baseline=asdict(MobileConfig()),
              reward=REWARD_SPEC, note="Development sensitivity, not independent test or calibrated inference.",
              source_sha256=snapshot(out)))
    print(f"Diagnostic: {out}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("train")
    t.add_argument("--output", required=True)
    t.add_argument("--steps", type=int, default=10000)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--layout-seed", type=int, default=42)
    t.add_argument("--offloading", default="ALL_UAV", choices=["ALL_UAV","DEADLINE_ENERGY","ALL_LOCAL","SHORTEST_FINISH"])
    t.add_argument("--scheduler", default="EDF", choices=["FIFO","EDF","PRIORITY","SPT","FEASIBLE_AGING"])
    t.add_argument("--area", type=float, default=250)
    t.add_argument("--local-mips", type=float, default=500)
    t.add_argument("--eval-freq", type=int, default=1000)
    t.add_argument("--validation-episodes", type=int, default=5)
    t.add_argument("--eval-episodes", type=int, default=10)
    d = sub.add_parser("diagnose")
    d.add_argument("--output", required=True)
    d.add_argument("--seeds", type=int, default=10)
    e = sub.add_parser("evaluate")
    e.add_argument("run", type=Path)
    e.add_argument("--episodes", type=int, default=30)
    e.add_argument("--first-seed", type=int, default=2_000_000)
    e.add_argument("--unseen-layouts", action="store_true")
    args = parser.parse_args()
    if any(getattr(args,k,1)<=0 for k in ("eval_freq","validation_episodes","eval_episodes","seeds","episodes")):
        parser.error("Episode counts and evaluation frequency must be positive")
    if args.command == "train":
        train(args)
    elif args.command == "diagnose":
        diagnose(args)
    else:
        evaluate(args.run.resolve(),args.episodes,args.first_seed,args.unseen_layouts)


if __name__ == "__main__":
    main()
