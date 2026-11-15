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
from sb3_contrib import MaskablePPO
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv

from .mec_env import FEATURES, MecEnv, MecSchedEnv, deadline_energy, shortest_finish

ROOT = Path(__file__).resolve().parents[1]
MODEL_FILE = "experiments/v21-main-model.json"
PATCH = {"preemptive": True}
TRAIN_LAYOUTS, TRAIN_TASKS = (1000, 2000), (1_000_000, 2_000_000)
VAL = [(l, t) for l in range(50, 55) for t in range(500, 530)]
VAL_SUBSET = [(l, t) for l in range(50, 55) for t in range(500, 504)]
EVAL = [(l, t) for l in range(200, 205) for t in range(2000, 2030)]
TEACHERS = {"shortest_finish": shortest_finish, "deadline_energy": deadline_energy,
            "edf": lambda info: 0}  # schedule control: candidate 0 is the EDF choice
CONTROL = {"offload": (MecEnv, PPO), "schedule": (MecSchedEnv, MaskablePPO)}


def env_kwargs(control):
    kw = dict(model_file=MODEL_FILE, model=PATCH, scheduler="EDF", admission="NONE")
    if control == "schedule":
        kw["offload"] = "SHORTEST_FINISH"
    return kw


def train_env_class(control):
    base = CONTROL[control][0]

    class TrainEnv(base):
        """Draws a fresh training layout and task seed at every reset."""

        def reset(self, *, seed=None, options=None):
            if seed is not None:
                gym_reset(self, seed)
            rng = self.np_random
            options = dict(options or {})
            options.setdefault("layout_seed", int(rng.integers(*TRAIN_LAYOUTS)))
            options.setdefault("task_seed", int(rng.integers(*TRAIN_TASKS)))
            return super().reset(options=options)
    return TrainEnv


def gym_reset(env, seed):
    import gymnasium as gym
    gym.Env.reset(env, seed=seed)


def make_env(rank, seed, energy_weight, control):
    def thunk():
        env = train_env_class(control)(energy_weight=energy_weight, **env_kwargs(control))
        env.reset(seed=seed * 1000 + rank)
        return env
    return thunk


def run_episode(env, choose, layout, task):
    obs, info = env.reset(options=dict(layout_seed=layout, task_seed=task))
    while True:
        obs, _, done, _, info = env.step(choose(obs, info, env))
        if done:
            return info


def score(infos):
    """Mean episode DVR and pooled marginal J per on-time task."""
    m = [i["metrics"] for i in infos]
    on = sum(x["on_time"] for x in m)
    offered, marginal = sum(x["offered"] for x in m), sum(x["marginal_j"] for x in m)
    return dict(dvr=float(np.mean([x["dvr"] for x in m])), j_per_on_time=marginal / on if on else math.nan,
                on_time=on, episodes=len(m), offered=offered, marginal_j=marginal, j_per_offered=marginal / offered)


def objective(s, energy_weight):
    """Per-task value of the training reward on a validation score: (on - violations)/offered - w * (J/offered)/100."""
    return (2 * s["on_time"] - s["offered"]) / s["offered"] - energy_weight * s["j_per_offered"] / 100


def policy_chooser(model):
    def choose(obs, info, env):
        if isinstance(env, MecSchedEnv):
            return int(model.predict(obs, deterministic=True, action_masks=env.action_masks())[0])
        return int(model.predict(obs, deterministic=True)[0])
    return choose


def evaluate_on(model_or_choose, pairs, control="offload", energy_weight=0.0):
    env = CONTROL[control][0](energy_weight=energy_weight, **env_kwargs(control))
    choose = model_or_choose if callable(model_or_choose) else policy_chooser(model_or_choose)
    try:
        return score([run_episode(env, choose, l, t) for l, t in pairs])
    finally:
        env.close()


