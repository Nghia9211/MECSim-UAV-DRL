"""Contracts for near-paper synthetic workload and independent audit."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('near',Path(__file__).with_name('near-paper-study.py'))
near=importlib.util.module_from_spec(spec);spec.loader.exec_module(near)
class NearPaperTests(unittest.TestCase):
    def test_seed_reconstruction_keeps_hardware_paper_scale_and_changes_only_estimate(self):
        p=json.loads((near.ROOT/'PureEdgeSim/uav/offloading/near-paper-protocol.json').read_text())
        a=near.generate(p,p['loads'][0],7,[])
        q=copy.deepcopy(p);q['estimateError']=.4
        b=near.generate(q,q['loads'][0],7,[])
        self.assertGreater(len(a),10)
        for x,y in zip(a,b):
            self.assertEqual({k:v for k,v in x.items() if k!='estimated_mi'},
                             {k:v for k,v in y.items() if k!='estimated_mi'})
            self.assertEqual(x['source'],'SYNTHETIC_IMAGE')
            self.assertTrue(2_000_000<=x['input_bytes']<=4_000_000)
        layout=near.paper_layout(p)
        self.assertEqual(sum(d['connected'] for d in layout),8)
        self.assertFalse(any(d['powered'] for d in layout))
    def test_background_toggle_preserves_every_image_field_including_estimate(self):
        p=json.loads((near.ROOT/'PureEdgeSim/uav/offloading/near-paper-protocol.json').read_text())
        load=copy.deepcopy(p['loads'][0])
        a=near.generate(p,load,7,[])
        load['backgroundRate']=.1
        pool=[dict(source_line=1,start_s=0,end_s=100,plan_cpu=20)]
        b=near.generate(p,load,7,pool)
        self.assertEqual(a,[j for j in b if j['source']=='SYNTHETIC_IMAGE'])
    def test_synthetic_images_are_counted_by_mandatory_metrics(self):
        j={'id':'0','source':'SYNTHETIC_IMAGE','arrival_s':'0'}
        o={'status':'COMPLETED_ON_TIME','resolved_s':'3'}
        e={'device':'-1','powered_s':'10','remaining_j':'100','idle_j':'80','compute_j':'20','tx_j':'0'}
        result=near.metrics.calculate({'0':j},{'0':o},[e],10)
        self.assertEqual(result['image_offered'],1)
        self.assertEqual(result['image_dvr'],0)
        self.assertEqual(result['j_per_ontime_image'],100)
        self.assertEqual(result['uav_death_observed'],0)
        o['status']='EXPIRED_WAITING'
        result=near.metrics.calculate({'0':j},{'0':o},[e],10)
        self.assertIsNone(result['j_per_ontime_image'])
        self.assertEqual(result['image_completed'],0)
    def test_reconstructs_48_episode_smoke_and_rejects_task_and_energy_corruption(self):
        root=near.ROOT/'target/near-paper-check-20261101'
        if not root.exists():self.skipTest('Optional generated smoke fixture absent')
        self.assertEqual(near.verify(root)['episodes'],48)
        rows=near.read(root/'primary/seed-0/workload.csv')
        p=json.loads((root/'manifest.json').read_text())['protocol']
        expected=near.generate(p,p['loads'][0],0,[])
        self.assertEqual(len(rows),len(expected))
        # Directly attack common physics audit on one actual episode.
        policy='ROUND_ROBIN__ALL_UAV__EDF';d=root/'primary/seed-0'
        jobs={int(j['id']):j for j in rows}
        original={int(o['id']):o for o in near.read(d/(policy+'-tasks.csv'))}
        cfg=json.loads((root/'manifest.json').read_text())['configs']['primary']
        def audit(jobs,energy):
            a=near.mobile.MobileAudit(jobs,original,energy,cfg,'EDF',p,
                *[near.read(d/(policy+'-'+s+'.csv')) for s in ('visits','positions','coverage','updates','views')])
            a.verify_mobile('ROUND_ROBIN',near.read(d/(policy+'-decisions.csv')),'ALL_UAV')
        energy=near.read(d/(policy+'-energy.csv'))
        bad=copy.deepcopy(energy);bad[0]['idle_j']=str(float(bad[0]['idle_j'])+100)
        with self.assertRaises(AssertionError):audit(jobs,bad)
        bad=copy.deepcopy(jobs);key=next(iter(bad));bad[key]['actual_mi']=str(float(bad[key]['actual_mi'])+100)
        with self.assertRaises(AssertionError):audit(bad,energy)
if __name__=='__main__':unittest.main()
