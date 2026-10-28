"""Integration checks against Java plus corruption checks on completed Gym traces."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from stable_baselines3.common.env_checker import check_env

from .mobile_environment import MobileConfig, MobileEnv, cumulative_utility, heuristic_action
from .environment import ROOT


class MobileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = MobileEnv()
        cls.tmp = tempfile.TemporaryDirectory(prefix="mobile-gym-",dir=ROOT/"target")
        cls.trace = Path(cls.tmp.name)/"trace"
        obs,info=cls.env.reset(seed=1,options={"task_seed":71000})
        total=0.
        while True:
            action=heuristic_action("ROUND_ROBIN",obs,info,np.random.default_rng(1))
            obs,r,t,u,info=cls.env.step(action)
            total+=r
            if t or u:
                break
        cls.total,cls.info=total,info
        cls.env.save_trace(cls.trace)
        spec=importlib.util.spec_from_file_location("gym_trace_audit",ROOT/"scripts/verify-uav-mobile-trace.py")
        cls.audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.audit)

    @classmethod
    def tearDownClass(cls):
        cls.env.close()
        cls.tmp.cleanup()

    def test_gym_contract(self):
        check_env(self.env,warn=True)

    def test_repeated_reset_is_deterministic_and_clears_partial_episode(self):
        a,info=self.env.reset(seed=7,options={"task_seed":71001})
        first=self.env.step(0)
        b,again=self.env.reset(seed=7,options={"task_seed":71001})
        second=self.env.step(0)
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(first[0],second[0])
        self.assertEqual(first[1:],second[1:])

    def test_action_changes_trajectory_and_causal_reward(self):
        self.env.reset(seed=1,options={"task_seed":71002})
        a=self.env.step(0)
        self.env.reset(seed=1,options={"task_seed":71002})
        b=self.env.step(1)
        self.assertNotEqual(a[4]["position"],b[4]["position"])
        self.assertNotEqual(a[4]["energy_j"],b[4]["energy_j"])

    def test_invalid_action_and_config(self):
        self.env.reset(seed=1)
        for action in (-1,12,.5):
            with self.assertRaises(ValueError):self.env.step(action)
        with self.assertRaises(ValueError):MobileConfig(localMips=-1)
        with self.assertRaises(ValueError):MobileConfig(connectedDevices=13)
        with self.assertRaises(ValueError):MobileConfig(horizonSeconds=300)

    def test_terminal_drain_and_reward_telescope(self):
        self.assertEqual(600,self.info["seconds"])
        self.assertAlmostEqual(self.total,cumulative_utility(self.info),places=7)
        history=json.loads((self.trace/"transitions.json").read_text())
        self.assertAlmostEqual(600,sum(s["info"].get("delta_seconds",0) for s in history))

    def test_full_independent_trace_audit(self):
        result=self.audit.verify(self.trace)
        self.assertEqual("PASS",result["status"])
        self.assertAlmostEqual(self.total,result["total_reward"],places=7)

    def test_corrupted_reward_observation_and_action_are_rejected(self):
        import shutil
        for kind in ("reward","observation","action"):
            with self.subTest(kind=kind):
                out=Path(self.tmp.name)/kind
                shutil.copytree(self.trace,out)
                history=json.loads((out/"transitions.json").read_text())
                if kind=="reward":history[1]["reward"]+=1
                if kind=="observation":history[0]["observation"][9]+=.1
                if kind=="action":history[1]["action"]=(history[1]["action"]+1)%12
                (out/"transitions.json").write_text(json.dumps(history))
                with self.assertRaises(AssertionError):self.audit.verify(out)

    def test_future_task_seed_does_not_change_initial_state(self):
        a,ia=self.env.reset(seed=0,options={"task_seed":11})
        b,ib=self.env.reset(seed=0,options={"task_seed":999})
        np.testing.assert_array_equal(a,b)
        self.assertEqual(0,ia["images_seen"])
        self.assertEqual(0,ib["images_seen"])


if __name__=="__main__":
    unittest.main()
