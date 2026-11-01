import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("failure_diag",Path(__file__).with_name("diagnose-study-failures.py"))
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
class FailureTests(unittest.TestCase):
    def test_exclusive_reasons_and_contact_vs_upload(self):
        j=dict(arrival_s="1",deadline_s="21",device="0",actual_mi="100")
        cfg=dict(uavMips=100,devices=[dict(mips=100)],sites=[dict(connected=False)])
        o=dict(route="UAV",status="EXPIRED_WAITING",ready_s="30",planned_upload_start_s="1")
        self.assertEqual(d.classify(j,o,cfg,True),"UPLOAD_COMPUTE_INTRINSIC")
        o.update(ready_s="22",planned_upload_start_s="20")
        self.assertEqual(d.classify(j,o,cfg,True),"CONTACT_WAIT_INTRINSIC")
        o.update(ready_s="4")
        self.assertEqual(d.classify(j,o,cfg,True),"CPU_WAIT_OR_RUNNING_MISS")
        o.update(route="LOCAL",status="COMPLETED_ON_TIME")
        self.assertEqual(d.classify(j,o,cfg,True),"LOCAL_ON_TIME_DISCONNECTED")
        self.assertEqual(d.classify(j,o,cfg,False),"DELIVERED_ON_TIME")
    def test_blocking_is_observed_and_distinguishes_pre_admission(self):
        jobs={"i":dict(source="RESCUENET",arrival_s="2",deadline_s="7",actual_mi="100"),
              "b":dict(source="ALIBABA",arrival_s="0")}
        outcomes={"i":dict(route="UAV",ready_s="3",start_s="",resolved_s="7"),
                  "b":dict(route="BACKGROUND",start_s="1",resolved_s="9")}
        b=d.blocking(jobs["i"],outcomes["i"],jobs,outcomes,100)
        self.assertEqual(b["bg_wait_overlap_s"],4)
        self.assertEqual(b["bg_committed_before_image_arrival_s"],4)
        self.assertEqual(b["bg_started_after_image_admission_s"],0)
        self.assertEqual(b["bg_overlap_exceeds_isolated_slack"],1)
if __name__=="__main__":unittest.main()
