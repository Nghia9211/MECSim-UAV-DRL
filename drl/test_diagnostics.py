"""Contracts for measurement and physical-device relabeling diagnostics."""
import unittest

import numpy as np

from .diagnostics import Policy, permute_observation
from .environment import EnvConfig, PaperEnv


class DiagnosticTests(unittest.TestCase):
    def test_relabel_keeps_battery_age_pair_and_decodes_to_physical_device(self):
        obs = np.r_[np.arange(12) / 12, np.arange(12)].astype(np.float32)
        class OldestModel:
            def predict(self, viewed, deterministic):
                np.testing.assert_allclose(viewed[:12] * 12, viewed[12:])
                return np.argmax(viewed[12:]), None
        for seed in range(10):
            order = np.random.default_rng(seed).permutation(12)
            self.assertEqual(Policy("DQN", 0, OldestModel(), order).choose(obs), 11)
            restored = permute_observation(permute_observation(obs, order), np.argsort(order))
            np.testing.assert_array_equal(restored, obs)

    def test_bridge_timer_is_cumulative_and_does_not_change_transitions(self):
        with PaperEnv(EnvConfig(max_slots=3)) as plain, PaperEnv(EnvConfig(
                max_slots=3, properties={"paper.measureRuntime": "true"})) as timed:
            a, ai = plain.reset(seed=17)
            b, bi = timed.reset(seed=17)
            np.testing.assert_array_equal(a, b)
            self.assertNotIn("kernel_nanos", ai)
            self.assertEqual(bi.pop("kernel_nanos"), 0)
            self.assertEqual(ai, bi)
            previous = 0
            for action in [3, 7, 0]:
                a, ar, at, ax, ai = plain.step(action)
                b, br, bt, bx, bi = timed.step(action)
                current = bi.pop("kernel_nanos")
                self.assertGreater(current, previous)
                previous = current
                np.testing.assert_array_equal(a, b)
                self.assertEqual((ar, at, ax, ai), (br, bt, bx, bi))


if __name__ == "__main__":
    unittest.main()
