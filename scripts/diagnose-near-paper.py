"""Read existing verified near-paper traces: paired task changes and exclusive diagnostic bounds.
No rerun, no counterfactual simulator; categories describe the executed route only.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def classify(j,o,c,delivered,cfg):
    """Exclusive descriptive diagnosis, not proof of a unique causal failure."""
    budget=float(j['deadline_s'])-float(j['arrival_s'])
    if o['status']=='COMPLETED_ON_TIME':
        return 'delivered_ontime' if delivered else 'local_ontime_undelivered'
    if 'BATTERY' in o['status']:return 'battery_failure'
    if o['route']=='UNDECIDED':return 'no_route'
    if o['route']=='LOCAL':
        compute=float(j['actual_mi'])/cfg['devices'][int(j['device'])]['mips']
        if compute>budget+1e-8:return 'local_intrinsic_compute_exceeds_budget'
        return 'local_wait_or_execution_failure'
    if o['route']=='UAV':
        upload=float(c['planned_upload_s']);compute=float(j['actual_mi'])/cfg['uavMips']
        wait=float(c['planned_upload_start_s'])-float(j['arrival_s'])
        if upload>budget+1e-8:return 'uav_upload_alone_exceeds_budget'
        if wait+upload+compute>budget+1e-8:return 'uav_contact_upload_compute_exceeds_budget'
        return 'uav_queue_or_execution_failure'
    return 'other_failure'
def diagnose(root,scenario='primary'):
    root=Path(root);m=json.loads((root/'manifest.json').read_text())
    proof=json.loads((root/'verification.json').read_text());assert proof['status']=='PASS' and m['status']=='COMPLETE'
    cfg=m['configs'][scenario];image_rows=[];pairs=[];energy=[];provenance={}
    policies=['ROUND_ROBIN__ALL_LOCAL__EDF','ROUND_ROBIN__ALL_UAV__EDF']
    counts=Counter()
    def inputs(p):provenance[str(p.relative_to(root)).replace('\\','/')]=sha(p);return read(p)
    for seed in m['task_seeds']:
        d=root/scenario/f'seed-{seed}';jobs={j['id']:j for j in inputs(d/'workload.csv')};success={}
        for policy in policies:
            outcomes={o['id']:o for o in inputs(d/(policy+'-tasks.csv'))}
            coverage={c['id']:c for c in inputs(d/(policy+'-coverage.csv'))}
            updates={u['id'] for u in inputs(d/(policy+'-updates.csv'))}
            decision={c['id']:c for c in inputs(d/(policy+'-decisions.csv'))}
            success[policy]={k for k in updates if outcomes[k]['status']=='COMPLETED_ON_TIME'}
            en=inputs(d/(policy+'-energy.csv'));uav=next(e for e in en if e['device']=='-1')
            row=next(r for r in inputs(root/'episodes.csv') if r['scenario']==scenario and r['seed']==str(seed) and r['policy']==policy)
            ground=[e for e in en if e['device']!='-1']
            e=dict(seed=seed,policy=policy,flight_j=float(row['flight_j']),hover_j=float(row['hover_j']),
                uav_compute_j=float(uav['compute_j']),uav_tx_j=float(uav['tx_j']),
                ground_idle_j=sum(float(x['idle_j']) for x in ground),
                ground_compute_j=sum(float(x['compute_j']) for x in ground),ground_tx_j=sum(float(x['tx_j']) for x in ground))
            total=sum(v for k,v in e.items() if k.endswith('_j'))
            assert math.isclose(total,float(row['total_energy_j']),rel_tol=1e-9)
            e.update(total_j=total,travelled_m=float(row['travelled_m']));energy.append(e)
            for tid,j in jobs.items():
                if j['source'] not in ('SYNTHETIC_IMAGE','RESCUENET'):continue
                o=outcomes[tid];c=coverage.get(tid);category=classify(j,o,c,tid in updates,cfg)
                counts[policy,category]+=1
                image_rows.append(dict(seed=seed,policy=policy,id=tid,device=j['device'],route=o['route'],
                    status=o['status'],connected=cfg['sites'][int(j['device'])]['connected'],
                    delivered_ontime=int(tid in success[policy]),diagnosis=category,
                    contact_eligible=(c or {}).get('offload_available',''),
                    budget_s=float(j['deadline_s'])-float(j['arrival_s']),
                    isolated_local_compute_s=float(j['actual_mi'])/cfg['devices'][int(j['device'])]['mips'],
                    local_estimated_finish_s=decision.get(tid,{}).get('local_finish_s',''),
                    uav_estimated_finish_s=decision.get(tid,{}).get('uav_finish_s','')))
        a,b=success[policies[0]],success[policies[1]]
        for tid,j in jobs.items():
            if j['source'] not in ('SYNTHETIC_IMAGE','RESCUENET'):continue
            state='retained_success' if tid in a and tid in b else 'rescued' if tid in b else 'harmed' if tid in a else 'failed_both'
            pairs.append(dict(seed=seed,id=tid,device=j['device'],change=state))
    out=root/'diagnosis';out.mkdir(exist_ok=True)
    write(out/'images.csv',image_rows);write(out/'paired-images.csv',pairs);write(out/'energy-components.csv',energy)
    pair_counts=Counter(r['change'] for r in pairs)
    lines=['# Phân tích trace hiện có: không chạy lại mô phỏng','',
        f"Run: {root.as_posix()}; scenario {scenario}; {len(m['task_seeds'])} workload seed, layout {m['protocol']['layoutSeed']}.",
        'Đơn vị đếm là task occurrence (seed, id), không phải ảnh thật độc lập.',
        '', '| So với ALL_LOCAL | Task occurrences |','|---|---:|']
    for k in ['retained_success','rescued','harmed','failed_both']:lines.append(f'| {k} | {pair_counts[k]} |')
    lines+=['','Rescued/harmed là chênh lệch paired của toàn policy: có thể bao gồm ảnh hưởng lên queue và contact sau đó; không chứng minh riêng tác động CPU offload.',
        '', '| Policy | Phân loại độc quyền | Task occurrences |','|---|---|---:|']
    for (policy,category),n in sorted(counts.items()):lines.append(f"| {policy.replace('ROUND_ROBIN__','')} | {category} | {n} |")
    lines+=['','Phân loại là kiểm tra lower bound thời gian theo route đã thực thi, không khẳng định một nguyên nhân nhân quả duy nhất.',
        'Ảnh local đúng hạn nhưng nguồn disconnected không được tính là giao thành công. Model chưa thu gom kết quả local về sau.',
        '', '| Năng lượng mean/episode | ALL_LOCAL J | ALL_UAV J | Δ J |','|---|---:|---:|---:|']
    for key in [k for k in energy[0] if k.endswith('_j')]:
        means=[sum(e[key] for e in energy if e['policy']==p)/len(m['task_seeds']) for p in policies]
        lines.append(f'| {key} | {means[0]:.3f} | {means[1]:.3f} | {means[1]-means[0]:.3f} |')
    lines+=['','Flight và hover được tách khỏi UAV idle_j trước khi cộng, không cộng hai lần.',
        'Quyết định offload có thể pin stop lâu hơn, làm thay đổi flight/hover; không gọi toàn bộ chênh lệch năng lượng là tiết kiệm compute.',
        'Không cần rerun baseline cũ. Giữ các trace gốc và hashes đầu vào để truy ngược.']
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    (out/'provenance.json').write_text(json.dumps(dict(status='ANALYZED_VERIFIED_EXISTING_TRACES',source_run=str(root),
        manifest_sha256=sha(root/'manifest.json'),verification_sha256=sha(root/'verification.json'),
        script_sha256=sha(Path(__file__)),input_sha256=provenance,paired_task_changes=dict(pair_counts)),indent=2)+'\n',encoding='utf8')
    return dict(pair_counts)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--scenario',default='primary')
    a=p.parse_args();print(json.dumps(diagnose(a.root,a.scenario),indent=2))
