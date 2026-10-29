"""Reject corrupted current-contact delivery routing and telemetry; keep traces unchanged."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

s=importlib.util.spec_from_file_location('mobile',Path(__file__).with_name('verify-uav-mobile.py'))
a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
root=Path(sys.argv.pop(1))


class DeliveryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=json.loads((root/'manifest.json').read_text())
        cls.name='ROUND_ROBIN__DELIVERY_AWARE__EDF'
        for path in root.glob('*/seed-*/'+cls.name+'-decisions.csv'):
            d=path.parent;jobs={int(j['id']):j for j in a.read(d/'workload.csv')}
            rows=a.read(path)
            candidates=[r for r in rows if r['local_delivery_available']=='false' and r['destination']=='UAV'
                and r['local_battery_feasible']=='true' and a.num(r,'local_finish_s')<=a.num(jobs[int(r['id'])],'deadline_s')+1e-8
                and a.num(r,'local_marginal_j')<a.num(r,'uav_marginal_j')]
            if candidates:break
        else:raise AssertionError('No exercised delivery override; inspect coverage before claiming a routing evaluation')
        cls.cfg=cls.m['configs'][d.parent.name];cls.jobs=jobs;cls.tid=candidates[0]['id']
        cls.data={suffix:a.read(d/(cls.name+'-'+suffix+'.csv')) for suffix in
            ['tasks','energy','visits','positions','coverage','updates','views','decisions']}

    def setUp(self):self.d=copy.deepcopy(self.data)

    def check(self):
        audit=a.MobileAudit(self.jobs,{int(o['id']):o for o in self.d['tasks']},self.d['energy'],
            self.cfg,'EDF',self.m['protocol'],
            *[self.d[s] for s in ['visits','positions','coverage','updates','views']])
        audit.verify_mobile('ROUND_ROBIN',self.d['decisions'],'DELIVERY_AWARE')

    def decision(self):return next(r for r in self.d['decisions'] if r['id']==self.tid)

    def test_original_exercised_override(self):self.check()

    def test_falsified_connectivity_rejected(self):
        self.decision()['local_delivery_available']='true'
        with self.assertRaisesRegex(AssertionError,'Local delivery availability'):self.check()

    def test_missing_delivery_observation_rejected(self):
        del self.decision()['local_delivery_available']
        with self.assertRaisesRegex(AssertionError,'Missing delivery availability'):self.check()

    def test_old_local_choice_rejected(self):
        self.decision()['destination']='LOCAL'
        with self.assertRaisesRegex(AssertionError,'Offloading policy/trace mismatch'):self.check()

    def test_missing_delivery_update_rejected(self):
        self.d['updates']=[r for r in self.d['updates'] if r['id']!=self.tid]
        # A later selector snapshot may expose the missing update before the final set check.
        with self.assertRaises(AssertionError):self.check()


if __name__=='__main__':unittest.main()
