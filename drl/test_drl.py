"""Integration tests require scripts/build-drl.ps1 and drl/requirements.txt."""
import csv
import json
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

from .environment import DATASET_PROPERTIES, REGISTRY, EnvConfig, PaperEnv, REWARDS, ROOT, reward_value
from .run import episode, model_options
from .experiments import configurations, suite_workload
from .registry import Registry


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
        self.compare_java(REGISTRY.workload_properties("mixed"))

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
        self.assertEqual({r["reward"] for r in table6}, set(REWARDS))
        self.assertEqual(suite_workload("table5", None), "synthetic")
        self.assertEqual(suite_workload("table5", "datasets"), "mixed")


class RegistryTests(unittest.TestCase):
    """scenarios.json is shared with Java (uav.ScenarioRegistryTest checks the same file there)."""
    FORMER_DATASET_PROPERTIES = {  # Values that used to be hard-coded here and in run-paper-datasets.ps1.
        "rescuenet.images": "datasets/raw/rescuenet/validation/val-org-img",
        "rescuenet.masks": "datasets/raw/rescuenet/validation/val-label-img",
        "alibaba.csv": "datasets/raw/alibaba2018/batch_task.csv",
        "paper.imageLimit": "449", "paper.alibabaLimit": "1000", "paper.alibabaScanLimit": "100000",
        "paper.uavMips": "2000", "paper.imageMiPerMegapixel": "833.3333333333334", "paper.cpuPowerW": "20",
        "alibaba.assumedMips": "1000", "alibaba.durationScale": "1",
        "paper.backgroundScale": "1", "paper.backgroundTasksPerSlot": "1",
    }

    def test_workload_properties_keep_former_values_and_pin_workload_identity(self):
        self.assertEqual(REGISTRY.workload_properties("datasets"), {"paper.workload": "datasets", **self.FORMER_DATASET_PROPERTIES})
        self.assertEqual(list(DATASET_PROPERTIES), ["paper.workload", *self.FORMER_DATASET_PROPERTIES])
        self.assertEqual(REGISTRY.workload_properties("mixed")["paper.workload"], "mixed")
        rescue = REGISTRY.workload_properties("rescuenet", {"paper.cpuPowerW": "7"})
        self.assertEqual((rescue["paper.backgroundScale"], rescue["paper.cpuPowerW"]), ("0", "7"))
        self.assertEqual(REGISTRY.workload_properties("synthetic"), {})
        with self.assertRaisesRegex(ValueError, "pins"):
            REGISTRY.workload_properties("rescuenet", {"paper.backgroundScale": "5"})
        with self.assertRaisesRegex(ValueError, "Unknown workload"):
            REGISTRY.workload_properties("google")

    def test_defaults_and_seed_protocol(self):
        config = EnvConfig()
        self.assertEqual((config.layout_seed, config.powered, config.connected, config.max_slots), (42, 8, 8, 200))
        seeds = REGISTRY.seed_protocol
        self.assertEqual((seeds.task_seed_offset, seeds.policy_seed_offset), (1, 2))
        self.assertEqual((seeds.drl_training_task_seed_end, seeds.drl_test_first_task_seed), (1_000_000, 2_000_000))

    def test_every_drl_suite_expands_and_invalid_registries_fail(self):
        for name in REGISTRY.suite_names("drl"):
            self.assertTrue(configurations(name, range(1)))
        data = json.loads(REGISTRY.source.read_text(encoding="utf-8"))
        bad = json.loads(json.dumps(data)); bad["scenarios"]["p8c8"]["powered"] = 13
        with self.assertRaisesRegex(ValueError, "p8c8"):
            Registry(bad, REGISTRY.source)
        bad = json.loads(json.dumps(data)); bad["suites"]["table6"]["scenarios"].append("p9c9")
        with self.assertRaisesRegex(ValueError, "p9c9"):
            Registry(bad, REGISTRY.source)
        bad = json.loads(json.dumps(data)); bad["workloads"]["rescuenet"]["fixed"] = {"alibaba.csv": "x"}
        with self.assertRaisesRegex(ValueError, "pins unsupported"):
            Registry(bad, REGISTRY.source)

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
