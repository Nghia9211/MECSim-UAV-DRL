"""Sequential one-factor-at-a-time sensitivity, reusing independently verified anchor traces.
No simulator edits, fitting, model training or changed radio conventions.
"""
import argparse
import copy
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
c=module('sensitivity_layouts','near-paper-layouts.py')
near=c.near
read,write,sha,save=c.read,c.write,c.sha,c.save
POLICIES=[c.BASE,'ROUND_ROBIN__ALL_UAV__EDF','ROUND_ROBIN__DEADLINE_ENERGY__EDF']
FACTORS={'cpu':('uavBytesPerSecond',500000,8000000),
         'deadline':('deadlineSeconds',300,900),
         'dwell':('dwellSeconds',15,180)}
def modify(anchor,factor,value):
    p=copy.deepcopy(anchor)
    if factor=='deadline':
        p['loads'][0]['criticalDeadlineSeconds']=value
        p['loads'][0]['imageDeadlineSeconds']=value
    else:p[FACTORS[factor][0]]=value
    return p
def validate_difference(anchor,p,factor,value):
    assert p==modify(anchor,factor,value),'More than the declared factor changed'
def prepare(out,reference,smoke=False):
    if out.exists():raise FileExistsError(out)
    reference=reference.resolve();old=c.validate_lock(reference)
    proof=json.loads((reference/'verification.json').read_text())
    assert proof['status']=='PASS'
    assert json.loads((reference/'campaign-status.json').read_text())['status']=='COMPLETE'
    layouts=old['layout_seeds'][:2] if smoke else old['layout_seeds']
    seeds=old['task_seeds'][:1] if smoke else old['task_seeds']
    sources=set(old['source_sha256'])|{'scripts/near-paper-sensitivity.py','scripts/test_near_paper_sensitivity.py'}
    out.mkdir(parents=True)
    hashes={name:sha(ROOT/name) for name in sorted(sources)}
    for name in hashes:
        dest=out/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    protocol_hashes={};anchors={}
    for layout in layouts:
        child=reference/'runs'/f'layout-{layout}'
        m=json.loads((child/'manifest.json').read_text())
        assert sha(child/'manifest.json')==proof['case_proofs'][str(layout)]['manifest_sha256']
        assert sha(child/'verification.json')==proof['case_proofs'][str(layout)]['verification_sha256']
        p=copy.deepcopy(m['protocol']);p['policies']=POLICIES;p['taskSeeds']=seeds;p['smoke']=smoke
        anchors[str(layout)]=p
        for factor,(_,low,high) in FACTORS.items():
            for tag,value in [('low',low),('high',high)]:
                setting=factor+'-'+tag;q=modify(p,factor,value);validate_difference(p,q,factor,value)
                target=out/'protocols'/setting/f'layout-{layout}.json';save(target,q)
                protocol_hashes[setting+'/'+str(layout)]=sha(target)
    plan=dict(schema='near-paper-sensitivity-v1',created=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        reference=str(reference),reference_plan_sha256=sha(reference/'plan.json'),
        reference_verification_sha256=sha(reference/'verification.json'),
        reference_core_hashes={str(l):sha(reference/'runs'/f'layout-{l}'/'core-metrics-episodes.csv') for l in layouts},
        layouts=layouts,seeds=seeds,policies=POLICIES,anchors=anchors,protocol_sha256=protocol_hashes,
        source_sha256=hashes,phase_order=list(FACTORS),factors=FACTORS,
        new_episodes=6*len(layouts)*len(seeds)*len(POLICIES),reused_episodes=len(layouts)*len(seeds)*len(POLICIES),
        smoke=smoke,bootstrap_reps=5000,
        gate='audit and isolated-factor/pairing must pass; no requirement that the effect improve',
        assumptions='CPU throughput changed at fixed incremental CPU watts: pure capacity sensitivity, not physical DVFS; same paper radio/flight/battery',
        inference='exploratory crossed layout x shared-workload bootstrap; no IID policy episodes or fresh holdout claims',
        source_holdout=False,training=False,paper_reproduction=False)
    save(out/'plan.json',plan);(out/'PLAN.sha256').write_text(sha(out/'plan.json')+'\n',encoding='ascii')
    return plan
