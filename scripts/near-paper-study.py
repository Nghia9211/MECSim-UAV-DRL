"""Near-paper offloading pilot: prepare, run, independently audit, export mandatory metrics.
Synthetic paper-sized images are not RescueNet inference benchmarks.
"""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
rng=module('near_rng','workload_rng.py')
mobile=module('near_mobile','verify-uav-mobile.py')
metrics=module('near_metrics','offloading_metrics.py')
check,close,read,sha=mobile.check,mobile.close,mobile.read,mobile.sha
STANDBY=[2.65,1.69,4.87,2.82,1.88]
ACTIVE=[[2.165,1.287,2.352,1.36,3.391],[1.335,1.621,1.124,.92,1.582],
        [3.234,1.9,2.972,2.421,2.595],[1.91,4.38,2.54,1.01,5.06],
        [3.268,1.925,3.07,1.35,2.874]]
RATES=[[74536.25,2758.14,4734.16,23867.61,1854.59],[12318.36,1114.03,1183.72,5277.71,949.66],
       [71731.84,3767.51,949.36,40294.21,973.1],[65088.52,87894.05,13020.39,65264.07,6957.73],
       [69985.94,7066.79,2733.97,22230.58,8298.13]]
HARDWARE=['RASPBERRY_PI_4B','RASPBERRY_PI_3B','FIREFLY','JETSON_NANO','NANOPC_T4']
TASKS=['HAAR','MMOD','DNN','DLIB','YOLOV3']
def random(seed,stream):
    h=hashlib.sha256(f"uav-workload/near-paper-v1\n{seed}\n{stream}".encode()).digest()
    return rng.JavaRandom(int.from_bytes(h[:8],'big',signed=True))
def paper_layout(p):
    r=rng.JavaRandom(p['layoutSeed']); power=list(range(12));comms=list(range(12))
    for a in (power,comms):
        for i in range(len(a),1,-1):
            j=r.integer(i);a[i-1],a[j]=a[j],a[i-1]
    result=[]
    for d in range(12):
        x,y=r.double()*800,r.double()*800;h,t=r.integer(5),r.integer(5)
        battery=50000+r.double()*30000
        result.append(dict(x=x,y=y,hardware=HARDWARE[h],task=TASKS[t],capacityJ=battery,powered=False,
            connected=comms.index(d)<p['connectedDevices'],h=h,t=t))
    return result
def generate(p,load,seed,pool):
    result=[]
    for image in (True,False):
        prefix='IMAGE' if image else 'BACKGROUND'
        arrivals=random(seed,prefix+'_ARRIVALS');choose=random(seed,prefix+'_SELECTION')
        priority=random(seed,'IMAGE_PRIORITY');rate=load['imageRate' if image else 'backgroundRate'];at=0.;n=0
        while rate>0:
            at+=-math.log1p(-arrivals.double())/rate
            if at>=p['arrivalWindowSeconds']:break
            if len(result)>=20000:raise ValueError('Too many tasks')
            if image:
                size=2000000+choose.integer(2000001);work=size/1000
                critical=priority.double()<p['criticalFraction']
                budget=load['criticalDeadlineSeconds' if critical else 'imageDeadlineSeconds']
                index=n;rank=3 if critical else 2
            else:
                row=pool[choose.integer(len(pool))];size=0;index=int(row['source_line']);rank=1
                work=(float(row['end_s'])-float(row['start_s']))*float(row['plan_cpu'])/100*p['backgroundReferenceMips']*p['backgroundWorkScale']
                budget=p['backgroundDeadlineSeconds']
            result.append(dict(id=2*n+(0 if image else 1),source='SYNTHETIC_IMAGE' if image else 'ALIBABA',
                source_index=index,arrival_s=at,upload_ready_s=at+size*8/20e6,deadline_s=at+budget,
                priority=rank,input_bytes=size,actual_mi=work))
            n+=1
    assign=random(seed,'DEVICE_ASSIGNMENT');error=random(seed,'COMPUTE_ESTIMATE');background_error=random(seed,'BACKGROUND_COMPUTE_ESTIMATE')
    result.sort(key=lambda j:j['id'])
    for j in result:
        j['device']=assign.integer(12) if j['source']=='SYNTHETIC_IMAGE' else -1
        j['estimated_mi']=j['actual_mi']*(1+p['estimateError']*(2*(error if j['source']=='SYNTHETIC_IMAGE' else background_error).double()-1))
    return result

