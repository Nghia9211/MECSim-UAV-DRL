"""Mutation tests; no files in the recorded campaign are changed."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(sys.argv.pop(1))
s=importlib.util.spec_from_file_location('qios',Path(__file__).with_name('verify-qios.py'))
q=importlib.util.module_from_spec(s);s.loader.exec_module(q)

class CorruptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=next(p for p in ROOT.glob('*/seed-*/QIOS__QIOS-projection.json') if json.loads(p.read_text()))
        cls.record=json.loads(path.read_text())[0];d=path.parent
        jobs={int(j['id']):j for j in q.a.read(d/'workload.csv')};outcomes={int(j['id']):j for j in q.a.read(d/'QIOS__QIOS-tasks.csv')}
        cfg=dict(horizonSeconds=600,uavMips=2000,uavCpuWatts=20,hoverWatts=80,uavBatteryJ=int(d.parent.name.split('-b')[1]),
            devices=[dict(mips=500,idleWatts=.5,cpuWatts=3,txWatts=.1,batteryJ=5000)]*4)
        cls.audit=q.a.Audit(jobs,outcomes,q.a.read(d/'QIOS__QIOS-energy.csv'),cfg,'EDF',.75)
    def test_original_passes(self):q.verify_record(self.record,self.audit)
    def corrupt(self,change):
        r=copy.deepcopy(self.record);change(r)
        with self.assertRaises(AssertionError):q.verify_record(r,self.audit)
    def test_score(self):self.corrupt(lambda r:r['local'].__setitem__('value',r['local']['value']+1))
    def test_energy(self):self.corrupt(lambda r:r['local'].__setitem__('energyJ',r['local']['energyJ']+10))
    def test_battery(self):self.corrupt(lambda r:r['localSnapshot']['nodes'][0].__setitem__('batteryJ',1))
    def test_route(self):self.corrupt(lambda r:r.__setitem__('selected','UAV' if r['selected']=='LOCAL' else 'LOCAL'))
    def test_ready(self):self.corrupt(lambda r:r['airSnapshot']['jobs'][-1].__setitem__('ready',r['airSnapshot']['jobs'][-1]['ready']+1))
    def test_estimate(self):self.corrupt(lambda r:r['localSnapshot']['jobs'][-1].__setitem__('estimatedRemainingMi',1))
    def test_missing_air_projection(self):self.corrupt(lambda r:r.__setitem__('airSnapshot',None))

if __name__=='__main__':unittest.main()
