"""H5a: learned per-task offloading on v2.1-main (PLAN_HUONG_2_3.md section 7).

  python -m drl.mec_rl train  --out DIR --seed S --energy-weight L [--steps N] [--teacher shortest_finish]
  python -m drl.mec_rl evaluate --runs DIR [DIR ...] --out RUN_DIR [--variant e0-pre-circle] [--with-baselines H4_RUN]

Protocol (no evaluation data is used for any choice):
  training    layouts 1000-1999, task seeds 1e6..2e6 drawn at random per episode
  validation  layouts 50-54 x task seeds 500-529 (subset of 20 episodes during training); picks the checkpoint
  evaluation  layouts 200-204 x task seeds 2000-2029, opened once per final policy, written in uav.mec run format
Start: behaviour cloning of the teacher heuristic, then PPO fine-tuning. Scheduler EDF with preemption, no admission.
"""
import argparse
import copy
import csv
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv

from .mec_env import FEATURES, MecEnv, deadline_energy, shortest_finish

ROOT = Path(__file__).resolve().parents[1]
MODEL_FILE = "experiments/v21-main-model.json"
PATCH = {"preemptive": True}
TRAIN_LAYOUTS, TRAIN_TASKS = (1000, 2000), (1_000_000, 2_000_000)
VAL = [(l, t) for l in range(50, 55) for t in range(500, 530)]
VAL_SUBSET = [(l, t) for l in range(50, 55) for t in range(500, 504)]
EVAL = [(l, t) for l in range(200, 205) for t in range(2000, 2030)]
TEACHERS = {"shortest_finish": shortest_finish, "deadline_energy": deadline_energy}


class TrainEnv(MecEnv):
    """Draws a fresh training layout and task seed at every reset."""

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            super(MecEnv, self).reset(seed=seed)
        rng = self.np_random
        options = dict(options or {})
        options.setdefault("layout_seed", int(rng.integers(*TRAIN_LAYOUTS)))
        options.setdefault("task_seed", int(rng.integers(*TRAIN_TASKS)))
        return super().reset(options=options)


def make_env(rank, seed, energy_weight):
    def thunk():
        env = TrainEnv(model_file=MODEL_FILE, model=PATCH, scheduler="EDF", admission="NONE", energy_weight=energy_weight)
        env.reset(seed=seed * 1000 + rank)
        return env
    return thunk


def run_episode(env, choose, layout, task):
    obs, info = env.reset(options=dict(layout_seed=layout, task_seed=task))
    while True:
        obs, _, done, _, info = env.step(choose(obs, info))
        if done:
            return info


def score(infos):
    """Mean episode DVR and pooled marginal J per on-time task."""
    m = [i["metrics"] for i in infos]
    on = sum(x["on_time"] for x in m)
    return dict(dvr=float(np.mean([x["dvr"] for x in m])), j_per_on_time=sum(x["marginal_j"] for x in m) / on if on else math.nan,
                on_time=on, episodes=len(m))


def policy_chooser(model):
    return lambda obs, info: int(model.predict(obs, deterministic=True)[0])


def evaluate_on(model_or_choose, pairs, energy_weight=0.0):
    env = MecEnv(model_file=MODEL_FILE, model=PATCH, energy_weight=energy_weight)
    choose = model_or_choose if callable(model_or_choose) else policy_chooser(model_or_choose)
    try:
        return score([run_episode(env, choose, l, t) for l, t in pairs])
    finally:
        env.close()


def behaviour_clone(model, teacher, episodes, seed, epochs=40):
    env = TrainEnv(model_file=MODEL_FILE, model=PATCH)
    env.reset(seed=seed + 77)
    X, Y = [], []
    try:
        for _ in range(episodes):
            obs, info = env.reset()
            while True:
                a = teacher(info)
                X.append(obs); Y.append(a)
                obs, _, done, _, info = env.step(a)
                if done:
                    break
    finally:
        env.close()
    X = torch.as_tensor(np.array(X), dtype=torch.float32)
    Y = torch.as_tensor(np.array(Y), dtype=torch.long)
    policy = model.policy
    opt = torch.optim.Adam(policy.parameters(), lr=1e-3)
    g = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        perm = torch.randperm(len(X), generator=g)
        for i in range(0, len(X), 512):
            idx = perm[i:i + 512]
            dist = policy.get_distribution(X[idx])
            loss = -dist.log_prob(Y[idx]).mean()
            opt.zero_grad(); loss.backward(); opt.step()
    with torch.no_grad():
        acc = float((policy.get_distribution(X).distribution.probs.argmax(1) == Y).float().mean())
    return dict(samples=len(X), accuracy=acc, uav_share=float(Y.float().mean()))


