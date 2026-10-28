"""Independent stdlib counterfactual and action replay, plus shared physical trace audit."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

spec=importlib.util.spec_from_file_location('physical',Path(__file__).with_name('verify-uav-offloading.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
E=1e-8
def better(x,y):
    return y is None or x['value']>y['value']+E or abs(x['value']-y['value'])<=E and (
        x['energyJ']<y['energyJ']-E or abs(x['energyJ']-y['energyJ'])<=E and x['weightedLatency']<y['weightedLatency']-E)
def choose(s):
    ready=sorted((j for j in s['jobs'] if j['air'] and j['phase']=='WAITING' and j['ready']<=s['now']+E and j['deadline']>s['now']+E),key=lambda j:(j['ready'],j['arrival'],j['id']))
    best=None;selected=None
    for j in ready:
        r=project(s,False,j['id'])
        if better(r,best):best=r;selected=j['id']
    assert selected is not None
    return selected
original_select=a.select
def scalar_select(ready,now,battery,mips,cpu,idle,horizon,name,alpha):
    if name!='QIOS':return original_select(ready,now,battery,mips,cpu,idle,horizon,name,alpha)
    # Independent replay of the original READY-only scalar scheduler used inside
    # the legacy candidate forecast (not the full context-aware kernel dispatch).
    nodes=[dict(id=-1,mips=mips,idleW=idle,cpuW=cpu,txW=0,batteryJ=battery,alive=True),
           dict(id=0,mips=1,idleW=0,cpuW=0,txW=0,batteryJ=1,alive=True)]
    jobs=[dict(id=t[0],device=-1 if t[1]=='ALIBABA' else 0,air=True,background=t[1]=='ALIBABA',arrival=t[2],ready=t[3],
               deadline=t[4],priority=t[5],estimatedRemainingMi=t[6],phase='WAITING',connected=True) for t in ready]
    return choose(dict(now=now,horizon=horizon,nodes=nodes,jobs=jobs))
a.select=scalar_select
def project(snapshot,lookahead=True,forced=None):
    s=copy.deepcopy(snapshot);now=s['now'];nodes={n['id']:n for n in s['nodes']};jobs=s['jobs'];energy=0
    for j in jobs:j.update(left=j['estimatedRemainingMi'],executed=0.,status=None,finish=None)
    def node(j):return -1 if j['air'] else j['device']
    def snap():
        return dict(now=now,horizon=s['horizon'],nodes=list(nodes.values()),jobs=[dict(j,estimatedRemainingMi=max(1e-6,j['left'])) for j in jobs if j['status'] is None])
    while True:
        for j in jobs:
            if j['status'] is None and j['phase']=='RUNNING' and j['left']<=E:
                j.update(status='COMPLETED_ON_TIME' if now<=j['deadline']+E else 'COMPLETED_LATE',finish=now)
            if j['status'] is None and j['phase']=='TRANSFERRING' and j['ready']<=now+E:j['phase']='WAITING'
            if j['status'] is None and j['phase']!='RUNNING' and j['deadline']<=now+E:j.update(status='EXPIRED_WAITING',finish=now)
        for n in nodes.values():
            if n['batteryJ']<=1e-6:n['alive']=False
        for j in jobs:
            if j['status'] is not None:continue
            if j['air'] and not nodes[-1]['alive']:j.update(status='DROPPED_UAV_BATTERY',finish=now)
            elif not j['background'] and not nodes[j['device']]['alive'] and (not j['air'] or j['phase']=='TRANSFERRING'):j.update(status='DROPPED_DEVICE_BATTERY',finish=now)
        if now>=s['horizon']-E:
            for j in jobs:
                if j['status'] is None:j.update(status='UNFINISHED_HORIZON',finish=s['horizon'])
            break
        for nid,n in nodes.items():
            if not n['alive'] or any(j['status'] is None and j['phase']=='RUNNING' and node(j)==nid for j in jobs):continue
            ready=[j for j in jobs if j['status'] is None and j['phase']=='WAITING' and node(j)==nid]
            if not ready:continue
            if nid==-1 and forced is not None:tid=forced;forced=None
            elif nid==-1 and lookahead:tid=choose(snap())
            else:tid=min(ready,key=lambda j:((j['deadline'],) if nid==-1 else ())+ (j['ready'],j['arrival'],j['id']))['id']
            selected=next(j for j in ready if j['id']==tid);selected['phase']='RUNNING'
        next_time=s['horizon'];power={}
        for nid,n in nodes.items():
            if not n['alive']:continue
            running=next((j for j in jobs if j['status'] is None and j['phase']=='RUNNING' and node(j)==nid),None)
            tx=sum(j['status'] is None and j['phase']=='TRANSFERRING' and j['device']==nid for j in jobs)
            power[nid]=n['idleW']+(n['cpuW'] if running else 0)+tx*n['txW']
            if power[nid]>0:next_time=min(next_time,now+n['batteryJ']/power[nid])
            if running:next_time=min(next_time,now+running['left']/n['mips'])
        for j in jobs:
            if j['status'] is None:
                if j['phase']=='TRANSFERRING':next_time=min(next_time,j['ready'])
                if j['deadline']>now+E:next_time=min(next_time,j['deadline'])
        assert next_time>now
        dt=next_time-now
        for nid,n in nodes.items():
            if not n['alive']:continue
            spent=min(n['batteryJ'],dt*power[nid]);n['batteryJ']=max(0,n['batteryJ']-spent);energy+=spent
            for j in jobs:
                if j['status'] is None and j['phase']=='RUNNING' and node(j)==nid:
                    work=min(j['left'],n['mips']*dt);j['left']-=work;j['executed']+=work
        now=next_time
    value=latency=0;out=[]
    for j in jobs:
        delivered=j['status']=='COMPLETED_ON_TIME' and (j['air'] or j['connected'])
        if delivered:
            weight=1 if j['background'] else max(1,j['priority']);value+=weight;latency+=weight*(j['finish']-j['arrival'])
        out.append(dict(id=j['id'],status=j['status'],finish=j['finish'],executedMi=j['executed'],delivered=delivered))
    return dict(value=value,energyJ=energy,weightedLatency=latency,outcomes=out)
def snapshot(audit,now,candidate=None,air=False):
    nodes=[]
    for nid,c in audit.nodes.items():
        nodes.append(dict(id=nid,mips=c['mips'],idleW=c['idleWatts'],cpuW=c['cpuWatts'],txW=c['txWatts'],batteryJ=audit.battery_at(nid,now),alive=audit.alive(nid,now)))
    jobs=[]
    for tid,j in audit.jobs.items():
        o=audit.o[tid]
        if tid==candidate:continue
        arrival=a.num(j,'arrival_s');start=a.num(o,'start_s');finish=a.num(o,'resolved_s')
        admitted=(arrival,tid)<(now,candidate) if candidate is not None else arrival<=now+E
        if not admitted or finish<=now+E or o['route']=='UNDECIDED':continue
        running=math.isfinite(start) and (start<now-E if candidate is not None else start<now-E)
        ready=a.num(o,'ready_s')
        executed=max(0,now-start)*audit.nodes[audit.node(tid)]['mips'] if running else 0
        jobs.append(dict(id=tid,device=int(j['device']),air=o['route']!='LOCAL',background=j['source']=='ALIBABA',arrival=arrival,ready=ready,
            deadline=a.num(j,'deadline_s'),priority=int(j['priority']),estimatedRemainingMi=max(1e-6,a.num(j,'estimated_mi')-executed),
            phase='RUNNING' if running else 'TRANSFERRING' if ready>now+E else 'WAITING',connected=True))
    jobs.sort(key=lambda j:(j['arrival'],j['id']))
    if candidate is not None:
        j=audit.jobs[candidate];ready=a.num(j,'upload_ready_s') if air else now
        jobs.append(dict(id=candidate,device=int(j['device']),air=air,background=False,arrival=a.num(j,'arrival_s'),ready=ready,
            deadline=a.num(j,'deadline_s'),priority=int(j['priority']),estimatedRemainingMi=a.num(j,'estimated_mi'),phase='TRANSFERRING' if ready>now else 'WAITING',connected=True))
    return dict(now=now,horizon=audit.horizon,nodes=nodes,jobs=jobs)
def compare(x,y):
    if isinstance(x,dict):
        assert set(x)==set(y)
        for k in x:compare(x[k],y[k])
    elif isinstance(x,list):
        assert len(x)==len(y)
        # Job/outcome order is defined by arrival,id in the kernel.
        for l,r in zip(x,y):compare(l,r)
    elif isinstance(x,(int,float)) and not isinstance(x,bool):a.close(float(x),float(y),'projection/state')
    else:assert x==y,(x,y)
def verify_record(record,audit):
    tid=record['task'];now=record['at'];local=snapshot(audit,now,tid,False);compare(local,record['localSnapshot'])
    lr=project(local);compare(lr,record['local']);ar=None
    if record['airSnapshot'] is not None:
        air=snapshot(audit,now,tid,True);compare(air,record['airSnapshot']);ar=project(air);compare(ar,record['air'])
    else:assert not audit.alive(-1,now),'Missing available air counterfactual'
    selected='UAV' if ar is not None and better(ar,lr) else 'LOCAL'
    assert selected==record['selected']==audit.o[tid]['route']
def verify(root):
    manifest=json.loads((root/'manifest.json').read_text());assert manifest['status']=='COMPLETE'
    for file,h in manifest['source_sha256'].items():assert a.sha(root/'source'/file)==h,'Source snapshot checksum'
    rows=a.read(root/'episodes.csv');assert len(rows)==manifest['episodes']==manifest['seeds']*24
    count=routes=dispatch=0;hashes={}
    for row in rows:
        directory=root/row['scenario']/('seed-'+row['seed']);policy=row['policy'];jobs={int(j['id']):j for j in a.read(directory/'workload.csv')}
        assert a.sha(directory/'workload.csv')==row['workload_sha256']
        key=(row['scenario'],row['seed']);hashes.setdefault(key,row['workload_sha256']);assert hashes[key]==row['workload_sha256']
        outcomes={int(o['id']):o for o in a.read(directory/(policy+'-tasks.csv'))};energies=a.read(directory/(policy+'-energy.csv'))
        battery=int(row['scenario'].split('-b')[1]);cfg=dict(horizonSeconds=600,uavMips=2000,uavCpuWatts=20,hoverWatts=80,uavBatteryJ=battery,
            devices=[dict(mips=500,idleWatts=.5,cpuWatts=3,txWatts=.1,batteryJ=5000)]*4)
        audit=a.Audit(jobs,outcomes,energies,cfg,'EDF',.75)
        # Shared physics verifier; policy checks replaced with the independent replay below.
        audit.verify([],None,dispatch_check=False,routing_check=False);count+=len(jobs)
        for tid,o in outcomes.items():
            t=a.num(o,'start_s')
            if not math.isfinite(t):continue
            s=snapshot(audit,t)
            if audit.node(tid)==-1 and policy.endswith('__QIOS'):expected=choose(s)
            else:
                node=audit.node(tid);ready=[j for j in s['jobs'] if (-1 if j['air'] else j['device'])==node and j['phase']=='WAITING' and j['deadline']>t+E]
                name='FIFO' if node>=0 else policy.split('__')[1]
                expected=min(ready,key=lambda j:((j['deadline'],) if name=='EDF' else (j['estimatedRemainingMi'],) if name=='SPT' else ())+(j['ready'],j['arrival'],j['id']))['id']
            assert expected==tid,('dispatch',policy,tid,expected);dispatch+=1
        for record in json.loads((directory/(policy+'-projection.json')).read_text()):
            verify_record(record,audit);routes+=1
        if not policy.startswith('QIOS'):
            audit.schedule=policy.split('__')[1]
            audit.verify(a.read(directory/(policy+'-decisions.csv')),'DEADLINE_ENERGY',dispatch_check=False)
        a.close(sum(sum(a.num(e,k) for k in ['idle_j','compute_j','tx_j']) for e in energies),float(row['total_j']),'total energy')
        on=lambda tid:outcomes[tid]['status']=='COMPLETED_ON_TIME'
        images=[tid for tid,j in jobs.items() if j['source']=='RESCUENET'];background=[tid for tid,j in jobs.items() if j['source']=='ALIBABA']
        assert (len(images),sum(on(tid) for tid in images),len(background),sum(on(tid) for tid in background))==tuple(int(row[k]) for k in ['image_offered','image_ontime','background_offered','background_ontime'])
        value=sum((1 if j['source']=='ALIBABA' else max(1,int(j['priority']))) for tid,j in jobs.items() if on(tid))
        a.close(value,float(row['weighted_service']),'weighted service')
    result=dict(status='PASS',episodes=len(rows),tasks=count,queue_route_audits=routes,dispatch_actions=dispatch,
        limitation='Fixed UAV, rho1 and exact estimates pilot; dataset-pool to generated task reconstruction not audited here.')
    (root/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':verify(Path(sys.argv[1]))