def validate(out):
    p=json.loads((out/'plan.json').read_text())
    assert sha(out/'plan.json')==(out/'PLAN.sha256').read_text().strip(),'Plan drift'
    ref=Path(p['reference']);c.validate_lock(ref)
    assert sha(ref/'plan.json')==p['reference_plan_sha256'],'Reference plan drift'
    assert sha(ref/'verification.json')==p['reference_verification_sha256'],'Reference proof drift'
    for name,h in p['source_sha256'].items():
        assert sha(ROOT/name)==h,'Live source changed: '+name
        assert sha(out/'source'/name)==h,'Snapshot changed: '+name
    for layout in p['layouts']:
        assert sha(ref/'runs'/f'layout-{layout}'/'core-metrics-episodes.csv')==p['reference_core_hashes'][str(layout)],'Anchor metrics drift'
        for factor,(_,low,high) in FACTORS.items():
            for tag,value in [('low',low),('high',high)]:
                setting=factor+'-'+tag;path=out/'protocols'/setting/f'layout-{layout}.json'
                assert sha(path)==p['protocol_sha256'][setting+'/'+str(layout)],'Protocol drift'
                validate_difference(p['anchors'][str(layout)],json.loads(path.read_text()),factor,value)
    return p
def row_identity(rows,drop_deadline=False):
    # Decimal float serialization is unchanged by CPU/dwell, while deadlines intentionally vary.
    keys=[k for k in rows[0] if not (drop_deadline and k=='deadline_s')] if rows else []
    return [{k:r[k] for k in keys} for r in rows]
def verify_pairing(case,reference,p,factor,layout):
    for seed in p['seeds']:
        a=case/'primary'/f'seed-{seed}'/'workload.csv'
        b=reference/'runs'/f'layout-{layout}'/'primary'/f'seed-{seed}'/'workload.csv'
        if factor!='deadline':assert sha(a)==sha(b),'CPU/dwell changed workload'
        if factor=='cpu':
            for suffix in ('tasks','energy','positions','visits','updates'):
                filename=c.BASE+'-'+suffix+'.csv'
                assert sha(a.parent/filename)==sha(b.parent/filename),'CPU-only negative control changed ALL_LOCAL '+suffix
        if factor=='deadline':
            assert row_identity(read(a),True)==row_identity(read(b),True),'Deadline changed arrivals/size/MI/priority/assignment/estimates'
def numeric_compare(actual,expected,key):
    if expected is None:assert actual in ('',None),'Expected NA '+key
    else:assert actual not in ('',None) and math.isclose(float(actual),float(expected),rel_tol=1e-9,abs_tol=1e-8),'Recount '+key
def checked_metrics(case):
    m=json.loads((case/'manifest.json').read_text());v=json.loads((case/'verification.json').read_text())
    assert m['status']=='COMPLETE' and v['status']=='PASS'
    rows=read(case/'core-metrics-episodes.csv')
    for r in rows:
        d=case/r['scenario']/('seed-'+r['seed'])
        assert sha(d/'workload.csv')==r['workload_sha256'],'Workload drift'
        jobs={j['id']:j for j in read(d/'workload.csv')}
        outcomes={o['id']:o for o in read(d/(r['policy']+'-tasks.csv'))}
        energy=read(d/(r['policy']+'-energy.csv'))
        values=near.metrics.calculate(jobs,outcomes,energy,m['protocol']['horizonSeconds'])
        for k,val in values.items():numeric_compare(r[k],val,k)
        updates={u['id'] for u in read(d/(r['policy']+'-updates.csv'))}
        assert len(updates)==int(r['delivered_completed_images'])
        assert sum(outcomes[k]['status']=='COMPLETED_ON_TIME' for k in updates)==int(r['delivered_ontime_images'])
    return rows
