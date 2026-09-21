"""Train/evaluate paper DQN (and PPO/A2C comparisons) against the real Java engine."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import statistics
import time

import numpy as np
import torch
from stable_baselines3 import A2C, DQN, PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor

from .environment import DATASET_PROPERTIES, EnvConfig, PaperEnv, REWARDS, ROOT

ALGORITHMS = {"DQN": DQN, "PPO": PPO, "A2C": A2C}


def model_options(algorithm):
    common = dict(gamma=0.98, policy_kwargs=dict(net_arch=[64, 64], activation_fn=torch.nn.ReLU))
    if algorithm == "DQN":
        return dict(**common, learning_rate=0.0071, batch_size=16,
            exploration_initial_eps=1.0, exploration_final_eps=0.05, exploration_fraction=0.35,
            buffer_size=1_000_000, learning_starts=100, train_freq=4, gradient_steps=1,
            target_update_interval=10_000, tau=1.0, max_grad_norm=10)
    # Paper does not publish PPO/A2C hyperparameters. These are explicit comparison choices.
    if algorithm == "PPO":
        return dict(**common, learning_rate=0.0003, n_steps=2048, batch_size=64,
                    n_epochs=10, gae_lambda=0.95, clip_range=0.2, ent_coef=0.0, vf_coef=0.5, max_grad_norm=0.5)
    return dict(**common, learning_rate=0.0007, n_steps=5, gae_lambda=1.0,
                ent_coef=0.0, vf_coef=0.5, max_grad_norm=0.5, use_rms_prop=True, rms_prop_eps=1e-5)


def episode(env, *, model=None, policy="DQN", task_seed=0, layout_seed=None, trace=None):
    options = {"task_seed": task_seed, "trace": trace is not None}
    if layout_seed is not None:
        options["layout_seed"] = layout_seed
    obs, _ = env.reset(seed=task_seed, options=options)
    rng, next_device, total_reward = np.random.default_rng(task_seed + 2), 0, 0.0
    while True:
        if model is not None:
            action, _ = model.predict(obs, deterministic=True)
            action = int(action)
        elif policy == "RANDOM":
            action = int(rng.integers(12))
        elif policy == "ROUND_ROBIN":
            action, next_device = next_device, (next_device + 1) % 12
        elif policy == "OLDEST_DATA":
            # Exactly the same cyclic tie-breaking as PaperSimulation.policy.
            order = [(next_device + k) % 12 for k in range(12)]
            action = max(order, key=lambda i: obs[12 + i])
            next_device = (action + 1) % 12
        else:
            raise ValueError(f"Unknown policy {policy}")
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if terminated or truncated:
            if trace is not None:
                env.save_trace(trace)
            return dict(policy=policy, layout_seed=options.get("layout_seed", env.config.layout_seed),
                task_seed=task_seed, slots=info["slots"], seconds=info["seconds"],
                reward=total_reward, terminated=terminated, truncated=truncated,
                reason=info["reason"], uav_battery_j=info["uav_battery_j"],
                uav_compute_j=info["uav_compute_j"], images_submitted=info["images_submitted"],
                images_delivered=info["images_delivered"], cpu_submitted=info["cpu_submitted"],
                cpu_completed=info["cpu_completed"], mean_delivered_latency_s=info["mean_delivered_latency_s"])


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def snapshot(output):
    destination = output / "source"
    for folder, pattern in [(ROOT / "drl", "*.py"), (ROOT / "PureEdgeSim/uav", "*.java")]:
        for source in folder.glob(pattern):
            target = destination / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    engine = ROOT / "PureEdgeSim/com/mechalikh/pureedgesim/simulationengine/PureEdgeSim.java"
    target = destination / engine.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(engine, target)
    for filename in ["pom.xml", "drl/requirements.txt", "PureEdgeSim/uav/PAPER_ALIGNMENT.md"]:
        target = destination / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / filename, target)


class Validation(BaseCallback):
    """Select by lifetime on held-out task seeds, never by final test results."""
    def __init__(self, config, directory, frequency, count):
        super().__init__()
        self.env = PaperEnv(config)
        self.directory, self.frequency, self.count = directory, frequency, count
        self.best, self.rows = -float("inf"), []
        self.started = time.monotonic()

    def evaluate(self):
        rows = [episode(self.env, model=self.model, task_seed=1_000_000 + i) for i in range(self.count)]
        mean = statistics.mean(r["slots"] for r in rows)
        self.rows.append(dict(steps=self.num_timesteps, gradient_updates=self.model._n_updates, mean_slots=mean,
            max_slots=max(r["slots"] for r in rows), mean_reward=statistics.mean(r["reward"] for r in rows),
            truncated=sum(r["truncated"] for r in rows), elapsed_s=time.monotonic()-self.started))
        write_csv(self.directory / "validation.csv", self.rows)
        if self.model._n_updates > 0 and mean > self.best:
            self.best = mean
            self.model.save(self.directory / "best_model")
        self.model.save(self.directory / "checkpoint")
        print(f"steps={self.num_timesteps} validation_slots={mean:.3f} best={self.best:.3f}", flush=True)

    def _on_step(self):
        if self.n_calls % self.frequency == 0:
            self.evaluate()
        return True

    def _on_training_end(self):
        # on_step runs BEFORE the last optimizer update (especially PPO's rollout).
        # Always assess the fully updated model, even at the same timestep count.
        self.evaluate()


def train(args):
    if args.algorithm == "DQN" and args.steps <= 100:
        raise ValueError("DQN needs more than 100 steps to pass replay warm-up and train")
    output = Path(args.output).resolve() if args.output else ROOT / "target" / ("drl-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    output.mkdir(parents=True, exist_ok=False)
    properties = dict(DATASET_PROPERTIES) if args.workload == "datasets" else {}
    for entry in args.property:
        key, value = entry.split("=", 1)
        properties[key] = value
    config = EnvConfig(args.layout_seed, args.powered, args.connected, args.max_slots, args.reward, properties)
    parameters = model_options(args.algorithm)
    manifest = dict(algorithm=args.algorithm, seed=args.seed, requested_steps=args.steps,
        environment=asdict(config), hyperparameters=parameters, python=platform.python_version(),
        packages={name: importlib.metadata.version(name) for name in ["torch", "numpy", "gymnasium", "stable-baselines3"]},
        threads=args.threads, device=args.device, validation_seeds=[1_000_000+i for i in range(args.validation_episodes)],
        observation="12 battery fractions then 12 unnormalized ages; no UAV location",
        protocol="Fixed layout; training task seeds in [0,1000000); validation starts at 1000000; test at 2000000.",
        status="RUNNING")
    snapshot(output)
    manifest_path = output / "config.json"
    def save_manifest():
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    save_manifest()
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    raw_env, validation = PaperEnv(config), Validation(config, output, args.eval_freq, args.validation_episodes)
    env = Monitor(raw_env, str(output / "train.monitor.csv"))
    start = time.monotonic()
    try:
        # Persist the actual layout and dataset pools/hashes used by this JVM once.
        raw_env.reset(seed=args.seed, options={"trace": True, "task_seed": 0})
        raw_env.save_trace(output / "environment")
        manifest["java_command"] = raw_env.command
        save_manifest()
        model = ALGORITHMS[args.algorithm]("MlpPolicy", env, seed=args.seed, device=args.device,
                                          verbose=0, **parameters)
        model.set_logger(configure(str(output), ["csv"]))
        model.learn(total_timesteps=args.steps, callback=validation, log_interval=100)
        model.save(output / "final_model")
        if args.save_replay and args.algorithm == "DQN":
            model.save_replay_buffer(output / "replay_buffer.pkl")
        manifest.update(status="COMPLETE", actual_steps=model.num_timesteps,
                        gradient_updates=model._n_updates, elapsed_s=time.monotonic()-start)
        save_manifest()
    except BaseException as error:
        manifest.update(status="INTERRUPTED", error=repr(error), elapsed_s=time.monotonic()-start)
        save_manifest()
        raise
    finally:
        env.close()
        validation.env.close()
    print(f"Training complete: {output}", flush=True)
    evaluate(output, args.eval_episodes, 2_000_000, "best_model.zip", False, False, args.device)


def evaluate(run, count=30, first_seed=2_000_000, checkpoint="best_model.zip", unseen=False, traces=False, device="cpu"):
    run = Path(run).resolve()
    manifest = json.loads((run / "config.json").read_text(encoding="utf-8"))
    config = EnvConfig(**manifest["environment"])
    model = ALGORITHMS[manifest["algorithm"]].load(run / checkpoint, device=device)
    output = run / ("evaluation-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    output.mkdir()
    rows = []
    env = PaperEnv(config)
    try:
        for i in range(count):
            task_seed = first_seed + i
            layout_seed = task_seed if unseen else config.layout_seed
            for policy in [manifest["algorithm"], "ROUND_ROBIN", "OLDEST_DATA", "RANDOM"]:
                # First trace archives exact source pools; optionally keep every episode.
                trace = output / "traces" / f"{i:03d}-{policy}" if traces or i == 0 else None
                rows.append(episode(env, model=model if policy == manifest["algorithm"] else None,
                    policy=policy, task_seed=task_seed, layout_seed=layout_seed, trace=trace))
    finally:
        env.close()
    write_csv(output / "episodes.csv", rows)
    summary = []
    for policy in [manifest["algorithm"], "ROUND_ROBIN", "OLDEST_DATA", "RANDOM"]:
        group = [r for r in rows if r["policy"] == policy]
        lifetimes = [r["slots"] for r in group]
        summary.append(dict(policy=policy, episodes=len(group), mean_slots=statistics.mean(lifetimes),
            sd_slots=statistics.stdev(lifetimes) if len(group)>1 else 0.0, max_slots=max(lifetimes),
            mean_seconds=statistics.mean(r["seconds"] for r in group),
            truncated=sum(r["truncated"] for r in group),
            mean_uav_compute_j=statistics.mean(r["uav_compute_j"] for r in group)))
    write_csv(output / "summary.csv", summary)
    paired = []
    for i in range(count):
        group = rows[i*4:i*4+4]
        paired.append(dict(task_seed=group[0]["task_seed"], layout_seed=group[0]["layout_seed"],
            **{f"delta_slots_vs_{r['policy']}": group[0]["slots"]-r["slots"] for r in group[1:]}))
    write_csv(output / "paired.csv", paired)
    (output / "evaluation.json").write_text(json.dumps(dict(checkpoint=str(run/checkpoint),
        model_training_steps=model.num_timesteps, model_gradient_updates=model._n_updates,
        first_seed=first_seed, count=count, unseen_layouts=unseen,
        deterministic=True, environment=asdict(config),
        note="Paired layout/task seeds; random baseline uses NumPy RNG, not Java Random. Not author results."), indent=2), encoding="utf-8")
    for row in summary:
        print(f"{row['policy']}: slots={row['mean_slots']:.3f} +/- {row['sd_slots']:.3f}; max={row['max_slots']}")
    print(f"Evaluation: {output}", flush=True)
    return rows


def positive(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("train")
    p.add_argument("--algorithm", choices=ALGORITHMS, default="DQN")
    p.add_argument("--steps", type=positive, default=1_000_000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--layout-seed", type=int, default=42)
    p.add_argument("--powered", type=int, default=8)
    p.add_argument("--connected", type=int, default=8)
    p.add_argument("--max-slots", type=positive, default=200)
    p.add_argument("--workload", choices=["synthetic", "datasets"], default="synthetic")
    p.add_argument("--reward", choices=REWARDS, default="paper")
    p.add_argument("--property", action="append", default=[], metavar="JAVA_KEY=VALUE")
    p.add_argument("--output")
    p.add_argument("--eval-freq", type=positive, default=10_000)
    p.add_argument("--validation-episodes", type=positive, default=5)
    p.add_argument("--eval-episodes", type=positive, default=30)
    p.add_argument("--threads", type=positive, default=1)
    p.add_argument("--device", default="cpu")
    p.add_argument("--save-replay", action="store_true")
    p = commands.add_parser("evaluate")
    p.add_argument("run", type=Path)
    p.add_argument("--episodes", type=positive, default=30)
    p.add_argument("--first-seed", type=int, default=2_000_000)
    p.add_argument("--checkpoint", default="best_model.zip")
    p.add_argument("--unseen-layouts", action="store_true")
    p.add_argument("--traces", action="store_true")
    p.add_argument("--device", default="cpu")
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.command == "train":
        train(args)
    else:
        evaluate(args.run, args.episodes, args.first_seed, args.checkpoint, args.unseen_layouts, args.traces, args.device)


if __name__ == "__main__":
    main()
