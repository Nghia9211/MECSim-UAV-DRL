"""Replay a real mobile risk-drop episode and reject corrupted guard outcomes."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

spec=importlib.util.spec_from_file_location('mobile',Path(__file__).with_name('verify-uav-mobile.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
root=Path(sys.argv.pop(1))


class MobileGuardAuditTests(unittest.TestCase):
    @classmethod
    def hand_fixture(cls):
        """Same hand case as Java: drop impossible BG while flying, serve next BG.

        Do not change benchmark seeds/workload to force a guard event. An inactive
        guard is a valid result; negative replay still needs a deterministic case.
        """
        cls.m=dict(protocol=dict(flightWatts=150,speedMps=5,altitudeMetres=10,dwellSeconds=10,rangeMetres=65))
        cls.cfg=dict(horizonSeconds=15,uavMips=100,uavCpuWatts=20,hoverWatts=80,uavBatteryJ=100000,
            startX=0,startY=0,sites=[dict(x=100,y=0,connected=False)],
            devices=[dict(mips=10,idleWatts=1,cpuWatts=3,txWatts=.1,batteryJ=10000)])
        cls.jobs={i:dict(id=str(i),source='ALIBABA' if i<2 else 'RESCUENET',device=str(-1 if i<2 else 0),
            arrival_s=str(0 if i<2 else 1),upload_ready_s=str(0 if i<2 else 1.00004),
            deadline_s=str([2,4,10][i]),priority='1' if i<2 else '2',input_bytes='0' if i<2 else '100',
            actual_mi=str([500,100,10][i]),estimated_mi=str([500,100,10][i])) for i in range(3)}
        task=lambda i,route,status,ready,start,end,work,left:dict(id=str(i),route=route,status=status,
            decision_s=str(0 if i<2 else 1),ready_s=str(ready),start_s=str(start),resolved_s=str(end),
            executed_mi=str(work),remaining_mi=str(left),uploaded_s='0')
        slant=math.hypot(95,10);upload=800/(20e6*math.log1p(.1*1e-8*slant**-4/1e-13)/math.log(2))
        cls.data=dict(tasks=[task(0,'BACKGROUND','DROPPED_DEADLINE_RISK',0,'',0,0,500),
            task(1,'BACKGROUND','COMPLETED_ON_TIME',0,0,1,100,0),task(2,'LOCAL','COMPLETED_ON_TIME',1,1,2,10,0)],
            energy=[dict(device='-1',idle_j='2250',compute_j='20',tx_j='0',powered_s='15',remaining_j='97730'),
                    dict(device='0',idle_j='15',compute_j='3',tx_j='0',powered_s='15',remaining_j='9982')],
            visits=[dict(at_s='0',previous='-1',target='0',from_x='0',from_y='0',to_x='100',to_y='0',planned_arrival_s='20')],
            positions=[dict(at_s='15',x='75',y='0',h='10',battery_j='97730')],
            coverage=[dict(id='2',at_s='1',device='0',available='false',slant_m=str(slant),upload_s=str(upload))],updates=[],
            views=[dict(at_s='0',id='0',x='100',y='0',battery_fraction='1',alive='true',connected='false',latest_generation_s='0',age_s='0')],
            decisions=[dict(id='2',at_s='1',device='0',estimated_mi='10',source_battery_j='9999',uav_battery_j='99830',
                local_finish_s='2',uav_finish_s='',local_marginal_j='3',uav_marginal_j=str(2+.1*upload),local_available='true',
                uav_available='false',local_battery_feasible='true',uav_battery_feasible='false',destination='LOCAL')])
        cls.tid=0
        print('No risk drops in this workload; negative audit uses explicit in-flight hand fixture.')

    @classmethod
    def setUpClass(cls):
        cls.m=json.loads((root/'manifest.json').read_text())
        cls.name='ROUND_ROBIN__DEADLINE_ENERGY__RISK_EDF'
        for path in root.glob('*/seed-*/'+cls.name+'-tasks.csv'):
            rows=a.read(path)
            if any(o['status']=='DROPPED_DEADLINE_RISK' for o in rows):break
        else:
            cls.hand_fixture()
            return
        d=path.parent;cls.cfg=cls.m['configs'][d.parent.name]
        cls.jobs={int(j['id']):j for j in a.read(d/'workload.csv')}
        cls.data={suffix:a.read(d/(cls.name+'-'+suffix+'.csv')) for suffix in
            ['tasks','energy','visits','positions','coverage','updates','views','decisions']}
        cls.tid=next(int(o['id']) for o in rows if o['status']=='DROPPED_DEADLINE_RISK')

    def setUp(self):
        self.d=copy.deepcopy(self.data);self.j=copy.deepcopy(self.jobs)

    def check(self):
        audit=a.MobileAudit(self.j,{int(o['id']):o for o in self.d['tasks']},self.d['energy'],
            self.cfg,'RISK_EDF',self.m['protocol'],
            *[self.d[s] for s in ['visits','positions','coverage','updates','views']])
        audit.verify_mobile('ROUND_ROBIN',self.d['decisions'],'DEADLINE_ENERGY')

    def test_original_mobile_guard_trace(self):self.check()

    def test_false_risk_estimate_rejected(self):
        self.j[self.tid]['estimated_mi']='0.000001'
        with self.assertRaises(AssertionError):self.check()

    def test_dropped_task_cannot_execute(self):
        next(o for o in self.d['tasks'] if int(o['id'])==self.tid)['executed_mi']='1'
        with self.assertRaises(AssertionError):self.check()


if __name__=='__main__':unittest.main()
