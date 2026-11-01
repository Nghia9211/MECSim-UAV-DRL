"""The still-supported paper forecast API stays causal and read-only after P1 policy retirement."""
import os
import unittest
import numpy as np
from .environment import DATASET_PROPERTIES,EnvConfig,PaperEnv

class ServiceEstimateTests(unittest.TestCase):
    def check_readonly(self,properties):
        with PaperEnv(EnvConfig(max_slots=2,properties=properties)) as queried,PaperEnv(EnvConfig(max_slots=2,properties=properties)) as plain:
            queried.reset(seed=1,options={"task_seed":1});plain.reset(seed=1,options={"task_seed":1})
            packet=queried.service_estimates()
            for _ in range(3):self.assertEqual(packet,queried.service_estimates())
            queried.reset(seed=999,options={"task_seed":999})
            self.assertEqual(packet,queried.service_estimates())
            queried.reset(seed=1,options={"task_seed":1})
            for action in [8,2]:
                queried.service_estimates()
                a,*rest=queried.step(action);b,*other=plain.step(action)
                np.testing.assert_array_equal(a,b);self.assertEqual(rest,other)
            with self.assertRaises(RuntimeError):queried.service_estimates()

    def test_forecast_is_seed_blind_readonly_synthetic(self):self.check_readonly({})

    @unittest.skipUnless(os.environ.get("DRL_TEST_DATASETS")=="1","requires raw datasets")
    def test_forecast_is_seed_blind_readonly_mixed(self):self.check_readonly(DATASET_PROPERTIES)

if __name__=="__main__":unittest.main()
