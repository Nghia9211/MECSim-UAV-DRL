"""UAV energy-budget scenarios: task deadline x absolute UAV energy budget (scenario + measurement only).

Reuses the near-paper kernel, workload generator and independent verifier. The budget is the UAV
battery capacity in joules, set per scenario; no new routing/scheduling/mobility policy is added.
Hover is a fixed mission cost, so the controllable UAV energy is flight + compute + TX.
Workload does not depend on the budget: every budget shares the workload hash of its deadline/seed.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result


near = module('budget_near', 'near-paper-study.py')
metrics = module('budget_metrics', 'offloading_metrics.py')

# Absolute budgets in kJ. Pure hover to the 1800 s horizon costs 144 kJ (80 W), so 60/100 kJ force
# the battery to run out during or after the arrival window, 150 kJ is about "hover only", 200 kJ leaves
# room for flight, and 1600 kJ is the paper battery (unconstrained control).
BUDGETS_KJ = (60, 100, 150, 200, 1600)
DEADLINES_S = (300, 600)
POLICIES = ['ROUND_ROBIN__'+r+'__EDF' for r in
            ('ALL_LOCAL', 'ALL_UAV', 'SHORTEST_FINISH', 'DEADLINE_ENERGY', 'DELIVERY_AWARE')]


def scenario_name(deadline, budget_kj):
    return f'd{deadline}-b{budget_kj}kj'


def build_protocol(smoke=False, budgets_kj=BUDGETS_KJ, deadlines=DEADLINES_S):
    """Near-paper protocol with one scenario per (deadline, absolute UAV budget)."""
    if len(set(budgets_kj)) != len(budgets_kj) or any(b <= 0 for b in budgets_kj):
        raise ValueError('Budgets must be unique and positive')
    base = json.loads((ROOT/'PureEdgeSim/uav/offloading/near-paper-protocol.json').read_text())
    base.update(purpose='UAV energy-budget scenarios (deadline x absolute UAV budget); not paper reproduction',
                taskSeeds=list(range(2 if smoke else 30)), smoke=smoke, policies=POLICIES,
                budgetsKj=list(budgets_kj), loads=[])
    for d in deadlines:
        if base['arrivalWindowSeconds'] + d > base['horizonSeconds']:
            raise ValueError('Deadline must fit the horizon')
        for b in budgets_kj:
            base['loads'].append(dict(name=scenario_name(d, b), imageRate=.04, backgroundRate=0.,
                criticalDeadlineSeconds=d, imageDeadlineSeconds=d, uavBatteryJ=b*1000))
    return base


def prepare(path, smoke=False):
    if path.exists():
        raise FileExistsError(path)
    p = build_protocol(smoke)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p, indent=2)+'\n', encoding='utf8')
    return p


def report(root):
    """Per-scenario deadline vs UAV-energy tables. Descriptive only: no weighted score, no ranking."""
    root = Path(root)
    m = json.loads((root/'manifest.json').read_text()); v = json.loads((root/'verification.json').read_text())
    assert m['status'] == 'COMPLETE' and v['status'] == 'PASS'
    rows = [r for r in metrics.read(root/'core-metrics-summary.csv') if r['scenario'] != 'ALL']
    f = lambda x, s=1: 'NA' if x in ('', None) else f'{float(x)*s:.2f}'
    lines = ['# UAV energy-budget scenarios', '',
        f"Verifier PASS: {v['episodes']} episodes, {v['task_outcomes']} task outcomes, {m['seeds']} paired workload seeds, one fixed layout.",
        'Scope: scenarios and measurement only; baseline policies, unchanged kernel. Budget = absolute UAV battery (J).',
        'Hover is a fixed mission cost. Controllable energy = flight + compute + TX. Dropped/late images stay failures; NA = no on-time image.',
        'Exhausted = UAV battery reached zero before the horizon. Not a statistical test; compare policies within the same scenario only.', '',
        '| Scenario | Policy | Delivered DVR % | Compute DVR % | UAV kJ | Flight kJ | Hover kJ | Compute kJ | Controllable kJ | Budget used % | Exhausted | Controllable J / delivered on-time image | Delivered mean / P95 s |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['scenario']} | {r['policy'].replace('ROUND_ROBIN__','')} | {f(r['delivered_image_dvr'],100)} | {f(r['image_dvr'],100)} | "
            f"{f(r['mean_uav_j'],.001)} | {f(r['mean_uav_flight_j'],.001)} | {f(r['mean_uav_hover_j'],.001)} | {f(r['mean_uav_compute_j'],.001)} | "
            f"{f(r['mean_uav_controllable_j'],.001)} | {f(r['mean_uav_budget_used_frac'],100)} | {r['uav_budget_exhausted_cases']}/{r['cases']} | "
            f"{f(r['uav_controllable_j_per_delivered_ontime_image'])} | {f(r['mean_delivered_latency_s'])} / {f(r['mean_delivered_episode_p95_s'])} |")
    lines += ['', '## Delivered DVR % by absolute UAV budget', '']
    budgets = sorted({int(float(r['mean_uav_budget_j'])/1000) for r in rows})
    lines += ['| Deadline | Policy | ' + ' | '.join(f'{b} kJ' for b in budgets) + ' |', '| --- | --- | ' + ' | '.join('---:' for _ in budgets) + ' |']
    for d in sorted({r['scenario'].split('-')[0] for r in rows}):
        for policy in sorted({r['policy'] for r in rows}):
            cells = {int(float(r['mean_uav_budget_j'])/1000): f(r['delivered_image_dvr'], 100)
                     for r in rows if r['scenario'].startswith(d+'-') and r['policy'] == policy}
            lines.append(f"| {d} | {policy.replace('ROUND_ROBIN__','')} | " + ' | '.join(cells.get(b, 'NA') for b in budgets) + ' |')
    lines += ['', 'Source: core-metrics-summary.csv / core-metrics-episodes.csv (full tables incl. per-seed rows), manifest.json, verification.json.']
    (root/'ENERGY_BUDGET_RESULTS.md').write_text('\n'.join(lines)+'\n', encoding='utf8')


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    q = sub.add_parser('prepare'); q.add_argument('--protocol', type=Path, required=True); q.add_argument('--smoke', action='store_true')
    q = sub.add_parser('run'); q.add_argument('--protocol', type=Path, required=True); q.add_argument('--output', type=Path, required=True)
    q = sub.add_parser('verify'); q.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        p = prepare(args.protocol, args.smoke)
        print(f"Prepared {len(p['loads'])*len(p['taskSeeds'])*len(p['policies'])} episodes: {args.protocol}")
        return
    if args.command == 'run':
        subprocess.run([shutil.which('mvn') or 'mvn', '-o', 'compile', 'exec:java', '-Dexec.mainClass=uav.offloading.NearPaperBenchmark',
                        '-Dnear.protocol='+str(args.protocol), '-Dnear.output='+str(args.output)], cwd=ROOT, check=True)
    print(json.dumps(near.verify(args.output), indent=2)); metrics.export(args.output); report(args.output)
    print(args.output/'ENERGY_BUDGET_RESULTS.md')


if __name__ == '__main__':
    main()
