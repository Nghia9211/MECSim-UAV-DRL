"""Independent audit of adapted mobile service, plus reused offloading CPU/queue audit. Stdlib only."""
import bisect
import copy
import csv
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

spec=importlib.util.spec_from_file_location('fixed_audit',Path(__file__).with_name('verify-uav-offloading.py'))
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
read,num,check,close,sha=base.read,base.num,base.check,base.close,base.sha


class MobileAudit(base.Audit):
    def local_delivery_available(self,tid):
        return self.cfg['sites'][int(self.jobs[tid]['device'])]['connected']
    def __init__(self,jobs,outcomes,energies,cfg,scheduler,protocol,visits,positions,coverage,updates,views):
        adjusted=copy.deepcopy(jobs)
        self.coverage={int(c['id']):c for c in coverage}
        check(len(self.coverage)==len(coverage),'Duplicate coverage records')
        for tid,c in self.coverage.items():
            adjusted[tid]['upload_ready_s']=str(num(jobs[tid],'arrival_s')+num(c,'upload_s'))
        super().__init__(adjusted,outcomes,energies,cfg,scheduler,.75)
        self.original=jobs;self.p=protocol;self.visits=visits;self.positions=positions;self.updates=updates;self.views=views
        self.visit_times=[num(v,'at_s') for v in visits]

    def flight_seconds(self,at):
        death=num(self.energy[-1],'powered_s')
        return sum(max(0,min(at,death,num(v,'planned_arrival_s'))-num(v,'at_s')) for v in self.visits)

    def energy_at(self,node,at):
        idle,cpu,tx=super().energy_at(node,at)
        if node==-1:
            idle+=self.flight_seconds(at)*(self.p['flightWatts']-self.cfg['hoverWatts'])
        return idle,cpu,tx

    def projection(self,candidate,now,air):
        if air and self.coverage[candidate]['available']!='true':
            j=self.jobs[candidate];g=self.nodes[int(j['device'])]
            marginal=num(j,'estimated_mi')/self.cfg['uavMips']*self.cfg['uavCpuWatts']+(num(j,'upload_ready_s')-now)*g['txWatts']
            return math.inf,marginal,False,False
        return super().projection(candidate,now,air)

    def route_destination(self,tid,destination):
        return destination if self.coverage[tid]['available']=='true' else 'LOCAL'

    def position_at(self,at):
        t=min(at,num(self.energy[-1],'powered_s'))
        index=bisect.bisect_right(self.visit_times,t)-1
        if index<0:return self.cfg['startX'],self.cfg['startY']
        v=self.visits[index];duration=num(v,'planned_arrival_s')-num(v,'at_s')
        ratio=min(1,max(0,(t-num(v,'at_s'))/duration)) if duration>0 else 1
        return num(v,'from_x')+ratio*(num(v,'to_x')-num(v,'from_x')),num(v,'from_y')+ratio*(num(v,'to_y')-num(v,'from_y'))

    def service_available(self,at):
        if not self.alive(-1,at):return False
        index=bisect.bisect_right(self.visit_times,at)-1
        if index<0:return False
        arrival=num(self.visits[index],'planned_arrival_s')
        return arrival<=at+1e-8 and at<arrival+self.p['dwellSeconds']

    def verify_mobile(self,selector,decisions,route):
        super().verify(decisions,route)
        check(len(self.coverage)==sum(j['source']=='RESCUENET' and o['route']!='UNDECIDED' for tid,j in self.jobs.items() for o in [self.o[tid]]),'Coverage count')
        check(self.visit_times==sorted(set(self.visit_times)),'Visit ordering')
        view_groups={t:[] for t in self.visit_times}
        for view in self.views:
            check(num(view,'at_s') in view_groups,'Unexpected selection snapshot')
            view_groups[num(view,'at_s')].append(view)
        for i,v in enumerate(self.visits):
            at=num(v,'at_s');target=int(v['target']);previous=int(v['previous'])
            check(previous==(-1 if i==0 else int(self.visits[i-1]['target'])),'Previous target')
            check(self.alive(-1,at),'Selection after UAV death')
            if i==0:
                close(at,0,'Initial choice time');close(num(v,'from_x'),self.cfg['startX'],'Initial x');close(num(v,'from_y'),self.cfg['startY'],'Initial y')
            else:
                prior=self.visits[i-1]
                stop=num(prior,'planned_arrival_s')+self.p['dwellSeconds']
                pin_until=stop
                for tid,o in self.o.items():
                    j=self.jobs[tid];arrival=num(j,'arrival_s')
                    if o['route']=='UAV' and num(prior,'planned_arrival_s')-1e-8<=arrival<stop:
                        upload_end=arrival+num(o,'uploaded_s')
                        pin_until=max(pin_until,upload_end)
                close(at,pin_until,'Dwell/upload departure')
                close(num(v,'from_x'),num(prior,'to_x'),'Continuous visit x');close(num(v,'from_y'),num(prior,'to_y'),'Continuous visit y')
            site=self.cfg['sites'][target]
            close(num(v,'to_x'),site['x'],'Target x');close(num(v,'to_y'),site['y'],'Target y')
            distance=math.hypot(num(v,'to_x')-num(v,'from_x'),num(v,'to_y')-num(v,'from_y'))
            close(num(v,'planned_arrival_s'),at+distance/self.p['speedMps'],'Travel duration')
            snapshots=view_groups[at];check(len(snapshots)==len(self.cfg['devices']),'Device view count')
            by_id={int(d['id']):d for d in snapshots};check(set(by_id)==set(range(len(snapshots))),'Device view IDs')
            latest=[0.]*len(snapshots)
            for update in self.updates:
                if num(update,'at_s')<=at+1e-8:
                    d=int(update['device']);latest[d]=max(latest[d],num(update,'generation_s'))
            for d,view in by_id.items():
                close(num(view,'x'),self.cfg['sites'][d]['x'],'View x');close(num(view,'y'),self.cfg['sites'][d]['y'],'View y')
                check((view['connected']=='true')==self.cfg['sites'][d]['connected'],'Connectivity view')
                check((view['alive']=='true')==self.alive(d,at),'Alive view')
                close(num(view,'battery_fraction'),self.battery_at(d,at)/self.nodes[d]['batteryJ'],'Battery view')
                close(num(view,'latest_generation_s'),latest[d],'Delivered generation view');close(num(view,'age_s'),at-latest[d],'Age view')
            eligible=[(previous+k)%len(snapshots) for k in range(1,len(snapshots)+1) if by_id[(previous+k)%len(snapshots)]['alive']=='true']
            check(eligible,'Selection without live devices')
            chosen=selector[at] if isinstance(selector,dict) else eligible[0] if selector=='ROUND_ROBIN' else max(eligible,key=lambda d:num(by_id[d],'age_s'))
            check(chosen in eligible,'Recorded action targets dead device')
            check(target==chosen,'Incorrect service selection')
        check(bool(self.positions) and num(self.positions[-1],'at_s')==self.horizon,'Final position missing')
        for pos in self.positions:
            at=num(pos,'at_s');x,y=self.position_at(at)
            close(num(pos,'x'),x,'Trajectory x');close(num(pos,'y'),y,'Trajectory y');close(num(pos,'h'),self.p['altitudeMetres'],'Altitude')
            close(num(pos,'battery_j'),self.battery_at(-1,at),'Trajectory battery')
        for tid,c in self.coverage.items():
            j=self.jobs[tid];at=num(j,'arrival_s');d=int(j['device']);site=self.cfg['sites'][d];x,y=self.position_at(at)
            check(int(c['device'])==d,'Coverage source');close(num(c,'at_s'),at,'Coverage timestamp')
            slant=math.hypot(math.hypot(x-site['x'],y-site['y']),self.p['altitudeMetres'])
            close(num(c,'slant_m'),slant,'3D coverage distance')
            available=self.service_available(at) and slant<=self.p['rangeMetres']+1e-8
            check((c['available']=='true')==available,'Physical coverage gate')
            rate=20e6*math.log1p(.1*1e-8*slant**(-4)/1e-13)/math.log(2)
            close(num(c,'upload_s'),num(j,'input_bytes')*8/rate,'Dynamic upload duration')
            if self.o[tid]['route']=='UAV':check(available,'Upload outside coverage/in flight')
        expected={tid for tid,o in self.o.items() if self.jobs[tid]['source']=='RESCUENET' and o['status'].startswith('COMPLETED')
                  and (o['route']=='UAV' or self.cfg['sites'][int(self.jobs[tid]['device'])]['connected'])}
        check(len(self.updates)==len(expected) and {int(u['id']) for u in self.updates}==expected,'Delivered update set')
        latest=[0.]*len(self.cfg['devices']);previous_time=-1
        for update in self.updates:
            tid=int(update['id']);d=int(update['device']);j=self.jobs[tid]
            check(d==int(j['device']),'Delivered source');close(num(update,'generation_s'),num(j,'arrival_s'),'Generation timestamp')
            close(num(update,'at_s'),num(self.o[tid],'resolved_s'),'Completion delivery')
            check(num(update,'at_s')>=previous_time,'Update ordering');previous_time=num(update,'at_s')
            latest[d]=max(latest[d],num(j,'arrival_s'));close(num(update,'latest_generation_s'),latest[d],'Stale update rollback')
        return self.flight_seconds(self.horizon),statistics.mean(self.horizon-t for t in latest)


