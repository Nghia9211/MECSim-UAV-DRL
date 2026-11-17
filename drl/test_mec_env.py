"""v2 Gym bridge: API conformance and exact parity with the Java baselines. Needs scripts/build-drl.ps1."""
import unittest

from gymnasium.utils.env_checker import check_env

from .mec_env import MecEnv, deadline_energy, shortest_finish

SMALL = {"arrival_window_s": 60}


def play(env, seed, chooser):
    obs, info = env.reset(options=dict(task_seed=seed))
    total, steps = 0.0, 0
    while True:
        obs, reward, done, _, info = env.step(chooser(info))
        total += reward; steps += 1
        if done:
            return info, total, steps


class MecEnvTests(unittest.TestCase):
    def test_teachers_match_java_on_v21_main(self):
        env = MecEnv(model_file="experiments/v21-main-model.json", model={"preemptive": True, "arrival_window_s": 60}, layout_seed=51)
        try:
            for name, chooser in (("SHORTEST_FINISH", shortest_finish), ("DEADLINE_ENERGY", deadline_energy)):
                info, _, _ = play(env, 503, chooser)
                ref = env.java_reference(name, 503)
                self.assertEqual(info["metrics"], ref["metrics"] | {"decision_ns_mean": info["metrics"]["decision_ns_mean"]}, name)
        finally:
            env.close()

    def test_gymnasium_api(self):
        env = MecEnv(model=SMALL)
        try:
            check_env(env, skip_render_check=True)
        finally:
            env.close()

    def test_python_decisions_match_java_baselines(self):
        env = MecEnv(model=SMALL, scheduler="EDF", layout_seed=2)
        try:
            for seed in (0, 1):
                for name, chooser in (("ALL_LOCAL", lambda i: 0), ("ALL_UAV", lambda i: 1), ("DEADLINE_ENERGY", deadline_energy),
                                     ("SHORTEST_FINISH", shortest_finish)):
                    info, total, steps = play(env, seed, chooser)
                    ref = env.java_reference(name, seed)
                    self.assertEqual(info["workload_sha256"], ref["workload_sha256"])
                    for key in ("on_time", "dvr", "marginal_j", "offloaded", "latency_mean_s"):
                        self.assertEqual(info["metrics"][key], ref["metrics"][key], f"{name} seed {seed} {key}")
                    self.assertEqual(steps, info["metrics"]["offered"])
                    # rewards telescope to on_time - violations when energy_weight = 0
                    self.assertAlmostEqual(total, info["metrics"]["on_time"] - (info["metrics"]["offered"] - info["metrics"]["on_time"]))
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
