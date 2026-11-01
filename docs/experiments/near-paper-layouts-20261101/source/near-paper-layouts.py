"""Locked, paired near-paper baseline campaign across sampled paper environments.
Only primary load; no fitting, no new algorithm, no changes to simulation assumptions.
"""
import argparse
from collections import Counter
import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import shutil
import statistics as st
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
near=module('layout_near','near-paper-study.py')
diagnostic=module('layout_diagnostic','diagnose-near-paper.py')
single_report=module('layout_single_report','report-near-paper.py')
BASE='ROUND_ROBIN__ALL_LOCAL__EDF'
POLICIES=['ROUND_ROBIN__'+p+'__EDF' for p in ('ALL_LOCAL','ALL_UAV','SHORTEST_FINISH','DEADLINE_ENERGY','DELIVERY_AWARE')]
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return near.read(p)
def write(p,rows):
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def prepare(out,reference,smoke=False):
    if out.exists():raise FileExistsError(out)
    ref=json.loads((reference/'manifest.json').read_text());proof=json.loads((reference/'verification.json').read_text())
    assert ref['status']=='COMPLETE' and proof['status']=='PASS'
    p=copy.deepcopy(ref['protocol']);p['loads']=[next(x for x in p['loads'] if x['name']=='primary')]
    p['policies']=POLICIES;p['taskSeeds']=list(range(1 if smoke else 30));p['smoke']=smoke
    p['seedRole']='crossed paired workload seeds; layout seed also samples hardware, task type, battery and connectivity'
    layout_seeds=list(range(100,102 if smoke else 110))
    sources=set(ref['source_sha256'])|{'scripts/near-paper-layouts.py','scripts/diagnose-near-paper.py'}
    source_hashes={name:sha(ROOT/name) for name in sorted(sources)}
    out.mkdir(parents=True)
    for name,h in source_hashes.items():
        dest=out/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    protocol_hashes={}
    for seed in layout_seeds:
        q=copy.deepcopy(p);q['layoutSeed']=seed
        target=out/'protocols'/f'layout-{seed}.json';save(target,q);protocol_hashes[str(seed)]=sha(target)
    plan=dict(schema='near-paper-multilayout-v1',status='LOCKED',created=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        reference_run=str(reference),reference_manifest_sha256=sha(reference/'manifest.json'),
        reference_verification_sha256=sha(reference/'verification.json'),reference_layout_seed=42,
        layout_seeds=layout_seeds,reserved_not_run_layout_seeds=list(range(110,120)),
        task_seeds=p['taskSeeds'],policies=POLICIES,episodes=len(layout_seeds)*len(p['taskSeeds'])*len(POLICIES),
        source_sha256=source_hashes,protocol_sha256=protocol_hashes,scenario='primary',
        objectives=['delivered DVR','whole-system J/on-time delivered image','compute DVR','completed mean/P95 latency',
                    'total/UAV energy','censored UAV service lifetime','runtime'],
        analysis='equal-case DVR; ratios of summed energy/success counts; crossed layout/workload bootstrap 5000; exploratory',
        assumptions='unchanged physical/CPU/radio/deadline/dwell parameters vs primary reference; no Alibaba background',
        layout_semantics='PaperSimulation.layout changes geometry AND hardware/task/battery/connectivity together',
        independent_units='10 sampled environments crossed with the same 30 workload seeds; 1500 policy episodes are NOT 1500 independent samples',
        reserved_note='Not executed in this campaign. No global claim these seeds have never appeared in other studies.',
        source_holdout=False,training=False,paper_reproduction=False,smoke=smoke)
    save(out/'plan.json',plan);(out/'PLAN.sha256').write_text(sha(out/'plan.json')+'\n',encoding='ascii')
    return plan
def validate_lock(out):
    plan=json.loads((out/'plan.json').read_text())
    assert sha(out/'plan.json')==(out/'PLAN.sha256').read_text().strip(),'Plan changed after locking'
    assert not set(plan['layout_seeds'])&set(plan['reserved_not_run_layout_seeds']),'Reserved environments overlap'
    reference=Path(plan['reference_run'])
    assert sha(reference/'manifest.json')==plan['reference_manifest_sha256'],'Reference manifest drift'
    assert sha(reference/'verification.json')==plan['reference_verification_sha256'],'Reference audit drift'
    for name,h in plan['source_sha256'].items():
        assert sha(ROOT/name)==h,'Live code changed: '+name
        assert sha(out/'source'/name)==h,'Frozen source changed: '+name
    for seed,h in plan['protocol_sha256'].items():assert sha(out/'protocols'/f'layout-{seed}.json')==h,'Protocol drift'
    return plan