def run_phase(out,factor):
    out=out.resolve();p=validate(out);index=p['phase_order'].index(factor)
    if index:
        prior=out/(p['phase_order'][index-1]+'-review.json')
        assert prior.exists() and json.loads(prior.read_text())['status']=='PASS','Prior phase review required'
        previous=json.loads(prior.read_text())
        assert previous['plan_sha256']==sha(out/'plan.json'),'Prior phase plan drift'
        prev_dir=out/'phases'/p['phase_order'][index-1]
        assert json.loads((prev_dir/'status.json').read_text())['status']=='COMPLETE','Prior phase not complete'
        assert sha(prev_dir/'summary.csv')==previous['summary_sha256'],'Prior phase summary drift'
        assert sha(prev_dir/'contrasts.csv')==previous['contrasts_sha256'],'Prior phase contrast drift'

    lock=out/'RUNNING.lock'
    with lock.open('x') as f:f.write(str(__import__('os').getpid()))
    phase=out/'phases'/factor;phase.mkdir(parents=True,exist_ok=True)
    try:
        save(phase/'status.json',dict(status='RUNNING'))
        with (phase/'compile.log').open('w',encoding='utf8') as log:
            subprocess.run([shutil.which('mvn') or 'mvn','-o','-q','compile'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        reference=Path(p['reference'])
        for tag in ('low','high'):
            setting=factor+'-'+tag
            for layout in p['layouts']:
                validate(out);case=out/'runs'/setting/f'layout-{layout}'
                protocol=out/'protocols'/setting/f'layout-{layout}.json';logpath=phase/f'{setting}-{layout}.log'
                receipt=phase/f'{setting}-{layout}-process.json'
                if not case.exists():
                    with logpath.open('w',encoding='utf8') as log:
                        proc=subprocess.run([shutil.which('mvn') or 'mvn','-o','-q','exec:java',
                            '-Dexec.mainClass=uav.offloading.NearPaperBenchmark',
                            '-Dnear.protocol='+str(protocol),'-Dnear.output='+str(case)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                    assert proc.returncode==0,'Java failed: '+str(logpath)
                    save(receipt,dict(exit_code=proc.returncode,log_sha256=sha(logpath)))
                assert json.loads(receipt.read_text())['exit_code']==0,'Missing successful process receipt'
                m=json.loads((case/'manifest.json').read_text())
                assert m['status']=='COMPLETE' and m['protocol']==json.loads(protocol.read_text()),'Incomplete/protocol drift'
                assert m['protocol_sha256']==sha(protocol)
                for name,h in m['source_sha256'].items():assert p['source_sha256'][name]==h,'Source drift '+name
                v=near.verify(case);near.metrics.export(case);verify_pairing(case,reference,p,factor,layout)
                print(f"{setting} layout={layout}: audit {v['status']} episodes={v['episodes']}",flush=True)
        result=review(out,factor);save(phase/'status.json',{**result,'status':'COMPLETE'})
        print('PHASE_COMPLETE '+factor,flush=True)
    except BaseException as e:
        save(phase/'status.json',dict(status='FAILED',error=str(e)));raise
    finally:lock.unlink()
def anchor_rows(p):
    ref=Path(p['reference']);result=[]
    for layout in p['layouts']:
        case=ref/'runs'/f'layout-{layout}'
        # Reference has five arms and 30 seeds; only declared subset is reused.
        for r in checked_metrics(case):
            if int(r['seed']) in p['seeds'] and r['policy'] in p['policies']:
                result.append(dict(setting='reference',layout=layout,**r))
    return result
def summarize(rows):
    out=c.summary(rows)
    out.update(offloaded_images=st.mean(float(r['offloaded_images']) for r in rows),
        covered_images=st.mean(float(r['covered_images']) for r in rows),
        flight_j=st.mean(float(r['flight_j']) for r in rows),
        hover_j=st.mean(float(r['hover_j']) for r in rows),
        travelled_m=st.mean(float(r['travelled_m']) for r in rows))
    return out
def boot_delta(a,b,layouts,seeds,metric,reps=5000):
    # Precompute crossed bootstrap weights; preserve pairing of settings/policies.
    rng=random.Random(20261102);values=[]
    for _ in range(reps):
        ls=rng.choices(layouts,k=len(layouts));ss=rng.choices(seeds,k=len(seeds))
        left=[a[l,s] for l in ls for s in ss];right=[b[l,s] for l in ls for s in ss]
        v=c.contrast(left,right,metric)
        if v is not None:values.append(v)
    values.sort()
    return (values[int(.025*len(values))],values[min(len(values)-1,int(.975*len(values)))],len(values)) if values else (None,None,0)
def phase_rows(out,factor,p):
    result=[];proofs={};reference=Path(p['reference'])
    for tag in ('low','high'):
        setting=factor+'-'+tag
        for layout in p['layouts']:
            case=out/'runs'/setting/f'layout-{layout}'
            expected=json.loads((out/'protocols'/setting/f'layout-{layout}.json').read_text())
            manifest=json.loads((case/'manifest.json').read_text())
            assert manifest['protocol']==expected
            verify_pairing(case,reference,p,factor,layout)
            rows=checked_metrics(case)
            assert len(rows)==len(p['seeds'])*len(p['policies'])
            assert {(int(r['seed']),r['policy']) for r in rows}=={(s,q) for s in p['seeds'] for q in p['policies']}
            receipt=out/'phases'/factor/f'{setting}-{layout}-process.json'
            process=json.loads(receipt.read_text())
            assert process['exit_code']==0
            assert sha(out/'phases'/factor/f'{setting}-{layout}.log')==process['log_sha256']
            for r in rows:result.append(dict(setting=setting,layout=layout,**r))
            proofs[setting+'/'+str(layout)]={name:sha(case/name) for name in ('manifest.json','verification.json','core-metrics-episodes.csv')}
    return result,proofs
def review(out,factor):
    p=validate(out);new,proofs=phase_rows(out,factor,p);rows=anchor_rows(p)+new
    phase=out/'phases'/factor;phase.mkdir(parents=True,exist_ok=True)
    write(phase/'episodes.csv',rows)
    summaries=[]
    for setting in ('reference',factor+'-low',factor+'-high'):
        for layout in ['ALL']+p['layouts']:
            for policy in p['policies']:
                group=[r for r in rows if r['setting']==setting and r['policy']==policy and (layout=='ALL' or r['layout']==layout)]
                summaries.append(dict(setting=setting,layout=layout,policy=policy,**summarize(group)))
    write(phase/'summary.csv',summaries)
    indexed={(r['setting'],r['policy'],r['layout'],int(r['seed'])):r for r in rows}
    contrasts=[]
    # Paired factor effect: same policy, changed parameter vs reference.
    # Baseline contrasts: routing policy vs ALL_LOCAL and DEADLINE_ENERGY vs ALL_UAV in each setting.
    specs=[]
    for setting in (factor+'-low',factor+'-high'):
        for policy in p['policies']:specs.append(('factor_effect','reference',policy,setting,policy))
    for setting in ('reference',factor+'-low',factor+'-high'):
        for a,b in ((POLICIES[0],POLICIES[1]),(POLICIES[0],POLICIES[2]),(POLICIES[1],POLICIES[2])):
            specs.append(('routing_effect',setting,a,setting,b))
    for kind,sa,pa,sb,pb in specs:
        a={(l,s):indexed[sa,pa,l,s] for l in p['layouts'] for s in p['seeds']}
        b={(l,s):indexed[sb,pb,l,s] for l in p['layouts'] for s in p['seeds']}
        # CI for main delivered DVR; energy ratios retained descriptively in full table.
        metric='delivered_dvr';point=c.contrast(list(a.values()),list(b.values()),metric)
        lo,hi,n=boot_delta(a,b,p['layouts'],p['seeds'],metric,p['bootstrap_reps'])
        contrasts.append(dict(kind=kind,baseline_setting=sa,baseline_policy=pa,candidate_setting=sb,candidate_policy=pb,
            metric=metric,delta=point,ci95_low=lo,ci95_high=hi,valid_bootstrap=n,reps=p['bootstrap_reps']))
    write(phase/'contrasts.csv',contrasts)
    lines=['# Sensitivity phase: '+factor,'',
        'Đã kiểm tra chỉ thay một yếu tố. Reference dùng trace cũ, không chạy lại. CI exploratory crossed environment/workload bootstrap.',
        'CPU capacity đổi tại CPU watts cố định: không phải DVFS/phần cứng đo được. Không chọn mức tốt nhất làm cấu hình thật.',
        '', '| Setting | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered | Mean/P95 delivered s | Mean total/UAV kJ | UAV censored/cases |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        if r['layout']!='ALL':continue
        fmt=lambda x:'NA' if x is None else f'{x:.2f}'
        lines.append(f"| {r['setting']} | {r['policy'].replace('ROUND_ROBIN__','')} | {100*r['image_dvr']:.2f} | {100*r['delivered_dvr']:.2f} | {fmt(r['j_per_delivered'])} | {fmt(r['delivered_mean_latency_s'])}/{fmt(r['delivered_mean_episode_p95_s'])} | {r['total_energy_j']/1000:.2f}/{r['uav_energy_j']/1000:.2f} | {r['censored_cases']}/{r['cases']} |")
    lines+=['','Không coi policy episodes là mẫu độc lập; latency chỉ trên completions/deliveries, gồm task muộn; P95 là mean episode P95.',
        'J/ảnh là ratio of sums. Không có background: background DVR NA. Lifetime còn pin ở horizon là censored.',
        'summary.csv chứa từng môi trường, compute latency mean/P95, restricted UAV time, energy components và contact/offload counts.',
        'Các contrasts.csv gồm effect tham số (giữ policy) và effect routing (giữ setting). CI là exploratory, không phải multiple-testing-corrected confirmatory tests.',
        'Không thay simulator/radio/battery; synthetic 2–4 MB, chưa phải RescueNet inference.']
    (phase/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    result=dict(status='PASS',factor=factor,new_episodes=len(new),reference_episodes_reused=len(rows)-len(new),
        plan_sha256=sha(out/'plan.json'),source_unchanged=True,isolated_factor=True,case_proofs=proofs,
        summary_sha256=sha(phase/'summary.csv'),contrasts_sha256=sha(phase/'contrasts.csv'),
        gate='audited and isolated changes; next phase may proceed regardless of improvement',
        training=False,source_holdout=False,paper_reproduction=False)
    save(out/(factor+'-review.json'),result)
    return result
def final_report(out):
    p=validate(out);rows=anchor_rows(p);reviews={}
    for factor in p['phase_order']:
        proof=json.loads((out/(factor+'-review.json')).read_text());assert proof['status']=='PASS'
        assert proof['plan_sha256']==sha(out/'plan.json')
        assert sha(out/'phases'/factor/'summary.csv')==proof['summary_sha256']
        assert sha(out/'phases'/factor/'contrasts.csv')==proof['contrasts_sha256']
        new,case_proofs=phase_rows(out,factor,p);assert case_proofs==proof['case_proofs']
        rows+=new;reviews[factor]=sha(out/(factor+'-review.json'))
    assert len(rows)==p['new_episodes']+p['reused_episodes']
    write(out/'episodes-core.csv',rows)
    summaries=[]
    for setting in ['reference']+[f+'-'+tag for f in p['phase_order'] for tag in ('low','high')]:
        for layout in ['ALL']+p['layouts']:
            for policy in p['policies']:
                group=[r for r in rows if r['setting']==setting and r['policy']==policy and (layout=='ALL' or r['layout']==layout)]
                summaries.append(dict(setting=setting,layout=layout,policy=policy,**summarize(group)))
    write(out/'summary.csv',summaries)
    result=dict(status='COMPLETE',verified=True,new_episodes=p['new_episodes'],reused_episodes=p['reused_episodes'],
        total_analysis_cases=len(rows),phase_review_sha256=reviews,plan_sha256=sha(out/'plan.json'),
        summary_sha256=sha(out/'summary.csv'),episode_metrics_sha256=sha(out/'episodes-core.csv'),
        source_holdout=False,training=False,paper_reproduction=False)
    save(out/'verification.json',dict(status='PASS',**{k:v for k,v in result.items() if k!='status'}))
    save(out/'campaign-status.json',result);return result
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--output',type=Path,required=True);q.add_argument('--reference',type=Path,required=True);q.add_argument('--smoke',action='store_true')
    q=sub.add_parser('run');q.add_argument('output',type=Path);q.add_argument('--phase',choices=list(FACTORS),required=True)
    q=sub.add_parser('report');q.add_argument('output',type=Path)
    a=p.parse_args()
    if a.command=='prepare':
        v=prepare(a.output,a.reference,a.smoke);print('PREPARED new='+str(v['new_episodes'])+' reused='+str(v['reused_episodes']))
    elif a.command=='run':run_phase(a.output,a.phase)
    else:print(json.dumps(final_report(a.output),indent=2))
if __name__=='__main__':main()
