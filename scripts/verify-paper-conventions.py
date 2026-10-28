"""Independent synthetic-paper replay and published-parameter audit. Python standard library only."""
import ast
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys


def check(ok,message):
    if not ok:raise AssertionError(message)


def close(a,b,label):
    check(math.isclose(float(a),float(b),rel_tol=2e-8,abs_tol=3e-5),f'{label}: {a} != {b}')


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


class JavaRandom:
    def __init__(self,seed):self.seed=(seed^0x5DEECE66D)&((1<<48)-1)
    def bits(self,n):
        self.seed=(self.seed*0x5DEECE66D+11)&((1<<48)-1)
        return self.seed>>(48-n)
    def double(self):return ((self.bits(26)<<27)+self.bits(27))/(1<<53)
    def integer(self,bound):
        if bound&(bound-1)==0:return (bound*self.bits(31))>>31
        while True:
            bits=self.bits(31);value=bits%bound
            if (bits-value+bound-1)&0xffffffff<0x80000000:return value


def verify_parameters(root,m):
    text=(root/'source/paper/2501.15305v1.md').read_text(encoding='utf-8');c=m['constants']
    # These values have explicit Table 1 / Section 5 locators; no invented radio normalization.
    expected={'devices':12,'area_m':800,'altitude_m':10,'speed_mps':5,'flight_w':150,'hover_w':80,'uav_battery_j':1600000,
              'range_m':65,'min_battery_j':50000,'max_battery_j':80000,'min_task_bytes':2000000,'max_task_bytes':4000000,
              'slot_cap_s':600,'bandwidth_hz':20000000,'transmit_w':.1,'age_limit':10}
    for k,v in expected.items():close(c[k],v,'Published constant '+k)
    names=['RASPBERRY_PI_4B','RASPBERRY_PI_3B','FIREFLY','JETSON_NANO','NANOPC_T4']
    tasks={'HAAR':'HAAR','MMOD':'MMOD','DNN':'DNN','Dlib':'DLIB','YOLOv3':'YOLOV3'}
    standby=re.search(r'Standby power.*?\[([\d., ]+)\]',text)
    check(standby,'Standby table missing')
    for h,v in zip(names,standby.group(1).split(',')):close(c['hardware'][h]['standby_w'],v,'Standby '+h)
    for label,key,table in [('Table 2. Power','active_w',2),('Table 3. Data processing','bytes_per_s',3)]:
        section=text.split(label,1)[1].split('Table '+str(table+1)+'.',1)[0] if table==2 else text.split(label,1)[1].split('5 RESULTS',1)[0]
        for printed,task in tasks.items():
            match=re.search(r'^'+printed+r' ((?:[\d.]+ ?){5})$',section,re.M)
            check(match,'Table row missing '+printed)
            values=match.group(1).split();check(len(values)==5,'Table width')
            for h,v in zip(names,values):close(c['hardware'][h][key][task],v,f'{label} {h} {task}')
    tree=ast.parse((root/'source/drl/run.py').read_text(encoding='utf-8'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='model_options')
    common=next(n.value for n in fn.body if isinstance(n,ast.Assign))
    kw={k.arg:k.value for k in common.keywords}
    close(ast.literal_eval(kw['gamma']),.98,'Table4 gamma')
    policy={k.arg:k.value for k in kw['policy_kwargs'].keywords}
    check(ast.literal_eval(policy['net_arch'])==[64,64] and ast.unparse(policy['activation_fn'])=='torch.nn.ReLU','Q architecture')
    ret=next(n.value for n in ast.walk(fn) if isinstance(n,ast.Return) and isinstance(n.value,ast.Call) and any(k.arg=='exploration_fraction' for k in n.value.keywords))
    params={k.arg:k.value for k in ret.keywords if k.arg}
    for k,v in {'learning_rate':.0071,'batch_size':16,'exploration_initial_eps':1.,'exploration_final_eps':.05,'exploration_fraction':.35}.items():
        close(ast.literal_eval(params[k]),v,'Table4 '+k)
    check('1,000,000' in text and 'Learning iterations' in text,'Published budget locator')
    return dict(status='PASS',table1_and_geometry_constants=len(expected),table2_entries=25,table3_entries=25,
                standby_entries=5,dqn_published_parameters=True,
                note='Static source/parameter audit and replay; no DQN has been trained by this benchmark.')


def replay(root,row,m,counting=None,*,layout_override=None,expected_actions=None):
    c=m['constants'];profile=m['profiles'][row['profile']];n=c['devices'];cap=c['slot_cap_s']
    directory=root/row['trace'];layout=layout_override if layout_override is not None else json.loads((directory.parent/'layout.json').read_text())
    check(json.loads((directory/'conventions.json').read_text())==profile,'Recorded conventions')
    slots=read(directory/'slots.csv');device_rows=read(directory/'devices.csv')
    check(len(slots)==int(row['slots']) and len(device_rows)==len(slots)*n,'Trace lengths')
    if expected_actions is not None:check(len(expected_actions)==len(slots),'Expected action count')
    by_slot={i:{} for i in range(1,len(slots)+1)}
    for d in device_rows:
        k,i=int(d['slot']),int(d['device']);check(i not in by_slot[k],'Duplicate device row');by_slot[k][i]=d
    task=JavaRandom(int(row['task_seed']));policy_rng=JavaRandom(int(row['seed'])+2);next_id=0
    battery=[d['capacity_j'] for d in layout];ages=[0]*n;x=y=time=reward_sum=ground_energy=0.;uav_j=c['uav_battery_j'];cap_slots=cap_items=full_slots=0
    for k,slot in enumerate(slots,1):
        check(set(by_slot[k])==set(range(n)),'Device IDs')
        check(int(slot['slot'])==k,'Slot indexing')
        a=int(slot['action']);check(0<=a<n,'Action range')
        order=[(next_id+i)%n for i in range(n)]
        chosen=expected_actions[k-1] if expected_actions is not None else next_id if row['policy']=='ROUND_ROBIN' else max(order,key=lambda d:ages[d]) if row['policy']=='OLDEST_DATA' else policy_rng.integer(n)
        check(a==chosen,'Independent policy action');next_id=(chosen+1)%n
        before=ages.copy();dx,dy=layout[a]['x'],layout[a]['y'];flight=math.hypot(x-dx,y-dy)/c['speed_mps']
        duration=min(flight,cap);work=[];local=[];coverage=[];starts=[];active=[];powers=[];upload=[];standby=[]
        for i,d in enumerate(layout):
            h=c['hardware'][d['hardware']];s=by_slot[k][i]
            w=c['min_task_bytes']+task.double()*(c['max_task_bytes']-c['min_task_bytes']);work.append(w)
            close(s['input_bytes'],w,'Task RNG/uniform bytes')
            check((s['powered']=='true')==d['powered'] and (s['connected']=='true')==d['connected'],'Availability')
            distance=math.sqrt((dx-d['x'])**2+(dy-d['y'])**2+c['altitude_m']**2)
            covered=distance<=c['range_m'];coverage.append(covered)
            check((s['offload_candidate']=='true')==covered,'Slant coverage')
            gain=(1e-8 if profile['radio']=='LITERAL_DBM' else 1e-5)*distance**-4
            rate=c['bandwidth_hz']*math.log1p(c['transmit_w']*gain/1e-13)/math.log(2)
            upload.append(w*8/rate);local.append(w/h['bytes_per_s'][d['task']]);starts.append(flight if covered else 0)
            requested=upload[-1] if covered else local[-1];active.append(min(requested,max(0,cap-starts[-1])))
            cap_items+=active[-1]<requested;powers.append(c['transmit_w'] if covered else h['active_w'][d['task']]);standby.append(h['standby_w'])
            duration=min(cap,max(duration,starts[-1]+active[-1]))
        planned_duration=duration
        available=uav_j/c['flight_w'] if uav_j<=flight*c['flight_w'] else flight+(uav_j-flight*c['flight_w'])/c['hover_w']
        duration=min(duration,available)
        for i,d in enumerate(layout):
            if d['powered']:continue
            remaining=battery[i];idle=standby[i];start=starts[i];busy=idle+powers[i]
            if remaining<=idle*start:empty=remaining/idle
            else:
                remaining-=idle*start
                empty=start+remaining/busy if remaining<=busy*active[i] else start+active[i]+(remaining-busy*active[i])/idle
            duration=min(duration,empty)
        full_slots+=duration>=planned_duration-1e-8
        close(slot['start_s'],time,'Slot start');time+=duration
        close(slot['duration_s'],duration,'Slot duration');close(slot['end_s'],time,'Slot end')
        ratio=min(1,duration/flight) if flight else 1;x+=(dx-x)*ratio;y+=(dy-y)*ratio
        spent=c['flight_w']*min(duration,flight)+c['hover_w']*max(0,duration-flight);uav_j=max(0,uav_j-spent)
        close(slot['x_m'],x,'UAV x');close(slot['y_m'],y,'UAV y');close(slot['h_m'],c['altitude_m'],'UAV altitude');close(slot['uav_battery_j'],uav_j,'UAV energy')
        completed=0;fail=[]
        for i,d in enumerate(layout):
            s=by_slot[k][i];used=standby[i]*duration+powers[i]*max(0,min(active[i],duration-starts[i]));ground_energy+=used
            if not d['powered']:battery[i]=max(0,battery[i]-used)
            served=coverage[i] and duration+1e-9>=flight+upload[i];completed+=served
            check((s['offload_completed']=='true')==served,'Completed upload')
            delivered=d['connected'] or served
            if profile['delivery']=='COMPLETED':delivered=served or (not coverage[i] and d['connected'] and local[i]<=duration+1e-9)
            elif profile['delivery']=='ARRIVED':delivered=d['connected'] or (coverage[i] and duration+1e-9>=flight)
            ages[i]=0 if delivered else ages[i]+1
            close(s['energy_used_j'],used,'Ground energy');close(s['battery_j'],battery[i],'Ground battery');check(int(s['data_age'])==ages[i],'Data age')
            if battery[i]<=1e-6:fail.append(f'DEVICE_{i}_BATTERY')
            if ages[i]>=c['age_limit'] if profile['expiry']=='AT_LIMIT' else ages[i]>c['age_limit']:fail.append(f'DEVICE_{i}_DATA_AGE')
        if uav_j<=1e-6:fail.append('UAV_BATTERY')
        truncated=not fail and k>=m['max_slots'];reason='|'.join(fail) if fail else 'SLOT_SAFETY_LIMIT' if truncated else 'RUNNING'
        check(slot['reason']==reason and (slot['terminated']=='true')==bool(fail) and (slot['truncated']=='true')==truncated,'Failure semantics')
        check(not (fail or truncated) or k==len(slots),'Continued after terminal')
        snapshot=before if profile['reward_snapshot']=='BEFORE' else ages;eps=profile['reward_epsilon']
        reward=k+math.log(max(eps,snapshot[a])/max(eps,max(snapshot)));reward_sum+=reward
        close(slot['reward'],reward,'Reward');check(int(slot['completed_offloads'])==completed,'Upload count')
        close(slot['min_device_battery_fraction'],min(b/d['capacity_j'] for b,d in zip(battery,layout)),'Min battery')
        check(int(slot['max_data_age'])==max(ages),'Max age');cap_slots+=duration>=cap-1e-6
    check(slots[-1]['reason']!='RUNNING','Unfinished episode')
    for key,v in [('seconds',time),('reward',reward_sum),('uav_energy_j',c['uav_battery_j']-uav_j),('ground_energy_j',ground_energy)]:close(row[key],v,'Episode '+key)
    check(int(row['cap_slots'])==cap_slots and int(row['capped_items'])==cap_items,'Cap counts')
    check(row['reason']==slots[-1]['reason'] and row['truncated']==slots[-1]['truncated'],'Episode termination')
    if counting is not None:counting.append(dict(profile=row['profile'],scenario=row['scenario'],seed=row['seed'],policy=row['policy'],
                                                attempted_slots=len(slots),fully_elapsed_slots=full_slots,partial_final_slot=len(slots)-full_slots))
    return len(device_rows)


def verify(root):
    m=json.loads((root/'manifest.json').read_text());check(m['schema']=='paper-convention-audit-v1' and m['status']=='COMPLETE','Incomplete run')
    for f,h in m['source_sha256'].items():check(hashlib.sha256((root/'source'/f).read_bytes()).hexdigest()==h,'Snapshot hash '+f)
    params=verify_parameters(root,m)
    rows=read(root/'episodes.csv');expected=m['seeds']*len(m['profiles'])*len(m['scenarios'])*len(m['policies'])
    check(len(rows)==m['episodes']==expected,'Episode count')
    keys=set();groups={};references={};total=0;counting=[]
    for r in rows:
        profile,sc,seed,policy=r['profile'],r['scenario'],int(r['seed']),r['policy']
        check(profile in m['profiles'] and sc in m['scenarios'] and policy in m['policies'] and m['first_seed']<=seed<m['first_seed']+m['seeds'],'Case range')
        key=profile,sc,seed,policy;check(key not in keys,'Duplicate episode');keys.add(key)
        check(int(r['task_seed'])==seed+1 and r['trace']==f'{sc}/seed-{seed}/{profile}-{policy}','Pairing')
        total+=replay(root,r,m,counting);groups.setdefault((profile,sc,policy),[]).append(r)
        if profile=='REFERENCE':references[sc,seed,policy]=r
    summaries=[]
    for (profile,sc,policy),group in sorted(groups.items()):
        check(len(group)==m['seeds'],'Missing group seed')
        vals=[int(r['slots']) for r in group];deltas=[int(r['slots'])-int(references[sc,int(r['seed']),policy]['slots']) for r in group]
        summaries.append(dict(profile=profile,scenario=sc,policy=policy,seeds=len(group),mean_slots=statistics.mean(vals),sd_slots=statistics.stdev(vals) if len(vals)>1 else 0,
                              mean_seconds=statistics.mean(float(r['seconds']) for r in group),mean_reward=statistics.mean(float(r['reward']) for r in group),
                              mean_paired_slot_delta=statistics.mean(deltas),changed_lifetimes=sum(d!=0 for d in deltas),truncated=sum(r['truncated']=='true' for r in group)))
    with (root/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=summaries[0]);w.writeheader();w.writerows(summaries)
    with (root/'slot-counting.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=counting[0]);w.writeheader();w.writerows(counting)
    result=dict(status='PASS',episodes=len(rows),device_slot_rows=total,parameter_audit=params,
                checks=['source hashes','published tables and DQN static parameters','independent Java RNG task draws and policies',
                        'slant channel and capped durations','flight/hover and standby/active energy','battery/depletion and positions',
                        'freshness/expiry and reward timing','per-case metrics and paired summaries'],
                dqn_trained=False,paper_results_reproduced=False,backlog_sensitivity=False,output_link_calibrated=False)
    (root/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result


if __name__=='__main__':
    check(len(sys.argv)==2,'Usage: python scripts/verify-paper-conventions.py RUN_DIR')
    print(json.dumps(verify(Path(sys.argv[1])),indent=2))
