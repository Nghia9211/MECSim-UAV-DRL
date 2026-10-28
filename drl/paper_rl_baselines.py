"""PPO/A2C on the frozen REFERENCE environment; reuse verified same-server DQN."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time

import torch
from .environment import ROOT
from .run import ALGORITHMS, evaluate, write_csv
from .paper_state_campaign import audit_trace, read, save, digest


def launch(out,plan,algorithm,seed):
    run=out/algorithm/f'seed-{seed}';run.parent.mkdir(exist_ok=True)
    command=[sys.executable,'-u','-m','drl.run','train','--algorithm',algorithm,'--steps',str(plan['steps']),
        '--seed',str(seed),'--layout-seed','0','--powered','8','--connected','8','--max-slots','200',
        '--reward','paper','--workload','synthetic','--observation-mode','paper24','--eval-freq',str(plan['eval_freq']),
        '--validation-episodes','5','--eval-episodes','1','--threads','1','--device','cpu','--output',str(run)]
    for k,v in plan['properties'].items():command+=['--property',f'{k}={v}']
    receipt=dict(algorithm=algorithm,seed=seed,command=command,started=time.time())
    with (out/f'{algorithm}-{seed}.log').open('w') as log:
        proc=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT);receipt['pid']=proc.pid
        save(out/f'{algorithm}-{seed}-process.json',receipt);receipt['exit_code']=proc.wait()
    receipt['finished']=time.time();save(out/f'{algorithm}-{seed}-process.json',receipt)
    assert receipt['exit_code']==0,receipt
    return run


def campaign(out,reference,smoke=False):
    plan=json.loads((ROOT/'drl/paper_reference_state_protocol.json').read_text())
    if smoke:plan.update(steps=1200,eval_freq=600,test_episodes=2,learning_seeds=[0],workers=2)
    torch.set_num_threads(1)
    previous=json.loads((reference/'manifest.json').read_text());pv=json.loads((reference/'verification.json').read_text())
    assert previous['status']=='COMPLETE' and pv['status']=='PASS'
    original_plan=json.loads((ROOT/'drl/paper_reference_state_protocol.json').read_text())
    assert previous['plan']==original_plan,'Reference configuration mismatch'
    for r in pv['checkpoints']:
        if r['run'].startswith('paper24/'):
            filename='best_model.zip' if r['checkpoint']=='best' else 'final_model.zip'
            assert digest(reference/r['run']/filename)==r['sha256'],'Reused DQN checkpoint changed'
    # Physics/reward/train implementations must match the reused DQN source exactly.
    old=reference/'paper24/seed-0/source'
    runtime=[ROOT/'drl/environment.py',ROOT/'drl/run.py',*sorted((ROOT/'PureEdgeSim/uav').glob('*.java'))]
    for p in runtime:assert digest(p)==digest(old/p.relative_to(ROOT)),p
    out.mkdir(parents=True,exist_ok=False)
    hashes={p.relative_to(ROOT).as_posix():digest(p) for folder,pattern in [('drl','*.py'),('PureEdgeSim/uav','*.java'),('scripts','verify-paper-conventions.py')]
            for p in (ROOT/folder).glob(pattern)}
    m=dict(status='RUNNING',started=time.time(),plan=plan,algorithms=['PPO','A2C'],state='paper24',smoke=smoke,
           commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_sha256=hashes,
           reference=str(reference),reference_summary_sha256=digest(reference/'summary.csv'))
    save(out/'manifest.json',m)
    try:
        with ThreadPoolExecutor(max_workers=plan['workers']) as pool:
            jobs=[pool.submit(launch,out,plan,algorithm,seed) for seed in plan['learning_seeds'] for algorithm in ['PPO','A2C']]
            runs=[f.result() for f in as_completed(jobs)]
        m['status']='TRAINING_COMPLETE';save(out/'manifest.json',m)
        spec=importlib.util.spec_from_file_location('physics_audit',ROOT/'scripts/verify-paper-conventions.py')
        audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
        summaries=[];proof=[];traces=device_rows=0
        for run in sorted(runs):
            cfg=json.loads((run/'config.json').read_text());alg=cfg['algorithm'];seed=cfg['seed']
            prior=json.loads((reference/f'paper24/seed-{seed}/config.json').read_text())
            assert cfg['packages']==prior['packages'] and cfg['python']==prior['python']
            assert cfg['environment']==prior['environment']
            final=ALGORITHMS[alg].load(run/'final_model.zip',device='cpu')
            expected=math.ceil(plan['steps']/final.n_steps)*final.n_steps
            assert cfg['actual_steps']==final.num_timesteps==expected
            assert final._n_updates==(expected//final.n_steps)*(final.n_epochs if alg=='PPO' else 1)
            validation=[r for r in read(run/'validation.csv') if int(r['gradient_updates'])>0]
            chosen=max(validation,key=lambda r:float(r['mean_slots']))
            for cp,file in [('best','best_model.zip'),('final','final_model.zip')]:
                model=ALGORITHMS[alg].load(run/file,device='cpu')
                assert model.num_timesteps==(int(chosen['steps']) if cp=='best' else expected)
                assert all(torch.isfinite(v).all() for v in model.policy.state_dict().values())
                rows=evaluate(run,plan['test_episodes'],plan['test_first_seed'],file,False,True,'cpu')
                evaluation=max(run.glob('evaluation-*'),key=lambda p:p.name)
                for i,row in enumerate(rows):
                    trace=evaluation/'traces'/f"{i//4:03d}-{row['policy']}"
                    device_rows+=audit_trace(trace,row,model,'paper24',plan,audit);traces+=1
                for policy in [alg,'ROUND_ROBIN','OLDEST_DATA','RANDOM']:
                    g=[r for r in rows if r['policy']==policy]
                    summaries.append(dict(algorithm=policy,training_algorithm=alg,seed=seed,checkpoint=cp,
                        mean_slots=statistics.mean(r['slots'] for r in g),mean_seconds=statistics.mean(r['seconds'] for r in g),
                        mean_uav_j=statistics.mean(1600000-r['uav_battery_j'] for r in g),episodes=len(g),reused=False))
                proof.append(dict(algorithm=alg,seed=seed,checkpoint=cp,sha256=digest(run/file),steps=model.num_timesteps,updates=model._n_updates))
        if not smoke:
            for r in read(reference/'summary.csv'):
                if r['mode']=='paper24' and r['policy']=='DQN':
                    summaries.append(dict(algorithm='DQN',training_algorithm='DQN',seed=int(r['seed']),checkpoint=r['checkpoint'],
                        mean_slots=float(r['mean_slots']),mean_seconds=float(r['mean_seconds']),mean_uav_j=float(r['mean_uav_j']),episodes=int(r['episodes']),reused=True))
        for policy in ['ROUND_ROBIN','OLDEST_DATA','RANDOM']:
            g=[r for r in summaries if r['algorithm']==policy]
            assert max(r['mean_slots'] for r in g)==min(r['mean_slots'] for r in g)
        for rel,h in hashes.items():assert digest(ROOT/rel)==h,rel
        assert digest(reference/'summary.csv')==m['reference_summary_sha256']
        write_csv(out/'summary.csv',summaries)
        save(out/'verification.json',dict(status='PASS',new_traces=traces,device_rows=device_rows,checkpoints=proof,
            source_unchanged=True,reused_dqn=not smoke,heuristics_are_shared_cases=True))
        lines=['# REFERENCE: PPO/A2C baselines','', 'Fixed layout0. Best selected by validation; final reported independently.',
            'PPO/A2C hyperparameters are implementation choices, not author settings. PPO rounds to a full rollout.',
            'Heuristic repetitions are shared cases, not additional independent samples.','',
            '| Algorithm | Best mean slots | Final mean slots |','| --- | ---: | ---: |']
        for algorithm in ['DQN','PPO','A2C','ROUND_ROBIN','OLDEST_DATA','RANDOM']:
            values=[]
            for cp in ['best','final']:
                g=[r['mean_slots'] for r in summaries if r['algorithm']==algorithm and r['checkpoint']==cp]
                values.append(f'{statistics.mean(g):.3f}' if g else 'not included in smoke')
            lines.append(f"| {algorithm} | {' | '.join(values)} |")
        (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
        m.update(status='COMPLETE',finished=time.time());save(out/'manifest.json',m)
    except BaseException as e:
        m.update(status='FAILED',error=repr(e),finished=time.time());save(out/'manifest.json',m);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--reference',required=True,type=Path);p.add_argument('--smoke',action='store_true')
    a=p.parse_args();campaign(a.output.resolve(),a.reference.resolve(),a.smoke)
