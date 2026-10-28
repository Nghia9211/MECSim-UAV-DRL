import unittest
import numpy as np
from .environment import PaperEnv, EnvConfig


class ExtendedStateTests(unittest.TestCase):
    def test_fixed_actions_preserve_physics_reward_and_raw_state(self):
        p={'paper.deliveryConvention':'COMPLETED'}
        with PaperEnv(EnvConfig(layout_seed=0,properties=p,decision_state=True)) as old, PaperEnv(
                EnvConfig(layout_seed=0,properties=p,observation_mode='extended125')) as new:
            a,ia=old.reset(seed=17,options={'task_seed':2000000})
            b,ib=new.reset(seed=17,options={'task_seed':2000000})
            self.assertEqual(b.shape,(125,));np.testing.assert_array_equal(a,b[:24])
            self.assertTrue(new.observation_space.contains(b))
            self.assertEqual(ia['decision_state'],ib['decision_state'])
            # Initial extension depends on layout/current state, not the upcoming task seed.
            c,_=new.reset(seed=17,options={'task_seed':2000001})
            np.testing.assert_array_equal(b,c)
            new.reset(seed=17,options={'task_seed':2000000})
            for action in [1,2,3,5,6,7,8,10,11,1]:
                a,ra,ta,xa,ia=old.step(action);b,rb,tb,xb,ib=new.step(action)
                np.testing.assert_array_equal(a,b[:24]);self.assertEqual((ra,ta,xa),(rb,tb,xb))
                self.assertEqual(ia['decision_state'],ib['decision_state'])
                self.assertTrue(new.observation_space.contains(b))
                u=ib['decision_state']['uav']
                np.testing.assert_allclose(b[24:27],[u['x_m']/800,u['y_m']/800,u['battery_j']/1600000],rtol=1e-6)
                if ta or xa:break

    def test_unsupported_modes_rejected(self):
        with self.assertRaises(ValueError):EnvConfig(observation_mode='unknown')
        with self.assertRaises(ValueError):EnvConfig(observation_mode='extended125',properties={'paper.workload':'datasets'})


if __name__=='__main__':unittest.main()
