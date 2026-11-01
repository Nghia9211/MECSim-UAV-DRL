import copy
import os
import unittest
import numpy as np

from .environment import DATASET_PROPERTIES, EnvConfig, PaperEnv
from .service_policy import ServiceOptions, ServicePolicy, VARIANTS


class ServiceTests(unittest.TestCase):
    def check_readonly(self, properties):
        with PaperEnv(EnvConfig(max_slots=2,properties=properties)) as queried, PaperEnv(EnvConfig(max_slots=2,properties=properties)) as plain:
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

    def test_relabeling_decodes_same_physical_action_and_fallback_is_defined(self):
        with PaperEnv() as env:
            env.reset(seed=0)
            packet=env.service_estimates()
        for variant in VARIANTS:
            original=ServicePolicy(variant).choose(packet)
            for seed in range(10):
                order=np.random.default_rng(seed).permutation(12) # new ID -> old ID
                inverse=np.argsort(order)
                shuffled=copy.deepcopy(packet)
                ds=shuffled["state"]["devices"]
                shuffled["state"]["devices"]=[ds[i] for i in order]
                for d in shuffled["state"]["devices"]:d["physical_id"]=int(inverse[d["physical_id"]])
                for c in shuffled["candidates"]:c["action"]=int(inverse[c["action"]])
                self.assertEqual(int(order[ServicePolicy(variant).choose(shuffled)]),original)
        empty=copy.deepcopy(packet)
        for c in empty["candidates"]:c["urgency_gain"]=0
        empty["state"]["devices"][7]["data_age_slots"]=9
        p=ServicePolicy();self.assertEqual(p.choose(empty),7)
        self.assertEqual(p.last_reason,"NO_POSITIVE_GAIN_OLDEST_FALLBACK")
        with self.assertRaises(ValueError):ServiceOptions(float("nan"),0)


if __name__=="__main__":unittest.main()