def behaviour_clone(model, teacher, episodes, seed, control="offload", epochs=40, smoothing=0.0):
    env = train_env_class(control)(**env_kwargs(control))
    env.reset(seed=seed + 77)
    X, Y, M = [], [], []
    try:
        for _ in range(episodes):
            obs, info = env.reset()
            while True:
                a = teacher(info)
                X.append(obs); Y.append(a)
                M.append(env.action_masks() if control == "schedule" else np.ones(2, dtype=bool))
                obs, _, done, _, info = env.step(a)
                if done:
                    break
    finally:
        env.close()
    X = torch.as_tensor(np.array(X), dtype=torch.float32)
    Y = torch.as_tensor(np.array(Y), dtype=torch.long)
    M = np.array(M)
    policy = model.policy
    dist_of = (lambda x, idx: policy.get_distribution(x, action_masks=M[idx])) if control == "schedule" \
        else (lambda x, idx: policy.get_distribution(x))
    opt = torch.optim.Adam(policy.parameters(), lr=1e-3)
    g = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        perm = torch.randperm(len(X), generator=g)
        for i in range(0, len(X), 512):
            idx = perm[i:i + 512]
            dist = dist_of(X[idx], idx.numpy())
            loss = -dist.log_prob(Y[idx]).mean()
            if smoothing > 0:  # label smoothing over the valid actions keeps exploration alive for PPO
                logp = torch.log(dist.distribution.probs.clamp_min(1e-12))
                valid = torch.as_tensor(M[idx.numpy()], dtype=torch.float32)
                spread = -(logp * valid).sum(1) / valid.sum(1)
                loss = (1 - smoothing) * loss + smoothing * spread.mean()
            opt.zero_grad(); loss.backward(); opt.step()
    with torch.no_grad():
        probs = dist_of(X, np.arange(len(X))).distribution.probs
        acc = float((probs.argmax(1) == Y).float().mean())
    return dict(samples=len(X), accuracy=acc, uav_share=float(Y.float().mean()))


def train(a):
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(a.seed); np.random.seed(a.seed)
    torch.set_num_threads(1)
    teacher = TEACHERS[a.teacher]
    log = dict(args=vars(a), started=time.strftime("%Y-%m-%d %H:%M:%S"), validation=[])
    vec = SubprocVecEnv([make_env(r, a.seed, a.energy_weight, a.control) for r in range(a.envs)])
    if a.init_from:  # continue a finished run: same hyperparameters, no new cloning, step 0 = the starting policy
        model = CONTROL[a.control][1].load(a.init_from, env=vec, device="cpu", learning_rate=a.lr, ent_coef=a.ent_coef)
        log["init_from"] = a.init_from
    else:
        model = CONTROL[a.control][1]("MlpPolicy", vec, seed=a.seed, learning_rate=a.lr, n_steps=a.n_steps, batch_size=1024, n_epochs=5,
                gamma=0.99, gae_lambda=0.95, clip_range=0.1, ent_coef=a.ent_coef, policy_kwargs=dict(net_arch=[128, 128]),
                device="cpu", verbose=0)
    log["teacher_validation"] = evaluate_on(lambda o, i, e: teacher(i), VAL_SUBSET, a.control)
    log["behaviour_cloning"] = dict(skipped="continued from " + a.init_from) if a.init_from else (
        behaviour_clone(model, teacher, a.bc_episodes, a.seed, a.control, smoothing=a.bc_smoothing)
        if a.bc_episodes > 0 else dict(skipped=True))
    best = None

    def checkpoint(step):
        nonlocal best
        s = evaluate_on(model, VAL_SUBSET, a.control)
        s["steps"] = step
        log["validation"].append(s)
        path = out / f"ckpt-{step:08d}.zip"
        model.save(path)
        s["objective"] = objective(s, a.energy_weight)
        key = (-s["objective"],) if a.select_rule == "objective" else (round(s["dvr"], 12), s["j_per_on_time"])
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


