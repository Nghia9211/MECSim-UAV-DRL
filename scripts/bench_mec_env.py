"""Steps per second of drl.mec_env.MecEnv (one bridge process, random actions). Usage: python scripts/bench_mec_env.py [episodes]"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np  # noqa: E402
from drl.mec_env import MecEnv  # noqa: E402

episodes = int(sys.argv[1]) if len(sys.argv) > 1 else 5
rng = np.random.default_rng(0)
for load in (0.9, 1.8):
    env = MecEnv(model={"rho_uav": load})
    env.reset(options=dict(task_seed=0))  # JVM start-up outside the timing
    steps, begin = 0, time.perf_counter()
    for seed in range(episodes):
        env.reset(options=dict(task_seed=seed + 1))
        done = False
        while not done:
            _, _, done, _, _ = env.step(int(rng.integers(2)))
            steps += 1
    elapsed = time.perf_counter() - begin
    env.close()
    print(f"rho_uav={load}: {steps} steps in {elapsed:.2f} s = {steps / elapsed:.0f} steps/s")