def prepare(path,smoke=False,background=False):
    if path.exists():raise FileExistsError(path)
    policies=['ROUND_ROBIN__'+r+'__EDF' for r in ['ALL_LOCAL','ALL_UAV','SHORTEST_FINISH','DEADLINE_ENERGY','DELIVERY_AWARE']]
    policies+=['ROUND_ROBIN__ALL_UAV__'+s for s in ['FIFO','SPT','RISK_EDF']]
    p=dict(workloadGenerator='near-paper-v1',estimateStreams='per-source-v1',purpose='Exploratory near-paper extension, not exact paper reproduction',
        paper='Azfar et al. arXiv:2501.15305v1',taskSeeds=list(range(2 if smoke else 30)),
        seedRole='paired workload seeds; fixed layout, no model training or unseen-layout claim',
        layoutSeed=42,devices=12,poweredDevices=0,connectedDevices=8,
        horizonSeconds=1800,arrivalWindowSeconds=600,altitudeMetres=10,speedMps=5,rangeMetres=65,
        flightWatts=150,dwellSeconds=60,allowContactWait=True,
        radioConvention='LITERAL_DBM: beta0 numeric 1e-8; reference gain ambiguity unchanged',
        uavBytesPerSecond=2000000,uavCpuWatts=20,
        workNormalization='1000 bytes per normalized MI; not measured CPU instructions',
        criticalFraction=.25,estimateError=.2,
        backgroundReferenceMips=2000,backgroundWorkScale=.01,backgroundDeadlineSeconds=120,
        alibabaPath='datasets/raw/alibaba2018/batch_task.csv',
        policies=policies,smoke=smoke,
        loads=[dict(name='primary',imageRate=.04,backgroundRate=0.,criticalDeadlineSeconds=600,imageDeadlineSeconds=600),
               dict(name='deadline-sensitivity',imageRate=.04,backgroundRate=0.,criticalDeadlineSeconds=300,imageDeadlineSeconds=300)])
    if background:
        check((ROOT/p['alibabaPath']).is_file(),'Missing optional Alibaba batch_task.csv')
        p['loads'].append(dict(name='background-sensitivity',imageRate=.04,backgroundRate=.1,
            criticalDeadlineSeconds=600,imageDeadlineSeconds=600))
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(p,indent=2)+'\n',encoding='utf8')
    return p

