"""Legacy replay and mixed-v2 integration against the real Java bridge."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
from .environment import ROOT
from .mobile_environment import MobileConfig
from .contact_environment import ContactEnv, heuristic

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
rng=load("workload_reconstruction",ROOT/"scripts/workload_rng.py")

class WorkloadVersionTests(unittest.TestCase):
    def test_old_configs_keep_legacy_and_unknown_versions_fail(self):
        self.assertEqual(MobileConfig().workloadGenerator,"legacy-v1")
        with self.assertRaises(ValueError):MobileConfig(workloadGenerator="unknown")
        with self.assertRaises(ValueError):rng.derive(42,"unknown","IMAGE_ARRIVALS")

    def test_v2_roundtrip_repetition_and_full_independent_trace_audit(self):
        cfg=MobileConfig(control_mode="contact_policy",allowContactWait=True,
                         workloadGenerator="mixed-v2",imageRate=.08,backgroundRate=.02,uavBatteryJ=30000)
        with tempfile.TemporaryDirectory(prefix="workload-version-",dir=ROOT/"target") as tmp,ContactEnv(cfg) as env:
            a,info=env.reset(seed=0,options={"task_seed":2800000})
            b,_=env.reset(seed=0,options={"task_seed":2800001})
            np.testing.assert_array_equal(a,b)  # Future tasks cannot leak into initial observation.
            a,_=env.reset(seed=0,options={"task_seed":2800000})
            rewards=0
            while True:
                action=heuristic("CONTACT_GREEDY",a,info)
                a,reward,t,u,info=env.step(action);rewards+=reward
                if t or u:break
            path=Path(tmp)/"trace";env.save_trace(path)
            meta=json.loads((path/"scenario.json").read_text())
            self.assertEqual(meta["protocol"]["workloadGenerator"],"mixed-v2")
            audit=load("full_workload_trace_audit",ROOT/"scripts/verify-uav-mobile-trace.py")
            result=audit.verify(path)
            self.assertEqual(result["status"],"PASS")
            self.assertAlmostEqual(result["total_reward"],rewards)
            rows=rng.read(path/"workload.csv")
            images=rng.read(path/"source-pools/rescuenet-pool.csv")
            bg=rng.read(path/"source-pools/alibaba-pool.csv")
            corrupted=[dict(r) for r in rows];corrupted[0]["device"]=str((int(rows[0]["device"])+1)%12)
            with self.assertRaises(AssertionError):
                rng.verify_rows(corrupted,images,bg,meta["protocol"],2800000)
            # Corrupting the declared version must not still pass cost/hash-only checks.
            meta["protocol"]["workloadGenerator"]="legacy-v1"
            (path/"scenario.json").write_text(json.dumps(meta),encoding="utf-8")
            with self.assertRaises(AssertionError):audit.verify(path)

if __name__=="__main__":unittest.main()
