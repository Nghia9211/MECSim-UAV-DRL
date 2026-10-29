"""Integration tests: policy actions, shared physics replay and adversarial traces."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from stable_baselines3.common.env_checker import check_env
from .environment import ROOT
from .joint_environment import JointEnv, utility
from .mobile_environment import MobileConfig


class JointTests(unittest.TestCase):
    def test_contract_and_future_independence(self):
        with JointEnv() as env:
            check_env(env,warn=True)
            a,_=env.reset(seed=7,options={'task_seed':123})
            b,_=env.reset(seed=7,options={'task_seed':456})
            np.testing.assert_array_equal(a,b)
            for action in (-1,9,.5):
                with self.assertRaises(ValueError):env.step(action)

    def test_dynamic_modes_audit_and_corruptions(self):
        spec=importlib.util.spec_from_file_location('joint_audit',ROOT/'scripts/verify-uav-mobile-trace.py')
        audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
        cfg=MobileConfig(control_mode='joint_policy',allowContactWait=True,areaMetres=50)
        with tempfile.TemporaryDirectory(dir=ROOT/'target') as tmp, JointEnv(cfg) as env:
            obs,info=env.reset(seed=7,options={'task_seed':95003})
            total=0.;i=0
            while True:
                obs,reward,done,truncated,info=env.step(i%9);total+=reward;i+=1
                if done or truncated:break
            self.assertAlmostEqual(total,utility(info))
            self.assertGreater(i,9)
            trace=Path(tmp)/'trace';env.save_trace(trace)
            self.assertEqual(audit.verify(trace)['status'],'PASS')
            for kind in ('action','reward','observation','route'):
                out=Path(tmp)/kind;shutil.copytree(trace,out)
                if kind=='route':
                    p=out/'episode-decisions.csv';text=p.read_text()
                    self.assertTrue('UAV' in text)
                    p.write_text(text.replace('UAV','LOCAL',1))
                else:
                    p=out/'transitions.json';h=json.loads(p.read_text())
                    if kind=='action':h[1]['action']=9
                    elif kind=='reward':h[1]['reward']+=1
                    else:h[0]['observation'][129]+=.1
                    p.write_text(json.dumps(h))
                with self.assertRaises(AssertionError):audit.verify(out)

    def test_fixed_actions_change_routes_not_rr_selection(self):
        with JointEnv() as env:
            results=[]
            for action in (0,8):
                env.reset(seed=7,options={'task_seed':95003})
                while True:
                    _,_,done,_,info=env.step(action)
                    if done:break
                results.append(info)
            self.assertEqual(results[0]['previous_target'],results[1]['previous_target'])
            self.assertNotEqual(results[0]['energy_j'],results[1]['energy_j'])

    def test_scenario_draws_reproducible_and_exposed(self):
        with JointEnv(random_scenarios=True) as env:
            a,_=env.reset(seed=22,options={'task_seed':123})
            b,_=env.reset(seed=22,options={'task_seed':123})
            np.testing.assert_array_equal(a,b)
            self.assertEqual(143,len(a))


if __name__=='__main__':unittest.main()
