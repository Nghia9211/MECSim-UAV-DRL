"""Replay guard/routing/dispatch and physical outcomes; summarize paired pilot."""
import importlib.util
import json
from pathlib import Path
import statistics
import sys
s=importlib.util.spec_from_file_location('physical',Path(__file__).with_name('verify-uav-offloading.py'))
a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
def verify(root):
    m=json.loads((root/'manifest.json').read_text());assert m['status']=='COMPLETE' and (m['riskOnly'] or m.get('paperInspired'))
    for file,h in m['source_sha256'].items():assert a.sha(root/'source'/file)==h
    rows=a.read(root/'episodes.csv');assert len(rows)==m['episodes']==m['seeds']*48
    count=drops=0
    for row in rows:
        d=root/row['scenario']/('seed-'+row['seed']);name=row['policy'];route,scheduler=name.split('__')
        assert a.sha(d/'workload.csv')==row['workload_sha256']
        jobs={int(j['id']):j for j in a.read(d/'workload.csv')};out={int(o['id']):o for o in a.read(d/(name+'-tasks.csv'))}
        energy=a.read(d/(name+'-energy.csv'));decisions=a.read(d/(name+'-decisions.csv'))
        cfg=dict(horizonSeconds=600,uavMips=2000,uavCpuWatts=20,hoverWatts=80,uavBatteryJ=int(row['scenario'].split('-b')[1]),
            devices=[dict(mips=500,idleWatts=.5,cpuWatts=3,txWatts=.1,batteryJ=5000)]*4)
        a.Audit(jobs,out,energy,cfg,scheduler,.75).verify(decisions,route)
        images=[tid for tid,j in jobs.items() if j['source']=='RESCUENET'];bg=[tid for tid,j in jobs.items() if j['source']=='ALIBABA']
        on=lambda tid:out[tid]['status']=='COMPLETED_ON_TIME'
        assert tuple(map(int,(row['image_offered'],row['image_ontime'],row['background_offered'],row['background_ontime'])))==(len(images),sum(map(on,images)),len(bg),sum(map(on,bg)))
        a.close(sum(sum(a.num(e,k) for k in ['idle_j','compute_j','tx_j']) for e in energy),float(row['total_j']),'total')
        count+=len(jobs);drops+=sum(o['status']=='DROPPED_DEADLINE_RISK' for o in out.values())
    result=dict(status='PASS',episodes=len(rows),tasks=count,risk_drops=drops,estimate_error=m['estimateError'],
        limitation='Generated workload replay, not raw-pool reconstruction; fixed UAV, development study.')
    (root/'verification.json').write_text(json.dumps(result,indent=2))
    lines=['# Deadline risk / transfer-aware pilot','',f"Estimate error: {m['estimateError']}. {m['seeds']} development seeds, paired loads/batteries. Drops count as failures.",'',
        '| Policy | Image DVR % | Background DVR % | Total kJ |','| --- | ---: | ---: | ---: |']
    for name in sorted({r['policy'] for r in rows}):
        g=[r for r in rows if r['policy']==name]
        vals=[statistics.mean(100*(1-int(r['image_ontime'])/int(r['image_offered'])) for r in g),
            statistics.mean(100*(1-int(r['background_ontime'])/int(r['background_offered'])) for r in g),statistics.mean(float(r['total_j'])/1000 for r in g)]
        lines.append('| '+name+' | '+' | '.join(f'{x:.3f}' for x in vals)+' |')
    (root/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(result,indent=2));print('\n'.join(lines))
if __name__=='__main__':verify(Path(sys.argv[1]))
