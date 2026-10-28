"""Check that invalid early-drop traces are rejected; recorded files stay untouched."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
root=Path(sys.argv.pop(1))
s=importlib.util.spec_from_file_location('audit',Path(__file__).with_name('verify-uav-offloading.py'))
a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
class GuardVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in root.glob('*/seed-*/ALL_UAV__RISK_EDF-tasks.csv'):
            rows=a.read(path)
            if any(r['status']=='DROPPED_DEADLINE_RISK' for r in rows):break
        else:raise AssertionError('No guard trace')
        d=path.parent;cls.jobs={int(j['id']):j for j in a.read(d/'workload.csv')};cls.out={int(r['id']):r for r in rows}
        cls.energy=a.read(d/'ALL_UAV__RISK_EDF-energy.csv');cls.decisions=a.read(d/'ALL_UAV__RISK_EDF-decisions.csv')
        cls.tid=next(t for t,o in cls.out.items() if o['status']=='DROPPED_DEADLINE_RISK')
        cls.cfg=dict(horizonSeconds=600,uavMips=2000,uavCpuWatts=20,hoverWatts=80,uavBatteryJ=int(d.parent.name.split('-b')[1]),
            devices=[dict(mips=500,idleWatts=.5,cpuWatts=3,txWatts=.1,batteryJ=5000)]*4)
    def check(self,jobs,out):a.Audit(jobs,out,self.energy,self.cfg,'RISK_EDF',.75).verify(self.decisions,'ALL_UAV')
    def test_original(self):self.check(self.jobs,self.out)
    def test_false_risk_estimate_rejected(self):
        jobs=copy.deepcopy(self.jobs);jobs[self.tid]['estimated_mi']='0.000001'
        with self.assertRaises(AssertionError):self.check(jobs,self.out)
    def test_dropped_task_cannot_execute(self):
        out=copy.deepcopy(self.out);out[self.tid]['executed_mi']='1'
        with self.assertRaises(AssertionError):self.check(self.jobs,out)
    def test_early_drop_not_allowed_without_guard(self):
        with self.assertRaises(AssertionError):a.Audit(self.jobs,self.out,self.energy,self.cfg,'EDF',.75).verify(self.decisions,'ALL_UAV')
if __name__=='__main__':unittest.main()
