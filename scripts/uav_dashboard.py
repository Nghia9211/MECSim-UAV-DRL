"""Build a self-contained local results dashboard; stdlib only, no training or raw-data mutation."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'visualization'


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def number(row,key,default=None):
    value=row.get(key,'')
    return float(value) if value not in ('',None) else default


def short(path):return str(path.relative_to(ROOT)).replace('\\','/')


def safe_trace(base,value):
    path=(base/Path(value.replace('\\','/'))).resolve()
    if not path.is_relative_to(ROOT.resolve()):raise ValueError('Trace outside repository')
    if not path.is_dir():raise FileNotFoundError(path)
    return path


def layout_csv(path):
    return [dict(id=int(r['device']),x=number(r,'x_m'),y=number(r,'y_m'),
                 powered=r['powered']=='true',connected=r['connected']=='true',hardware=r['hardware'],task=r['vision_task']) for r in read(path)]


def paper_trace(path):
    rows=read(path/'slots.csv')
    return dict(kind='paper',area=800,altitude=10,speed=5,range=65,
                layout=layout_csv(path/'layout.csv'),
                points=[[number(r,'start_s'),number(r,'end_s')]+[round(number(r,k),4) for k in ('x_m','y_m','uav_battery_j','max_data_age','action')] for r in rows])


def mobile_trace(path):
    scenario=json.loads((path/'scenario.json').read_text(encoding='utf-8'))
    positions=read(path/'episode-positions.csv')
    return dict(kind='mobile',area=scenario['areaMetres'],altitude=10,speed=5,range=65,
                layout=[dict(id=i,x=s['x'],y=s['y'],powered=False,connected=s['connected'],hardware='Ground CPU',task='Image workload') for i,s in enumerate(scenario['sites'])],
                points=[[number(r,'at_s')]+[round(number(r,k),4) for k in ('x','y','battery_j')]+[r['travelling']=='true',int(r['target'])] for r in positions])


def paper_record(row,profile,checkpoint,trace):
    return dict(profile=profile,checkpoint=checkpoint,policy=row['policy'],seed=int(row['training_seed']),
                layout=int(row['layout_seed']),task=int(row['task_seed']),slots=int(row['slots']),seconds=number(row,'seconds'),
                energy=1600000-number(row,'uav_battery_j'),reason=row['reason'],trace=trace)


def add_traces(dataset,locator):
    traces={};lookup={};layouts={}
    for r in dataset['rows']:
        path=locator(r)
        if path is None:continue
        key=short(path)
        if key not in lookup:
            trace=paper_trace(path) if dataset['kind']=='paper' else mobile_trace(path)
            layout_key=str(r['layout'])
            if layout_key in layouts:
                assert layouts[layout_key]==trace['layout'],'Different coordinates under one layout ID'
            layouts[layout_key]=trace.pop('layout');trace['layout']=layout_key
            lookup[key]=str(len(traces));traces[lookup[key]]=trace
        r['traceId']=lookup[key]
    dataset.update(traces=traces,layouts=layouts)


def conventions_dataset():
    base=ROOT/'target/paper-convention-retrain-20261024'
    if not (base/'verification.json').exists():return None
    m=json.loads((base/'manifest.json').read_text());v=json.loads((base/'verification.json').read_text())
    if m['status']!='COMPLETE' or v['status']!='PASS':raise ValueError('Convention run not audited')
    rows=read(base/'episodes.csv')
    reference=ROOT/m['protocol']['reference_campaign']
    ds=dict(id='conventions',kind='paper',title='Paper · Reward & freshness',source=short(base),
            unit='3 learning seed · 1 layout · 30 task case',audit='540 trace mới đạt replay; 270 dòng REFERENCE dùng lại',
            budget='1.000.000 bước/model',defaultProfile='REFERENCE',profiles=['REFERENCE','REWARD_AFTER','LOCAL_COMPLETION'],
            note='Ba quy ước khác nhau là đối chứng môi trường/reward; không phải ba thuật toán mới. Best chọn bằng validation, final đúng 1m. Baseline chỉ tính một lần/case.',
            metrics=['slots','seconds','energy'],rows=[],curves=[])
    for row in rows:
        cp=row['checkpoint'] if row['policy']=='DQN' else 'heuristic'
        trace=safe_trace(reference if row['profile']=='REFERENCE' else base,row['trace'])
        ds['rows'].append(paper_record(row,row['profile'],cp,short(trace)))
    add_traces(ds,lambda r:ROOT/r['trace'])
    refmeta=json.loads((reference/'manifest.json').read_text())
    for profile in ds['profiles']:
        for seed in (0,1,2):
            if profile=='REFERENCE':
                saved=next(r['run'] for r in refmeta['runs'] if r['seed']==seed).replace('\\','/')
                run=ROOT/'target'/saved.split('/target/',1)[1] if '/target/' in saved else ROOT/saved
            else:run=base/profile/f'seed-{seed}'
            vals=read(run/'validation.csv')
            ds['curves'].append(dict(profile=profile,seed=seed,points=[[int(r['steps']),number(r,'mean_slots')] for r in vals]))
    return ds


def reference_dataset():
    base=ROOT/'target/paper-reference-1m-restart-20261023'
    if not (base/'verification.json').exists():return None
    m=json.loads((base/'manifest.json').read_text());v=json.loads((base/'verification.json').read_text())
    if m['status']!='COMPLETE' or v['status']!='PASS':raise ValueError('Reference campaign not audited')
    ds=dict(id='reference',kind='paper',title='Paper · 3 learning/layout pairs',source=short(base),
            unit='3 cặp learning/layout seed · 30 task case/cặp',audit='360 trace chính + 90 trace final đạt replay',
            budget='1.000.000 bước/model',defaultProfile='REFERENCE',profiles=['REFERENCE'],
            note='Learning và layout seed thay cùng nhau. SD giữa run không phải riêng độ bất ổn training. Kết quả chưa xác nhận khớp toàn bộ paper.',
            metrics=['slots','seconds','energy'],rows=[],curves=[])
    for row in read(base/'episodes.csv'):
        path=safe_trace(base,row['trace'])
        ds['rows'].append(paper_record(row,'REFERENCE','best' if row['policy']=='DQN' else 'heuristic',short(path)))
    for row in read(base/'secondary-final-evaluation/episodes.csv'):
        path=safe_trace(base,row['trace'])
        ds['rows'].append(paper_record(row,'REFERENCE','final',short(path)))
    add_traces(ds,lambda r:ROOT/r['trace'])
    for seed in (0,1,2):
        ds['curves'].append(dict(profile='REFERENCE',seed=seed,points=[[int(r['steps']),number(r,'mean_slots')] for r in read(base/f'seed-{seed}/validation.csv')]))
    return ds


def mobile_dataset():
    base=ROOT/'target/mobile-dqn-smoke-20261023'
    if not (base/'training-verification.json').exists():return None
    cfg=json.loads((base/'config.json').read_text())
    candidates=sorted(base.glob('evaluation-*/protocol.json'))
    candidates=[p for p in candidates if json.loads(p.read_text()).get('status')=='COMPLETE']
    if not candidates:return None
    evaluation=candidates[0].parent
    ds=dict(id='mobile',kind='mobile',title='Mobile · Offloading + EDF pilot',source=short(evaluation),
            unit='1 learning seed · 10 task case · layout 42',audit='Pipeline train đạt; 4 trace của task đầu đã audit',
            budget='2.000 bước · 468 gradient updates · pilot',defaultProfile='MOBILE',profiles=['MOBILE'],
            note='Môi trường 129D mở rộng, UAV di chuyển, local/UAV + EDF; không so trực tiếp với lifetime paper. Episode cố định 600s, chưa đo network lifetime. Chỉ có trace task đầu.',
            metrics=['dvr','energy','delivery','offloaded'],rows=[],curves=[])
    for row in read(evaluation/'episodes.csv'):
        ds['rows'].append(dict(profile='MOBILE',checkpoint='best' if row['policy']=='DQN' else 'heuristic',policy=row['policy'],seed=0,
                               layout=int(row['layout_seed']),task=int(row['task_seed']),seconds=number(row,'seconds'),dvr=number(row,'image_dvr'),
                               energy=number(row,'total_energy_j'),delivery=number(row,'delivered_on_time'),offloaded=number(row,'offloaded'),
                               reason='HORIZON_600S',trace=short(evaluation/('trace-'+row['policy'])) if int(row['task_seed'])==2000000 else None))
    add_traces(ds,lambda r:ROOT/r['trace'] if r['trace'] else None)
    ds['curves']=[dict(profile='MOBILE',seed=0,points=[[int(r['steps']),number(r,'mean_image_dvr')] for r in read(base/'validation.csv')])]
    return ds


def build(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    datasets=[d for d in [conventions_dataset(),reference_dataset(),mobile_dataset()] if d]
    if not datasets:raise FileNotFoundError('No completed, verified campaigns found under target/')
    payload=dict(schema='uav-comparison-dashboard-v1',built=datetime.now().isoformat(timespec='seconds'),datasets=datasets)
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    html=(UI/'dashboard.html').read_text(encoding='utf-8').replace('__EXPERIMENT_DATA__',encoded)
    (out/'index.html').write_text(html,encoding='utf-8')
    for f in ('dashboard.css','dashboard.js'):shutil.copy2(UI/f,out/f)
    receipt=dict(schema=payload['schema'],built=payload['built'],datasets=[dict(id=d['id'],episodes=len(d['rows']),traces=len(d['traces'])) for d in datasets],
                 index_sha256=hashlib.sha256((out/'index.html').read_bytes()).hexdigest(),no_training=True,raw_outputs_modified=False)
    (out/'build.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return out,receipt


def serve(out,port,instance=None):
    handler=partial(SimpleHTTPRequestHandler,directory=str(out))
    server=ThreadingHTTPServer(('127.0.0.1',port),handler)
    url=f'http://127.0.0.1:{server.server_port}/'
    receipt=dict(pid=os.getpid(),url=url,port=server.server_port,directory=str(out),started=datetime.now().isoformat(),instance=instance)
    (out/'server.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt),flush=True)
    try:server.serve_forever()
    finally:server.server_close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'target/uav-dashboard')
    p.add_argument('--serve',action='store_true');p.add_argument('--port',type=int,default=0)
    p.add_argument('--instance')
    args=p.parse_args();out,receipt=build(args.output);print(json.dumps(receipt,indent=2),flush=True)
    if args.serve:serve(out,args.port,args.instance)


if __name__=='__main__':main()
