"""Read-only trace diagnosis; writes derived evidence only under target/."""
import csv,json,re,math
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'target/paper-convention-retrain-20261024'
OUT=ROOT/'target/local-completion-diagnosis';OUT.mkdir(exist_ok=True)
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
rows=[r for r in read(BASE/'episodes.csv') if r['profile']=='LOCAL_COMPLETION']
layout=read(BASE/rows[0]['trace']/'layout.csv')
source=(BASE/'source/PureEdgeSim/uav/PaperParameters.java').read_text()
rates=[list(map(float,x.split(','))) for x in re.findall(r'\{([\d., ]+)\}',source.split('BYTES_PER_SECOND =')[1].split('};')[0])]
hw=['RASPBERRY_PI_4B','RASPBERRY_PI_3B','FIREFLY','JETSON_NANO','NANOPC_T4'];tasks=['HAAR','MMOD','DNN','DLIB','YOLOV3']
capacity=[]
for d in layout:
 rate=rates[tasks.index(d['vision_task'])][hw.index(d['hardware'])]
 capacity.append(dict(device=int(d['device']),connected=d['connected'],rate=rate,min_local_s=2e6/rate,max_local_s=4e6/rate,prob_complete_600=max(0,min(1,(600*rate-2e6)/2e6))))
groups={};examples={};checks=Counter()
for key in sorted(set((r['policy'],r['checkpoint'],r['training_seed']) for r in rows)):
 subset=[r for r in rows if (r['policy'],r['checkpoint'],r['training_seed'])==key]
 actions=Counter();fail=Counter();served=Counter();preoldest=0;total=0;rewards=[];surplus=[]
 for r in subset:
  trace=BASE/r['trace'];slots=read(trace/'slots.csv');dev=read(trace/'devices.csv');previous=[0]*12
  byslot=defaultdict(list)
  for d in dev:byslot[int(d['slot'])].append(d)
  for s in slots:
   a=int(s['action']);actions[a]+=1;total+=1;preoldest+=previous[a]==max(previous)
   expected_reward=int(s['slot'])+math.log(max(1e-6,previous[a])/max(1e-6,max(previous)))
   assert abs(expected_reward-float(s['reward']))<1e-7,(trace,s['slot'],'reward')
   checks['slot_rewards']+=1
   rewards.append(float(s['reward']))
   for d in byslot[int(s['slot'])]:
    i=int(d['device']);delivered=d['offload_completed']=='true' or (d['offload_candidate']=='false' and d['connected']=='true' and float(d['input_bytes'])/capacity[i]['rate']<=float(s['duration_s'])+1e-9)
    expected_age=0 if delivered else previous[i]+1
    assert int(d['data_age'])==expected_age,(trace,s['slot'],i,'age')
    previous[i]=int(d['data_age']);served[i]+=d['offload_completed']=='true';checks['device_age_transitions']+=1
   expected_fail={f'DEVICE_{i}_DATA_AGE' for i,age in enumerate(previous) if age>=10}
   actual_fail={f for f in s['reason'].split('|') if f.endswith('_DATA_AGE')}
   assert expected_fail==actual_fail,(trace,s['slot'],'termination')
   checks['age_termination_checks']+=1
  fail.update(r['reason'].split('|'));surplus.append(float(r['uav_battery_j']))
 groups['/'.join(key)]=dict(episodes=len(subset),mean_slots=sum(int(r['slots']) for r in subset)/len(subset),actions=dict(actions),terminal_reasons=dict(fail),offloads_per_device=dict(served),selected_oldest_fraction=preoldest/total,mean_step_reward=sum(rewards)/len(rewards),mean_remaining_uav_j=sum(surplus)/len(surplus))
 if key[0]=='DQN' and key[1] in ('best','final'):
  r=subset[0];examples['/'.join(key)]=dict(task=r['task_seed'],slots=read(BASE/r['trace']/'slots.csv'),terminal_devices=[d for d in read(BASE/r['trace']/'devices.csv') if int(d['slot'])==int(r['slots'])])
result=dict(local_capacity=capacity,groups=groups,examples=examples,trace_episodes=len(rows),verification=dict(checks))
(OUT/'evidence.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(dict(capacity=capacity,groups=groups),indent=2))
