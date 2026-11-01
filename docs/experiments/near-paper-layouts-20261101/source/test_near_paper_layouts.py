import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('layouts',Path(__file__).with_name('near-paper-layouts.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LayoutTests(unittest.TestCase):
    def test_paired_rescue_classification_checks_delivery_and_intrinsic_time(self):
        j=dict(deadline_s='10',arrival_s='0',device='0',actual_mi='20')
        cfg=dict(devices=[dict(mips=1)],uavMips=100)
        self.assertEqual(m.diagnostic.classify(j,dict(status='COMPLETED_ON_TIME',route='LOCAL'),None,False,cfg),
                         'local_ontime_undelivered')
        self.assertEqual(m.diagnostic.classify(j,dict(status='COMPLETED_LATE',route='LOCAL'),None,False,cfg),
                         'local_intrinsic_compute_exceeds_budget')
        o=dict(status='EXPIRED_WAITING',route='UAV')
        c=dict(planned_upload_s='11',planned_upload_start_s='0')
        self.assertEqual(m.diagnostic.classify(j,o,c,False,cfg),'uav_upload_alone_exceeds_budget')
        c=dict(planned_upload_s='1',planned_upload_start_s='9')
        self.assertEqual(m.diagnostic.classify(j,o,c,False,cfg),'uav_contact_upload_compute_exceeds_budget')
    def test_bootstrap_resamples_environment_and_shared_workload_as_crossed_factors(self):
        layouts=[100,101];seeds=[0,1,2];policy=m.POLICIES[1];index={}
        for l in layouts:
            for s in seeds:
                index[l,s,m.BASE]=dict(delivered_image_dvr='.5')
                index[l,s,policy]=dict(delivered_image_dvr='.25')
        low,high,n=m.bootstrap(index,layouts,seeds,policy,'delivered_dvr',reps=100)
        self.assertEqual((low,high,n),(-.25,-.25,100))
        self.assertEqual(m.contrast([dict(total_energy_j='100',delivered_ontime_images='0')],
                                   [dict(total_energy_j='100',delivered_ontime_images='1')],'j_per_delivered'),None)
    def test_summary_uses_ratio_of_sums_and_keeps_censoring(self):
        rows=[]
        for success,energy in [(1,100),(3,120)]:
            rows.append(dict(delivered_ontime_images=str(success),image_ontime=str(success),
                image_dvr='.5',delivered_image_dvr='.5',total_energy_j=str(energy),uav_energy_j='50',
                image_completed='1',delivered_completed_images='1',image_mean_latency_s='2',image_p95_latency_s='3',
                delivered_mean_latency_s='2',delivered_p95_latency_s='3',uav_observed_time_s='1800',
                uav_death_observed='0',background_dvr='',image_offered='4'))
        r=m.summary(rows)
        self.assertEqual(r['j_per_delivered'],55)
        self.assertEqual(r['censored_cases'],2)
        self.assertIsNone(r['background_dvr'])
        self.assertEqual(r['cases'],2)
    def test_prepare_lock_changes_only_layout_seed_among_cases_and_rejects_drift(self):
        ref=m.ROOT/'target/near-paper-final-20261101'
        if not ref.exists():self.skipTest('Reference artifact unavailable')
        import json
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'campaign'
            plan=m.prepare(out,ref,True)
            self.assertEqual(plan['episodes'],10)
            self.assertFalse(set(plan['layout_seeds'])&set(plan['reserved_not_run_layout_seeds']))
            a=json.loads((out/'protocols/layout-100.json').read_text())
            b=json.loads((out/'protocols/layout-101.json').read_text())
            self.assertNotEqual(a.pop('layoutSeed'),b.pop('layoutSeed'));self.assertEqual(a,b)
            self.assertEqual(len(a['policies']),5)
            self.assertEqual(len(a['loads']),1)
            m.validate_lock(out)
            (out/'protocols/layout-100.json').write_text('{}')
            with self.assertRaisesRegex(AssertionError,'Protocol drift'):m.validate_lock(out)
if __name__=='__main__':unittest.main()
