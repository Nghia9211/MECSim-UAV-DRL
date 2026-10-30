"""PPO policy selection at service boundaries; fixed RR mobility, causal shared kernel.

Action = 3*route + scheduler. The selected pair remains fixed until the next
service decision, including counterfactual queue forecasts. This is a policy
selector, not a learned per-task priority or learned trajectory.
"""
from dataclasses import asdict
import json
from pathlib import Path

import gymnasium as gym
import numpy as np

from .mobile_environment import MobileConfig, MobileEnv

ROUTES = ('DELIVERY_AWARE','DEADLINE_ENERGY','SHORTEST_FINISH')
SCHEDULES = ('EDF','SPT','FIFO')
REWARD = dict(delivered_on_time=2., images_seen=-1., background_misses=-.25, energy_j=-.1/10000)


def utility(info):
    return sum(v*info[k] for k,v in REWARD.items())


class JointEnv(MobileEnv):
    def __init__(self, config=None, *, random_scenarios=False):
        config=config or MobileConfig(control_mode='joint_policy',allowContactWait=True)
        if config.control_mode not in ('joint_policy','contact_policy'):
            raise ValueError('JointEnv requires joint_policy control mode')
        super().__init__(config)
        self.action_space=gym.spaces.Discrete(9)
        self.observation_space=gym.spaces.Box(0.,1.,shape=(143,),dtype=np.float32)
        self.random_scenarios=random_scenarios

    def _decode(self,result):
        c=self.config;last=result['info']['requested_action']
        if c.control_mode=='contact_policy' and last>=0:last%=9
        obs=np.asarray([*result['observation'],c.areaMetres/800,c.uavBatteryJ/1600000,c.imageRate/.24,
                        c.backgroundRate/.1,c.estimateError,*[float(last==i) for i in range(9)]],dtype=np.float32)
        if not self.observation_space.contains(obs):
            raise RuntimeError('Joint state outside declared space')
        return obs

    def reset(self, *, seed=None, options=None):
        # Scenario draws are independent of task generation; never infer layout from task seed.
        gym.Env.reset(self,seed=seed)
        if self.random_scenarios:
            c=self.config
            c.areaMetres=float(self.np_random.choice([250,800]))
            c.uavBatteryJ=float(self.np_random.choice([30000,1600000]))
            c.imageRate,c.backgroundRate=[(.08,.02),(.24,.1)][self.np_random.integers(2)]
            c.estimateError=float(self.np_random.choice([0.,.4]))
        obs,info=super().reset(seed=None,options=options)
        self._utility=utility(info)
        return obs,info

    def step(self,action):
        if self._done:raise RuntimeError('RESET required')
        if not self.action_space.contains(action):raise ValueError('Action must be 0..8')
        result=self._request(dict(cmd='step',action=int(action)))
        obs=self._decode(result);info=result['info'];value=utility(info);reward=value-self._utility
        info.update(delta_seconds=info['seconds']-self._info['seconds'],cumulative_utility=value)
        self._utility,self._info,self._observation=value,info,obs
        self._done=result['terminated'] or result['truncated']
        self._history.append(dict(action=int(action),reward=reward,observation=obs.tolist(),info=info.copy()))
        return obs.copy(),reward,result['terminated'],result['truncated'],info.copy()

    def save_trace(self,directory):
        super().save_trace(directory)
        path=Path(directory)/'environment.json'
        value=json.loads(path.read_text())
        value.update(reward=REWARD,action_routes=ROUTES,action_schedules=SCHEDULES,
                     extra_features=['area','initial_battery','image_rate','background_rate','estimate_error','previous_mode_onehot_9'])
        path.write_text(json.dumps(value,indent=2),encoding='utf-8')
