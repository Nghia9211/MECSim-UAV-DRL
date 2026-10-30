"""Pilot of contact-aware MaskablePPO; reuses the audited kernel and metrics."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import torch
from sb3_contrib import MaskablePPO
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.logger import configure
from .environment import ROOT
from .contact_environment import ContactEnv,heuristic,masks
from .joint_environment import REWARD
from .mobile_environment import MobileConfig,MobileEnv
from .mobile_run import save_json,snapshot
from .joint_campaign import scenarios,parameters,evaluate_with_envs
from .run import write_csv


def configs(smoke=False):
    cases=list(scenarios().items())[:1] if smoke else list(scenarios().items())
    for _,cfg in cases:cfg.control_mode='contact_policy'
    return cases


class Predictor:
    def __init__(self,model=None,name=None,legacy=False):
        self.model,self.name,self.legacy=model,name,legacy

    def predict(self,obs,deterministic=True):
        obs=np.asarray(obs,dtype=np.float32);ds=obs[9:129].reshape(12,10)
        previous=np.flatnonzero(ds[:,9]>.5)
        info={'previous_target':int(previous[0]) if len(previous) else -1}
        if self.name:action=heuristic(self.name,obs,info)
        elif self.legacy:
            mode=int(self.model.predict(obs[:143],deterministic=True)[0])
            action=heuristic('RR',obs,info)+mode
        else:action=int(self.model.predict(obs,deterministic=True,action_masks=masks(obs))[0])
        assert masks(obs)[action],'Policy returned masked action'
        return np.int64(action),None


def rollout(env,predictor,seed):
    obs,info=env.reset(seed=seed,options={'task_seed':seed});reward=0.
    while True:
        action,_=predictor.predict(obs)
        obs,r,t,u,info=env.step(action);reward+=r
        if t or u:return reward


class Validation(BaseCallback):
    def __init__(self,out,smoke):
        super().__init__();self.out=out;self.smoke=smoke;self.env=ContactEnv();self.rows=[];self.best=-float('inf')

    def evaluate(self):
        scores=[]
        for _,cfg in configs(self.smoke):
            self.env.config=cfg
            scores.append(rollout(self.env,Predictor(model=self.model),1900000))
        value=float(np.mean(scores))
        self.rows.append(dict(steps=self.num_timesteps,sb3_n_updates=self.model._n_updates,mean_reward=value))
        write_csv(self.out/'validation.csv',self.rows)
        if self.model._n_updates>0 and value>self.best:
            self.best=value;self.model.save(self.out/'best_model')
            save_json(self.out/'best.json',dict(steps=self.num_timesteps,reward=value))
        print(f'steps={self.num_timesteps} sb3_epochs={self.model._n_updates} validation={value:.6f}',flush=True)

    def _on_step(self):
        if self.n_calls%(512 if self.smoke else 4096)==0:self.evaluate()
        return True

    def _on_training_end(self):self.evaluate()


def worker(out,seed,smoke):
    out.mkdir(parents=True,exist_ok=False);steps=1024 if smoke else 32768
    cfg=dict(status='RUNNING',algorithm='MaskablePPO',seed=seed,steps=steps,
        observation_size=179,actions=108,reward=REWARD,hyperparameters=parameters('PPO'),
        action='9*target + 3*route + scheduler',threads=1,device='cpu',validation_seed=1900000,
        training_task_seed_range=[0,999999],sb3_n_updates_semantics='PPO training epochs, not optimizer minibatches')
    save_json(out/'config.json',cfg);start=time.monotonic();torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    validation=Validation(out,smoke)
    try:
        with ContactEnv(random_scenarios=True) as env:
            model=MaskablePPO('MlpPolicy',env,seed=seed,device='cpu',**parameters('PPO'))
            model.set_logger(configure(str(out),['csv']))
            model.learn(steps,callback=validation);model.save(out/'final_model')
            assert model.num_timesteps==steps and model._n_updates>0 and (out/'best_model.zip').exists()
            cfg.update(status='COMPLETE',actual_steps=model.num_timesteps,sb3_n_updates=model._n_updates,elapsed_s=time.monotonic()-start)
    except BaseException as exc:cfg.update(status='FAILED',error=repr(exc));raise
    finally:
        validation.env.close();save_json(out/'config.json',cfg)


def evaluate(out,smoke):
    policies=[(name,Predictor(name=name),0,None) for name in ('RR','DISCONNECTED_RR','CONTACT_GREEDY')]
    policies += [(name,None,0,pair) for name,pair in (
        ('RR_DELIVERY_RISK_EDF',('DELIVERY_AWARE','RISK_EDF')),
        ('RR_DEADLINE_RISK_EDF',('DEADLINE_ENERGY','RISK_EDF')),
        ('RR_DELIVERY_RISK_SPT',('DELIVERY_AWARE','RISK_SPT')),
        ('RR_DELIVERY_AGING',('DELIVERY_AWARE','FEASIBLE_AGING')))]
    proofs=[]
    for path in sorted((out/'models').glob('seed-*/config.json')):
        cfg=json.loads(path.read_text());assert cfg['status']=='COMPLETE'
        for checkpoint in ('best','final'):
            p=path.parent/(checkpoint+'_model.zip')
            policies.append((f"CONTACT_PPO_s{cfg['seed']}_{checkpoint}",Predictor(model=MaskablePPO.load(p,device='cpu')),0,None))
            proofs.append(dict(run=p.parent.relative_to(out).as_posix(),checkpoint=checkpoint,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    if not smoke:
        old=ROOT/'target/joint-rl-20261030-v2'
        assert json.loads((old/'manifest.json').read_text())['status']=='COMPLETE'
        verification=json.loads((old/'verification.json').read_text());assert verification['status']=='PASS'
        for seed in range(3):
            p=old/'models/PPO'/f'seed-{seed}'/'best_model.zip'
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            assert any(c['run']==f'models/PPO/seed-{seed}' and c['checkpoint']=='best' and c['sha256']==digest for c in verification['checkpoints'])
            policies.append((f'OLD_PPO_RR_s{seed}_best',Predictor(model=PPO.load(p,device='cpu'),legacy=True),0,None))
            proofs.append(dict(run=str(p.parent),checkpoint='best',sha256=digest,legacy=True))
    with ContactEnv() as env,MobileEnv() as fixed:
        # The shared evaluator uses the same test seeds2800000..9. These are now
        # development-used; no fresh-holdout claim. Validation1900000 is separate.
        return evaluate_with_envs(out,smoke,env,fixed,policy_override=policies,
                                  case_override=configs(smoke),proof_override=proofs)


def campaign(out,smoke):
    out.mkdir(parents=True,exist_ok=False);seeds=[0] if smoke else [0,1,2]
    manifest=dict(schema='contact-aware-ppo-v1',status='RUNNING',smoke=smoke,seeds=seeds,
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        observation_size=179,actions=108,steps_per_model=1024 if smoke else 32768,reward=REWARD,
        scenarios={n:asdict(c) for n,c in configs(smoke)},validation_seed=1900000,
        test_seeds=[2800000+i for i in range(1 if smoke else 10)],source_holdout=False,
        note='Development comparison on reused task seeds; one layout scaled to two areas; no optimality or novelty claim.',
        packages={p:importlib.metadata.version(p) for p in ('sb3-contrib','stable-baselines3','torch','numpy')})
    manifest['source_sha256']=snapshot(out);save_json(out/'manifest.json',manifest);start=time.monotonic()
    def launch(seed):
        command=[sys.executable,'-u','-m','drl.contact_campaign','worker','--output',str(out/'models'/f'seed-{seed}'),'--seed',str(seed)]
        if smoke:command.append('--smoke')
        with (out/f'seed-{seed}.log').open('w') as log:
            proc=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            receipt=dict(pid=proc.pid,command=command,started=time.time());save_json(out/f'seed-{seed}-process.json',receipt)
            code=proc.wait();receipt.update(exit_code=code,finished=time.time());save_json(out/f'seed-{seed}-process.json',receipt)
        assert code==0,f'Worker seed{seed} failed'
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(launch,seeds))
        proof=evaluate(out,smoke)
        proof['source_unchanged']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in manifest['source_sha256'].items())
        assert proof['source_unchanged'] and proof['traces']==(9 if smoke else 2560)
        save_json(out/'verification.json',proof)
        manifest.update(status='COMPLETE',episodes=proof['traces'],elapsed_s=time.monotonic()-start)
    except BaseException as exc:manifest.update(status='FAILED',error=repr(exc));raise
    finally:save_json(out/'manifest.json',manifest)
    print('CONTACT_PPO_COMPLETE_AND_VERIFIED',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['worker','campaign']);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=0);parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    if args.command=='worker':worker(args.output.resolve(),args.seed,args.smoke)
    else:campaign(args.output.resolve(),args.smoke)