def validate_case_protocol(out,seed,manifest,plan):
    expected=json.loads((out/'protocols'/f'layout-{seed}.json').read_text())
    assert manifest['protocol']==expected,'Executed protocol differs from locked protocol'
    assert manifest['episodes']==len(plan['task_seeds'])*len(plan['policies']),'Case count'
    assert manifest['protocol_sha256']==plan['protocol_sha256'][str(seed)],'Executed protocol hash'
    for name,h in manifest['source_sha256'].items():
        assert plan['source_sha256'].get(name)==h,'Case source differs from lock: '+name
def run(out):
    out=out.resolve();plan=validate_lock(out);lock=out/'RUNNING.lock'
    with lock.open('x') as f:f.write(str(__import__('os').getpid()))
    try:
        save(out/'campaign-status.json',dict(status='RUNNING',episodes=plan['episodes']))
        with (out/'compile.log').open('w',encoding='utf8') as log:
            subprocess.run([shutil.which('mvn') or 'mvn','-o','-q','compile'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        for seed in plan['layout_seeds']:
            validate_lock(out);case=out/'runs'/f'layout-{seed}';protocol=out/'protocols'/f'layout-{seed}.json'
            logpath=out/f'layout-{seed}.log'
            if not case.exists():
                with logpath.open('w',encoding='utf8') as log:
                    proc=subprocess.run([shutil.which('mvn') or 'mvn','-o','-q','exec:java',
                        '-Dexec.mainClass=uav.offloading.NearPaperBenchmark','-Dnear.protocol='+str(protocol),
                        '-Dnear.output='+str(case)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                assert proc.returncode==0,f'Java failure, see {logpath}'
                save(out/f'layout-{seed}-process.json',dict(exit_code=proc.returncode,log_sha256=sha(logpath)))
            else:
                assert (case/'manifest.json').exists(),'Existing incomplete directory; inspect manually'
                assert json.loads((case/'manifest.json').read_text())['status']=='COMPLETE','Existing incomplete run; do not overwrite'
            manifest=json.loads((case/'manifest.json').read_text());validate_case_protocol(out,seed,manifest,plan)
            verification=near.verify(case);near.metrics.export(case)
            diagnostic.diagnose(case)
            print(f"LAYOUT {seed}: audit {verification['status']}, {verification['episodes']} episodes",flush=True)
        validate_lock(out);result=report(out)
        save(out/'campaign-status.json',dict(status='COMPLETE',episodes=result['episodes'],verified=True))
        print('CAMPAIGN_COMPLETE '+str(out),flush=True)
    except BaseException as e:
        save(out/'campaign-status.json',dict(status='FAILED',error=str(e)))
        raise
    finally:lock.unlink()
def average(values):
    a=[x for x in values if x is not None];return st.mean(a) if a else None
def float_or_none(x):return float(x) if x not in ('',None) else None
def summary(rows):
    images=sum(int(r['delivered_ontime_images']) for r in rows)
    compute=sum(int(r['image_ontime']) for r in rows)
    latency=[r for r in rows if int(r['image_completed'])>0]
    delivered_latency=[r for r in rows if int(r['delivered_completed_images'])>0]
    return dict(cases=len(rows),image_dvr=average([float_or_none(r['image_dvr']) for r in rows]),
        delivered_dvr=average([float_or_none(r['delivered_image_dvr']) for r in rows]),
        ontime_images=compute,delivered_ontime_images=images,
        total_energy_j=average([float(r['total_energy_j']) for r in rows]),
        uav_energy_j=average([float(r['uav_energy_j']) for r in rows]),
        j_per_delivered=sum(float(r['total_energy_j']) for r in rows)/images if images else None,
        j_per_compute=sum(float(r['total_energy_j']) for r in rows)/compute if compute else None,
        completed_mean_latency_s=average([float(r['image_mean_latency_s']) for r in latency]),
        completed_mean_episode_p95_s=average([float(r['image_p95_latency_s']) for r in latency]),
        delivered_mean_latency_s=average([float(r['delivered_mean_latency_s']) for r in delivered_latency]),
        delivered_mean_episode_p95_s=average([float(r['delivered_p95_latency_s']) for r in delivered_latency]),
        restricted_uav_time_s=average([float(r['uav_observed_time_s']) for r in rows]),
        censored_cases=sum(1-int(r['uav_death_observed']) for r in rows),
        background_dvr=average([float_or_none(r['background_dvr']) for r in rows]),
        zero_delivered_cases=sum(int(r['delivered_ontime_images'])==0 for r in rows),
        offered_images=sum(int(r['image_offered']) for r in rows))
def contrast(base,candidate,metric):
    if metric in ('delivered_dvr','image_dvr'):
        key='delivered_image_dvr' if metric=='delivered_dvr' else 'image_dvr'
        return st.mean(float(b[key])-float(a[key]) for a,b in zip(base,candidate))
    assert metric=='j_per_delivered'
    def ratio(rows):
        n=sum(int(r['delivered_ontime_images']) for r in rows)
        return sum(float(r['total_energy_j']) for r in rows)/n if n else None
    a,b=ratio(base),ratio(candidate)
    return b-a if a is not None and b is not None else None
def bootstrap(index,layouts,seeds,policy,metric,reps=5000):
    """Crossed factors: sample layouts and shared workload seeds independently with replacement."""
    rng=random.Random(20261101);samples=[]
    for _ in range(reps):
        ls=rng.choices(layouts,k=len(layouts));ss=rng.choices(seeds,k=len(seeds))
        pairs=[(index[l,s,BASE],index[l,s,policy]) for l in ls for s in ss]
        v=contrast([a for a,b in pairs],[b for a,b in pairs],metric)
        if v is not None:samples.append(v)
    if not samples:return None,None,0
    samples.sort();return samples[int(.025*len(samples))],samples[min(len(samples)-1,int(.975*len(samples)))],len(samples)
def report(out):
    plan=validate_lock(out);all_rows=[];runtime=[];queue=[];pair_counts=Counter();case_proofs={};pair_hash={}
    full_protocols={};total_outcomes=0
    for seed in plan['layout_seeds']:
        case=out/'runs'/f'layout-{seed}'
        m=json.loads((case/'manifest.json').read_text());v=json.loads((case/'verification.json').read_text())
        assert m['status']=='COMPLETE' and v['status']=='PASS';validate_case_protocol(out,seed,m,plan)
        total_outcomes+=v['task_outcomes'];case_proofs[str(seed)]=dict(manifest_sha256=sha(case/'manifest.json'),
            verification_sha256=sha(case/'verification.json'),core_metrics_sha256=sha(case/'core-metrics-episodes.csv'))
        entries=read(case/'core-metrics-episodes.csv')
        assert len(entries)==len(plan['task_seeds'])*len(plan['policies'])
        seen=set()
        for r in entries:
            key=int(r['seed']),r['policy'];assert key not in seen;seen.add(key)
            assert key[0] in plan['task_seeds'] and key[1] in plan['policies']
            assert r['scenario']=='primary'
            old=pair_hash.setdefault(int(r['seed']),r['workload_sha256'])
            assert old==r['workload_sha256'],'Layout or policy changed workload bytes'
            d=case/'primary'/('seed-'+r['seed'])
            assert sha(d/'workload.csv')==r['workload_sha256'],'Live workload changed'
            all_rows.append(dict(layout_seed=seed,**r))
            jobs={j['id']:j for j in read(d/'workload.csv')}
            outcomes={o['id']:o for o in read(d/(r['policy']+'-tasks.csv'))}
            # Recompute mandatory metrics from live traces, not inherited summary numbers.
            values=near.metrics.calculate(jobs,outcomes,read(d/(r['policy']+'-energy.csv')),m['protocol']['horizonSeconds'])
            for k,val in values.items():
                actual=float_or_none(r[k])
                assert (actual is None and val is None) or actual is not None and val is not None and math.isclose(actual,val,rel_tol=1e-9,abs_tol=1e-8),'Recount '+k
            delivered={u['id'] for u in read(d/(r['policy']+'-updates.csv'))}
            assert int(r['delivered_ontime_images'])==sum(outcomes[k]['status']=='COMPLETED_ON_TIME' for k in delivered)
            queue.append(dict(layout_seed=seed,seed=int(r['seed']),policy=r['policy'],**single_report.queue_counts(jobs,outcomes)))
        process=json.loads((out/f'layout-{seed}-process.json').read_text());assert process['exit_code']==0
        assert sha(out/f'layout-{seed}.log')==process['log_sha256'],'Process log drift'
        for r in read(case/'episodes.csv'):runtime.append(dict(layout_seed=seed,seed=r['seed'],policy=r['policy'],wall_ms=r['wall_ms']))
        for r in read(case/'diagnosis/paired-images.csv'):pair_counts[r['change']]+=1
    assert len(all_rows)==plan['episodes']
    write(out/'episodes-core.csv',all_rows);write(out/'queue-opportunities.csv',queue)
    summaries=[]
    for layout in ['ALL']+plan['layout_seeds']:
        for policy in plan['policies']:
            group=[r for r in all_rows if r['policy']==policy and (layout=='ALL' or r['layout_seed']==layout)]
            summaries.append(dict(layout_seed=layout,policy=policy,**summary(group)))
    write(out/'summary.csv',summaries)
    runtime_summary=[]
    for policy in plan['policies']:
        vals=sorted(float(r['wall_ms']) for r in runtime if r['policy']==policy)
        runtime_summary.append(dict(policy=policy,episodes=len(vals),mean_wall_ms=st.mean(vals),
            p95_wall_ms=vals[math.ceil(.95*len(vals))-1],scope='Java kernel only; local Windows; excludes startup, IO, audit'))
    write(out/'runtime.csv',runtime_summary)
    index={(r['layout_seed'],int(r['seed']),r['policy']):r for r in all_rows}
    contrasts=[]
    for policy in plan['policies'][1:]:
        for metric in ('delivered_dvr','image_dvr','j_per_delivered'):
            pairs=[(index[l,s,BASE],index[l,s,policy]) for l in plan['layout_seeds'] for s in plan['task_seeds']]
            point=contrast([a for a,b in pairs],[b for a,b in pairs],metric)
            lo,hi,valid=bootstrap(index,plan['layout_seeds'],plan['task_seeds'],policy,metric)
            contrasts.append(dict(baseline=BASE,candidate=policy,metric=metric,delta=point,ci95_low=lo,ci95_high=hi,
                bootstrap_valid=valid,bootstrap_reps=5000,method='crossed environment x shared-workload bootstrap; exploratory'))
    write(out/'contrasts.csv',contrasts)
    result=dict(status='PASS',episodes=len(all_rows),task_outcomes=total_outcomes,environment_count=len(plan['layout_seeds']),
        workload_seeds=len(plan['task_seeds']),plan_sha256=sha(out/'plan.json'),case_proofs=case_proofs,
        identical_workload_across_environments=True,source_holdout=False,training=False,paper_reproduction=False,
        paired_all_uav_task_changes=dict(pair_counts))
    save(out/'verification.json',result)
    fmt=lambda v:'NA' if v is None else f'{float(v):.2f}'
    lines=['# Multi-layout near-paper offloading baseline','',
        f"Audit PASS: {len(all_rows)} episode; {len(plan['layout_seeds'])} môi trường paper × {len(plan['task_seeds'])} workload seed × 5 policy.",
        'Không train, không thay tham số vật lý/radio/deadline/CPU/dwell so với primary. Không có background Alibaba trong đợt này.',
        'Mỗi layout seed đổi tọa độ, hardware, loại vision task, pin và connectivity cùng lúc theo PaperSimulation.layout.',
        'Đây là exploratory baseline robustness, không phải xác nhận thuật toán mới hay tái hiện paper. Các seed dự phòng không được chạy.',
        '', '| Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered đúng hạn | Mean/P95 delivered s | Total/UAV kJ | Delivered đúng hạn | UAV censored/cases |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        if r['layout_seed']!='ALL':continue
        lines.append(f"| {r['policy'].replace('ROUND_ROBIN__','')} | {100*r['image_dvr']:.2f} | {100*r['delivered_dvr']:.2f} | {fmt(r['j_per_delivered'])} | {fmt(r['delivered_mean_latency_s'])}/{fmt(r['delivered_mean_episode_p95_s'])} | {r['total_energy_j']/1000:.2f}/{r['uav_energy_j']/1000:.2f} | {r['delivered_ontime_images']} | {r['censored_cases']}/{r['cases']} |")
    lines+=['','DVR/latency là macro average theo episode; P95 là mean episode P95, không phải pooled P95. Latency chỉ dùng completions/deliveries, gồm cả muộn.',
        'J/ảnh là ratio tổng năng lượng / tổng ảnh đúng hạn; zero-success không gán efficiency = 0.',
        'Compute latency mean/P95, J/compute, lifetime restricted và background DVR (NA vì không có background) có đầy đủ trong summary.csv.',
        '', '| Policy vs ALL_LOCAL | Δ delivered DVR, điểm % [CI 95%] | Δ J/ảnh delivered [CI 95%] |',
        '|---|---:|---:|']
    for policy in plan['policies'][1:]:
        a=next(r for r in contrasts if r['candidate']==policy and r['metric']=='delivered_dvr')
        b=next(r for r in contrasts if r['candidate']==policy and r['metric']=='j_per_delivered')
        lines.append(f"| {policy.replace('ROUND_ROBIN__','')} | {100*a['delta']:.2f} [{100*a['ci95_low']:.2f}, {100*a['ci95_high']:.2f}] | {fmt(b['delta'])} [{fmt(b['ci95_low'])}, {fmt(b['ci95_high'])}] |")
    lines+=['','CI dùng crossed bootstrap: resample layout và shared workload seed độc lập, giữ ghép cặp policy. Không coi 1.500 episode là 1.500 mẫu độc lập.',
        'Chỉ 10 môi trường; CI exploratory, chưa có xác nhận holdout. Mỗi layout phải đọc riêng để thấy regression.',
        '', '| Layout seed | ALL_LOCAL delivered DVR % | ALL_UAV delivered DVR % | Δ điểm % |',
        '|---|---:|---:|---:|']
    for l in plan['layout_seeds']:
        a=next(r for r in summaries if r['layout_seed']==l and r['policy']==BASE)
        b=next(r for r in summaries if r['layout_seed']==l and r['policy']=='ROUND_ROBIN__ALL_UAV__EDF')
        lines.append(f"| {l} | {100*a['delivered_dvr']:.2f} | {100*b['delivered_dvr']:.2f} | {100*(b['delivered_dvr']-a['delivered_dvr']):.2f} |")
    q=[r for r in queue if r['policy']=='ROUND_ROBIN__ALL_UAV__EDF']
    lines+=['',f"ALL_UAV+EDF: {sum(r['multi_ready_dispatches'] for r in q)}/{sum(r['uav_dispatches'] for r in q)} dispatch có ≥2 task ready.",
        'Paired task changes ALL_UAV vs ALL_LOCAL: '+json.dumps(dict(pair_counts),ensure_ascii=False)+'.',
        'Các chênh lệch task/năng lượng bao gồm thay đổi contact do upload pin stop; không phải isolated compute effect.',
        'Pin còn sống đến horizon là censored. Chưa thể khẳng định lifetime dài hơn. Synthetic 2–4 MB không phải inference RescueNet.',
        'Radio ambiguity, full independent bandwidth, zero output delay và thiếu thu gom kết quả local vẫn là giới hạn.',
        '', 'runtime.csv: wall time kernel Java trên máy local, không phải runtime mỗi quyết định hoặc server benchmark.',
        'Nguồn: plan.json, source snapshots, từng run/manifest.json, verification.json, episode traces, summary.csv và contrasts.csv.']
    (out/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--output',type=Path,required=True);q.add_argument('--reference',type=Path,default=ROOT/'target/near-paper-final-20261101');q.add_argument('--smoke',action='store_true')
    for name in ('run','report'):
        q=sub.add_parser(name);q.add_argument('output',type=Path)
    a=p.parse_args()
    if a.command=='prepare':print(json.dumps(prepare(a.output,a.reference,a.smoke),indent=2))
    elif a.command=='run':run(a.output)
    else:print(json.dumps(report(a.output),indent=2))
if __name__=='__main__':main()
