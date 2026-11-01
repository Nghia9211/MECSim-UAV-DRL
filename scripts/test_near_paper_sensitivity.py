import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
s=importlib.util.spec_from_file_location('sensitivity',Path(__file__).with_name('near-paper-sensitivity.py'))
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class SensitivityTests(unittest.TestCase):
    def anchor(self):
        return dict(uavBytesPerSecond=2000000,dwellSeconds=60,loads=[dict(name='primary',criticalDeadlineSeconds=600,imageDeadlineSeconds=600)])
    def test_cpu_and_dwell_change_exactly_one_field(self):
        a=self.anchor()
        for factor,key,value in [('cpu','uavBytesPerSecond',500000),('dwell','dwellSeconds',15)]:
            b=m.modify(a,factor,value);m.validate_difference(a,b,factor,value)
            self.assertEqual(a[key],self.anchor()[key]);self.assertEqual(b[key],value)
            b['unplanned']='change'
            with self.assertRaises(AssertionError):m.validate_difference(a,b,factor,value)
    def test_deadline_changes_both_priority_budgets_and_nothing_else(self):
        a=self.anchor();b=m.modify(a,'deadline',300)
        self.assertEqual(b['loads'][0]['criticalDeadlineSeconds'],300)
        self.assertEqual(b['loads'][0]['imageDeadlineSeconds'],300)
        self.assertEqual(a['loads'][0]['criticalDeadlineSeconds'],600)
        m.validate_difference(a,b,'deadline',300)
    def test_workload_pairing_ignores_only_deadline_when_declared(self):
        a=[dict(id='0',actual_mi='4',deadline_s='600',estimated_mi='4.2')]
        b=copy.deepcopy(a);b[0]['deadline_s']='300'
        self.assertEqual(m.row_identity(a,True),m.row_identity(b,True))
        self.assertNotEqual(m.row_identity(a),m.row_identity(b))
        b[0]['estimated_mi']='4.3'
        self.assertNotEqual(m.row_identity(a,True),m.row_identity(b,True))
    def test_crossed_bootstrap_preserves_constant_pair_difference(self):
        ls=[100,101];ss=[0,1,2]
        a={(l,s):dict(delivered_image_dvr='.4') for l in ls for s in ss}
        b={(l,s):dict(delivered_image_dvr='.3') for l in ls for s in ss}
        lo,hi,n=m.boot_delta(a,b,ls,ss,'delivered_dvr',100)
        self.assertAlmostEqual(lo,-.1);self.assertAlmostEqual(hi,-.1);self.assertEqual(n,100)
    def test_prepare_smoke_locks_all_stages_and_source(self):
        ref=m.ROOT/'target/near-paper-layout-full-20261101'
        if not ref.exists():self.skipTest('Optional verified reference fixture unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'study';plan=m.prepare(out,ref,True)
            self.assertEqual(plan['new_episodes'],36);self.assertEqual(plan['reused_episodes'],6)
            self.assertEqual(plan['phase_order'],['cpu','deadline','dwell'])
            m.validate(out)
            with self.assertRaisesRegex(AssertionError,'Prior phase review required'):m.run_phase(out,'deadline')
            target=out/'protocols/cpu-low/layout-100.json';v=json.loads(target.read_text());v['dwellSeconds']=80
            target.write_text(json.dumps(v))
            with self.assertRaisesRegex(AssertionError,'Protocol drift'):m.validate(out)
if __name__=='__main__':unittest.main()
