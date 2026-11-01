import json
from pathlib import Path
import tempfile
import unittest
from .sequential_study import prepare_stage1,prepare_stage2,queue_diagnostic,ROOT
class SequentialStudyTests(unittest.TestCase):
    def test_mobile_cannot_be_prepared_without_valid_full_stage1_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/"STAGE1_REVIEW.json").write_text(json.dumps(dict(status="PASS",allow_stage2=False)))
            with self.assertRaises(ValueError):prepare_stage2(p,p/"stage2.json")
    def test_offered_load_contract_and_frozen_development_partition(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"plan.json";prepare_stage1(path)
            p=json.loads(path.read_text())
            self.assertEqual(len(p["loads"])*len(p["taskSeeds"])*len(p["policies"]),1440)
            self.assertEqual(p["workloadGenerator"],"mixed-v2")
            self.assertTrue(all(name.startswith("ALL_UAV__") for name in p["policies"]))
            for l in p["loads"]:
                rho=l["imageRate"]*p["imageFixedMi"]/p["uavMips"]+l["backgroundRate"]*p["backgroundServiceMeanSecondsProxy"]
                self.assertAlmostEqual(rho,l["targetRho"])
                self.assertGreaterEqual(l["criticalDeadlineSeconds"],10)
    def test_queue_opportunity_counts_only_admitted_ready_unexpired_jobs(self):
        jobs={0:dict(source="RESCUENET",arrival_s="1",actual_mi="100",deadline_s="10"),
              1:dict(source="ALIBABA",arrival_s="1",actual_mi="100",deadline_s="10"),
              2:dict(source="RESCUENET",arrival_s="7",actual_mi="100",deadline_s="10")}
        outcomes={0:dict(route="UAV",start_s="2",ready_s="2",resolved_s="3",status="COMPLETED_ON_TIME"),
                  1:dict(route="BACKGROUND",start_s="3",ready_s="1",resolved_s="4",status="COMPLETED_ON_TIME"),
                  2:dict(route="UAV",start_s="8",ready_s="8",resolved_s="9",status="COMPLETED_ON_TIME")}
        d=queue_diagnostic(jobs,outcomes,dict(uavMips=100),10)
        self.assertEqual(d["uav_dispatches"],3)
        self.assertEqual(d["multi_ready_dispatches"],1)
        self.assertEqual(d["max_ready"],2)
if __name__=="__main__":unittest.main()
