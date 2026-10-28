"""Two new full-budget runs plus one verified reused run on one fixed paper layout."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import numpy as np
import torch
from stable_baselines3 import DQN

from .environment import EnvConfig,PaperEnv,ROOT
from .paper_reference import command,constants,layout,read,save,sha,snapshot
from .run import episode,model_options,write_csv

PROTOCOL=ROOT/'drl/paper_seed_isolation_protocol.json'


def load_protocol():
    p=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    if not (p['schema']=='paper-learning-seed-isolation-v1' and p['fixed_layout_seed']==0
            and p['learning_seeds']==[0,1,2] and p['new_training_seeds']==[1,2] and p['reused_seed']==0
            and p['steps_per_model']==1000000 and p['algorithm']=='DQN' and p['workload']=='synthetic'
            and p['powered']==p['connected']==8):raise ValueError('Frozen isolation protocol changed')
    return p


def validate_config(cfg,p,seed):
    e=cfg['environment']
    assert cfg['algorithm']=='DQN' and cfg['seed']==seed and cfg['requested_steps']==p['steps_per_model']
    assert cfg['status']=='COMPLETE' and cfg['actual_steps']==1000000 and cfg['gradient_updates']==249975
    assert e['layout_seed']==p['fixed_layout_seed'] and e['powered']==p['powered'] and e['connected']==p['connected']
    assert e['reward']==p['reward'] and e['properties']==p['properties'] and e['max_slots']==p['max_slots']
    assert cfg['threads']==1 and cfg['device']=='cpu'
    for key,value in model_options('DQN').items():
        if key!='policy_kwargs':assert cfg['hyperparameters'][key]==value,(key,cfg['hyperparameters'][key],value)
    assert cfg['hyperparameters']['policy_kwargs']['net_arch']==[64,64]
    return e


def reused_run(p):
    base=ROOT/p['reused_campaign'];run=base/p['reused_run']
    manifest=json.loads((base/'manifest.json').read_text());v=json.loads((base/'verification.json').read_text())
    assert manifest['status']=='COMPLETE' and v['status']=='PASS'
    proof=next(r for r in v['checkpoints'] if r['seed']==p['reused_seed'])
    cfg=json.loads((run/'config.json').read_text());validate_config(cfg,p,p['reused_seed'])
    for name,key in [('best_model.zip','best_sha256'),('final_model.zip','final_sha256')]:assert sha(run/name)==proof[key]
    # Existing Python/Java environment and learner must match exactly. New files are not silently substituted.
    for rel,digest in manifest['source_sha256'].items():
        assert sha(base/'source'/rel)==digest,rel
        if rel.endswith(('.py','.java')):assert sha(ROOT/rel)==digest,rel
    return run,dict(seed=0,layout_seed=0,reused=True,run=str(run),original_verification_sha256=sha(base/'verification.json'),
                    best_sha256=proof['best_sha256'],final_sha256=proof['final_sha256'])


def train(out,workers):
    p=load_protocol();reuse,receipt=reused_run(p)
    out.mkdir(parents=True,exist_ok=False)
    manifest=dict(schema='paper-learning-seed-isolation-v1',status='RUNNING',started=time.time(),pid=os.getpid(),
                  protocol=p,protocol_sha256=sha(PROTOCOL),source_sha256=snapshot(out),workers=workers,
                  python=sys.version,platform=platform.platform(),runs=[receipt],
                  note='Two fresh learner processes and one historical verified checkpoint; no reused baseline counts as new independent data.')
    save(out/'manifest.json',manifest)
    def launch(seed):
        run=out/f'seed-{seed}';args=command(p,seed,p['fixed_layout_seed'],run)
        r=dict(seed=seed,layout_seed=p['fixed_layout_seed'],reused=False,run=str(run),command=args,started=time.time())
        with (out/f'seed-{seed}.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            r['pid']=proc.pid;save(out/f'seed-{seed}-process.json',r);r['exit_code']=proc.wait()
        r['finished']=time.time();save(out/f'seed-{seed}-process.json',r);return r
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(launch,s) for s in p['new_training_seeds']]):
            r=future.result();manifest['runs'].append(r);save(out/'manifest.json',manifest)
            print(f"seed={r['seed']} exit={r['exit_code']}",flush=True)
    failed=any(r.get('exit_code',0)!=0 for r in manifest['runs'])
    manifest.update(status='TRAINING_FAILED' if failed else 'TRAINING_COMPLETE',finished=time.time())
    save(out/'manifest.json',manifest)
    if failed:raise RuntimeError('Training failure; original and new outputs preserved')
    verify(out)


def expected_actions(model,policy,task,slots,devices,ds):
    by={}
    for d in devices:by.setdefault(int(d['slot']),{})[int(d['device'])]=d
    batteries=[1.]*12;ages=[0.]*12;rng=np.random.default_rng(task+2);next_id=0;result=[]
    for k,s in enumerate(slots,1):
        if model is not None:action=int(model.predict(np.asarray(batteries+ages,np.float32),deterministic=True)[0])
        elif policy=='ROUND_ROBIN':action=next_id;next_id=(action+1)%12
        elif policy=='RANDOM':action=int(rng.integers(12))
        else:
            action=max([(next_id+i)%12 for i in range(12)],key=lambda d:ages[d]);next_id=(action+1)%12
        result.append(action)
        batteries=[float(by[k][d]['battery_j'])/ds[d]['capacity_j'] for d in range(12)]
        ages=[float(by[k][d]['data_age']) for d in range(12)]
    return result


def run_episode(out,env,model,policy,seed,checkpoint,task,audit,ds,am,counts):
    rel=Path('evaluation')/f'seed-{seed}'/checkpoint/f'task-{task}-{policy}'
    trace=out/rel
    r=episode(env,model=model,policy=policy,task_seed=task,trace=trace)
    slots=read(trace/'slots.csv');devices=read(trace/'devices.csv')
    actions=expected_actions(model,policy,task,slots,devices,ds)
    ground=sum(float(d['energy_used_j']) for d in devices)
    row=dict(profile='REFERENCE',scenario='p8-c8',seed=seed,task_seed=task,policy=policy,trace=rel.as_posix(),
             slots=r['slots'],seconds=r['seconds'],reason=r['reason'],truncated=str(r['truncated']).lower(),reward=r['reward'],
             uav_energy_j=1600000-float(slots[-1]['uav_battery_j']),ground_energy_j=ground,
             cap_slots=sum(float(s['duration_s'])>=600-1e-6 for s in slots),capped_items=sum(int(s['capped_work_items']) for s in slots))
    audit.replay(out,row,am,counts,layout_override=ds,expected_actions=actions)
    scenario=json.loads((trace/'scenario.json').read_text())
    assert scenario['mode']=='legacy' and scenario['base_layout_seed']==0 and scenario['task_seed']==task
    return dict(training_seed=seed,checkpoint=checkpoint,**r,ground_energy_j=ground,trace=rel.as_posix(),layout_sha256=scenario['layout_sha256'])


def verify(out):
    m=json.loads((out/'manifest.json').read_text());p=m['protocol']
    if m['status'] not in ('TRAINING_COMPLETE','AUDIT_FAILED'):raise ValueError('Fresh completed training required; preserve existing evaluation outputs')
    for rel,digest in m['source_sha256'].items():
        assert sha(out/'source'/rel)==digest,rel
        if rel.endswith(('.py','.java')):assert sha(ROOT/rel)==digest,rel
    torch.set_num_threads(1)
    spec=importlib.util.spec_from_file_location('seed_isolation_audit',ROOT/'scripts/verify-paper-conventions.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    c=constants();save(out/'parameter-verification.json',audit.verify_parameters(out,dict(constants=c)))
    ds=layout(p['fixed_layout_seed'],8,8,audit.JavaRandom);save(out/'fixed-layout.json',ds)
    conventions=dict(radio='LITERAL_DBM',expiry='AT_LIMIT',delivery='LEGACY',reward_snapshot='BEFORE',reward_epsilon=1e-6,
                     backlog='discard at slot end; not varied',output_link='instantaneous; uncalibrated and not varied')
    am=dict(constants=c,profiles=dict(REFERENCE=conventions),max_slots=200);rows=[];counts=[];proofs=[]
    for seed in p['learning_seeds']:
        record=next(r for r in m['runs'] if r['seed']==seed);run=Path(record['run'])
        cfg=json.loads((run/'config.json').read_text());e=validate_config(cfg,p,seed);envcfg=EnvConfig(**e)
        best=DQN.load(run/'best_model.zip',device='cpu');final=DQN.load(run/'final_model.zip',device='cpu')
        assert final.num_timesteps==1000000 and final._n_updates==249975
        assert all(torch.isfinite(v).all() for v in final.q_net.state_dict().values())
        with PaperEnv(envcfg) as env:
            initial=DQN('MlpPolicy',env,seed=seed,device='cpu',**model_options('DQN'))
            delta=max((initial.q_net.state_dict()[k]-v).abs().max().item() for k,v in final.q_net.state_dict().items());assert delta>0
            vals=[r for r in read(run/'validation.csv') if int(r['gradient_updates'])>0]
            chosen=max(vals,key=lambda r:float(r['mean_slots']));assert best.num_timesteps==int(chosen['steps'])
            score=[episode(env,model=best,task_seed=1000000+i)['slots'] for i in range(5)]
            audit.close(statistics.mean(score),float(chosen['mean_slots']),'Selected checkpoint validation')
            for label,model in [('best',best),('final',final)]:
                for task in range(p['first_test_seed'],p['first_test_seed']+30):
                    rows.append(run_episode(out,env,model,'DQN',seed,label,task,audit,ds,am,counts))
            if seed==p['reused_seed']:
                for policy in p['heuristics']:
                    for task in range(p['first_test_seed'],p['first_test_seed']+30):
                        rows.append(run_episode(out,env,None,policy,-1,'heuristic',task,audit,ds,am,counts))
        losses=[float(r['train/loss']) for r in read(run/'progress.csv') if r.get('train/loss')]
        assert losses and all(np.isfinite(losses))
        proofs.append(dict(seed=seed,reused=record['reused'],layout_seed=0,steps=1000000,updates=249975,
                           best_steps=best.num_timesteps,best_sha256=sha(run/'best_model.zip'),final_sha256=sha(run/'final_model.zip'),
                           max_abs_weight_change=delta,validation_best_mean=statistics.mean(score),
                           final_validation_mean=float(vals[-1]['mean_slots']),logged_losses=len(losses)))
        print(f'Audited seed {seed}: best+final checkpoints',flush=True)
    assert len(rows)==270 and len({r['layout_sha256'] for r in rows})==1
    write_csv(out/'episodes.csv',rows);write_csv(out/'slot-counting.csv',counts)
    groups=[]
    for seed in p['learning_seeds']:
        for checkpoint in ('best','final'):
            g=[r for r in rows if r['policy']=='DQN' and r['training_seed']==seed and r['checkpoint']==checkpoint]
            assert len(g)==30
            groups.append(dict(seed=seed,checkpoint=checkpoint,episodes=30,mean_slots=statistics.mean(r['slots'] for r in g),
                               sd_slots=statistics.stdev(r['slots'] for r in g),mean_seconds=statistics.mean(r['seconds'] for r in g),
                               failure_reasons=json.dumps(dict(__import__('collections').Counter(r['reason'] for r in g)))))
    write_csv(out/'runs.csv',groups)
    summary=[]
    for checkpoint in ('best','final'):
        g=[r for r in groups if r['checkpoint']==checkpoint];vals=[r['mean_slots'] for r in g]
        summary.append(dict(policy='DQN',checkpoint=checkpoint,learning_seeds=3,unique_layouts=1,episodes=90,
                            mean_slots=statistics.mean(vals),sd_across_learning_run_means=statistics.stdev(vals),
                            min_run_mean=min(vals),max_run_mean=max(vals)))
    for policy in p['heuristics']:
        g=[r for r in rows if r['policy']==policy];assert len(g)==30
        summary.append(dict(policy=policy,checkpoint='heuristic',learning_seeds=0,unique_layouts=1,episodes=30,
                            mean_slots=statistics.mean(r['slots'] for r in g),sd_across_learning_run_means='',min_run_mean='',max_run_mean=''))
    write_csv(out/'summary.csv',summary)
    result=dict(status='PASS',trained_new_models=2,reused_models=1,steps_per_model=1000000,
                primary_dqn_audits=90,secondary_final_audits=90,heuristic_audits=90,total_trace_audits=270,
                unique_layouts=1,source_snapshot_verified=True,common_layout_sha256=rows[0]['layout_sha256'],checkpoints=proofs,
                note='Fixed-layout development diagnostic; no generalization, full-paper reproduction or statistical superiority claim.')
    save(out/'verification.json',result);m.update(status='COMPLETE',verified=time.time());save(out/'manifest.json',m)
    write_report(out,p,groups,summary,proofs);print(json.dumps(summary,indent=2),flush=True)


def write_report(out,p,groups,summary,proofs):
    lines=['# Learning-seed isolation: fixed layout0','',
           'Two new1m-step DQN runs (seeds1/2) plus the verified historical seed0/layout0 checkpoint. All270 physical traces and actions replayed independently.',
           'Same source model, properties, hardware, capacities, outage masks, workload mapping, test cases and hyperparameters. Learning seed also affects training task order/exploration, not only network initialization.','',
           '| Learning seed | Best checkpoint mean slots | Final1m mean slots | Best step | Reused |',
           '| --- | ---: | ---: | ---: | --- |']
    for seed in p['learning_seeds']:
        best=next(r for r in groups if r['seed']==seed and r['checkpoint']=='best');final=next(r for r in groups if r['seed']==seed and r['checkpoint']=='final');proof=next(r for r in proofs if r['seed']==seed)
        lines.append(f"| {seed} | {best['mean_slots']:.3f} | {final['mean_slots']:.3f} | {proof['best_steps']} | {proof['reused']} |")
    lines+=['','| Policy / checkpoint | Mean slots | SD across learning-run means | Episodes |','| --- | ---: | ---: | ---: |']
    for r in summary:
        sd=r['sd_across_learning_run_means'];sd=f'{sd:.3f}' if isinstance(sd,(float,int)) else 'not applicable'
        lines.append(f"| {r['policy']} / {r['checkpoint']} | {r['mean_slots']:.3f} | {sd} | {r['episodes']} |")
    lines+=['','Interpretation: compare learning-run means conditionally on this one layout. Do not compare this mean directly with the Table5 average across unknown layouts, or treat heuristic repetitions as extra learner seeds.',
            'The best-validation checkpoint is selected before test; final1m is a secondary diagnostic on the same cases. These90+90 DQN rows are not180 independent training runs.',
            'Layout0 outcomes were already seen and the seed0 model is reused. This is a development diagnostic, not a newly blinded benchmark.',
            'No freshness/radio/reward convention changed. This stage measures learning-seed sensitivity; it cannot identify the cause of any instability or establish that the paper is reproduced.',
            '', 'Evidence: `verification.json`, `episodes.csv`, `runs.csv`, `summary.csv`, `fixed-layout.json`, `source/`. No model or raw source dataset was deleted.','']
    (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train');t.add_argument('--output',type=Path,required=True);t.add_argument('--workers',type=int,choices=(1,2),default=2)
    v=sub.add_parser('verify');v.add_argument('run',type=Path)
    args=parser.parse_args()
    if args.command=='train':train(args.output.resolve(),args.workers)
    else:verify(args.run.resolve())


if __name__=='__main__':main()
