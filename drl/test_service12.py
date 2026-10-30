import unittest
import numpy as np
from .service12_campaign import ServiceEnv,TRAIN_LAYOUTS,VALID_LAYOUTS,TEST_LAYOUTS
from .contact_environment import ContactEnv
from .service12_campaign import config
class Service12Tests(unittest.TestCase):
 def test_disjoint_layout_splits(self):
  self.assertFalse(set(TRAIN_LAYOUTS)&set(VALID_LAYOUTS));self.assertFalse(set(TRAIN_LAYOUTS)&set(TEST_LAYOUTS));self.assertFalse(set(VALID_LAYOUTS)&set(TEST_LAYOUTS))
 def test_action_adapter_matches_canonical_physics(self):
  with ServiceEnv() as short,ContactEnv(config()) as full:
   a,_=short.reset(seed=1,options={'task_seed':95003,'layout_seed':300})
   b,_=full.reset(seed=1,options={'task_seed':95003,'layout_seed':300})
   np.testing.assert_array_equal(a,b)
   for target in [0,3,5,2]:
    x=short.step(target);y=full.step(target*9)
    np.testing.assert_array_equal(x[0],y[0]);self.assertEqual(x[1:],y[1:])
   for action in [-1,12,.5]:
    with self.assertRaises(ValueError):short.step(action)
 def test_random_training_layouts_reproducible(self):
  with ServiceEnv(training=True) as env:
   a,ia=env.reset(seed=33);b,ib=env.reset(seed=33)
   self.assertIn(ia['layout_seed'],TRAIN_LAYOUTS);self.assertEqual(ia['layout_seed'],ib['layout_seed']);np.testing.assert_array_equal(a,b)
if __name__=='__main__':unittest.main()
