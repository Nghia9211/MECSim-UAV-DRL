"""Frozen three-run synthetic reference campaign. Independent JVMs; no mobile or dataset extension."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

import numpy as np
import torch
from stable_baselines3 import DQN

from .environment import EnvConfig, PaperEnv, ROOT
from .run import evaluate, model_options, write_csv

PROTOCOL=ROOT/'drl/paper_reference_protocol.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,value):path.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')


def load_protocol():
    p=json.loads(PROTOCOL.read_text(encoding='utf-8'))
    if (p['schema']!='paper-reference-stage1-v1' or p['algorithm']!='DQN' or p['workload']!='synthetic'
            or p['steps_per_model']!=1_000_000 or p['learning_seeds']!=[0,1,2] or p['layout_seeds']!=[0,1,2]
            or p['powered']!=8 or p['connected']!=8):
        raise ValueError('Frozen reference protocol changed; review it before running')
    return p


def command(p,seed,layout,out):
    args=[sys.executable,'-u','-m','drl.run','train','--algorithm','DQN','--workload','synthetic',
          '--reward',p['reward'],'--steps',str(p['steps_per_model']),'--seed',str(seed),'--layout-seed',str(layout),
          '--powered',str(p['powered']),'--connected',str(p['connected']),'--max-slots',str(p['max_slots']),
          '--eval-freq',str(p['eval_freq']),'--validation-episodes',str(p['validation_episodes']),
          '--eval-episodes',str(p['evaluation_episodes_per_model']),'--device','cpu','--threads','1','--output',str(out)]
    for k,v in p['properties'].items():args+=['--property',f'{k}={v}']
    return args


def snapshot(out):
    paths=[*ROOT.glob('drl/*.py'),*ROOT.glob('drl/*protocol*.json'),*ROOT.glob('PureEdgeSim/uav/**/*.java'),
           *ROOT.glob('PureEdgeSim/com/mechalikh/pureedgesim/simulationengine/*.java'),*ROOT.glob('src/test/java/uav/*.java')]
    paths += [ROOT/f for f in ['pom.xml','drl/requirements.txt','scripts/verify-paper-conventions.py',
                              'scripts/test-paper-convention-verifier.py','PureEdgeSim/uav/PAPER_ALIGNMENT.md']]
    hashes={}
    for source in paths:
        rel=source.relative_to(ROOT);target=out/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target);hashes[rel.as_posix()]=sha(source)
    for ext in ('pdf','md'):
        target=out/'source/paper'/f'2501.15305v1.{ext}';target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT.parent/f'2501.15305v1.{ext}',target)
        hashes['paper/'+target.name]=sha(target)
    return hashes


def train_campaign(out,workers):
    p=load_protocol();out.mkdir(parents=True,exist_ok=False)
    manifest=dict(schema='paper-reference-campaign-v1',status='RUNNING',started=time.time(),protocol=p,
                  protocol_sha256=sha(PROTOCOL),source_sha256=snapshot(out),workers=workers,
                  timing_note='Concurrent local training when workers>1; runtime is not comparable to paper hardware.',
                  python=sys.version,platform=platform.platform(),pid=os.getpid(),runs=[])
    save(out/'manifest.json',manifest)
    def launch(seed,layout):
        run=out/f'seed-{seed}';args=command(p,seed,layout,run)
        receipt=dict(seed=seed,layout_seed=layout,run=str(run),command=args,started=time.time())
        with (out/f'seed-{seed}.log').open('w',encoding='utf-8') as log:
            proc=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            receipt['pid']=proc.pid;save(out/f'seed-{seed}-process.json',receipt)
            receipt['exit_code']=proc.wait()
        receipt['finished']=time.time();save(out/f'seed-{seed}-process.json',receipt)
        return receipt
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures=[pool.submit(launch,s,l) for s,l in zip(p['learning_seeds'],p['layout_seeds'])]
        for future in as_completed(futures):
            receipt=future.result();manifest['runs'].append(receipt);save(out/'manifest.json',manifest)
            print(f"seed={receipt['seed']} exit={receipt['exit_code']}",flush=True)
    failed=[r for r in manifest['runs'] if r['exit_code']!=0]
    manifest.update(status='TRAINING_FAILED' if failed else 'TRAINING_COMPLETE',finished=time.time())
    save(out/'manifest.json',manifest)
    if failed:raise RuntimeError('A training process failed; logs/checkpoints preserved')
    print('Training finished; auditing all held-out traces next.',flush=True)
    verify_campaign(out)


def layout(seed,powered,connected,random_type):
    rng=random_type(seed);power=list(range(12));comms=list(range(12))
    for ids in (power,comms):
        for i in range(len(ids),1,-1):
            k=rng.integer(i);ids[i-1],ids[k]=ids[k],ids[i-1]
    hardware=('RASPBERRY_PI_4B','RASPBERRY_PI_3B','FIREFLY','JETSON_NANO','NANOPC_T4')
    tasks=('HAAR','MMOD','DNN','DLIB','YOLOV3')
    return [dict(x=rng.double()*800,y=rng.double()*800,hardware=hardware[rng.integer(5)],task=tasks[rng.integer(5)],
                 capacity_j=50000+rng.double()*30000,powered=power.index(i)<powered,connected=comms.index(i)<connected) for i in range(12)]


def constants():
    # Parse exactly the published tables from the supplied extracted paper; audit module checks them again.
    import re
    text=(ROOT.parent/'2501.15305v1.md').read_text(encoding='utf-8')
    names=('RASPBERRY_PI_4B','RASPBERRY_PI_3B','FIREFLY','JETSON_NANO','NANOPC_T4')
    standbys=[float(x) for x in re.search(r'Standby power.*?\[([\d., ]+)\]',text).group(1).split(',')]
    h={name:dict(standby_w=w,active_w={},bytes_per_s={}) for name,w in zip(names,standbys)}
    for title,key,end in [('Table 2. Power','active_w','Table 3.'),('Table 3. Data processing','bytes_per_s','5 RESULTS')]:
        section=text.split(title,1)[1].split(end,1)[0]
        for printed,task in [('HAAR','HAAR'),('MMOD','MMOD'),('DNN','DNN'),('Dlib','DLIB'),('YOLOv3','YOLOV3')]:
            vals=[float(x) for x in re.search(r'^'+printed+r' ((?:[\d.]+ ?){5})$',section,re.M).group(1).split()]
            for name,value in zip(names,vals):h[name][key][task]=value
    return dict(devices=12,area_m=800,altitude_m=10,speed_mps=5,flight_w=150,hover_w=80,uav_battery_j=1600000,
                range_m=65,min_battery_j=50000,max_battery_j=80000,min_task_bytes=2000000,max_task_bytes=4000000,
                slot_cap_s=600,bandwidth_hz=20000000,transmit_w=.1,age_limit=10,hardware=h)


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def verify_campaign(out):
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'));p=manifest['protocol']
    if manifest['status'] not in ('TRAINING_COMPLETE','COMPLETE','AUDIT_FAILED'):
        raise ValueError('All training processes must finish first')
    for rel,digest in manifest['source_sha256'].items():
        if sha(out/'source'/rel)!=digest:raise ValueError('Snapshot hash mismatch '+rel)
    # Never silently assess old training with new evaluator or physics source.
    for rel,digest in manifest['source_sha256'].items():
        if rel.endswith(('.py','.java')) and sha(ROOT/rel)!=digest:raise ValueError('Live source drift '+rel)
    torch.set_num_threads(1)
    spec=importlib.util.spec_from_file_location('reference_audit',ROOT/'scripts/verify-paper-conventions.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    c=constants();params=audit.verify_parameters(out,dict(constants=c));save(out/'parameter-verification.json',params)
    conventions=dict(radio='LITERAL_DBM',expiry='AT_LIMIT',delivery='LEGACY',reward_snapshot='BEFORE',reward_epsilon=1e-6,
                     backlog='discard at slot end; not varied',output_link='instantaneous; uncalibrated and not varied')
    all_rows=[];receipts=[];counts=[]
    for seed,ls in zip(p['learning_seeds'],p['layout_seeds']):
        run=out/f'seed-{seed}';cfg=json.loads((run/'config.json').read_text(encoding='utf-8'))
        e=cfg['environment'];properties=e['properties']
        if not (cfg['status']=='COMPLETE' and cfg['requested_steps']==cfg['actual_steps']==p['steps_per_model']
                and cfg['seed']==seed and e['layout_seed']==ls and e['powered']==p['powered'] and e['connected']==p['connected']
                and e['reward']=='paper' and properties==p['properties']):raise AssertionError('Training config mismatch')
        if cfg['gradient_updates']!=249975:raise AssertionError('Unexpected full-budget optimizer count')
        model=DQN.load(run/'best_model.zip',device='cpu');final=DQN.load(run/'final_model.zip',device='cpu')
        if final.num_timesteps!=p['steps_per_model'] or final._n_updates!=cfg['gradient_updates']:raise AssertionError('Checkpoint budget mismatch')
        if not all(torch.isfinite(v).all() for v in final.q_net.state_dict().values()):raise AssertionError('Nonfinite Q weights')
        env=PaperEnv(EnvConfig(**e))
        try:
            initial=DQN('MlpPolicy',env,seed=seed,device='cpu',**model_options('DQN'))
            delta=max((initial.q_net.state_dict()[k]-v).abs().max().item() for k,v in final.q_net.state_dict().items())
            if delta<=0:raise AssertionError('Weights unchanged')
            vrows=read(run/'validation.csv');eligible=[r for r in vrows if int(r['gradient_updates'])>0]
            first_best=max(eligible,key=lambda r:float(r['mean_slots']))
            if model.num_timesteps!=int(first_best['steps']):raise AssertionError('Best checkpoint not first validation maximum')
            score=[]
            from .run import episode
            for i in range(p['validation_episodes']):score.append(episode(env,model=model,task_seed=1000000+i)['slots'])
            audit.close(statistics.mean(score),float(first_best['mean_slots']),'Best validation replay')
        finally:env.close()
        proof=dict(seed=seed,layout_seed=ls,steps=final.num_timesteps,gradient_updates=final._n_updates,
                   final_sha256=sha(run/'final_model.zip'),best_sha256=sha(run/'best_model.zip'),best_steps=model.num_timesteps,
                   max_abs_weight_change=delta,elapsed_s=cfg['elapsed_s'],validation_replay_mean=statistics.mean(score))
        # The existing train command already evaluates with only first-case traces. Re-evaluate the
        # SAME 30 cases with complete traces for replay; these are not additional independent samples.
        export=run/'reference-evaluation.json'
        if export.exists():evaluation=run/json.loads(export.read_text())['directory']
        else:
            previous=set(run.glob('evaluation-*'))
            evaluate(run,p['evaluation_episodes_per_model'],2000000,'best_model.zip',False,True,'cpu')
            created=set(run.glob('evaluation-*'))-previous
            if len(created)!=1:raise AssertionError('Evaluation directory ambiguity')
            evaluation=created.pop();save(export,dict(directory=evaluation.name,duplicate_cases_not_new_samples=True))
        rows=read(evaluation/'episodes.csv');ds=layout(ls,p['powered'],p['connected'],audit.JavaRandom)
        a_manifest=dict(constants=c,profiles=dict(REFERENCE=conventions),max_slots=p['max_slots'])
        for i,r in enumerate(rows):
            task=int(r['task_seed']);policy=r['policy'];trace=evaluation/'traces'/f'{(task-2000000):03d}-{policy}'
            slots=read(trace/'slots.csv');devices=read(trace/'devices.csv');by_slot={}
            for d in devices:by_slot.setdefault(int(d['slot']),{})[int(d['device'])]=d
            batteries=[1.]*12;ages=[0.]*12;expected=[];rng=np.random.default_rng(task+2);next_id=0
            for k,s in enumerate(slots,1):
                obs=np.array(batteries+ages,np.float32)
                if policy=='DQN':action=int(model.predict(obs,deterministic=True)[0])
                elif policy=='RANDOM':action=int(rng.integers(12))
                elif policy=='ROUND_ROBIN':action=next_id;next_id=(action+1)%12
                else:
                    order=[(next_id+j)%12 for j in range(12)];action=max(order,key=lambda j:ages[j]);next_id=(action+1)%12
                expected.append(action)
                batteries=[float(by_slot[k][j]['battery_j'])/ds[j]['capacity_j'] for j in range(12)]
                ages=[float(by_slot[k][j]['data_age']) for j in range(12)]
            uav_j=1600000-float(slots[-1]['uav_battery_j'])
            row=dict(profile='REFERENCE',scenario='p8-c8',seed=seed,task_seed=task,policy=policy,trace=str(trace.relative_to(out)),
                     slots=r['slots'],seconds=r['seconds'],reason=r['reason'],truncated=r['truncated'].lower(),reward=r['reward'],
                     uav_energy_j=uav_j,ground_energy_j=sum(float(d['energy_used_j']) for d in devices),
                     cap_slots=sum(float(s['duration_s'])>=600-1e-6 for s in slots),capped_items=sum(int(s['capped_work_items']) for s in slots))
            audit.replay(out,row,a_manifest,counts,layout_override=ds,expected_actions=expected)
            scenario=json.loads((trace/'scenario.json').read_text())
            if scenario['workload_mode']!='synthetic' or scenario['base_layout_seed']!=ls or scenario['task_seed']!=task:raise AssertionError('Trace provenance')
            all_rows.append(dict(training_seed=seed,**r,trace=row['trace']))
        if len(rows)!=p['evaluation_episodes_per_model']*4:raise AssertionError('Evaluation sample count')
        receipts.append(proof);save(run/'reference-verification.json',dict(status='PASS',**proof,audited_episodes=len(rows)))
        print(f'Audited seed {seed}: {len(rows)} episodes',flush=True)
    write_csv(out/'episodes.csv',all_rows);write_csv(out/'slot-counting.csv',counts)
    groups=[]
    for seed in p['learning_seeds']:
        for policy in ('DQN','ROUND_ROBIN','OLDEST_DATA','RANDOM'):
            g=[r for r in all_rows if r['training_seed']==seed and r['policy']==policy];vals=[int(r['slots']) for r in g]
            groups.append(dict(training_seed=seed,layout_seed=seed,policy=policy,episodes=len(g),mean_slots=statistics.mean(vals),
                               sd_slots=statistics.stdev(vals),max_slots=max(vals),mean_seconds=statistics.mean(float(r['seconds']) for r in g),
                               truncated=sum(r['truncated']=='True' for r in g)))
    write_csv(out/'runs.csv',groups)
    summaries=[]
    for policy in ('DQN','ROUND_ROBIN','OLDEST_DATA','RANDOM'):
        g=[r for r in groups if r['policy']==policy];vals=[r['mean_slots'] for r in g]
        summaries.append(dict(policy=policy,training_layout_units=len(g),episodes=sum(r['episodes'] for r in g),
                              mean_of_run_means=statistics.mean(vals),sd_of_run_means=statistics.stdev(vals),
                              max_observed_slots=max(r['max_slots'] for r in g),mean_seconds=statistics.mean(r['mean_seconds'] for r in g)))
    write_csv(out/'summary.csv',summaries)
    deltas=[]
    for seed in p['learning_seeds']:
        by={r['policy']:r for r in groups if r['training_seed']==seed}
        deltas.append(dict(training_layout_seed=seed,**{f'dqn_minus_{key}':by['DQN']['mean_slots']-by[key]['mean_slots'] for key in ('ROUND_ROBIN','OLDEST_DATA','RANDOM')}))
    write_csv(out/'paired-run-differences.csv',deltas)
    result=dict(status='PASS',models=3,steps_per_model=1000000,audited_episodes=len(all_rows),
                checkpoints=receipts,mean_metric_reference_table5=18.3,max_metric_reference_table6=28,
                independent_training_layout_units=3,full_table5_or_table6_reproduced=False,
                note='Checkpoint/config/validation/policy and physical trace replay pass. Not proof of author-code equivalence or statistical equivalence.')
    save(out/'verification.json',result);manifest.update(status='COMPLETE',verified=time.time());save(out/'manifest.json',manifest)
    print(json.dumps(summaries,indent=2),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    t=sub.add_parser('train');t.add_argument('--output',type=Path,required=True);t.add_argument('--workers',type=int,choices=(1,2,3),default=1)
    v=sub.add_parser('verify');v.add_argument('run',type=Path)
    args=parser.parse_args()
    if args.command=='train':train_campaign(args.output.resolve(),args.workers)
    else:verify_campaign(args.run.resolve())


if __name__=='__main__':main()
