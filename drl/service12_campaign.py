"""Twelve-target PPO, fixed DA/RISK_EDF, disjoint layout splits."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import gymnasium as gym
from sb3_contrib import MaskablePPO
from .contact_environment import ContactEnv,masks,heuristic
from .mobile_environment import MobileConfig,MobileEnv
from .contact_campaign import Predictor,rollout
from .joint_campaign import scenarios,parameters,evaluate_with_envs
from .mobile_run import save_json,snapshot
from .run import write_csv
from stable_baselines3.common.callbacks import BaseCallback
import torch,subprocess,sys,time,hashlib
from concurrent.futures import ThreadPoolExecutor

TRAIN_LAYOUTS=list(range(100,132))
VALID_LAYOUTS=[200,201]
TEST_LAYOUTS=[300,301,302,303]

def config():return MobileConfig(control_mode='service_only',offloading='DELIVERY_AWARE',scheduler='RISK_EDF',allowContactWait=True)

class ServiceEnv(ContactEnv):
    def __init__(self,training=False):
        super().__init__(config(),random_scenarios=training)
        self.action_space=gym.spaces.Discrete(12);self.training=training
    def reset(self,*,seed=None,options=None):
        gym.Env.reset(self,seed=seed)
        options=dict(options or {})
        if self.training:options['layout_seed']=int(self.np_random.choice(TRAIN_LAYOUTS))
        return super().reset(seed=None,options=options)
    def action_masks(self):return masks(self._observation)[::9]
    def step(self,action):
        if not self.action_space.contains(action) or not self.action_masks()[int(action)]:raise ValueError('Invalid target')
        # JointEnv handles transport/history; saved trace actions use canonical9*target.
        from .joint_environment import JointEnv
        original=self.action_space
        self.action_space=gym.spaces.Discrete(108)
        try:return JointEnv.step(self,int(action)*9)
        finally:self.action_space=original

class ModelAdapter:
    def __init__(self,model):self.model=model
    def predict(self,obs,deterministic=True):
        a,_=self.model.predict(obs,deterministic=True,action_masks=masks(obs)[::9])
        return np.int64(int(a)*9),None

class Validate(BaseCallback):
    def __init__(self,out,smoke):
        super().__init__();self.out=out;self.smoke=smoke;self.rows=[];self.best=-float('inf');self.env=ContactEnv(config())
    def evaluate(self):
        scores=[]
        cases=list(scenarios().values())[:1] if self.smoke else list(scenarios().values())
        for c in cases:
            for layout in VALID_LAYOUTS[:1] if self.smoke else VALID_LAYOUTS:
                c=MobileConfig(**asdict(c));c.control_mode='service_only';c.scheduler='RISK_EDF';c.layout_seed=layout
                self.env.config=c
                for task in [1950000] if self.smoke else [1950000,1950001,1950002]:
                    scores.append(rollout(self.env,ModelAdapter(self.model),task))
        reward=float(np.mean(scores));self.rows.append(dict(steps=self.num_timesteps,reward=reward,cases=len(scores)))
        write_csv(self.out/'validation.csv',self.rows)
        if self.model._n_updates>0 and reward>self.best:
            self.best=reward;self.model.save(self.out/'best_model')
        print(f'steps={self.num_timesteps} validation={reward:.5f}',flush=True)
    def _on_step(self):
        if self.n_calls%(512 if self.smoke else 8192)==0:self.evaluate()
        return True
    def _on_training_end(self):self.evaluate()

def worker(out,seed,smoke):
    out.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    steps=1024 if smoke else 32768;v=Validate(out,smoke)
    cfg=dict(status='RUNNING',steps=steps,seed=seed,train_layouts=TRAIN_LAYOUTS,validation_layouts=VALID_LAYOUTS,actions=12)
    save_json(out/'config.json',cfg)
    try:
        with ServiceEnv(training=True) as env:
            model=MaskablePPO('MlpPolicy',env,seed=seed,device='cpu',**parameters('PPO'))
            model.learn(steps,callback=v);model.save(out/'final_model')
            assert model.num_timesteps==steps and (out/'best_model.zip').exists()
            cfg.update(status='COMPLETE',actual_steps=model.num_timesteps)
    except BaseException as e:cfg.update(status='FAILED',error=repr(e));raise
    finally:v.env.close();save_json(out/'config.json',cfg)

def campaign(out,smoke):
    out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    manifest=dict(status='RUNNING',schema='service12-v1',smoke=smoke,train_layouts=TRAIN_LAYOUTS,
        validation_layouts=VALID_LAYOUTS,test_layouts=TEST_LAYOUTS,validation_tasks=[1950000,1950001,1950002],
        note='Fixed DA/RISK_EDF; reward unchanged; test tasks reused but layouts held out; no raw-source holdout',
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_sha256=snapshot(out))
    save_json(out/'manifest.json',manifest)
    def launch(seed):
        cmd=[sys.executable,'-u','-m','drl.service12_campaign','worker','--output',str(out/'models'/f'seed-{seed}'),'--seed',str(seed)]
        if smoke:cmd+=['--smoke']
        with (out/f'seed-{seed}.log').open('w') as log:
            p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
            save_json(out/f'seed-{seed}-process.json',dict(pid=p.pid,command=cmd))
            assert p.wait()==0,'Training worker failed'
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(launch,[0] if smoke else [0,1,2]))
        policies=[(n,Predictor(name=n),0,None) for n in ['RR','DISCONNECTED_RR','CONTACT_GREEDY']]
        proofs=[]
        for seed in [0] if smoke else [0,1,2]:
            for cp in ['best','final']:
                path=out/'models'/f'seed-{seed}'/(cp+'_model.zip')
                policies.append((f'PPO12_s{seed}_{cp}',ModelAdapter(MaskablePPO.load(path,device='cpu')),0,None))
                proofs.append(dict(run=str(path.parent),checkpoint=cp,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        cases=[]
        for layout in TEST_LAYOUTS[:1] if smoke else TEST_LAYOUTS:
            for name,c in list(scenarios().items())[:1] if smoke else scenarios().items():
                c.control_mode='service_only';c.scheduler='RISK_EDF';c.layout_seed=layout
                cases.append((f'l{layout}-'+name,c))
        with ContactEnv(config()) as env,MobileEnv() as fixed:
            proof=evaluate_with_envs(out,smoke,env,fixed,policy_override=policies,case_override=cases,proof_override=proofs)
        assert proof['traces']==(5 if smoke else 5760)
        proof['source_unchanged']=all(hashlib.sha256((Path(p)).read_bytes()).hexdigest()==h for p,h in manifest['source_sha256'].items())
        assert proof['source_unchanged'];save_json(out/'verification.json',proof)
        manifest.update(status='COMPLETE',episodes=proof['traces'],elapsed_s=time.monotonic()-start)
    except BaseException as e:manifest.update(status='FAILED',error=repr(e));raise
    finally:save_json(out/'manifest.json',manifest)
    print('SERVICE12_COMPLETE_AND_VERIFIED',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,default=0);p.add_argument('--smoke',action='store_true');a=p.parse_args()
    (worker(a.output.resolve(),a.seed,a.smoke) if a.command=='worker' else campaign(a.output.resolve(),a.smoke))
