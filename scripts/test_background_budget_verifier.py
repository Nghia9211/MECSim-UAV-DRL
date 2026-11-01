"""Independent negative checks for new admission/drop traces; no saved-run dependency."""
import copy,importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("budget_audit",Path(__file__).with_name("verify-uav-offloading.py"))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class BudgetVerifierTests(unittest.TestCase):
    def audit(self,cap=4,schedule="BG_CAP_EDF",deadline=9,status="DROPPED_BACKGROUND_BUDGET"):
        jobs={1:dict(id="1",source="ALIBABA",device="-1",arrival_s="0",upload_ready_s="0",
            deadline_s=str(deadline),actual_mi="500",estimated_mi="500",priority="1")}
        outcomes={1:dict(route="BACKGROUND",status=status,decision_s="0",ready_s="0",start_s="",resolved_s="0",
            executed_mi="0",remaining_mi="500",uploaded_s="0")}
        cfg=dict(horizonSeconds=10,uavMips=100,uavCpuWatts=20,hoverWatts=80,uavBatteryJ=100000,
            devices=[dict(mips=100,idleWatts=.5,cpuWatts=3,txWatts=.1,batteryJ=10000)])
        energy=[dict(device="-1",idle_j="800",compute_j="0",tx_j="0",remaining_j="99200",powered_s="10"),
            dict(device="0",idle_j="5",compute_j="0",tx_j="0",remaining_j="9995",powered_s="10")]
        audit=a.Audit(jobs,outcomes,energy,cfg,schedule,.75);audit.background_cap_seconds=cap
        return audit
    def test_valid_cap_drop_conserves_work_but_is_not_completion(self):
        self.audit().verify([],"ALL_UAV")
    def test_rejects_false_drop_and_undeclared_mechanism(self):
        with self.assertRaises(AssertionError):self.audit(cap=6).verify([],"ALL_UAV")
        with self.assertRaises(AssertionError):self.audit(schedule="EDF").verify([],"ALL_UAV")
    def test_risk_precedence_and_fake_completion_are_rejected(self):
        with self.assertRaises(AssertionError):self.audit(schedule="RISK_BG_CAP_EDF",deadline=4).verify([],"ALL_UAV")
        with self.assertRaises(AssertionError):self.audit(status="COMPLETED_ON_TIME").verify([],"ALL_UAV")
if __name__=="__main__":unittest.main()
