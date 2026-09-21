"""Integration tests require scripts/build-drl.ps1 and drl/requirements.txt."""
import csv
from dataclasses import replace
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
import torch
from gymnasium.utils.env_checker import check_env as gym_check
from stable_baselines3 import DQN
from stable_baselines3.common.env_checker import check_env

from .environment import DATASET_PROPERTIES, EnvConfig, PaperEnv, REWARDS, ROOT, reward_value
from .run import episode, model_options
from .experiments import configurations


class EnvironmentTests(unittest.TestCase):
    def test_java_process_failure_reports_original_cause(self):
        with PaperEnv() as env:
            env.reset(seed=1)
            env._process.kill()
            env._process.wait(timeout=5)
            with self.assertRaisesRegex(RuntimeError, "Java bridge exited"):
                env._receive()

    def test_api_reset_determinism_and_abort_cleanup(self):
        with PaperEnv() as env:
            check_env(env)
            gym_check(env, skip_render_check=True)
            obs, _ = env.reset(seed=123)
            self.assertEqual(obs.shape, (24,))
            first = env.step(3)
            for _ in range(20):
                env.reset(seed=123)  # Abort before natural termination.
                actual = env.step(3)
                np.testing.assert_array_equal(first[0], actual[0])
                self.assertEqual(first[1:], actual[1:])
            with self.assertRaises(ValueError):
                env.step(12)

    def test_terminal_versus_time_limit_and_owns_observation(self):
        with PaperEnv(EnvConfig(max_slots=1)) as env:
            observation, _ = env.reset(seed=1)
            observation[:] = -999  # Returned arrays must not mutate environment state.
            _, reward, terminated, truncated, _ = env.step(0)
            self.assertTrue(math.isfinite(reward))
            self.assertFalse(terminated)
            self.assertTrue(truncated)
            with self.assertRaises(RuntimeError):
                env.step(0)
        with PaperEnv(EnvConfig(powered=12, connected=0)) as env:
            env.reset(seed=1)
            for _ in range(10):
                _, _, terminated, truncated, info = env.step(0)
            self.assertTrue(terminated)
            self.assertFalse(truncated)
            self.assertIn("DATA_AGE", info["reason"])

    def compare_java(self, properties):
        cp = (ROOT / "target/drl-classpath.txt").read_text().strip()
        result = subprocess.run(["java", *[f"-D{k}={v}" for k,v in properties.items()],
            "-Dpaper.seed=42", "-Dpaper.policy=OLDEST_DATA", "-cp", cp, "uav.PaperSimulation"],
            cwd=ROOT, text=True, capture_output=True, timeout=120, check=True)
        reference = Path(result.stdout.strip().split("; output=")[-1])
        with tempfile.TemporaryDirectory(dir=ROOT / "target", prefix="drl-test-") as directory:
            with PaperEnv(EnvConfig(properties=properties)) as env:
                row = episode(env, policy="OLDEST_DATA", task_seed=43, trace=directory)
                for name in ["slots.csv", "devices.csv", "layout.csv"]:
                    self.assertEqual((reference/name).read_text(), (Path(directory)/name).read_text())
                if properties:
                    self.assertGreater(row["cpu_completed"], 0)
                    self.assertGreater(row["uav_compute_j"], 0)
                    for name in ["dataset-tasks.csv", "cpu-tasks.csv", "dataset-summary.csv"]:
                        self.assertEqual((reference/name).read_text(), (Path(directory)/name).read_text())
                # Trace-free training must give exactly the same rewards and physics.
                without_trace = episode(env, policy="OLDEST_DATA", task_seed=43)
                self.assertEqual(row, without_trace)

    def test_java_trace_parity_synthetic(self):
        self.compare_java({})

    @unittest.skipUnless(os.environ.get("DRL_TEST_DATASETS") == "1", "Set DRL_TEST_DATASETS=1 for real raw data test")
    def test_java_trace_parity_real_mixed(self):
        self.compare_java(dict(DATASET_PROPERTIES))

    def test_rewards_and_paper_hyperparameters(self):
        before = np.array([1.] * 12 + [0.] * 12)
        after = before.copy()
        for name in REWARDS:
            self.assertTrue(math.isfinite(reward_value(name, before, 0, after, 1, 1)))
        before[12], before[13] = 2, 4
        self.assertEqual(reward_value("sum", before, 0, after, 3, 0), 2)
        opts = model_options("DQN")
        self.assertEqual((opts["gamma"], opts["learning_rate"], opts["batch_size"]), (.98,.0071,16))
        self.assertEqual(opts["policy_kwargs"]["net_arch"], [64,64])

    def test_experiment_grids_match_paper_scenarios(self):
        table5 = configurations("table5", range(2))
        table6 = configurations("table6", range(2))
        self.assertEqual(len(table5), 50)
        self.assertEqual(len(table6), 198)
        self.assertEqual({(r["powered"],r["connected"]) for r in table6}, {(6,6),(8,8),(10,8)})
        self.assertEqual({r["algorithm"] for r in table6}, {"DQN","PPO","A2C"})

    def test_dqn_learns_and_save_reload_preserves_policy(self):
        torch.set_num_threads(1)
        with PaperEnv() as env, tempfile.TemporaryDirectory(dir=ROOT / "target", prefix="drl-test-") as directory:
            options = model_options("DQN")
            options["buffer_size"] = 1000  # Test-only memory reduction.
            model = DQN("MlpPolicy", env, seed=7, device="cpu", **options)
            before = [p.detach().clone() for p in model.q_net.parameters()]
            model.learn(256)
            self.assertGreater(model._n_updates, 0)
            self.assertTrue(any(not torch.equal(p, q) for p,q in zip(before, model.q_net.parameters())))
            self.assertGreater(model.replay_buffer.size(), 100)
            obs, _ = env.reset(seed=10)
            path = Path(directory)/"model.zip"
            model.save(path)
            loaded = DQN.load(path, device="cpu")
            self.assertEqual(int(model.predict(obs, deterministic=True)[0]), int(loaded.predict(obs, deterministic=True)[0]))
            for p,q in zip(model.q_net.parameters(), loaded.q_net.parameters()):
                self.assertTrue(torch.equal(p,q))
            self.assertEqual(episode(env, model=model, task_seed=11), episode(env, model=loaded, task_seed=11))


if __name__ == "__main__":
    unittest.main()
