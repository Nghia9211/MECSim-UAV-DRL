"""Audit a completed Gym trace against physical traces, causal observations and fixed reward. Stdlib only."""
import importlib.util
import bisect
import json
import math
from pathlib import Path
import sys

spec=importlib.util.spec_from_file_location('mobile_audit',Path(__file__).with_name('verify-uav-mobile.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
read,num,check,close=audit.read,audit.num,audit.check,audit.close


def verify(root):
    meta=json.loads((root/'scenario.json').read_text(encoding='utf-8'));p=meta['protocol']
    ec=json.loads((root/'environment.json').read_text(encoding='utf-8'));cfg=ec['config']
    for key,value in cfg.items():
        if key in p and isinstance(value,(float,int)):close(p[key],value,'Config '+key)
    check(audit.sha(root/'workload.csv')==meta['workload_sha256'],'Workload hash')
    nodes=[{k:p[v] for k,v in [('mips','localMips'),('idleWatts','localIdleWatts'),('cpuWatts','localCpuWatts'),('txWatts','localTxWatts'),('batteryJ','localBatteryJ')]} for _ in range(12)]
    kernel={k:p[k] for k in ['horizonSeconds','uavMips','uavCpuWatts','hoverWatts']}
    kernel.update(devices=nodes,uavBatteryJ=meta['uavBatteryJ'],sites=meta['sites'],startX=0,startY=0)
    jobs={int(j['id']):j for j in read(root/'workload.csv')}
    images={i:r for i,r in enumerate(read(root/'source-pools/rescuenet-pool.csv'))}
    bg={int(r['source_line']):r for r in read(root/'source-pools/alibaba-pool.csv')}
    for tid,j in jobs.items():
        if j['source']=='RESCUENET':
            im=images[int(j['source_index'])]
            close(num(j,'input_bytes'),num(im,'bytes'),'Image bytes')
            close(num(j,'actual_mi'),num(im,'width')*num(im,'height')/1e6*p['imageMiPerMegapixel'],'Image MI')
        else:
            row=bg[int(j['source_index'])]
            close(num(j,'actual_mi'),(num(row,'end_s')-num(row,'start_s'))*num(row,'plan_cpu')/100*p['referenceMips']*p['backgroundWorkScale'],'Background MI')
        check(1-p['estimateError']-1e-8<=num(j,'estimated_mi')/num(j,'actual_mi')<=1+p['estimateError']+1e-8,'Estimate range')
    outcomes={int(o['id']):o for o in read(root/'episode-tasks.csv')}
    check(set(jobs)==set(outcomes),'Outcome IDs')
    a=audit.MobileAudit(jobs,outcomes,read(root/'episode-energy.csv'),kernel,cfg['scheduler'],p,
                        *[read(root/('episode-'+s+'.csv')) for s in ['visits','positions','coverage','updates','views']])
    history=json.loads((root/'transitions.json').read_text(encoding='utf-8'))
    service=cfg.get('control_mode')=='service_only'
    contact=service or cfg.get('control_mode','device')=='contact_policy'
    joint=contact or cfg.get('control_mode','device')=='joint_policy'
    routes=('DELIVERY_AWARE','DEADLINE_ENERGY','SHORTEST_FINISH')
    schedules=('EDF','SPT','FIFO')
    if joint:
        times=[s['info']['seconds'] for s in history[:-1]]
        actions=[s['action']%9 if contact else s['action'] for s in history[1:]]
        def action_at(at):
            i=bisect.bisect_right(times,at)-1
            check(i>=0,'Policy action before first decision')
            return actions[i]
        a.schedule_at=lambda at:cfg['scheduler'] if service else schedules[action_at(at)%3]
        a.routing_policy_at=lambda at,default:routes[action_at(at)//3]
    check(len(history)==len(a.visits)+1,'Transition/visit count')
    choices={}
    for before,after in zip(history,history[1:]):
        requested=after['action'];check(type(requested) is int and 0<=requested<(108 if contact else 9 if joint else 12),'Action range')
        alive=before['info']['alive'];executed=requested
        check(any(alive),'Choice without live source')
        if not joint:
            while not alive[executed]:executed=(executed+1)%12
        check(after['info']['requested_action']==requested and after['info']['executed_action']==executed,'Action mapping')
        if joint:
            if contact:
                executed=requested//9;check(alive[executed],'Masked dead-device action')
            else:
                executed=(before['info']['previous_target']+1)%12
                while not alive[executed]:executed=(executed+1)%12
        choices[before['info']['seconds']]=executed
    a.verify_mobile(choices,read(root/'episode-decisions.csv'),cfg['offloading'])
    # Reconstruct every observation from admitted queues and already-executed work.
    unit=lambda x:max(0,min(1,x))
    cumulative=[]
    for index,state in enumerate(history):
        info=state['info'];at=info['seconds'];h=kernel['horizonSeconds'];terminal=index==len(history)-1
        close(at,0 if index==0 else h if terminal else num(a.visits[index],'at_s'),'Decision timestamp')
        check(info['steps']==index,'Decision count')
        arrived=[tid for tid,j in jobs.items() if num(j,'arrival_s')<at]
        resolved=[tid for tid in arrived if num(outcomes[tid],'resolved_s')<=at+1e-8]
        image=[tid for tid in arrived if jobs[tid]['source']=='RESCUENET']
        failures=lambda ids:sum(outcomes[tid]['status']!='COMPLETED_ON_TIME' for tid in ids)
        done_images=[tid for tid in resolved if jobs[tid]['source']=='RESCUENET']
        delivered=sum(outcomes[tid]['status']=='COMPLETED_ON_TIME' and
                      (outcomes[tid]['route']=='UAV' or kernel['sites'][int(jobs[tid]['device'])]['connected']) for tid in done_images)
        expected=dict(images_seen=len(image),image_on_time=sum(outcomes[tid]['status']=='COMPLETED_ON_TIME' for tid in done_images),
                      image_misses=failures(done_images),delivered_on_time=delivered,
                      background_misses=failures([tid for tid in resolved if jobs[tid]['source']=='ALIBABA']),
                      image_latency_s=sum(num(outcomes[tid],'resolved_s')-num(jobs[tid],'arrival_s') for tid in done_images),
                      energy_j=sum(sum(a.energy_at(d,at)) for d in a.nodes),
                      offloaded=sum(outcomes[tid]['route']=='UAV' for tid in image),local=sum(outcomes[tid]['route']=='LOCAL' for tid in image),
                      covered=sum(num(c,'at_s')<at and c['available']=='true' for c in a.coverage.values()))
        for k,v in expected.items():close(info[k],v,'Causal feedback '+k)
        value=(2*delivered-len(image)-.25*expected['background_misses']-.1*expected['energy_j']/10000 if joint else
               delivered-expected['image_misses']-.25*expected['background_misses']-.05*expected['image_latency_s']/60-.1*expected['energy_j']/10000)
        cumulative.append(value)
        close(state['reward'],0 if index==0 else value-cumulative[-2],'Reward delta')
        if index:
            close(info['delta_seconds'],at-history[index-1]['info']['seconds'],'Step physical duration')
        active=[tid for tid in arrived if tid not in resolved]
        transfers=[tid for tid in active if outcomes[tid]['route']=='UAV' and num(outcomes[tid],'ready_s')>at+1e-8]
        def queue(node):
            return [tid for tid in active if outcomes[tid]['route']!='UNDECIDED' and a.node(tid)==node]
        def work(tid):
            o=outcomes[tid];start=num(o,'start_s');executed=max(0,at-start)*a.nodes[a.node(tid)]['mips'] if math.isfinite(start) else 0
            return max(1e-6,num(jobs[tid],'estimated_mi')-executed)
        def load(node):
            q=queue(node)
            return [unit(sum(work(tid) for tid in q)/a.nodes[node]['mips']/h),unit(len(q)/100),
                    unit(min([num(jobs[tid],'deadline_s')-at for tid in q],default=h)/h)]
        x,y=a.position_at(at);load_air=load(-1)
        previous=-1 if index==0 else int(a.visits[index-1]['target'])
        check(info['previous_target']==previous,'Previous target observation')
        alive=[a.alive(d,at) for d in range(12)]
        check(info['alive']==alive,'Action live mask')
        close(info['position'][0],x,'Info position x');close(info['position'][1],y,'Info position y')
        close(info['uav_battery_j'],a.battery_at(-1,at),'Info UAV battery')
        obs=[at/h,x/meta['areaMetres'],y/meta['areaMetres'],unit(a.battery_at(-1,at)/meta['uavBatteryJ']),
             load_air[0],load_air[1],unit(len(transfers)/100),float(a.alive(-1,at)),load_air[2]]
        for d,site in enumerate(kernel['sites']):
            latest=max([num(u,'generation_s') for u in a.updates if int(u['device'])==d and num(u,'at_s')<=at+1e-8],default=0)
            obs.extend([site['x']/meta['areaMetres'],site['y']/meta['areaMetres'],unit(a.battery_at(d,at)/nodes[d]['batteryJ']),
                        unit((at-latest)/h),float(site['connected']),float(alive[d]),*load(d),float(d==previous)])
        if joint:
            previous_action=info['requested_action']
            if contact and previous_action>=0:previous_action%=9
            obs.extend([cfg['areaMetres']/800,cfg['uavBatteryJ']/1600000,cfg['imageRate']/.24,
                        cfg['backgroundRate']/.1,cfg['estimateError']])
            obs.extend([float(previous_action==i) for i in range(9)])
        if contact:
            for site in kernel['sites']:
                seconds=math.hypot(site['x']-x,site['y']-y)/p['speedMps']
                if seconds<1e-7:seconds=0.
                neighbours=sum(alive[d] and not s['connected'] and
                    math.hypot(math.hypot(site['x']-s['x'],site['y']-s['y']),p['altitudeMetres'])<=p['rangeMetres']+1e-8
                    for d,s in enumerate(kernel['sites']))
                obs.extend([unit(seconds/h),unit(p['flightWatts']*seconds/max(1e-9,a.battery_at(-1,at))),neighbours/12])
        check(len(state['observation'])==len(obs)==(179 if contact else 143 if joint else 129),'Observation size')
        for i,(observed,replayed) in enumerate(zip(state['observation'],obs)):close(observed,replayed,'Observation '+str(i))
    return dict(status='PASS',decisions=len(a.visits),tasks=len(jobs),total_reward=cumulative[-1],
                checks=['shared kernel physics/energy/queues','source-pool cost mapping','requested/executed actions',
                        'all causal observation features','terminal drain and cumulative reward'])


if __name__=='__main__':
    check(len(sys.argv)==2,'Usage: python scripts/verify-uav-mobile-trace.py TRACE_DIR')
    root=Path(sys.argv[1]);result=verify(root)
    (root/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
