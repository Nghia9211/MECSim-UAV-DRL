"""Audited development PPO vs DQN policy selector on mobile contact-wait workloads."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import importlib.util
import importlib.metadata
import itertools
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
import torch
from stable_baselines3 import DQN, PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure

from .environment import ROOT
from .joint_environment import JointEnv, ROUTES, SCHEDULES, REWARD
from .mobile_environment import MobileConfig
from .mobile_run import audit_trace, save_json, snapshot
from .run import write_csv

ALGORITHMS={'PPO':PPO,'DQN':DQN}


def scenarios():
    result={}
    for area,battery,load,error in itertools.product((250,800),(30000,1600000),('light','overload'),(0.,.4)):
        ir,br=(.08,.02) if load=='light' else (.24,.1)
        name=f'a{area}-{load}-b{battery}-e{int(error*100)}'
        result[name]=MobileConfig(control_mode='joint_policy',allowContactWait=True,areaMetres=area,
            uavBatteryJ=battery,imageRate=ir,backgroundRate=br,estimateError=error)
    return result


def parameters(algorithm):
    common=dict(learning_rate=.0003,gamma=1.,policy_kwargs=dict(net_arch=[64,64]))
    if algorithm=='PPO':
        return dict(**common,n_steps=256,batch_size=64,n_epochs=5,gae_lambda=1.,
                    ent_coef=.01,clip_range=.2,target_kl=.02)
    return dict(**common,batch_size=64,buffer_size=100000,learning_starts=128,train_freq=4,
                gradient_steps=1,target_update_interval=500,exploration_fraction=.5,exploration_final_eps=.05)


def rollout(env,seed,model=None,action=0,trace=None):
    obs,info=env.reset(seed=seed,options={'task_seed':seed})
    total=0.
    while True:
        selected=int(model.predict(obs,deterministic=True)[0]) if model is not None else action
        obs,r,t,u,info=env.step(selected);total+=r
        if t or u:break
    if trace is not None:env.save_trace(trace)
    return total,info


class Validation(BaseCallback):
    def __init__(self,out,frequency,smoke):
        super().__init__();self.out=out;self.frequency=frequency;self.best=-float('inf');self.rows=[]
        self.configs=list(scenarios().values())[:1] if smoke else list(scenarios().values())

    def evaluate(self):
        values=[]
        for cfg in self.configs:
            with JointEnv(cfg) as env:values.append(rollout(env,1800000,model=self.model)[0])
        value=float(np.mean(values));updates=self.model._n_updates
        self.rows.append(dict(steps=self.num_timesteps,gradient_updates=updates,mean_reward=value))
        write_csv(self.out/'validation.csv',self.rows)
        if updates>0 and value>self.best:
            self.best=value;self.model.save(self.out/'best_model')
            save_json(self.out/'best.json',dict(steps=self.num_timesteps,gradient_updates=updates,reward=value))
        print(f'steps={self.num_timesteps} updates={updates} validation={value:.6f}',flush=True)

    def _on_step(self):
        if self.n_calls%self.frequency==0:self.evaluate()
        return True

    def _on_training_end(self):self.evaluate()


def worker(out,algorithm,seed,steps,smoke):
    out.mkdir(parents=True,exist_ok=False)
    cfg=dict(status='RUNNING',algorithm=algorithm,seed=seed,requested_steps=steps,
        environment='mobile_joint_policy_v1',observation_size=143,actions=9,hyperparameters=parameters(algorithm),
        reward=REWARD,device='cpu',threads=1,validation_seed=1800000,training_task_seed_range=[0,999999])
    save_json(out/'config.json',cfg);start=time.monotonic()
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    try:
        with JointEnv(random_scenarios=True) as env:
            model=ALGORITHMS[algorithm]('MlpPolicy',env,seed=seed,device='cpu',**parameters(algorithm))
            model.set_logger(configure(str(out),['csv']))
            model.learn(steps,callback=Validation(out,512 if smoke else 4096,smoke))
            model.save(out/'final_model')
            assert model.num_timesteps==steps and model._n_updates>0 and (out/'best_model.zip').is_file()
            cfg.update(status='COMPLETE',actual_steps=model.num_timesteps,gradient_updates=model._n_updates,
                       elapsed_s=time.monotonic()-start)
    except BaseException as exc:
        cfg.update(status='FAILED',error=repr(exc));raise
    finally:save_json(out/'config.json',cfg)


def import_metrics():
    spec=importlib.util.spec_from_file_location('core_metrics',ROOT/'scripts/offloading_metrics.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def evaluate(out,smoke):
    metrics=import_metrics();rows=[];proofs=[];audits=0;tasks=0;paired={};action_rows=[]
    policies=[(f'FIXED_{r}_{s}',None,3*i+j,None) for i,r in enumerate(ROUTES) for j,s in enumerate(SCHEDULES)]
    policies += [('ALL_LOCAL_EDF',None,0,'ALL_LOCAL'),('ALL_UAV_FIFO',None,2,'ALL_UAV')]
    for config in sorted((out/'models').glob('*/seed-*/config.json')):
        cfg=json.loads(config.read_text());assert cfg['status']=='COMPLETE'
        for checkpoint in ('best','final'):
            path=config.parent/(checkpoint+'_model.zip')
            model=ALGORITHMS[cfg['algorithm']].load(path,device='cpu')
            policies.append((f"{cfg['algorithm']}_s{cfg['seed']}_{checkpoint}",model,0,None))
            proofs.append(dict(run=config.parent.relative_to(out).as_posix(),checkpoint=checkpoint,
                               sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    cases=list(scenarios().items())[:1] if smoke else list(scenarios().items())
    count=1 if smoke else 10
    for name,cfg in cases:
        for i in range(count):
            seed=2800000+i
            for policy,model,action,fixed in policies:
                trace=out/'evaluation'/name/f'seed-{seed}'/policy
                # The two external baselines use the original device-control environment,
                # with the identical contact-wait physics and fixed RR target choices.
                if fixed:
                    from .mobile_environment import MobileEnv,heuristic_action
                    c=MobileConfig(**asdict(cfg));c.control_mode='device';c.offloading=fixed;c.scheduler='FIFO' if fixed=='ALL_UAV' else 'EDF'
                    with MobileEnv(c) as env:
                        obs,info=env.reset(seed=seed,options={'task_seed':seed})
                        while True:
                            a=heuristic_action('ROUND_ROBIN',obs,info,np.random.default_rng(seed))
                            obs,_,t,u,info=env.step(a)
                            if t or u:break
                        env.save_trace(trace)
                else:
                    with JointEnv(MobileConfig(**asdict(cfg))) as env:rollout(env,seed,model,action,trace)
                result=audit_trace(trace);assert result['status']=='PASS';audits+=1;tasks+=result['tasks']
                history=json.loads((trace/'transitions.json').read_text())
                if not fixed:
                    action_rows.append(dict(scenario=name,seed=seed,policy=policy,
                        **{f'mode_{k}':sum(s['action']==k for s in history[1:]) for k in range(9)}))
                if model is not None:
                    for before,after in zip(history,history[1:]):
                        assert int(model.predict(np.asarray(before['observation'],dtype=np.float32),deterministic=True)[0])==after['action'], 'Checkpoint/action mismatch'
                meta=json.loads((trace/'scenario.json').read_text());digest=meta['workload_sha256']
                assert paired.setdefault((name,seed),digest)==digest,'Unpaired workload'
                jobs={j['id']:j for j in metrics.read(trace/'workload.csv')}
                outcomes={o['id']:o for o in metrics.read(trace/'episode-tasks.csv')}
                energies=metrics.read(trace/'episode-energy.csv')
                values=metrics.calculate(jobs,outcomes,energies,cfg.horizonSeconds)
                delivered={u['id'] for u in metrics.read(trace/'episode-updates.csv')}
                on=sum(outcomes[k]['status']=='COMPLETED_ON_TIME' for k in delivered)
                lat=[float(outcomes[k]['resolved_s'])-float(jobs[k]['arrival_s']) for k in delivered]
                coverage=metrics.read(trace/'episode-coverage.csv')
                visits=metrics.read(trace/'episode-visits.csv')
                powered=values['uav_observed_time_s']
                flight_s=sum(max(0,min(powered,float(v['planned_arrival_s']))-float(v['at_s'])) for v in visits)
                reserved={k for k,o in outcomes.items() if o['route']=='UAV' and
                          float(o.get('planned_upload_start_s') or jobs[k]['arrival_s'])>float(jobs[k]['arrival_s'])+1e-8}
                values.update(delivered_ontime_images=on,delivered_image_dvr=1-on/values['image_offered'] if values['image_offered'] else None,
                              j_per_delivered_ontime_image=values['total_energy_j']/on if on else None,
                              delivered_completed_images=len(delivered),
                              delivered_mean_latency_s=metrics.mean(lat),delivered_p95_latency_s=metrics.p95(lat),
                              covered_images=sum(c['available']=='true' for c in coverage),
                              offloaded_images=sum(jobs[k]['source']=='RESCUENET' and o['route']=='UAV' for k,o in outcomes.items()),
                              flight_j=flight_s*150,hover_j=(powered-flight_s)*80,travelled_m=flight_s*5,
                              contact_wait_enabled=1,offload_eligible_images=sum(c['offload_available']=='true' for c in coverage),
                              reserved_images=len(reserved),reserved_uploaded_images=sum(float(outcomes[k]['uploaded_s'])>0 for k in reserved),
                              reserved_delivered_ontime_images=sum(k in delivered and outcomes[k]['status']=='COMPLETED_ON_TIME' for k in reserved),
                              actual_contact_wait_s=sum(max(0,min(float(outcomes[k]['planned_upload_start_s']),float(outcomes[k]['resolved_s']))
                                                        -float(jobs[k]['arrival_s'])) for k in reserved))
                rows.append(dict(scenario=name,seed=seed,policy=policy,workload_sha256=digest,**values))
            print(f'evaluation {name} seed={seed} audited={audits}',flush=True)
    # Reuse the mandatory exporter on the same audited task/energy traces. Its
    # general summarizer handles compute metrics; delivery details get a separate table.
    metrics.write_csv(out/'core-metrics-episodes.csv',rows)
    metrics.summarize(rows,out)
    delivery=[]
    for name in ['ALL']+[n for n,_ in cases]:
        for policy,_,_,_ in policies:
            g=[r for r in rows if r['policy']==policy and (name=='ALL' or r['scenario']==name)]
            on=sum(r['delivered_ontime_images'] for r in g)
            delivery.append(dict(scenario=name,policy=policy,cases=len(g),
                delivered_image_dvr=metrics.mean([r['delivered_image_dvr'] for r in g]),
                j_per_delivered_ontime_image=sum(r['total_energy_j'] for r in g)/on if on else None,
                mean_delivered_latency_s=metrics.mean([r['delivered_mean_latency_s'] for r in g]),
                mean_episode_delivered_p95_s=metrics.mean([r['delivered_p95_latency_s'] for r in g])))
    metrics.write_csv(out/'delivery-summary.csv',delivery)
    metrics.write_csv(out/'policy-actions.csv',action_rows)
    return dict(status='PASS',traces=audits,tasks=tasks,paired_cases=len(paired),checkpoints=proofs,
                checkpoint_actions_replayed=True,all_physics_observations_rewards_audited=True)


def campaign(out,smoke):
    out.mkdir(parents=True,exist_ok=False);steps=1024 if smoke else 32768;seeds=[0] if smoke else [0,1,2]
    manifest=dict(schema='mobile-joint-policy-v1',status='RUNNING',smoke=smoke,steps=steps,seeds=seeds,
        algorithms=list(ALGORITHMS),commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        action_routes=ROUTES,action_schedules=SCHEDULES,selection_interval='service boundary; hold until next boundary',
        mobility='fixed ROUND_ROBIN',reward=REWARD,gamma=1.,validation_seed=1800000,
        scenarios={name:asdict(cfg) for name,cfg in scenarios().items()},
        packages={p:importlib.metadata.version(p) for p in ('stable-baselines3','torch','gymnasium','numpy')},
        test_seeds=list(range(2800000,2800000+(1 if smoke else 10))),source_holdout=False,
        limitations=['Policy selection, not per-task learned priorities','Same layout seed42 scaled to two areas; no unseen-layout claim',
                     'Development pilot budget; no guaranteed PPO improvement','No calibrated real inference or output/backhaul delay'])
    manifest['source_sha256']=snapshot(out);save_json(out/'manifest.json',manifest)
    start=time.monotonic()
    def launch(item):
        algo,seed=item;run=out/'models'/algo/f'seed-{seed}';run.parent.mkdir(parents=True,exist_ok=True)
        cmd=[sys.executable,'-u','-m','drl.joint_campaign','worker','--output',str(run),'--algorithm',algo,'--seed',str(seed),'--steps',str(steps)]
        if smoke:cmd.append('--smoke')
        log=out/f'{algo}-seed-{seed}.log'
        with log.open('w') as handle:
            proc=subprocess.Popen(cmd,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT)
            receipt=dict(pid=proc.pid,command=cmd,started=time.time());save_json(out/f'{algo}-seed-{seed}-process.json',receipt)
            code=proc.wait();receipt.update(exit_code=code,finished=time.time());save_json(out/f'{algo}-seed-{seed}-process.json',receipt)
        if code:raise RuntimeError(f'{algo} seed{seed} failed: {log}')
    try:
        with ThreadPoolExecutor(max_workers=2 if smoke else 3) as pool:list(pool.map(launch,itertools.product(ALGORITHMS,seeds)))
        proof=evaluate(out,smoke)
        proof['source_unchanged']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in manifest['source_sha256'].items())
        assert proof['source_unchanged'],'Source changed during campaign'
        expected=(15 if smoke else 3680)
        assert proof['traces']==expected,(proof['traces'],expected)
        save_json(out/'verification.json',proof)
        manifest.update(status='COMPLETE',episodes=proof['traces'],elapsed_s=time.monotonic()-start)
    except BaseException as exc:manifest.update(status='FAILED',error=repr(exc));raise
    finally:save_json(out/'manifest.json',manifest)
    print('JOINT_RL_COMPLETE_AND_VERIFIED',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['campaign','worker']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--smoke',action='store_true');p.add_argument('--algorithm',choices=list(ALGORITHMS));p.add_argument('--seed',type=int,default=0);p.add_argument('--steps',type=int,default=32768)
    a=p.parse_args()
    if a.command=='worker':worker(a.output.resolve(),a.algorithm,a.seed,a.steps,a.smoke)
    else:campaign(a.output.resolve(),a.smoke)


if __name__=='__main__':main()
