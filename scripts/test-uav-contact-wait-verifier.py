"""Independently replay an exercised reservation and reject forged contact/TX timing."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

s=importlib.util.spec_from_file_location('mobile',Path(__file__).with_name('verify-uav-mobile.py'))
a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
root=Path(sys.argv.pop(1))


class ContactWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=json.loads((root/'manifest.json').read_text())
        assert cls.m['protocol']['allowContactWait']
        cls.name='ROUND_ROBIN__ALL_UAV__FIFO'
        for path in root.glob('*/seed-*/'+cls.name+'-tasks.csv'):
            d=path.parent;jobs={int(j['id']):j for j in a.read(d/'workload.csv')}
            rows=a.read(path)
            candidates=[o for o in rows if o['route']=='UAV' and a.num(o,'uploaded_s')>0
                and a.num(o,'planned_upload_start_s')>a.num(jobs[int(o['id'])],'arrival_s')+1e-8]
            if candidates:break
        else:raise AssertionError('No exercised contact wait; do not claim waiting was evaluated')
        cls.cfg=cls.m['configs'][d.parent.name];cls.jobs=jobs;cls.tid=candidates[0]['id']
        cls.data={suffix:a.read(d/(cls.name+'-'+suffix+'.csv')) for suffix in
            ['tasks','energy','visits','positions','coverage','updates','views','decisions']}

    def setUp(self):self.d=copy.deepcopy(self.data)

    def check(self):
        audit=a.MobileAudit(self.jobs,{int(o['id']):o for o in self.d['tasks']},self.d['energy'],
            self.cfg,'FIFO',self.m['protocol'],*[self.d[s] for s in ['visits','positions','coverage','updates','views']])
        audit.verify_mobile('ROUND_ROBIN',self.d['decisions'],'ALL_UAV')

    def task(self):return next(o for o in self.d['tasks'] if o['id']==self.tid)
    def coverage(self):return next(c for c in self.d['coverage'] if c['id']==self.tid)

    def test_original_exercised_wait(self):self.check()

    def test_upload_start_in_flight_rejected(self):
        self.task()['planned_upload_start_s']=self.jobs[int(self.tid)]['arrival_s']
        with self.assertRaises(AssertionError):self.check()

    def test_tx_energy_during_wait_rejected(self):
        source=self.jobs[int(self.tid)]['device'];e=next(e for e in self.d['energy'] if e['device']==source)
        e['tx_j']=str(float(e['tx_j'])+1)
        with self.assertRaises(AssertionError):self.check()

    def test_invented_future_contact_rejected(self):
        c=self.coverage();c['planned_upload_start_s']=str(float(c['planned_upload_start_s'])+30)
        with self.assertRaises(AssertionError):self.check()

    def test_missing_wait_plan_rejected(self):
        del self.coverage()['offload_available']
        with self.assertRaises(AssertionError):self.check()


if __name__=='__main__':unittest.main()