def deep_merge(base, patch):
    """Same rules as uav.mec.Json.merge: objects merge recursively, null deletes, anything else replaces."""
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def merged_model(extra=None):
    base = json.loads((ROOT / MODEL_FILE).read_text(encoding="utf-8"))
    return deep_merge(deep_merge(base, PATCH), extra or {})


def evaluate(a):
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "models").mkdir()
    extra = json.loads(a.model_patch) if a.model_patch else {}
    (out / "models" / f"{a.variant}.json").write_text(json.dumps(merged_model(extra), indent=2), encoding="utf-8")
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
        control = log["args"].get("control", "offload")
        name = (f"RL_PPO_w{log['args']['energy_weight']:g}_s{log['args']['seed']}+EDF+NONE" if control == "offload"
                else f"SHORTEST_FINISH+RL_MPPO_w{log['args']['energy_weight']:g}_s{log['args']['seed']}+NONE")
        policies.append(name)
        model = CONTROL[control][1].load(Path(run) / log["best_checkpoint"], device="cpu")
        kw = env_kwargs(control)
        kw["model"] = deep_merge(kw["model"], extra)  # robustness variants: the trained policy is unchanged
        env = CONTROL[control][0](trace=True, **kw)
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


def select(a):
    """Full validation (150 episodes) of each run's best checkpoint; picks the energy weight with the lowest mean DVR,
    then the lowest pooled marginal J per on-time task. Unfinished runs are reported and skipped."""
    from collections import defaultdict
    groups, skipped = defaultdict(list), []
    for run in a.runs:
        path = Path(run) / "train.json"
        log = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if "finished" not in log:
            skipped.append(str(run)); continue
        control = log["args"].get("control", "offload")
        if "validation_full" not in log:
            model = CONTROL[control][1].load(Path(run) / log["best_checkpoint"], device="cpu")
            log["validation_full"] = evaluate_on(model, VAL, control)
            path.write_text(json.dumps(log, indent=2), encoding="utf-8")
        groups[(control, log["args"]["energy_weight"])].append(dict(run=str(run), **log["validation_full"]))
        print(run, "full validation DVR %.3f%% J/on %.3f" % (100 * log["validation_full"]["dvr"], log["validation_full"]["j_per_on_time"]), flush=True)
    summary = []
    for (control, w), rs in groups.items():
        summary.append(dict(control=control, energy_weight=w, runs=[r["run"] for r in rs], seeds=len(rs),
                            mean_dvr=float(np.mean([r["dvr"] for r in rs])), mean_j=float(np.mean([r["j_per_on_time"] for r in rs]))))
    summary.sort(key=lambda g: (g["mean_dvr"], g["mean_j"]))
    out = dict(chosen=summary[0] if summary else None, groups=summary, skipped=skipped)
    Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["chosen"], indent=2))


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
    t.add_argument("--control", choices=CONTROL, default="offload")
    t.add_argument("--ent-coef", type=float, default=0.001)
    t.add_argument("--bc-smoothing", type=float, default=0.0)
    t.add_argument("--init-from", help="checkpoint .zip of a finished run to continue training from")
    t.add_argument("--select-rule", choices=["dvr", "objective"], default="dvr",
                   help="checkpoint choice: lowest DVR then energy (default), or highest training objective (H5d-2)")
    e = sub.add_parser("evaluate")
    e.add_argument("--runs", nargs="+", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--variant", default="e0-pre-circle")
    e.add_argument("--with-baselines")
    e.add_argument("--model-patch", help="JSON patch on top of the training model, e.g. estimate error 0.4")
    sl = sub.add_parser("select")
    sl.add_argument("--runs", nargs="+", required=True)
    sl.add_argument("--out", required=True)
    a = p.parse_args()
    {"train": train, "evaluate": evaluate, "select": select}[a.cmd](a)


if __name__ == "__main__":
    main()
