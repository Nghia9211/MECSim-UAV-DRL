"""One-factor design contracts and actual Java transition checks; old run fixtures are isolated."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .environment import EnvConfig,PaperEnv
from .paper_convention_retrain import PROTOCOL,feasibility_preflight,load_plan,profile_config
from .paper_seed_isolation import load_protocol

class ConventionRetrainTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        p=json.loads(PROTOCOL.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="convention-provenance-") as tmp:
            root=Path(tmp);base=root/p["reference_campaign"];base.mkdir(parents=True)
            proposal=root/p["proposal"];proposal.parent.mkdir(parents=True);proposal.write_text("# fixture proposal")
            source=b"# fixture source\n"
            for target in [root/"drl/environment.py",base/"source/drl/environment.py"]:
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source)
            (base/"manifest.json").write_text(json.dumps(dict(status="COMPLETE",protocol=load_protocol(),
                source_sha256={"drl/environment.py":hashlib.sha256(source).hexdigest()})))
            (base/"verification.json").write_text(json.dumps(dict(status="PASS",total_trace_audits=270)))
            (base/"final-artifact-check.json").write_text(json.dumps(dict(status="PASS")))
            with patch("drl.paper_convention_retrain.ROOT",root):
                yield root

    def test_profiles_change_exactly_one_setting(self):
        with self.fixture():
            p,base=load_plan()
            for _,override in p["profiles"].items():
                cfg=profile_config(base,override)
                changed={k for k in cfg["properties"] if cfg["properties"][k]!=base["properties"][k]}
                self.assertEqual(set(override),changed)
                self.assertEqual(1000000,cfg["steps_per_model"])
                self.assertEqual([0,1,2],cfg["learning_seeds"])

    def test_source_drift_still_rejects_plan(self):
        with self.fixture() as root:
            (root/"drl/environment.py").write_text("# changed source")
            with self.assertRaises(AssertionError):load_plan()

    def test_completion_changes_freshness_not_single_slot_energy(self):
        with PaperEnv(EnvConfig(layout_seed=0,powered=12,connected=12,max_slots=1)) as ref,PaperEnv(EnvConfig(layout_seed=0,powered=12,connected=12,max_slots=1,properties={"paper.deliveryConvention":"COMPLETED"})) as altered:
            ref.reset(seed=43,options={"task_seed":43});altered.reset(seed=43,options={"task_seed":43})
            a=ref.step(0);b=altered.step(0)
            self.assertEqual(a[4]["seconds"],b[4]["seconds"])
            self.assertEqual(a[4]["uav_battery_j"],b[4]["uav_battery_j"])
            self.assertEqual(0,max(a[0][12:]));self.assertGreater(max(b[0][12:]),0)

    def test_optimistic_cover_bound_is_not_immediately_impossible(self):
        p=feasibility_preflight();self.assertEqual(9,len(p["LOCAL_COMPLETION"]["always_uav_dependent_devices"]))
        self.assertEqual(7,p["LOCAL_COMPLETION"]["optimistic_min_visits_per_age_window"])
        self.assertTrue(p["LOCAL_COMPLETION"]["necessary_cover_bound_satisfied"])

if __name__=="__main__":unittest.main()
