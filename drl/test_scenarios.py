"""P0 integration checks: interventions, pre-action information, paired workload."""
import csv
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from .environment import DATASET_PROPERTIES, EnvConfig, PaperEnv, ROOT, SCENARIO_MODES


class ScenarioTests(unittest.TestCase):
    def run_pairing(self, properties):
        with tempfile.TemporaryDirectory(dir=ROOT/"target",prefix="p0-test-") as temporary:
            base=None
            with PaperEnv(EnvConfig(max_slots=2,properties=properties,decision_state=True)) as env:
                for mode in SCENARIO_MODES:
                    obs,info=env.reset(seed=31,options={"task_seed":2000000,"scenario_mode":mode,
                        "shift_seed":2100000,"trace":True})
                    initial=info["decision_state"]
                    self.assertEqual(initial["time_s"],0)
                    self.assertEqual(initial["slots_completed"],0)
                    self.assertEqual(initial["devices"][0]["data_age_slots"],0)
                    for action in [0,1]: obs,_,_,_,info=env.step(action)
                    self.assertFalse(info["decision_state"]["action_allowed"])
                    self.assertEqual(initial["slots_completed"],0) # independent snapshot
                    trace=Path(temporary)/mode;env.save_trace(trace)
                    with (trace/"devices.csv").open() as f: rows=list(csv.DictReader(f))
                    inputs=[(r["slot"],r["device"],r["input_bytes"]) for r in rows]
                    if base is None: base=inputs
                    else:self.assertEqual(base,inputs) # interventions do not perturb task draws
                    m=json.loads((trace/"scenario.json").read_text())
                    self.assertEqual(m["mode"],mode)
                    self.assertEqual(m["task_seed"],2000000)

    def test_synthetic_task_sequence_is_paired_across_interventions(self):
        self.run_pairing({})

    @unittest.skipUnless(os.environ.get("DRL_TEST_DATASETS")=="1","enable real raw dataset checks")
    def test_real_dataset_sequence_is_paired_across_interventions(self):
        self.run_pairing(DATASET_PROPERTIES)

    def test_decision_snapshot_is_seed_blind_and_preserves_legacy_rollout(self):
        with PaperEnv(EnvConfig(max_slots=2)) as plain, PaperEnv(EnvConfig(max_slots=2,decision_state=True)) as rich:
            a,ai=plain.reset(seed=1,options={"task_seed":1})
            b,bi=rich.reset(seed=1,options={"task_seed":1})
            state=bi.pop("decision_state")
            np.testing.assert_array_equal(a,b);self.assertEqual(ai,bi)
            # A different future task stream cannot change the initial exposed state.
            _,other=rich.reset(seed=999,options={"task_seed":999})
            self.assertEqual(state,other["decision_state"])
            rich.reset(seed=1,options={"task_seed":1})
            self.assertEqual(set(state),{"schema","time_s","slots_completed","action_allowed",
                "slot_cap_s","data_age_limit_slots","workload_mode","uav","devices","compute"})
            for action in [8,2]:
                a,ar,at,ax,ai=plain.step(action);b,br,bt,bx,bi=rich.step(action)
                decision=bi.pop("decision_state")
                np.testing.assert_array_equal(a,b);self.assertEqual((ar,at,ax,ai),(br,bt,bx,bi))
                np.testing.assert_allclose([d["battery_j"]/d["capacity_j"] for d in decision["devices"]],b[:12])
                np.testing.assert_array_equal([d["data_age_slots"] for d in decision["devices"]],b[12:])

    def test_invalid_scenario_rejected_before_jvm_starts(self):
        for values in [dict(scenario_mode="unknown"),dict(shift_seed=2.5),dict(shift_seed=True),dict(decision_state="true")]:
            with self.assertRaises(ValueError): EnvConfig(**values)
        with PaperEnv() as env:
            with self.assertRaises(ValueError):env.reset(options={"scenario_mode":"unknown"})
            self.assertIsNone(env._process)


if __name__=="__main__":unittest.main()