def verify(root):
    root=Path(root)
    (root/'verification.json').unlink(missing_ok=True)
    m=json.loads((root/'manifest.json').read_text());p=m['protocol']
    check(m['study_stage']=='near-paper' and m['status']=='COMPLETE','Incomplete/unknown run')
    check(p['workloadGenerator']=='near-paper-v1' and p.get('estimateStreams')=='per-source-v1','Wrong generator/estimate streams')
    check(sha(root/'source/protocol.json')==m['protocol_sha256'],'Protocol hash')
    check(json.loads((root/'source/protocol.json').read_text())==p,'Protocol mismatch')
    for name,digest in m['source_sha256'].items():check(sha(root/'source'/name)==digest,'Source snapshot '+name)
    check(sha(root/'alibaba-pool.csv')==m['alibaba_pool_sha256'],'Alibaba pool hash')
    pool=read(root/'alibaba-pool.csv');expected_layout=paper_layout(p)
    layout=json.loads((root/'paper-layout.json').read_text())
    for a,b in zip(layout,expected_layout):
        for k in ('x','y','capacityJ'):close(a[k],b[k],'Paper layout '+k)
        for k in ('hardware','task','powered','connected'):check(a[k]==b[k],'Paper layout '+k)
    check(len(layout)==12,'Paper layout size')
    for scenario,cfg in m['configs'].items():
        close(cfg['horizonSeconds'],p['horizonSeconds'],'Horizon')
        for key,value in [('uavMips',p['uavBytesPerSecond']/1000),('uavCpuWatts',p['uavCpuWatts']),
                          ('hoverWatts',80),('uavBatteryJ',1600000),('startX',0),('startY',0)]:
            close(cfg[key],value,'CPU/config '+key)
        check(cfg['allowContactWait']==p['allowContactWait'],'Wait config')
        check(cfg['load']==next(x for x in p['loads'] if x['name']==scenario),'Scenario load')
        check(len(cfg['sites'])==len(cfg['devices'])==12,'Device count')
        for i,d in enumerate(expected_layout):
            h,t=d['h'],d['t'];a=cfg['devices'][i];site=cfg['sites'][i]
            for k,v in [('mips',RATES[t][h]/1000),('idleWatts',STANDBY[h]),('cpuWatts',ACTIVE[t][h]),('txWatts',.1),('batteryJ',d['capacityJ'])]:
                close(a[k],v,'Paper hardware '+k)
            close(site['x'],d['x'],'Site x');close(site['y'],d['y'],'Site y');check(site['connected']==d['connected'],'Connection')
    rows=read(root/'episodes.csv');seen=set();cases={};outcome_count=0
    check(len(rows)==m['episodes']==len(m['configs'])*len(p['taskSeeds'])*len(p['policies']),'Episode count')
    for row in rows:
        scenario,seed,policy=row['scenario'],int(row['seed']),row['policy'];key=scenario,seed,policy
        check(key not in seen and scenario in m['configs'] and seed in p['taskSeeds'] and policy in p['policies'],'Unexpected/duplicate case')
        seen.add(key);cfg=m['configs'][scenario];d=root/scenario/f'seed-{seed}'
        if (scenario,seed) not in cases:
            workload=read(d/'workload.csv');expected=generate(p,cfg['load'],seed,pool)
            check(len(workload)==len(expected),'Task count')
            for a,b in zip(workload,expected):
                for k,v in b.items():
                    if k=='source':check(a[k]==v,'Task source')
                    else:close(float(a[k]),v,'Seed task '+k)
            cases[scenario,seed]=({int(j['id']):j for j in workload},sha(d/'workload.csv'))
        jobs,digest=cases[scenario,seed];check(digest==row['workload_sha256'],'Pair hash')
        outcome_rows=read(d/(policy+'-tasks.csv'));outcomes={int(o['id']):o for o in outcome_rows}
        check(len(outcomes)==len(outcome_rows),'Duplicate outcome IDs')
        energies=read(d/(policy+'-energy.csv'))
        check(len({e['device'] for e in energies})==len(energies),'Duplicate energy nodes')
        selector,route,scheduler=policy.split('__')
        a=mobile.MobileAudit(jobs,outcomes,energies,cfg,scheduler,p,
            *[read(d/(policy+'-'+suffix+'.csv')) for suffix in ('visits','positions','coverage','updates','views')])
        flight,_=a.verify_mobile(selector,read(d/(policy+'-decisions.csv')),route)
        outcome_count+=len(jobs)
        check(len(jobs)==int(row['offered']),'Offered summary')
        for key,status in [('on_time','COMPLETED_ON_TIME'),('late','COMPLETED_LATE'),('uav_dropped','DROPPED_UAV_BATTERY'),
                           ('device_dropped','DROPPED_DEVICE_BATTERY'),('unfinished','UNFINISHED_HORIZON')]:
            check(int(row[key])==sum(o['status']==status for o in outcomes.values()),'Summary '+key)
        check(int(row['expired'])==sum(o['status'] in ('EXPIRED_WAITING','DROPPED_DEADLINE_RISK','DROPPED_BACKGROUND_BUDGET') for o in outcomes.values()),'Expired summary')
        for field,destination in [('local','LOCAL'),('offloaded','UAV')]:
            check(int(row[field])==sum(o['route']==destination for o in outcomes.values()),'Route summary')
        all_j=sum(float(e[k]) for e in energies for k in ('idle_j','compute_j','tx_j'))
        uav=next(e for e in energies if e['device']=='-1')
        uav_j=sum(float(uav[k]) for k in ('idle_j','compute_j','tx_j'))
        for k,v in [('total_energy_j',all_j),('uav_energy_j',uav_j),('ground_energy_j',all_j-uav_j),
                    ('flight_j',flight*150),('hover_j',(float(uav['powered_s'])-flight)*80),('travelled_m',flight*5)]:
            close(float(row[k]),v,'Summary '+k)
    result=dict(status='PASS',episodes=len(seen),task_outcomes=outcome_count,paired_cases=len(cases),
        checks=['independent seed reconstruction','paper layout and hardware tables','CPU/queue/routing replay',
                'flight/contact/upload replay','energy conservation','delivered update set','source/protocol hashes'],
        paper_reproduction=False,training=False,unseen_layouts=False)
    (root/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare');q.add_argument('--protocol',type=Path,required=True);q.add_argument('--smoke',action='store_true');q.add_argument('--background',action='store_true')
    q=sub.add_parser('run');q.add_argument('--protocol',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
    q=sub.add_parser('verify');q.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.command=='prepare':
        p=prepare(args.protocol,args.smoke,args.background)
        print(f"Prepared {len(p['loads'])*len(p['taskSeeds'])*len(p['policies'])} episodes: {args.protocol}")
    elif args.command=='run':
        cmd=[shutil.which('mvn') or 'mvn','-o','compile','exec:java','-Dexec.mainClass=uav.offloading.NearPaperBenchmark',
             '-Dnear.protocol='+str(args.protocol),'-Dnear.output='+str(args.output)]
        subprocess.run(cmd,cwd=ROOT,check=True)
        print(json.dumps(verify(args.output),indent=2));metrics.export(args.output)
        module('near_report','report-near-paper.py').report(args.output)
    else:
        print(json.dumps(verify(args.output),indent=2));metrics.export(args.output)
        module('near_report','report-near-paper.py').report(args.output)
if __name__=='__main__':main()
