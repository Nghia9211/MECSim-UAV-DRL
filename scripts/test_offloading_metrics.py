"""Check denominator, latency selection, censoring and zero-success semantics."""
import unittest
import json
from pathlib import Path
import tempfile
import csv
import hashlib
from offloading_metrics import calculate, p95, compare, export, read


class MetricsTests(unittest.TestCase):
    def test_mobile_delivery_and_flight_energy_without_source_row_tripling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/'compact-light-b1000/seed-1';d.mkdir(parents=True)
            def write(path,rows):
                with path.open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            write(d/'workload.csv',[dict(id=str(i),source='RESCUENET',arrival_s='0') for i in (1,2)])
            name='ROUND_ROBIN__ALL_LOCAL__FIFO'
            write(d/(name+'-tasks.csv'),[dict(id=str(i),status='COMPLETED_ON_TIME',resolved_s=str(i),route='LOCAL') for i in (1,2)])
            write(d/(name+'-energy.csv'),[
                dict(device=-1,idle_j=200,compute_j=20,tx_j=0,powered_s=20,remaining_j=780),
                dict(device=0,idle_j=10,compute_j=10,tx_j=0,powered_s=20,remaining_j=980)])
            write(d/(name+'-updates.csv'),[dict(id='1')])
            write(d/(name+'-coverage.csv'),[dict(available='true'),dict(available='false')])
            row=dict(scenario=d.parent.name,seed='1',policy=name,
                workload_sha256=hashlib.sha256((d/'workload.csv').read_bytes()).hexdigest(),flight_j=100,hover_j=100,travelled_m=5)
            write(root/'episodes.csv',[dict(row,source=s) for s in ('ALL','RESCUENET','ALIBABA')])
            (root/'manifest.json').write_text(json.dumps(dict(schema='uav-mobile-service-v1',status='COMPLETE',episodes=1,protocol=dict(horizonSeconds=20))))
            (root/'verification.json').write_text(json.dumps(dict(status='PASS')))
            rows=export(root);self.assertEqual(len(rows),1)
            r=rows[0]
            self.assertEqual(r['total_energy_j'],240)
            self.assertEqual(r['image_dvr'],0)
            self.assertEqual(r['delivered_image_dvr'],.5)
            self.assertEqual(r['j_per_ontime_image'],120)
            self.assertEqual(r['j_per_delivered_ontime_image'],240)
            self.assertEqual(r['delivered_completed_images'],1)
            self.assertEqual(r['delivered_mean_latency_s'],1)
            self.assertEqual(r['delivered_p95_latency_s'],1)
            self.assertEqual(r['flight_j'],100)
            self.assertEqual(len(read(root/'core-metrics-episodes.csv')),1)

    def test_comparison_rejects_changed_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp)/name for name in ('a','b')]
            for root,horizon in zip(roots,(600,900)):
                root.mkdir()
                (root/'manifest.json').write_text(json.dumps(dict(protocol=dict(horizonSeconds=horizon))))
            with self.assertRaisesRegex(AssertionError,'Different protocols'):
                compare(roots,Path(tmp)/'comparison')

    def test_drops_late_and_horizon_survivor(self):
        jobs = {str(i):dict(source='RESCUENET',arrival_s='1') for i in range(4)}
        outcomes = {str(i):dict(status=status,resolved_s=str(end)) for i,(status,end) in enumerate([
            ('COMPLETED_ON_TIME',3),('COMPLETED_LATE',11),('DROPPED_DEADLINE_RISK',2),('UNFINISHED_HORIZON',20)])}
        energy = [dict(device='-1',idle_j='80',compute_j='20',tx_j='0',powered_s='20',remaining_j='100')]
        r = calculate(jobs,outcomes,energy,20)
        self.assertEqual(r['image_dvr'],.75)
        self.assertEqual(r['j_per_ontime_image'],100)
        self.assertEqual(r['image_mean_latency_s'],6)
        self.assertEqual(r['image_p95_latency_s'],10)
        self.assertEqual(r['uav_death_observed'],0)
        self.assertEqual(r['uav_observed_time_s'],20)

    def test_zero_success_and_actual_depletion(self):
        r = calculate({'1':dict(source='RESCUENET',arrival_s='0')},
            {'1':dict(status='DROPPED_UAV_BATTERY',resolved_s='5')},
            [dict(device='-1',idle_j='80',compute_j='20',tx_j='0',powered_s='5',remaining_j='0')],20)
        self.assertIsNone(r['j_per_ontime_image'])
        self.assertIsNone(r['image_p95_latency_s'])
        self.assertEqual(r['image_dvr'],1)
        self.assertEqual(r['uav_death_observed'],1)
        self.assertEqual(p95(list(range(1,21))),19)


if __name__ == '__main__':
    unittest.main()
