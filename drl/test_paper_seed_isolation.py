"""Preflight contracts use disposable artifact fixtures, not a particular machine's old target/ runs."""
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .paper_seed_isolation import command,load_protocol,reused_run,validate_config
from .run import model_options

class SeedIsolationTests(unittest.TestCase):
    def config(self,p):
        hp={k:v for k,v in model_options("DQN").items() if k!="policy_kwargs"}
        hp["policy_kwargs"]={"net_arch":[64,64],"activation_fn":"ReLU"}
        return dict(algorithm="DQN",seed=0,requested_steps=1000000,status="COMPLETE",
            actual_steps=1000000,gradient_updates=249975,threads=1,device="cpu",
            environment=dict(layout_seed=0,powered=8,connected=8,reward=p["reward"],
                             properties=p["properties"],max_slots=p["max_slots"]),hyperparameters=hp)

    @contextmanager
    def fixture(self,p):
        # Byte placeholders test provenance validation, never model performance or training.
        with tempfile.TemporaryDirectory(prefix="paper-provenance-") as tmp:
            root=Path(tmp);base=root/p["reused_campaign"];run=base/p["reused_run"]
            run.mkdir(parents=True)
            cfg=self.config(p)
            (run/"config.json").write_text(json.dumps(cfg),encoding="utf-8")
            hashes={}
            for name,key in [("best_model.zip","best_sha256"),("final_model.zip","final_sha256")]:
                data=("fixture:"+name).encode();(run/name).write_bytes(data)
                hashes[key]=hashlib.sha256(data).hexdigest()
            source=b"# fixture source\n"
            for target in [root/"drl/environment.py",base/"source/drl/environment.py"]:
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source)
            (base/"manifest.json").write_text(json.dumps(dict(status="COMPLETE",
                source_sha256={"drl/environment.py":hashlib.sha256(source).hexdigest()})))
            (base/"verification.json").write_text(json.dumps(dict(status="PASS",checkpoints=[dict(seed=0,**hashes)])))
            with patch("drl.paper_seed_isolation.ROOT",root):
                yield root,run,cfg

    def test_new_seeds_use_same_layout_and_full_paper_budget(self):
        p=load_protocol()
        for seed in p["new_training_seeds"]:
            args=command(p,seed,p["fixed_layout_seed"],Path("target/example"))
            self.assertEqual("0",args[args.index("--layout-seed")+1])
            self.assertEqual(str(seed),args[args.index("--seed")+1])
            self.assertEqual("1000000",args[args.index("--steps")+1])
            self.assertEqual("synthetic",args[args.index("--workload")+1])
        self.assertEqual([1,2],p["new_training_seeds"])
        self.assertEqual(3,len(set(p["learning_seeds"])))

    def test_reused_run_provenance_and_config_are_verified(self):
        p=load_protocol()
        with self.fixture(p) as (_,run,cfg):
            actual,receipt=reused_run(p)
            self.assertEqual(actual,run);self.assertTrue(receipt["reused"]);self.assertEqual(0,receipt["seed"])
            self.assertEqual(0,validate_config(cfg,p,0)["layout_seed"])

    def test_wrong_layout_budget_or_hyperparameter_rejected(self):
        p=load_protocol();cfg=self.config(p)
        for name in ("layout","budget","gamma"):
            bad=copy.deepcopy(cfg)
            if name=="layout":bad["environment"]["layout_seed"]=1
            elif name=="budget":bad["actual_steps"]=990000
            else:bad["hyperparameters"]["gamma"]=1.
            with self.subTest(name=name),self.assertRaises(AssertionError):validate_config(bad,p,0)

    def test_checkpoint_corruption_is_rejected(self):
        p=load_protocol()
        with self.fixture(p) as (_,run,_):
            (run/"best_model.zip").write_bytes(b"changed checkpoint")
            with self.assertRaises(AssertionError):reused_run(p)

    def test_current_source_drift_is_rejected(self):
        p=load_protocol()
        with self.fixture(p) as (root,_,_):
            (root/"drl/environment.py").write_text("# changed source")
            with self.assertRaises(AssertionError):reused_run(p)

if __name__=="__main__":unittest.main()
