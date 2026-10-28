"""Reference delivery differs from completion only in the declared convention."""
import json
import unittest
import numpy as np
from .environment import ROOT, EnvConfig, PaperEnv


class ReferenceStateTests(unittest.TestCase):
    def test_protocol_keeps_budget_seeds_and_other_physics_fixed(self):
        old=json.loads((ROOT/'drl/paper_state_protocol.json').read_text())
        new=json.loads((ROOT/'drl/paper_reference_state_protocol.json').read_text())
        self.assertEqual({k for k in old if old[k]!=new[k]}, {'properties','test_first_seed'})
        self.assertEqual({k for k in old['properties'] if old['properties'][k]!=new['properties'][k]}, {'paper.deliveryConvention'})
        self.assertEqual(new['properties']['paper.deliveryConvention'],'LEGACY')
        self.assertEqual(new['steps'],1000000);self.assertEqual(new['learning_seeds'],[0,1,2])
        self.assertEqual(new['test_first_seed'],4000000)

    def test_reference_connected_devices_refresh_in_both_state_modes(self):
        results=[]
        for mode in ['paper24','extended125']:
            with PaperEnv(EnvConfig(layout_seed=0,connected=12,max_slots=1,
                    properties={'paper.deliveryConvention':'LEGACY'},observation_mode=mode)) as env:
                env.reset(seed=0,options={'task_seed':4000000})
                obs,reward,terminated,truncated,info=env.step(0)
                np.testing.assert_array_equal(obs[12:24],np.zeros(12))
                self.assertTrue(truncated);self.assertFalse(terminated)
                results.append((obs[:24],reward,info['seconds'],info['uav_battery_j']))
        np.testing.assert_array_equal(results[0][0],results[1][0])
        self.assertEqual(results[0][1:],results[1][1:])


if __name__=='__main__':unittest.main()
