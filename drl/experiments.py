"""Launch Table 5/6 experiment grids; each layout/learning seed gets its own model."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics
import subprocess
import sys

from .environment import REWARDS, ROOT
from .run import positive, write_csv


def configurations(suite, seeds):
    scenarios = [(p,c) for p in [12,10,8,6,4] for c in [12,10,8,6,4]] if suite == "table5" else [(6,6),(8,8),(10,8)]
    algorithms = ["DQN"] if suite == "table5" else ["DQN", "PPO", "A2C"]
    rewards = ["paper"] if suite == "table5" else REWARDS
    return [dict(powered=p, connected=c, algorithm=a, reward=r, seed=seed, layout_seed=seed)
            for p,c in scenarios for a in algorithms for r in rewards for seed in seeds]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["table5", "table6"], required=True)
    parser.add_argument("--seeds", type=positive, default=3, help="Independent layout/learning seeds, starting at zero")
    parser.add_argument("--steps", type=positive, default=1_000_000)
    parser.add_argument("--eval-episodes", type=positive, default=30)
    parser.add_argument("--workload", choices=["synthetic","datasets"], default="synthetic")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    configs = configurations(args.suite, range(args.seeds))
    output = args.output.resolve()
    if args.plan_only:
        print(json.dumps(dict(runs=len(configs), environment_steps=len(configs)*args.steps,
                              configurations=configs), indent=2))
        return
    output.mkdir(parents=True, exist_ok=False)
    (output/"plan.json").write_text(json.dumps(dict(suite=args.suite, workload=args.workload,
        steps=args.steps, evaluation_episodes=args.eval_episodes, configurations=configs),indent=2),encoding="utf-8")
    completed = []
    for index, config in enumerate(configs):
        run = output / f"{index:04d}-{config['algorithm']}-p{config['powered']}-c{config['connected']}-{config['reward']}-s{config['seed']}"
        command = [sys.executable,"-m","drl.run","train","--output",str(run),"--steps",str(args.steps),
                   "--eval-episodes",str(args.eval_episodes),"--workload",args.workload]
        for key,value in config.items():
            command += ["--"+key.replace("_","-"),str(value)]
        print(f"Run {index+1}/{len(configs)}: {run.name}",flush=True)
        with (output/f"run-{index:04d}.log").open("w",encoding="utf-8") as log:
            subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        evaluation = next(run.glob("evaluation-*/summary.csv"))
        with evaluation.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                completed.append({**config, **row})
        write_csv(output/"runs.csv",completed)
        groups = defaultdict(list)
        for row in completed:
            groups[tuple(row[k] for k in ["powered","connected","algorithm","reward","policy"])].append(row)
        summary = []
        for key, rows in groups.items():
            means = [float(r["mean_slots"]) for r in rows]
            summary.append(dict(zip(["powered","connected","training_algorithm","reward","policy"],key),
                independent_runs=len(rows), mean_of_run_mean_slots=statistics.mean(means),
                sd_of_run_mean_slots=statistics.stdev(means) if len(means)>1 else 0,
                maximum_observed_slots=max(int(r["max_slots"]) for r in rows)))
        write_csv(output/"summary.csv",summary)


if __name__ == "__main__":
    main()