def verify(root):
    m=json.loads((root/'manifest.json').read_text());p=m['protocol']
    check(m['schema']=='uav-mobile-service-v1' and m['status']=='COMPLETE','Incomplete mobile run')
    check(sha(root/'source/mobile-protocol.json')==m['protocol_sha256'],'Protocol hash')
    check(json.loads((root/'source/mobile-protocol.json').read_text())==p,'Resolved protocol mismatch')
    for path,digest in m['source_sha256'].items():check(sha(root/'source'/path)==digest,'Source hash: '+path)
    rows=read(root/'episodes.csv');expected=len(m['configs'])*m['seeds']*len(m['policies'])
    check(m['episodes']==expected and len(rows)==expected*3,'Episode count')
    images={i:r for i,r in enumerate(read(root/'source-pools/rescuenet-pool.csv'))};background={int(r['source_line']):r for r in read(root/'source-pools/alibaba-pool.csv')}
    cases={};done=set();source_keys=set();pair={};total=0;summary={};cached_key=None
    for row in rows:
        scenario,seed,name=row['scenario'],int(row['seed']),row['policy'];key=(scenario,seed,name)
        check(scenario in m['configs'] and name in m['policies'] and m['first_seed']<=seed<m['first_seed']+m['seeds'],'Unexpected case')
        check(row['source'] in {'ALL','RESCUENET','ALIBABA'},'Unexpected source')
        check((*key,row['source']) not in source_keys,'Duplicate source row');source_keys.add((*key,row['source']))
        cfg=m['configs'][scenario];directory=root/scenario/f'seed-{seed}'
        if (scenario,seed) not in cases:
            inputs=read(directory/'workload.csv');jobs={int(j['id']):j for j in inputs};check(len(jobs)==len(inputs),'Duplicate jobs')
            digest=sha(directory/'workload.csv');cases[scenario,seed]=(jobs,digest)
            load=scenario.split('-')[1];check(pair.setdefault((load,seed),digest)==digest,'Geometry/battery changed offered workload')
            for j in jobs.values():
                if j['source']=='RESCUENET':
                    im=images[int(j['source_index'])];close(num(j,'actual_mi'),num(im,'width')*num(im,'height')/1e6*p['imageMiPerMegapixel'],'Image actual MI')
                    close(num(j,'input_bytes'),num(im,'bytes'),'Image bytes');check(0<=int(j['device'])<len(cfg['devices']),'Device ID')
                    check(int(j['priority']) in {2,3},'Image priority');budget=p['criticalDeadlineSeconds'] if int(j['priority'])==3 else p['imageDeadlineSeconds']
                    close(num(j,'upload_ready_s')-num(j,'arrival_s'),num(j,'input_bytes')*8/20e6,'Reference link duration')
                else:
                    check(j['source']=='ALIBABA' and int(j['device'])==-1 and int(j['priority'])==1 and num(j,'input_bytes')==0,'Background fields')
                    bg=background[int(j['source_index'])];close(num(j,'actual_mi'),(num(bg,'end_s')-num(bg,'start_s'))*num(bg,'plan_cpu')/100*p['referenceMips']*p['backgroundWorkScale'],'Background actual MI')
                    close(num(j,'upload_ready_s'),num(j,'arrival_s'),'Native background ready');budget=p['backgroundDeadlineSeconds']
                close(num(j,'deadline_s')-num(j,'arrival_s'),budget,'Deadline budget')
                check(0<=num(j,'arrival_s')<p['arrivalWindowSeconds'] and num(j,'deadline_s')<=p['horizonSeconds'],'Time range')
                check(1-p['estimateError']-1e-8<=num(j,'estimated_mi')/num(j,'actual_mi')<=1+p['estimateError']+1e-8,'Estimate range')
        jobs,digest=cases[scenario,seed];check(digest==row['workload_sha256'],'Workload hash')
        if key not in done:
            outcomes=read(directory/(name+'-tasks.csv'));indexed={int(o['id']):o for o in outcomes}
            check(set(indexed)==set(jobs) and len(indexed)==len(outcomes),'Outcome IDs')
            energies=read(directory/(name+'-energy.csv'));selector,route,scheduler=name.split('__')
            a=MobileAudit(jobs,indexed,energies,cfg,scheduler,p,*[read(directory/(name+'-'+suffix+'.csv')) for suffix in ['visits','positions','coverage','updates','views']])
            flight,age=a.verify_mobile(selector,read(directory/(name+'-decisions.csv')),route)
            done.add(key);cached_key=key;total+=len(jobs)
        else:
            # Writer emits the three source rows together. Keep one audit in memory, not all trajectories.
            check(cached_key==key,'Per-episode source rows must be contiguous')
        group=[o for tid,o in a.o.items() if row['source']=='ALL' or jobs[tid]['source']==row['source']]
        statuses=['COMPLETED_ON_TIME','COMPLETED_LATE','EXPIRED_WAITING','DROPPED_UAV_BATTERY','DROPPED_DEVICE_BATTERY','UNFINISHED_HORIZON']
        for field,status in zip(['on_time','late','expired','uav_dropped','device_dropped','unfinished'],statuses):
            count=sum(o['status']==status or field=='expired' and o['status']=='DROPPED_DEADLINE_RISK' for o in group)
            check(int(row[field])==count,'Summary '+field)
        check(int(row['offered'])==len(group),'Offered count')
        for field,route in [('local','LOCAL'),('offloaded','UAV')]:check(int(row[field])==sum(o['route']==route for o in group),'Route count')
        if group:close(num(row,'dvr'),1-int(row['on_time'])/len(group),'DVR')
        completed=[num(o,'resolved_s')-num(jobs[int(o['id'])],'arrival_s') for o in group if o['status'].startswith('COMPLETED')]
        if completed:close(num(row,'mean_completed_latency_s'),statistics.mean(completed),'Latency')
        energy=[sum(num(e,f) for f in ['idle_j','compute_j','tx_j']) for e in a.energy.values()]
        close(num(row,'uav_energy_j'),energy[0],'UAV total');close(num(row,'ground_energy_j'),sum(energy[1:]),'Ground total');close(num(row,'total_energy_j'),sum(energy),'System total')
        close(num(row,'flight_j'),flight*p['flightWatts'],'Flight J');close(num(row,'hover_j'),(num(a.energy[-1],'powered_s')-flight)*p['hoverWatts'],'Hover J')
        close(num(row,'travelled_m'),flight*p['speedMps'],'Distance');close(num(row,'mean_final_age_s'),age,'Final freshness')
        check(int(row['visits'])==len(a.visits),'Visit count');check(row['trace']==f'{scenario}/seed-{seed}/{name}-tasks.csv','Trace path')
        summary.setdefault((scenario,name,row['source']),[]).append(row)
    check(len(done)==expected,'Missing episodes')
    output=[]
    for (scenario,name,source),group in sorted(summary.items()):
        check(len(group)==m['seeds'],'Missing per-source seed')
        r=dict(scenario=scenario,policy=name,source=source,seeds=len(group))
        for field in ['dvr','mean_completed_latency_s','total_energy_j','flight_j','hover_j','travelled_m','mean_final_age_s','offloaded','local','wall_ms']:
            vals=[num(x,field) for x in group if math.isfinite(num(x,field))];r['mean_'+field]=statistics.mean(vals) if vals else ''
        output.append(r)
    with (root/'summary.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=output[0]);writer.writeheader();writer.writerows(output)
    result=dict(status='PASS',episodes=len(done),task_outcomes=total,paired_cases=len(cases),
                checks=['source cost/hash pairing','local/UAV execution and energy conservation','causal route forecasts and scheduling replay','service-policy snapshots and decisions',
                        'flight duration/trajectory/propulsion battery','coverage/slant rate/local fallback','upload pins and departure times','completion-based freshness and stale generation'],
                paper_reproduction=False,dqn_trained=False,source_holdout=False)
    (root/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result


if __name__=='__main__':
    check(len(sys.argv)==2,'Usage: python scripts/verify-uav-mobile.py RUN_DIR')
    print(json.dumps(verify(Path(sys.argv[1])),indent=2))
    from offloading_metrics import export
    export(Path(sys.argv[1]))
