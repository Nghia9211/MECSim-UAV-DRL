"""Prespecified one-factor reward/freshness retraining against the audited fixed-layout reference."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

import numpy as np
import torch
from stable_baselines3 import DQN

from .environment import EnvConfig,PaperEnv,ROOT
from .paper_reference import command,constants,layout,read,save,sha,snapshot
from .paper_seed_isolation import run_episode,validate_config
from .run import episode,model_options,write_csv

PROTOCOL=ROOT/'drl/paper_convention_retrain_protocol.json'


def load_plan():
    p=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    expected={'REWARD_AFTER':{'paper.rewardSnapshot':'AFTER'},'LOCAL_COMPLETION':{'paper.deliveryConvention':'COMPLETED'}}
    assert p['schema']=='paper-convention-retrain-v1' and p['profiles']==expected
    assert p['learning_seeds']==[0,1,2] and p['layout_seed']==0 and p['steps_per_model']==1000000
    assert (ROOT/p['proposal']).is_file(),'Write proposal before launch'
    base=ROOT/p['reference_campaign'];m=json.loads((base/'manifest.json').read_text());v=json.loads((base/'verification.json').read_text())
    assert m['status']=='COMPLETE' and v['status']=='PASS' and v['total_trace_audits']==270
    assert json.loads((base/'final-artifact-check.json').read_text())['status']=='PASS'
    for rel,digest in m['source_sha256'].items():
        assert sha(base/'source'/rel)==digest,rel
        if rel.endswith(('.py','.java')):assert sha(ROOT/rel)==digest,rel
    return p,m['protocol']


def profile_config(base,overrides):
    p=copy.deepcopy(base);p['properties'].update(overrides)
    assert sum(base['properties'].get(k)!=v for k,v in p['properties'].items())==1
    return p


def feasibility_preflight():
    spec=importlib.util.spec_from_file_location('preflight_channel',ROOT/'scripts/verify-paper-conventions.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    c=constants();ds=layout(0,8,8,audit.JavaRandom);result={}
    for profile in ('REFERENCE','LOCAL_COMPLETION'):
        critical=[i for i,d in enumerate(ds) if not d['connected'] or profile=='LOCAL_COMPLETION' and
                  2000000/c['hardware'][d['hardware']]['bytes_per_s'][d['task']]>600]
        masks=[]
        for target in ds:
            mask=0
            for k,i in enumerate(critical):
                d=ds[i];distance=math.sqrt((target['x']-d['x'])**2+(target['y']-d['y'])**2+100)
                rate=20e6*math.log1p(.1*1e-8*distance**-4/1e-13)/math.log(2)
                if distance<=65 and 2000000*8/rate<=600:mask|=1<<k
            masks.append(mask)
        dp={0:0}
        for _ in range(12):
            for covered,n in list(dp.items()):
                for mask in masks:
                    key=covered|mask;dp[key]=min(dp.get(key,99),n+1)
        lower=dp.get((1<<len(critical))-1,99)
        result[profile]=dict(always_uav_dependent_devices=critical,optimistic_min_visits_per_age_window=lower,
                             age_limit=10,necessary_cover_bound_satisfied=lower<=10,
                             caveat='Optimistic set-cover lower bound with minimum2MB and no flight/battery cost; not proof of feasible long-term operation.')
    return result


def train(out,workers):
    p,base=load_plan();source=ROOT/p['reference_campaign'];out.mkdir(parents=True,exist_ok=False)
    feasibility=feasibility_preflight();save(out/'feasibility-preflight.json',feasibility)
    assert all(r['necessary_cover_bound_satisfied'] for r in feasibility.values()),'Necessary coverage bound fails; review before expensive training'
    sources=snapshot(out)
    proposal=ROOT/p['proposal'];target=out/'source'/p['proposal'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(proposal.read_bytes())
    sources[p['proposal']]=sha(proposal)
    provenance={f:sha(source/f) for f in ['manifest.json','verification.json','final-artifact-check.json','episodes.csv','runs.csv','summary.csv']}
    manifest=dict(schema='paper-convention-retrain-v1',status='RUNNING',pid=os.getpid(),started=time.time(),workers=workers,
                  protocol=p,base_protocol=base,protocol_sha256=sha(PROTOCOL),source_sha256=sources,
                  reference_provenance=provenance,runs=[],timing='Concurrent CPU1thread processes; not a hardware-comparable paper runtime.')
    save(out/'manifest.json',manifest)
    jobs=[(name,seed) for name in p['profiles'] for seed in p['learning_seeds']]
    def launch(name,seed):
        cfg=profile_config(base,p['profiles'][name]);run=out/name/f'seed-{seed}'
        args=command(cfg,seed,p['layout_seed'],run);(out/name).mkdir(exist_ok=True)
        receipt=dict(profile=name,seed=seed,run=str(run),command=args,started=time.time())
        with (out/name/f'seed-{seed}.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            receipt['pid']=proc.pid;save(out/name/f'seed-{seed}-process.json',receipt);receipt['exit_code']=proc.wait()
        receipt['finished']=time.time();save(out/name/f'seed-{seed}-process.json',receipt);return receipt
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(launch,n,s) for n,s in jobs]):
            receipt=future.result();manifest['runs'].append(receipt);save(out/'manifest.json',manifest)
            print(f"profile={receipt['profile']} seed={receipt['seed']} exit={receipt['exit_code']}",flush=True)
    failed=any(r['exit_code']!=0 for r in manifest['runs']);manifest.update(status='TRAINING_FAILED' if failed else 'TRAINING_COMPLETE',finished=time.time())
    save(out/'manifest.json',manifest)
    if failed:raise RuntimeError('A run failed; preserve all outputs and inspect logs')
    verify(out)


def verify(out):
    m=json.loads((out/'manifest.json').read_text());p=m['protocol'];base=m['base_protocol'];reference=ROOT/p['reference_campaign']
    assert m['status']=='TRAINING_COMPLETE','Completed fresh training required; do not overwrite audited evaluation'
    for rel,digest in m['source_sha256'].items():
        assert sha(out/'source'/rel)==digest,rel
        if rel.endswith(('.py','.java')):assert sha(ROOT/rel)==digest,rel
    for rel,digest in m['reference_provenance'].items():assert sha(reference/rel)==digest,rel
    torch.set_num_threads(1)
    spec=importlib.util.spec_from_file_location('convention_retrain_audit',ROOT/'scripts/verify-paper-conventions.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    c=constants();save(out/'parameter-verification.json',audit.verify_parameters(out,dict(constants=c)))
    ds=layout(0,8,8,audit.JavaRandom)
    reference_rows=read(reference/'episodes.csv')
    rows=[dict(r,profile='REFERENCE') for r in reference_rows];counts=[];proofs=[]
    refmeta=json.loads((reference/'manifest.json').read_text())
    ref_runtime=json.loads((Path(refmeta['runs'][0]['run'])/'config.json').read_text())
    for name,overrides in p['profiles'].items():
        cfg=profile_config(base,overrides);profile_root=out/name
        conventions=dict(radio='LITERAL_DBM',expiry='AT_LIMIT',delivery='LEGACY',reward_snapshot='BEFORE',reward_epsilon=1e-6,
                         backlog='discard at slot end; not varied',output_link='instantaneous; uncalibrated and not varied')
        if name=='REWARD_AFTER':conventions['reward_snapshot']='AFTER'
        else:conventions['delivery']='COMPLETED'
        am=dict(constants=c,profiles=dict(REFERENCE=conventions),max_slots=200)
        for seed in p['learning_seeds']:
            run=profile_root/f'seed-{seed}';record=json.loads((run/'config.json').read_text());e=validate_config(record,cfg,seed)
            assert record['packages']==ref_runtime['packages'] and record['python']==ref_runtime['python']
            best=DQN.load(run/'best_model.zip',device='cpu');final=DQN.load(run/'final_model.zip',device='cpu')
            assert final.num_timesteps==1000000 and final._n_updates==249975
            assert all(torch.isfinite(v).all() for model in (best,final) for v in model.q_net.state_dict().values())
            vrows=[r for r in read(run/'validation.csv') if int(r['gradient_updates'])>0]
            chosen=max(vrows,key=lambda r:float(r['mean_slots']));assert best.num_timesteps==int(chosen['steps'])
            with PaperEnv(EnvConfig(**e)) as env:
                initial=DQN('MlpPolicy',env,seed=seed,device='cpu',**model_options('DQN'))
                delta=max((initial.q_net.state_dict()[k]-v).abs().max().item() for k,v in final.q_net.state_dict().items());assert delta>0
                scores=[episode(env,model=best,task_seed=1000000+i)['slots'] for i in range(5)]
                audit.close(statistics.mean(scores),float(chosen['mean_slots']),'Validation checkpoint replay')
                for cp,model in [('best',best),('final',final)]:
                    for task in range(2000000,2000030):
                        r=run_episode(profile_root,env,model,'DQN',seed,cp,task,audit,ds,am,counts)
                        r['trace']=name+'/'+r['trace'];rows.append(dict(r,profile=name))
                if seed==0:
                    for policy in base['heuristics']:
                        for task in range(2000000,2000030):
                            r=run_episode(profile_root,env,None,policy,-1,'heuristic',task,audit,ds,am,counts)
                            r['trace']=name+'/'+r['trace'];rows.append(dict(r,profile=name))
            losses=[float(r['train/loss']) for r in read(run/'progress.csv') if r.get('train/loss')];assert losses and all(np.isfinite(losses))
            proofs.append(dict(profile=name,seed=seed,steps=1000000,updates=249975,best_steps=best.num_timesteps,
                               best_sha256=sha(run/'best_model.zip'),final_sha256=sha(run/'final_model.zip'),
                               validation_best_mean=statistics.mean(scores),final_validation_mean=float(vrows[-1]['mean_slots']),
                               max_abs_weight_change=delta,logged_finite_losses=len(losses)))
            print(f'Audited {name} seed={seed}',flush=True)
    assert len(rows)==810 and len(counts)==540 and len({r['layout_sha256'] for r in rows})==1
    write_csv(out/'episodes.csv',rows);write_csv(out/'new-slot-counting.csv',counts)
    groups=[]
    for profile in ['REFERENCE',*p['profiles']]:
        for seed in (0,1,2):
            for cp in ('best','final'):
                g=[r for r in rows if r['profile']==profile and r['policy']=='DQN' and int(r['training_seed'])==seed and r['checkpoint']==cp]
                assert len(g)==30
                groups.append(dict(profile=profile,seed=seed,checkpoint=cp,episodes=30,mean_slots=statistics.mean(float(r['slots']) for r in g),
                                   mean_seconds=statistics.mean(float(r['seconds']) for r in g),
                                   age_failure_episodes=sum('DATA_AGE' in r['reason'] for r in g),battery_failure_episodes=sum('BATTERY' in r['reason'] for r in g)))
    write_csv(out/'runs.csv',groups);summary=[];paired=[]
    for profile in ['REFERENCE',*p['profiles']]:
        for cp in ('best','final'):
            g=[r for r in groups if r['profile']==profile and r['checkpoint']==cp];vals=[r['mean_slots'] for r in g]
            summary.append(dict(profile=profile,checkpoint=cp,mean_slots=statistics.mean(vals),sd_across_run_means=statistics.stdev(vals),
                                mean_seconds=statistics.mean(r['mean_seconds'] for r in g),age_failure_episodes=sum(r['age_failure_episodes'] for r in g),
                                battery_failure_episodes=sum(r['battery_failure_episodes'] for r in g)))
            if profile!='REFERENCE':
                for r in g:
                    ref=next(x for x in groups if x['profile']=='REFERENCE' and x['seed']==r['seed'] and x['checkpoint']==cp)
                    paired.append(dict(profile=profile,seed=r['seed'],checkpoint=cp,delta_mean_slots=r['mean_slots']-ref['mean_slots']))
    write_csv(out/'summary.csv',summary);write_csv(out/'paired-run-differences.csv',paired)
    result=dict(status='PASS',new_full_budget_models=6,reused_full_budget_models=3,new_trace_audits=540,reused_reference_rows=270,
                total_rows=810,unique_layouts=1,checkpoints=proofs,reference_provenance=m['reference_provenance'],
                note='One-factor developmental sensitivity; reward totals not compared across definitions. No full-paper or superiority claim.')
    save(out/'verification.json',result);write_report(out,summary,groups,paired)
    m.update(status='COMPLETE',verified=time.time());save(out/'manifest.json',m);print(json.dumps(summary,indent=2),flush=True)


def write_report(out,summary,groups,paired):
    lines=['# One-factor reward/freshness retraining on layout0','',
           'Six new1m-step models, three reused reference models.540new traces independently replayed;270reference rows reused. Same cases are not new independent replications.','',
           '| Profile | Checkpoint | Mean slots | SD across3learner means | Mean seconds | Age-failure episodes /90 |',
           '| --- | --- | ---: | ---: | ---: | ---: |']
    for r in summary:lines.append(f"| {r['profile']} | {r['checkpoint']} | {r['mean_slots']:.3f} | {r['sd_across_run_means']:.3f} | {r['mean_seconds']:.2f} | {r['age_failure_episodes']} |")
    lines+=['','| Profile | Seed | Checkpoint | Paired delta slots vs REFERENCE |','| --- | ---: | --- | ---: |']
    for r in paired:lines.append(f"| {r['profile']} | {r['seed']} | {r['checkpoint']} | {r['delta_mean_slots']:+.3f} |")
    lines+=['','REWARD_AFTER changes only A/O snapshot timing, not the timing of the reward call. LOCAL_COMPLETION changes only connected-local delivery semantics. Neither is presumed to be the author code.',
            'Primary checkpoint selection uses held-out validation only. Final1m is secondary; do not replace the primary result using test scores. Raw rewards have different meanings/scales and are not used to rank profiles.',
            'One previously observed layout and3learning seeds cannot establish generalization, statistical superiority or equivalence to the paper. Freshness changes the problem, so lower lifetime does not automatically mean a worse learner.',
            'All metrics/assumptions and negative outcomes must be reported; do not pick the convention whose number is closest to Table5.','']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train');t.add_argument('--output',type=Path,required=True);t.add_argument('--workers',type=int,choices=(1,2,3),default=3)
    v=sub.add_parser('verify');v.add_argument('run',type=Path)
    a=parser.parse_args()
    if a.command=='train':train(a.output.resolve(),a.workers)
    else:verify(a.run.resolve())


if __name__=='__main__':main()
