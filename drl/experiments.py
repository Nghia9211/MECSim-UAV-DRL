"""Launch DRL suites from scenarios.json (table5, table6); each layout/learning seed gets its own model."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics
import subprocess
import sys

from .environment import REGISTRY, REWARDS, ROOT
from .run import ALGORITHMS, positive, write_csv


def configurations(suite, seeds):
    """Runs of a drl suite, in scenario > algorithm > reward > seed order (run directories are indexed by it)."""
    definition = REGISTRY.suite(suite, "drl")
    unknown = (set(definition["algorithms"]) - set(ALGORITHMS)) | (set(definition["rewards"]) - set(REWARDS))
    if unknown:
        raise ValueError(f"Suite {suite} uses unknown algorithms/rewards: {sorted(unknown)}")
    scenarios = [REGISTRY.scenario(name) for name in definition["scenarios"]]
    return [dict(powered=s.powered, connected=s.connected, algorithm=a, reward=r, seed=seed, layout_seed=seed)
            for s in scenarios for a in definition["algorithms"] for r in definition["rewards"] for seed in seeds]


def suite_workload(suite, requested):
    """--workload, else the suite's single workload (multi-workload DRL suites are not supported yet)."""
    if requested is not None:
        return REGISTRY.canonical_workload(requested)
    workloads = REGISTRY.suite(suite, "drl")["workloads"]
    if len(workloads) != 1:
        raise ValueError(f"Suite {suite} lists several workloads; pick one with --workload")
    return workloads[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=REGISTRY.suite_names("drl"), required=True)
    parser.add_argument("--seeds", type=positive, help="Independent layout/learning seeds from zero (default: suite's seeds)")
    parser.add_argument("--steps", type=positive, default=1_000_000)
    parser.add_argument("--eval-episodes", type=positive, default=30)
    parser.add_argument("--workload", choices=REGISTRY.workload_choices(), help="Default: the suite's workload")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    seeds = args.seeds or REGISTRY.suite(args.suite, "drl")["seeds"]
    workload = suite_workload(args.suite, args.workload)
    configs = configurations(args.suite, range(seeds))
    output = args.output.resolve()
    if args.plan_only:
        print(json.dumps(dict(runs=len(configs), environment_steps=len(configs)*args.steps,
                              configurations=configs), indent=2))
        return
    output.mkdir(parents=True, exist_ok=False)
    (output/"plan.json").write_text(json.dumps(dict(suite=args.suite, workload=workload,
        steps=args.steps, evaluation_episodes=args.eval_episodes, configurations=configs),indent=2),encoding="utf-8")
    completed = []
    for index, config in enumerate(configs):
        run = output / f"{index:04d}-{config['algorithm']}-p{config['powered']}-c{config['connected']}-{config['reward']}-s{config['seed']}"
        command = [sys.executable,"-m","drl.run","train","--output",str(run),"--steps",str(args.steps),
                   "--eval-episodes",str(args.eval_episodes),"--workload",workload]
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
