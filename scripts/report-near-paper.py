"""Report a completed independently verified near-paper pilot. No fitting or scenario selection."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as st

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,rows):
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def number(r,k):return float(r[k]) if r[k] else None
def queue_counts(jobs,out):
    air=[k for k,o in out.items() if o['route'] in ('UAV','BACKGROUND')]
    def finite(o,k):return bool(o[k]) and math.isfinite(float(o[k]))
    starts=[(float(out[k]['start_s']),k) for k in air if finite(out[k],'start_s')]
    ready=[]
    for at,chosen in starts:
        ready.append(sum(float(jobs[k]['arrival_s'])<=at+1e-8 and float(out[k]['ready_s'])<=at+1e-8
            and float(jobs[k]['deadline_s'])>at+1e-8 and float(out[k]['resolved_s'])>=at-1e-8
            and (k==chosen or not finite(out[k],'start_s') or float(out[k]['start_s'])>at+1e-8) for k in air))
    return dict(uav_dispatches=len(starts),multi_ready_dispatches=sum(n>=2 for n in ready),max_ready=max(ready,default=0))
def report(root):
    m=json.loads((root/'manifest.json').read_text());v=json.loads((root/'verification.json').read_text())
    assert m['status']=='COMPLETE' and v['status']=='PASS'
    rows=read(root/'core-metrics-episodes.csv');summaries=read(root/'core-metrics-summary.csv')
    diagnostics=[]
    for r in rows:
        d=root/r['scenario']/('seed-'+r['seed']);prefix=r['policy']
        jobs={j['id']:j for j in read(d/'workload.csv')}
        out={o['id']:o for o in read(d/(prefix+'-tasks.csv'))}
        diagnostics.append(dict(scenario=r['scenario'],seed=r['seed'],policy=prefix,**queue_counts(jobs,out)))
    write(root/'queue-opportunities.csv',diagnostics)
    contrasts=[];ref='ROUND_ROBIN__ALL_LOCAL__EDF'
    for scenario in sorted(m['configs']):
        indexed={(r['policy'],r['seed']):r for r in rows if r['scenario']==scenario}
        for baseline,policy in [(ref,'ROUND_ROBIN__ALL_UAV__EDF'),
                ('ROUND_ROBIN__ALL_UAV__FIFO','ROUND_ROBIN__ALL_UAV__EDF'),
                ('ROUND_ROBIN__ALL_UAV__FIFO','ROUND_ROBIN__ALL_UAV__RISK_EDF')]:
            pairs=[(indexed[baseline,str(seed)],indexed[policy,str(seed)]) for seed in m['task_seeds']]
            check_hash=all(a['workload_sha256']==b['workload_sha256'] for a,b in pairs)
            assert check_hash
            for key in ('delivered_image_dvr','image_dvr'):
                ds=[float(b[key])-float(a[key]) for a,b in pairs]
                rand=random.Random(1729);boot=sorted(st.mean(rand.choices(ds,k=len(ds))) for _ in range(5000))
                contrasts.append(dict(scenario=scenario,baseline=baseline,candidate=policy,metric=key,seeds=len(ds),
                    delta=st.mean(ds),ci95_low=boot[124],ci95_high=boot[4874],method='paired workload-seed bootstrap 5000, exploratory'))
    write(root/'paired-contrasts.csv',contrasts)
    f=lambda x:'NA' if x in ('',None) else f'{float(x):.2f}'
    lines=['# Scenario gần paper: kết quả baseline','',
        'Đây là pilot mở rộng continuous-time, không phải tái hiện kết quả DQN/lifetime của paper.',
        f"Đã audit PASS: {v['episodes']} episode; {v['task_outcomes']} task outcomes; {m['seeds']} workload seed trên một layout cố định.",
        'Task ảnh synthetic 2–4 MB; không phải benchmark inference RescueNet. Alibaba, nếu bật, là tải nền theo proxy CPU, không replay trace nguyên bản.',
        'Các seed chỉ thay workload; chưa chứng minh khả năng tổng quát qua layout. CI dưới đây là exploratory; không dùng kết quả này để tuyên bố SOTA.',
        '', '| Scenario | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered đúng hạn | Delivered latency mean / P95 s | Total / UAV kJ | Offload/episode |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in summaries:
        if r['scenario']=='ALL':continue
        lines.append(f"| {r['scenario']} | {r['policy'].replace('ROUND_ROBIN__','')} | {f(100*float(r['image_dvr']))} | {f(100*float(r['delivered_image_dvr']))} | {f(r['j_per_delivered_ontime_image'])} | {f(r['mean_delivered_latency_s'])} / {f(r['mean_delivered_episode_p95_s'])} | {f(float(r['mean_total_j'])/1000)} / {f(float(r['mean_uav_j'])/1000)} | {f(r['mean_offloaded_images'])} |")
    lines+=['','Mean/P95 chỉ tính ảnh đã hoàn thành/giao được, có cả ảnh muộn. P95 là trung bình P95 từng episode, không phải pooled P95.',
        'J/ảnh là tổng năng lượng toàn hệ thống chia tổng ảnh giao đúng hạn. Drops vẫn tính là thất bại.','',
        '| Scenario | So sánh | Δ delivered DVR, điểm % [CI 95%] |',
        '|---|---|---:|']
    for r in contrasts:
        if r['metric']=='delivered_image_dvr':
            lines.append(f"| {r['scenario']} | {r['candidate'].replace('ROUND_ROBIN__','')} − {r['baseline'].replace('ROUND_ROBIN__','')} | {100*r['delta']:.2f} [{100*r['ci95_low']:.2f}, {100*r['ci95_high']:.2f}] |")
    lines+=['','Δ âm là giảm lỗi. So sánh offloading giữ EDF; so sánh scheduler giữ ALL_UAV. Cùng workload hash trong từng cặp.',
        '', '| Scenario, ALL_UAV+EDF | Dispatch có ≥2 task ready / tất cả dispatch | Background DVR | UAV censored / tổng |',
        '|---|---:|---:|---:|']
    for scenario in sorted(m['configs']):
        group=[d for d in diagnostics if d['scenario']==scenario and d['policy']=='ROUND_ROBIN__ALL_UAV__EDF']
        r=next(r for r in summaries if r['scenario']==scenario and r['policy']=='ROUND_ROBIN__ALL_UAV__EDF')
        lines.append(f"| {scenario} | {sum(d['multi_ready_dispatches'] for d in group)} / {sum(d['uav_dispatches'] for d in group)} | {f(None if not r['background_dvr'] else 100*float(r['background_dvr']))}% | {r['censored_cases']} / {r['cases']} |")
    lines+=['','Không suy ra tăng lifetime khi pin chưa cạn trước horizon. UAV time bị censor là cận dưới, không phải thời điểm hết pin.',
        'Giới hạn: một layout; các tham số deadline/CPU UAV là giả định; radio beta0 còn mơ hồ; chưa chia sẻ bandwidth; chưa có downlink cost hay thu gom kết quả local khi nguồn mất kết nối.',
        '', 'Xem cấu hình và ranh giới paper/phần mở rộng tại PureEdgeSim/uav/NEAR_PAPER_SCENARIO.md.',
        'Nguồn: manifest.json, verification.json, core-metrics-episodes.csv, core-metrics-summary.csv, paired-contrasts.csv và queue-opportunities.csv.']
    (root/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    return contrasts
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);args=p.parse_args()
    report(args.root);print(args.root/'RESULTS.md')
