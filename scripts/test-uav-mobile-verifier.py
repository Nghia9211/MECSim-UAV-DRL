"""Audit a stored mobile episode, then reject corruptions without touching original traces."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

spec=importlib.util.spec_from_file_location('mobile_audit',Path(__file__).with_name('verify-uav-mobile.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class MobileAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=Path(sys.argv[1]);cls.manifest=json.loads((root/'manifest.json').read_text())
        row=next(r for r in audit.read(root/'episodes.csv') if r['policy']=='ROUND_ROBIN__ALL_UAV__FIFO')
        cls.scenario=row['scenario'];cls.name=row['policy']
        directory=root/cls.scenario/f"seed-{row['seed']}"
        cls.jobs={int(j['id']):j for j in audit.read(directory/'workload.csv')}
        cls.data={suffix:audit.read(directory/(cls.name+'-'+suffix+'.csv')) for suffix in
                  ['tasks','energy','visits','positions','coverage','updates','views','decisions']}

    def setUp(self):self.d=copy.deepcopy(self.data)

    def instance(self):
        return audit.MobileAudit(self.jobs,{int(o['id']):o for o in self.d['tasks']},self.d['energy'],
            self.manifest['configs'][self.scenario],'FIFO',self.manifest['protocol'],
            *[self.d[s] for s in ['visits','positions','coverage','updates','views']])

    def verify(self):self.instance().verify_mobile('ROUND_ROBIN',self.d['decisions'],'ALL_UAV')

    def test_original_episode(self):self.verify()

    def test_changed_trajectory_is_rejected(self):
        self.d['positions'][-1]['x']=str(float(self.d['positions'][-1]['x'])+1)
        with self.assertRaisesRegex(AssertionError,'Trajectory x'):self.verify()

    def test_changed_coverage_distance_is_rejected(self):
        self.d['coverage'][0]['slant_m']=str(float(self.d['coverage'][0]['slant_m'])+1)
        with self.assertRaisesRegex(AssertionError,'3D coverage distance'):self.verify()

    def test_changed_service_snapshot_is_rejected(self):
        self.d['views'][0]['age_s']=str(float(self.d['views'][0]['age_s'])+1)
        with self.assertRaisesRegex(AssertionError,'Age view'):self.verify()

    def test_changed_arrival_plan_is_rejected(self):
        self.d['visits'][0]['planned_arrival_s']=str(float(self.d['visits'][0]['planned_arrival_s'])+1)
        with self.assertRaises(AssertionError):self.verify()

    def test_missing_completion_update_is_rejected(self):
        self.assertTrue(self.d['updates']);self.d['updates'].pop()
        with self.assertRaises(AssertionError):self.verify()

    def test_changed_battery_energy_is_rejected(self):
        self.d['energy'][0]['idle_j']=str(float(self.d['energy'][0]['idle_j'])+1)
        with self.assertRaisesRegex(AssertionError,'idle_j'):self.verify()

    def test_missing_route_decision_is_rejected(self):
        self.assertTrue(self.d['decisions']);self.d['decisions'].pop()
        with self.assertRaisesRegex(AssertionError,'Missing routing decisions'):self.verify()


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python scripts/test-uav-mobile-verifier.py RUN_DIR')
    unittest.main(argv=[sys.argv[0]],verbosity=2)
