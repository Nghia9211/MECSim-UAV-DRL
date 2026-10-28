"""Campaign protocol and independent layout/RNG checks before full-budget training."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from .environment import EnvConfig,PaperEnv,ROOT
from .paper_reference import command,constants,layout,load_protocol


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('reference_replay_test',ROOT/'scripts/verify-paper-conventions.py')
        cls.audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.audit)

    def test_frozen_train_budget_and_properties(self):
        p=load_protocol();args=command(p,1,1,Path('target/example'))
        self.assertEqual('1000000',args[args.index('--steps')+1])
        self.assertEqual('synthetic',args[args.index('--workload')+1])
        self.assertEqual('1',args[args.index('--layout-seed')+1])
        for k,v in p['properties'].items():self.assertIn(f'{k}={v}',args)

    def test_independent_layout_matches_java_full_precision_for_three_seeds(self):
        for seed in (0,1,2):
            with self.subTest(seed=seed),PaperEnv(EnvConfig(layout_seed=seed,decision_state=True)) as env:
                _,info=env.reset(seed=7)
                rows=info['decision_state']['devices'];ds=layout(seed,8,8,self.audit.JavaRandom)
                for actual,expected in zip(rows,ds):
                    self.assertEqual(actual['x_m'],expected['x']);self.assertEqual(actual['y_m'],expected['y'])
                    self.assertEqual(actual['capacity_j'],expected['capacity_j'])
                    self.assertEqual(actual['hardware'],expected['hardware']);self.assertEqual(actual['vision_task'],expected['task'])
                    self.assertEqual(actual['powered'],expected['powered']);self.assertEqual(actual['connected'],expected['connected'])

    def test_table_constants_mapping(self):
        c=constants();self.assertEqual(2.165,c['hardware']['RASPBERRY_PI_4B']['active_w']['HAAR'])
        self.assertEqual(8298.13,c['hardware']['NANOPC_T4']['bytes_per_s']['YOLOV3'])
        self.assertEqual(1600000,c['uav_battery_j'])


if __name__=='__main__':unittest.main()
