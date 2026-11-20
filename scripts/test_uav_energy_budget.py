"""Contracts for the UAV energy-budget scenario grid and report (no simulator needed)."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('budget', Path(__file__).with_name('uav-energy-budget-study.py'))
budget = importlib.util.module_from_spec(spec); spec.loader.exec_module(budget)


class EnergyBudgetTests(unittest.TestCase):
    def test_grid_is_deadline_cross_absolute_budget(self):
        p = budget.build_protocol()
        names = [x['name'] for x in p['loads']]
        self.assertEqual(len(names), len(budget.DEADLINES_S)*len(budget.BUDGETS_KJ))
        self.assertEqual(len(set(names)), len(names))
        self.assertTrue(all(n.replace('-', '').isalnum() and n == n.lower() for n in names))  # Java scenario-name regex
        for load in p['loads']:
            d = int(load['name'].split('-')[0][1:]); b = int(load['name'].split('-b')[1][:-2])
            self.assertEqual((load['criticalDeadlineSeconds'], load['imageDeadlineSeconds']), (d, d))
            self.assertEqual(load['uavBatteryJ'], b*1000)
            self.assertLessEqual(p['arrivalWindowSeconds']+d, p['horizonSeconds'])
        self.assertIn(1_600_000, [x['uavBatteryJ'] for x in p['loads']])   # unconstrained control kept
        self.assertEqual(len(budget.build_protocol(smoke=True)['taskSeeds']), 2)

    def test_physical_parameters_unchanged_from_near_paper(self):
        base = json.loads((budget.ROOT/'PureEdgeSim/uav/offloading/near-paper-protocol.json').read_text())
        p = budget.build_protocol()
        for k in ('flightWatts', 'dwellSeconds', 'uavBytesPerSecond', 'uavCpuWatts', 'horizonSeconds', 'arrivalWindowSeconds',
                  'estimateError', 'layoutSeed', 'connectedDevices', 'speedMps', 'rangeMetres'):
            self.assertEqual(p[k], base[k], k)

    def test_workload_is_identical_across_budgets(self):
        p = budget.build_protocol()
        a = [x for x in p['loads'] if x['name'] == 'd600-b60kj'][0]
        b = [x for x in p['loads'] if x['name'] == 'd600-b1600kj'][0]
        self.assertEqual(budget.near.generate(p, a, 3, []), budget.near.generate(p, b, 3, []))

    def test_rejects_bad_budgets_and_overlong_deadline(self):
        with self.assertRaises(ValueError): budget.build_protocol(budgets_kj=(60, 60))
        with self.assertRaises(ValueError): budget.build_protocol(budgets_kj=(0, 10))
        with self.assertRaises(ValueError): budget.build_protocol(deadlines=(1500,))

    def test_prepare_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'p.json'; budget.prepare(path, smoke=True)
            with self.assertRaises(FileExistsError): budget.prepare(path)

    def test_report_marks_na_and_keeps_scenarios_separate(self):
        keys = ['scenario', 'policy', 'cases', 'delivered_image_dvr', 'image_dvr', 'mean_uav_j', 'mean_uav_flight_j', 'mean_uav_hover_j',
                'mean_uav_compute_j', 'mean_uav_controllable_j', 'mean_uav_budget_j', 'mean_uav_budget_used_frac', 'uav_budget_exhausted_cases',
                'uav_controllable_j_per_delivered_ontime_image', 'mean_delivered_latency_s', 'mean_delivered_episode_p95_s']
        def row(sc, dvr, per):
            return dict(scenario=sc, policy='ROUND_ROBIN__ALL_UAV__EDF', cases=2, delivered_image_dvr=dvr, image_dvr=dvr, mean_uav_j=60000,
                mean_uav_flight_j=20000, mean_uav_hover_j=35000, mean_uav_compute_j=5000, mean_uav_controllable_j=25000,
                mean_uav_budget_j=60000 if sc.endswith('b60kj') else 1600000, mean_uav_budget_used_frac=1, uav_budget_exhausted_cases=2,
                uav_controllable_j_per_delivered_ontime_image=per, mean_delivered_latency_s='', mean_delivered_episode_p95_s='')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'manifest.json').write_text(json.dumps(dict(status='COMPLETE', seeds=2)))
            (root/'verification.json').write_text(json.dumps(dict(status='PASS', episodes=4, task_outcomes=10)))
            with (root/'core-metrics-summary.csv').open('w', newline='') as fh:
                w = csv.DictWriter(fh, fieldnames=keys); w.writeheader()
                w.writerows([row('ALL', .5, ''), row('d300-b60kj', 1.0, ''), row('d300-b1600kj', .25, 100)])
            budget.report(root)
            text = (root/'ENERGY_BUDGET_RESULTS.md').read_text()
        self.assertIn('| d300-b60kj |', text); self.assertIn('| d300-b1600kj |', text)
        self.assertNotIn('| ALL |', text)
        self.assertIn('NA', text)                       # zero-success scenario shows NA, not 0
        self.assertIn('| 60 kJ | 1600 kJ |', text.replace('  ', ' '))


if __name__ == '__main__':
    unittest.main()
