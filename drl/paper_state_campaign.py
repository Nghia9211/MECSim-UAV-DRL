"""Paired paper24/extended125 training; frozen delivery/reward. CPU only."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

import numpy as np
import torch
from stable_baselines3 import DQN
from .environment import ROOT
from .paper_reference import layout
from .run import evaluate

PLAN = ROOT/'drl/paper_state_protocol.json'


def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def save(p,v):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2,default=str),encoding='utf8');tmp.replace(p)


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def audit_trace(trace,row,model,mode,plan,audit):
    ds=layout(plan['layout_seed'],plan['powered'],plan['connected'],audit.JavaRandom)
    c=plan['constants'];slots=read(trace/'slots.csv');dev=read(trace/'devices.csv')
    by={}
    for d in dev:by.setdefault(int(d['slot']),{})[int(d['device'])]=d
    history=json.loads((trace/'extended-state.json').read_text()) if mode=='extended125' else None
    if history is not None:assert len(history)==len(slots)+1
    raw=np.array([1.]*12+[0.]*12,np.float32);x=y=seconds=0.;battery=1600000.;actions=[];next_id=0
    rng=np.random.default_rng(int(row['task_seed'])+2)
    def expected(k):
        extra=[x/800,y/800,battery/1600000,k/200,seconds/(200*600)]
        for d in ds:
            h=c['hardware'][d['hardware']]
            extra.extend([d['x']/800,d['y']/800,float(d['powered']),float(d['connected']),d['capacity_j']/80000,
                          h['bytes_per_s'][d['task']]/100000,h['standby_w']/10,h['active_w'][d['task']]/10])
        return np.concatenate((raw,np.array(extra,np.float32)))
    for k,s in enumerate(slots):
        obs=expected(k) if mode=='extended125' else raw
        if history is not None:
            np.testing.assert_allclose(history[k]['observation'],obs,atol=2e-6,rtol=2e-6)
            np.testing.assert_allclose(history[k]['raw'],raw,atol=2e-6,rtol=2e-6)
            snap=history[k]['snapshot'];assert snap['slots_completed']==k
            assert abs(snap['time_s']-seconds)<1e-5
            if k:assert history[k]['action']==int(slots[k-1]['action'])
        if row['policy']=='DQN':a=int(model.predict(obs,deterministic=True)[0])
        elif row['policy']=='ROUND_ROBIN':a=k%12
        elif row['policy']=='RANDOM':a=int(rng.integers(12))
        else:
            a=max([(next_id+i)%12 for i in range(12)],key=lambda i:raw[12+i]);next_id=(a+1)%12
        actions.append(a)
        # Reconstruct full-precision motion rather than rounding layout.csv coordinates.
        dx,dy=ds[a]['x'],ds[a]['y'];distance=np.hypot(dx-x,dy-y)
        ratio=min(1,float(s['duration_s'])*5/distance) if distance else 1
        x+=(dx-x)*ratio;y+=(dy-y)*ratio;seconds=float(s['end_s']);battery=float(s['uav_battery_j'])
        raw=np.array([float(by[k+1][i]['battery_j'])/ds[i]['capacity_j'] for i in range(12)]+
                     [float(by[k+1][i]['data_age']) for i in range(12)],np.float32)
    if history is not None:
        np.testing.assert_allclose(history[-1]['observation'],expected(len(slots)),atol=2e-6,rtol=2e-6)
        assert history[-1]['action']==int(slots[-1]['action'])
    conventions=json.loads((trace/'conventions.json').read_text())
    assert conventions['delivery']==plan['properties']['paper.deliveryConvention']
    assert conventions['reward_snapshot']==plan['properties']['paper.rewardSnapshot']
    assert conventions['radio']==plan['properties']['paper.radioConvention']
    assert conventions['expiry']==plan['properties']['paper.expiryConvention']
    assert conventions['reward_epsilon']==float(plan['properties']['paper.rewardEpsilon'])
    record=dict(profile='REFERENCE',seed=0,task_seed=row['task_seed'],policy=row['policy'],trace=trace.relative_to(ROOT).as_posix(),
        slots=row['slots'],seconds=row['seconds'],reward=row['reward'],reason=row['reason'],truncated=str(row['truncated']).lower(),
        uav_energy_j=1600000-float(row['uav_battery_j']),ground_energy_j=sum(float(d['energy_used_j']) for d in dev),
        cap_slots=sum(float(s['duration_s'])>=600-1e-6 for s in slots),capped_items=sum(int(s['capped_work_items']) for s in slots))
    return audit.replay(ROOT,record,dict(constants=c,profiles=dict(REFERENCE=conventions),max_slots=200),
                        layout_override=ds,expected_actions=actions)


def launch(out,plan,mode,seed):
    run=out/mode/f'seed-{seed}';run.parent.mkdir(exist_ok=True)
    command=[sys.executable,'-u','-m','drl.run','train','--algorithm','DQN','--steps',str(plan['steps']),
        '--seed',str(seed),'--layout-seed',str(plan['layout_seed']),'--powered','8','--connected','8',
        '--max-slots','200','--reward','paper','--workload','synthetic','--observation-mode',mode,
        '--eval-freq',str(plan['eval_freq']),'--validation-episodes','5','--eval-episodes','1',
        '--threads','1','--device','cpu','--output',str(run)]
    for k,v in plan['properties'].items():command+=['--property',f'{k}={v}']
    receipt=dict(mode=mode,seed=seed,command=command,started=time.time())
    with (out/f'{mode}-{seed}.log').open('w') as log:
        p=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT);receipt['pid']=p.pid
        save(out/f'{mode}-{seed}-process.json',receipt);receipt['exit_code']=p.wait()
    receipt['finished']=time.time();save(out/f'{mode}-{seed}-process.json',receipt)
    assert receipt['exit_code']==0,receipt
    return run


def campaign(out,smoke=False,protocol=PLAN):
    plan=json.loads(protocol.read_text());torch.set_num_threads(1)
    if smoke:plan.update(steps=1200,eval_freq=600,test_episodes=2,learning_seeds=[0],workers=2)
    out.mkdir(parents=True,exist_ok=False)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    hashes={p.relative_to(ROOT).as_posix():digest(p) for folder,pattern in [('drl','*.py'),('PureEdgeSim/uav','*.java'),('scripts','verify-paper-conventions.py')]
            for p in (ROOT/folder).glob(pattern)}
    m=dict(status='RUNNING',plan=plan,protocol_sha256=digest(protocol),commit=sha,source_sha256=hashes,smoke=smoke,started=time.time())
    save(out/'manifest.json',m)
    try:
        with ThreadPoolExecutor(max_workers=plan['workers']) as pool:
            futures=[pool.submit(launch,out,plan,mode,seed) for seed in plan['learning_seeds'] for mode in plan['modes']]
            runs=[f.result() for f in as_completed(futures)]
        m['status']='TRAINING_COMPLETE';save(out/'manifest.json',m)
        spec=importlib.util.spec_from_file_location('audit',ROOT/'scripts/verify-paper-conventions.py')
        audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
        summaries=[];proof=[];traces=device_rows=0
        for run in sorted(runs):
            cfg=json.loads((run/'config.json').read_text());assert cfg['actual_steps']==plan['steps']
            assert cfg['gradient_updates']==(plan['steps']-100)//4
            assert cfg['environment']['properties']==plan['properties']
            validation=read(run/'validation.csv');chosen=max(validation,key=lambda r:float(r['mean_slots']))
            for cp,file in [('best','best_model.zip'),('final','final_model.zip')]:
                model=DQN.load(run/file,device='cpu')
                assert model.num_timesteps==(int(chosen['steps']) if cp=='best' else plan['steps'])
                assert all(torch.isfinite(v).all() for v in model.q_net.state_dict().values())
                rows=evaluate(run,plan['test_episodes'],plan['test_first_seed'],file,False,True,'cpu')
                evaluation=max(run.glob('evaluation-*'),key=lambda p:p.name)
                for i,row in enumerate(rows):
                    trace=evaluation/'traces'/f"{i//4:03d}-{row['policy']}"
                    device_rows+=audit_trace(trace,row,model,cfg['environment']['observation_mode'],plan,audit);traces+=1
                for policy in ['DQN','ROUND_ROBIN','OLDEST_DATA','RANDOM']:
                    g=[r for r in rows if r['policy']==policy]
                    summaries.append(dict(mode=cfg['environment']['observation_mode'],seed=cfg['seed'],checkpoint=cp,policy=policy,
                        mean_slots=statistics.mean(r['slots'] for r in g),mean_seconds=statistics.mean(r['seconds'] for r in g),
                        mean_uav_j=statistics.mean(1600000-r['uav_battery_j'] for r in g),episodes=len(g)))
                proof.append(dict(run=run.relative_to(out).as_posix(),checkpoint=cp,sha256=digest(run/file),steps=model.num_timesteps))
        for rel,h in hashes.items():assert digest(ROOT/rel)==h,rel
        with (out/'summary.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
        save(out/'verification.json',dict(status='PASS',traces=traces,device_rows=device_rows,checkpoints=proof,source_unchanged=True))
        lines=['# State extension: '+plan['properties']['paper.deliveryConvention'],'', 'Same-server paired learning seeds. Best selected by validation; final reported separately.',
               'Heuristics repeated across modes/checkpoints are shared cases, not extra independent samples.','',
               '| Mode | Checkpoint | DQN mean slots | SD across learner means |','| --- | --- | ---: | ---: |']
        for mode in plan['modes']:
            for cp in ['best','final']:
                g=[r['mean_slots'] for r in summaries if r['mode']==mode and r['checkpoint']==cp and r['policy']=='DQN']
                lines.append(f'| {mode} | {cp} | {statistics.mean(g):.3f} | {statistics.stdev(g) if len(g)>1 else 0:.3f} |')
        (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
        m.update(status='COMPLETE',finished=time.time());save(out/'manifest.json',m)
    except BaseException as e:
        m.update(status='FAILED',error=repr(e),finished=time.time());save(out/'manifest.json',m);raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--smoke',action='store_true')
    p.add_argument('--protocol',type=Path,default=PLAN)
    a=p.parse_args();campaign(a.output.resolve(),a.smoke,a.protocol.resolve())
