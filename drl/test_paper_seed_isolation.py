"""Preflight checks for the fixed-layout development diagnostic."""
import copy
from pathlib import Path
import unittest

from .paper_seed_isolation import command,load_protocol,reused_run,validate_config
from .paper_reference import read


class SeedIsolationTests(unittest.TestCase):
    def test_new_seeds_use_same_layout_and_full_paper_budget(self):
        p=load_protocol()
        for seed in p['new_training_seeds']:
            args=command(p,seed,p['fixed_layout_seed'],Path('target/example'))
            self.assertEqual('0',args[args.index('--layout-seed')+1])
            self.assertEqual(str(seed),args[args.index('--seed')+1])
            self.assertEqual('1000000',args[args.index('--steps')+1])
            self.assertEqual('synthetic',args[args.index('--workload')+1])
        self.assertEqual([1,2],p['new_training_seeds'])
        self.assertEqual(3,len(set(p['learning_seeds'])))

    def test_reused_run_provenance_and_config_are_verified(self):
        import json
        p=load_protocol();run,receipt=reused_run(p)
        self.assertTrue(receipt['reused']);self.assertEqual(0,receipt['seed'])
        cfg=json.loads((run/'config.json').read_text())
        self.assertEqual(0,validate_config(cfg,p,0)['layout_seed'])

    def test_wrong_layout_budget_or_hyperparameter_rejected(self):
        import json
        p=load_protocol();run,_=reused_run(p);cfg=json.loads((run/'config.json').read_text())
        for name in ('layout','budget','gamma'):
            bad=copy.deepcopy(cfg)
            if name=='layout':bad['environment']['layout_seed']=1
            elif name=='budget':bad['actual_steps']=990000
            else:bad['hyperparameters']['gamma']=1.
            with self.subTest(name=name),self.assertRaises(AssertionError):validate_config(bad,p,0)


if __name__=='__main__':unittest.main()
