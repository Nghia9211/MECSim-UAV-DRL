import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import numpy as np
from stable_baselines3.common.env_checker import check_env
from .environment import ROOT
from .contact_environment import ContactEnv,heuristic,masks
from .mobile_environment import MobileConfig
from .joint_environment import utility
from .joint_environment import JointEnv


class ContactTests(unittest.TestCase):
    def test_legacy_adapter_preserves_old_policy_physics(self):
        from .contact_campaign import Predictor
        class Legacy:
            def predict(self,obs,deterministic=True):
                assert len(obs)==143
                return np.int64(int(obs[0]*100)%9),None
        seed=95003;legacy=Legacy()
        with JointEnv() as old,ContactEnv() as new:
            old_obs,old_info=old.reset(seed=seed,options={'task_seed':seed})
            new_obs,new_info=new.reset(seed=seed,options={'task_seed':seed})
            wrapped=Predictor(model=legacy,legacy=True)
            while True:
                np.testing.assert_array_equal(old_obs,new_obs[:143])
                action=int(legacy.predict(old_obs)[0]);joint=int(wrapped.predict(new_obs)[0])
                old_obs,old_r,done,_,old_info=old.step(action)
                new_obs,new_r,new_done,_,new_info=new.step(joint)
                self.assertEqual(done,new_done);self.assertAlmostEqual(old_r,new_r)
                for key in ('seconds','energy_j','delivered_on_time','offloaded','previous_target'):
                    self.assertEqual(old_info[key],new_info[key])
                if done:break

    def test_contract_future_independence_and_target_effect(self):
        with ContactEnv() as env:
            check_env(env,warn=True)
            a,info=env.reset(seed=4,options={'task_seed':11})
            b,_=env.reset(seed=4,options={'task_seed':999})
            np.testing.assert_array_equal(a,b)
            self.assertEqual(108,int(env.action_masks().sum()))
            first=env.step(0)
            env.reset(seed=4,options={'task_seed':999})
            second=env.step(9)
            self.assertNotEqual(first[4]['position'],second[4]['position'])
            for action in (-1,108,.1):
                with self.assertRaises(ValueError):env.step(action)

    def test_mask_excludes_only_dead_targets(self):
        with ContactEnv() as env:
            obs,_=env.reset(seed=1)
            obs[9+10*3+5]=0
            mask=masks(obs)
            self.assertFalse(mask[27:36].any())
            self.assertEqual(99,int(mask.sum()))

    def test_dynamic_joint_actions_and_corrupted_contact_features(self):
        spec=importlib.util.spec_from_file_location('contact_audit',ROOT/'scripts/verify-uav-mobile-trace.py')
        audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
        cfg=MobileConfig(control_mode='contact_policy',allowContactWait=True,areaMetres=50)
        with tempfile.TemporaryDirectory(dir=ROOT/'target') as tmp,ContactEnv(cfg) as env:
            obs,info=env.reset(seed=7,options={'task_seed':95003});i=0;total=0
            while True:
                action=heuristic('DISCONNECTED_RR',obs,info)+i%9
                obs,r,t,u,info=env.step(action);total+=r;i+=1
                if t or u:break
            self.assertAlmostEqual(total,utility(info));trace=Path(tmp)/'trace';env.save_trace(trace)
            self.assertEqual('PASS',audit.verify(trace)['status'])
            for kind in ('feature','target','mode','reward'):
                out=Path(tmp)/kind;shutil.copytree(trace,out)
                p=out/'transitions.json';h=json.loads(p.read_text())
                if kind=='feature':h[0]['observation'][145]+=.1
                elif kind=='target':h[1]['action']=(h[1]['action']+9)%108
                elif kind=='mode':h[1]['action']=(h[1]['action']+1)%108
                else:h[1]['reward']+=1
                p.write_text(json.dumps(h))
                with self.assertRaises(AssertionError):audit.verify(out)


if __name__=='__main__':unittest.main()
