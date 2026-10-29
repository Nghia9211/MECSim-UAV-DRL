"""Mandatory fixed-UAV metrics from full task/energy traces (stdlib only).

Run after the independent verifier. Never treats risk drops as completions.
Lifetime is UAV battery service availability, not whole-network lifetime.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics as st


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def p95(values):
    return sorted(values)[math.ceil(.95 * len(values))-1] if values else None


def mean(values):
    values = [v for v in values if v is not None]
    return st.mean(values) if values else None


def calculate(jobs, outcomes, energies, horizon):
    assert set(jobs) == set(outcomes), 'Missing/extra outcomes'
    images = [k for k, j in jobs.items() if j['source'] == 'RESCUENET']
    bg = [k for k, j in jobs.items() if j['source'] == 'ALIBABA']
    on = lambda keys: sum(outcomes[k]['status'] == 'COMPLETED_ON_TIME' for k in keys)
    latency = [float(outcomes[k]['resolved_s'])-float(jobs[k]['arrival_s'])
               for k in images if outcomes[k]['status'] in ('COMPLETED_ON_TIME', 'COMPLETED_LATE')]
    assert all(math.isfinite(x) and x >= 0 for x in latency)
    energy = sum(float(e[k]) for e in energies for k in ('idle_j', 'compute_j', 'tx_j'))
    uav = next(e for e in energies if int(e['device']) == -1)
    alive = float(uav['powered_s'])
    # Horizon survivors are right-censored; never invent their exhaustion time.
    observed = alive < horizon-1e-7 or float(uav['remaining_j']) <= 1e-7
    return dict(image_offered=len(images), image_ontime=on(images),
                image_completed=len(latency), background_offered=len(bg), background_ontime=on(bg),
                image_dvr=1-on(images)/len(images) if images else None,
                background_dvr=1-on(bg)/len(bg) if bg else None,
                total_energy_j=energy, uav_energy_j=sum(float(uav[k]) for k in ('idle_j','compute_j','tx_j')),
                # Whole system energy / useful image completions; background energy included.
                j_per_ontime_image=energy/on(images) if on(images) else None,
                image_mean_latency_s=mean(latency), image_p95_latency_s=p95(latency),
                uav_observed_time_s=alive, uav_death_observed=int(observed), horizon_s=horizon)


def export(root):
    root = Path(root)
    m = json.loads((root/'manifest.json').read_text())
    v = json.loads((root/'verification.json').read_text())
    assert m['status'] == 'COMPLETE' and v['status'] == 'PASS', 'Require completed verified run'
    rows = read(root/'episodes.csv')
    if rows and 'source' in rows[0]:
        rows = [r for r in rows if r['source'] == 'ALL']  # Energy repeated per source!
    assert len(rows) == m['episodes']
    results = []
    for r in rows:
        d = root/r['scenario']/('seed-'+r['seed'])
        workload = d/'workload.csv'
        assert hashlib.sha256(workload.read_bytes()).hexdigest() == r['workload_sha256']
        jobs = {j['id']:j for j in read(workload)}
        outcomes = {o['id']:o for o in read(d/(r['policy']+'-tasks.csv'))}
        horizon = m['protocol']['horizonSeconds']
        values = calculate(jobs, outcomes, read(d/(r['policy']+'-energy.csv')), horizon)
        results.append(dict(scenario=r['scenario'], seed=r['seed'], policy=r['policy'],
                            workload_sha256=r['workload_sha256'], **values))
    write_csv(root/'core-metrics-episodes.csv', results)
    summarize(results, root)
    return results


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def summarize(rows, out):
    summary = []
    for scenario in ['ALL'] + sorted({r['scenario'] for r in rows}):
        for policy in sorted({r['policy'] for r in rows}):
            g = [r for r in rows if r['policy'] == policy and (scenario == 'ALL' or r['scenario'] == scenario)]
            if not g:
                continue
            on = sum(r['image_ontime'] for r in g)
            # Ratios of sums for efficiency; macro average for per-case DVR and latency.
            summary.append(dict(scenario=scenario, policy=policy, cases=len(g),
                image_dvr=mean([r['image_dvr'] for r in g]), background_dvr=mean([r['background_dvr'] for r in g]),
                total_ontime_images=on, mean_ontime_images=mean([r['image_ontime'] for r in g]),
                j_per_ontime_image=sum(r['total_energy_j'] for r in g)/on if on else None,
                zero_success_cases=sum(r['image_ontime']==0 for r in g),
                mean_image_latency_s=mean([r['image_mean_latency_s'] for r in g]),
                mean_episode_p95_s=mean([r['image_p95_latency_s'] for r in g]),
                latency_cases=sum(r['image_completed']>0 for r in g),
                mean_total_j=mean([r['total_energy_j'] for r in g]), mean_uav_j=mean([r['uav_energy_j'] for r in g]),
                mean_restricted_uav_lifetime_s=mean([r['uav_observed_time_s'] for r in g]),
                deaths_observed=sum(r['uav_death_observed'] for r in g),
                censored_cases=sum(1-r['uav_death_observed'] for r in g)))
    write_csv(out/'core-metrics-summary.csv', summary)
    lines = ['# Core offloading + scheduling metrics', '',
        'Image DVR includes every offered image: drops/rejections/deadline-risk failures remain failures.',
        'Energy efficiency = sum(whole-system J) / sum(on-time images), including background/hover energy. Empty efficiency means no successes.',
        'Latency uses completed images (on-time + late), never dropped tasks. Mean and P95 columns are equal-case means; P95 uses nearest rank per episode, not a pooled percentile.',
        'UAV lifetime is battery-based availability, not network lifetime. Restricted time = min(exhaustion time, horizon); censored survivors have only a lower bound. No extrapolation.',
        'All-case averages mix loads/batteries; consult per-scenario CSV before concluding. These are descriptive results, not significance tests.', '',
        '| Policy | Image DVR % | J/on-time image | Mean latency s | Mean episode P95 s | Restricted UAV time s | Censored/total |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    fmt = lambda x: 'NA' if x is None else f'{x:.3f}'
    for r in summary:
        if r['scenario'] == 'ALL':
            lines.append(f"| {r['policy']} | {fmt(100*r['image_dvr']) if r['image_dvr'] is not None else 'NA'} | {fmt(r['j_per_ontime_image'])} | {fmt(r['mean_image_latency_s'])} | {fmt(r['mean_episode_p95_s'])} | {fmt(r['mean_restricted_uav_lifetime_s'])} | {r['censored_cases']}/{r['cases']} |")
    (out/'CORE_METRICS.md').write_text('\n'.join(lines)+'\n', encoding='utf8')


def compare(roots, out):
    manifests = [json.loads((Path(p)/'manifest.json').read_text()) for p in roots]
    assert all(m['protocol'] == manifests[0]['protocol'] for m in manifests), 'Different protocols'
    errors = {m.get('estimate_error', m.get('estimateError')) for m in manifests}
    assert len(errors) == 1, 'Compare estimate-error settings separately'
    # Shared kernel and scheduler source hashes must agree; entrypoints may differ.
    shared = set.intersection(*(set(m['source_sha256']) for m in manifests))
    assert 'PureEdgeSim/uav/offloading/OffloadingSimulation.java' in shared, 'Missing shared kernel snapshot'
    for name in shared:
        if name.endswith(('Benchmark.java', 'Pilot.java', 'Study.java')):
            continue
        assert len({m['source_sha256'][name] for m in manifests}) == 1, 'Different model: '+name
    merged = {}
    paired = {}
    for root in roots:
        records = export(root)
        cases = {(r['scenario'],r['seed']):r['workload_sha256'] for r in records}
        if paired:
            assert paired == cases, 'Different scenarios/seeds/workloads'
        paired = cases
        for r in records:
            key = (r['scenario'],r['seed'],r['policy'])
            assert key not in merged or merged[key] == r, 'Inconsistent duplicate policy result'
            merged[key] = r
    out.mkdir(parents=True, exist_ok=False)
    write_csv(out/'core-metrics-episodes.csv', list(merged.values()))
    summarize(list(merged.values()), out)
    (out/'comparison-provenance.json').write_text(json.dumps(dict(roots=[str(p) for p in roots],
        estimate_error=next(iter(errors)),paired_cases=len(paired), episodes=len(merged),
        status='PAIRED_VERIFIED_INPUTS'),indent=2),encoding='utf8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        compare(args.runs, args.output)
    else:
        for root in args.runs:
            export(root)