def train(a):
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    torch.set_num_threads(1)
    teacher = TEACHERS[a.teacher]
    log = dict(args=vars(a), started=time.strftime("%Y-%m-%d %H:%M:%S"), validation=[])
    vec = SubprocVecEnv([make_env(r, a.seed, a.energy_weight) for r in range(a.envs)])
    model = PPO("MlpPolicy", vec, seed=a.seed, learning_rate=a.lr, n_steps=a.n_steps, batch_size=1024, n_epochs=5,
                gamma=0.99, gae_lambda=0.95, clip_range=0.1, ent_coef=0.001, policy_kwargs=dict(net_arch=[128, 128]),
                device="cpu", verbose=0)
    log["teacher_validation"] = evaluate_on(lambda o, i: teacher(i), VAL_SUBSET)
    log["behaviour_cloning"] = behaviour_clone(model, teacher, a.bc_episodes, a.seed)
    best = None

    def checkpoint(step):
        nonlocal best
        s = evaluate_on(model, VAL_SUBSET)
        s["steps"] = step
        log["validation"].append(s)
        path = out / f"ckpt-{step:08d}.zip"
        model.save(path)
        key = (round(s["dvr"], 12), s["j_per_on_time"])
        if best is None or key < best[0]:  # lower DVR first, then lower energy; ties keep the earlier checkpoint
            best = (key, step, path)
        (out / "train.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
        print(f"step {step}: val DVR {100*s['dvr']:.2f}% J/on {s['j_per_on_time']:.2f} (teacher "
              f"{100*log['teacher_validation']['dvr']:.2f}% {log['teacher_validation']['j_per_on_time']:.2f})", flush=True)

    checkpoint(0)  # the behaviour-cloned policy
    done = 0
    while done < a.steps:
        model.learn(total_timesteps=a.eval_every, reset_num_timesteps=False)
        done += a.eval_every
        checkpoint(done)
    vec.close()
    log["best_step"], log["best_checkpoint"] = best[1], best[2].name
    log["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out / "train.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print("best checkpoint", best[2].name, flush=True)


def merged_model():
    base = json.loads((ROOT / MODEL_FILE).read_text(encoding="utf-8"))
    out = copy.deepcopy(base)
    for k, v in PATCH.items():
        out[k] = v
    return out


def evaluate(a):
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "models").mkdir()
    (out / "models" / f"{a.variant}.json").write_text(json.dumps(merged_model(), indent=2), encoding="utf-8")
    rows, header = [], None
    if a.with_baselines:  # heuristic rows of the same variant and seeds, for paired comparison and hash checks
        with open(Path(a.with_baselines) / "episodes.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["variant"] == a.variant:
                    header = header or list(r.keys())
                    rows.append(r)
    policies = []
    for run in a.runs:
        log = json.loads((Path(run) / "train.json").read_text(encoding="utf-8"))
        name = f"RL_PPO_w{log['args']['energy_weight']:g}_s{log['args']['seed']}+EDF+NONE"
        policies.append(name)
        model = PPO.load(Path(run) / log["best_checkpoint"], device="cpu")
        env = MecEnv(model_file=MODEL_FILE, model=PATCH, trace=True)
        try:
            for k, (layout, task) in enumerate(EVAL):
                t0 = time.perf_counter()
                info = run_episode(env, policy_chooser(model), layout, task)
                wall = time.perf_counter() - t0
                if k == 0:
                    env.save_trace(out / "traces" / a.variant / f"L{layout}" / f"S{task}" / name.replace("+", "__"))
                m = info["metrics"]
                row = dict(variant=a.variant, layout=str(layout), seed=str(task), policy=name, resolved_policy=name,
                           workload_sha256=info["workload_sha256"], wall_s=str(wall))
                for key, v in m.items():
                    row[key] = "" if isinstance(v, float) and math.isnan(v) else str(v)
                header = header or list(row.keys())
                rows.append(row)
        finally:
            env.close()
        print("evaluated", name, flush=True)
    with open(out / "episodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    manifest = dict(name=out.name, status="COMPLETE", model_versions={a.variant: "v2.1"}, policies=policies,
                    runs=[str(Path(r)) for r in a.runs], baselines_from=a.with_baselines, partition="evaluation-v21")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "config.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--out", required=True)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--energy-weight", type=float, default=1.0)
    t.add_argument("--steps", type=int, default=1_000_000)
    t.add_argument("--eval-every", type=int, default=100_000)
    t.add_argument("--envs", type=int, default=8)
    t.add_argument("--n-steps", type=int, default=512)
    t.add_argument("--lr", type=float, default=1e-4)
    t.add_argument("--bc-episodes", type=int, default=30)
    t.add_argument("--teacher", choices=TEACHERS, default="shortest_finish")
    e = sub.add_parser("evaluate")
    e.add_argument("--runs", nargs="+", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--variant", default="e0-pre-circle")
    e.add_argument("--with-baselines")
    a = p.parse_args()
    train(a) if a.cmd == "train" else evaluate(a)


if __name__ == "__main__":
    main()
