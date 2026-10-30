"""Contact-aware joint service/policy selection. No new simulator physics."""
import math
import json
from pathlib import Path
import gymnasium as gym
import numpy as np
from .joint_environment import JointEnv
from .mobile_environment import MobileConfig


def contact_features(raw,cfg):
    ds=np.asarray(raw[9:129]).reshape(12,10)
    extra=[]
    for site in ds:
        seconds=math.hypot(site[0]-raw[1],site[1]-raw[2])*cfg.areaMetres/5
        neighbours=sum(d[5]>.5 and d[4]<.5 and
            math.hypot(math.hypot(site[0]-d[0],site[1]-d[1])*cfg.areaMetres,10)<=65+1e-8 for d in ds)
        extra.extend([min(1.,seconds/cfg.horizonSeconds),
                      min(1.,150*seconds/max(1e-9,raw[3]*cfg.uavBatteryJ)),neighbours/12])
    return extra


def masks(observation):
    return np.repeat(np.asarray(observation)[9:129].reshape(12,10)[:,5]>.5,9)


class ContactEnv(JointEnv):
    def __init__(self,config=None,**kwargs):
        config=config or MobileConfig(control_mode='contact_policy',allowContactWait=True)
        if config.control_mode!='contact_policy':raise ValueError('Expected contact_policy mode')
        super().__init__(config,**kwargs)
        self.action_space=gym.spaces.Discrete(108)
        self.observation_space=gym.spaces.Box(0.,1.,shape=(179,),dtype=np.float32)

    def _decode(self,result):
        # Parent validates against its declared shape, so build the shared state
        # explicitly here rather than changing the space during a reset.
        c=self.config;last=result['info']['requested_action'];mode=last%9 if last>=0 else -1
        raw=result['observation']
        obs=np.asarray([*raw,c.areaMetres/800,c.uavBatteryJ/1600000,c.imageRate/.24,
                        c.backgroundRate/.1,c.estimateError,*[float(mode==i) for i in range(9)],
                        *contact_features(raw,c)],dtype=np.float32)
        if not self.observation_space.contains(obs):raise RuntimeError('Invalid contact state')
        return obs

    def action_masks(self):return masks(self._observation)

    def step(self,action):
        if not self.action_space.contains(action) or not self.action_masks()[int(action)]:
            raise ValueError('Invalid/masked contact action')
        return super().step(action)

    def save_trace(self,directory):
        super().save_trace(directory)
        p=Path(directory)/'environment.json';meta=json.loads(p.read_text())
        meta.update(action='9*target + 3*route + scheduler',observation_size=179,
                    candidate_features=['travel_time/horizon','flight_energy/remaining_battery clipped',
                                        'reachable_live_disconnected_devices/12'],
                    action_mask='only live destination devices; no deadline or connectivity oracle')
        p.write_text(json.dumps(meta,indent=2),encoding='utf-8')


def heuristic(name,obs,info):
    ds=np.asarray(obs[9:129]).reshape(12,10)
    order=[(info['previous_target']+k)%12 for k in range(1,13)]
    live=[d for d in order if ds[d,5]>.5]
    disconnected=[d for d in live if ds[d,4]<.5]
    if name=='RR':target=live[0]
    elif name=='DISCONNECTED_RR':target=(disconnected or live)[0]
    elif name=='CONTACT_GREEDY':
        candidates=np.asarray(obs[143:]).reshape(12,3)
        # Coverage per travel+dwell time; all quantities are already observable.
        target=max(live,key=lambda d:candidates[d,2]/(candidates[d,0]+30/600))
    else:raise ValueError(name)
    return target*9  # DELIVERY_AWARE + EDF, shared with the learned action space.
