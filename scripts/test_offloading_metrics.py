"""Check denominator, latency selection, censoring and zero-success semantics."""
import unittest
from offloading_metrics import calculate, p95


class MetricsTests(unittest.TestCase):
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
