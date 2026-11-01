"""Post-run explanation and plot for verified multi-environment baselines.
Descriptive analysis, not a pre-registered algorithm proposal or additional simulation.
"""
import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
def module(name,file):
    s=importlib.util.spec_from_file_location(name,ROOT/'scripts'/file)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
campaign=module('explain_campaign','near-paper-layouts.py')
read=campaign.read;write=campaign.write;sha=campaign.sha
def analyze(root,plot=True):
    plan=campaign.validate_lock(root);proof=json.loads((root/'verification.json').read_text())
    assert proof['status']=='PASS' and json.loads((root/'campaign-status.json').read_text())['status']=='COMPLETE'
    inputs={};harm_rows=[];changes=Counter();energy=[]
    def source(p):
        inputs[str(p.relative_to(root)).replace('\\','/')]=sha(p);return read(p)
    for layout in plan['layout_seeds']:
        case=root/'runs'/f'layout-{layout}';m=json.loads((case/'manifest.json').read_text());cfg=m['configs']['primary']
        cp=proof['case_proofs'][str(layout)]
        for name,key in [('manifest.json','manifest_sha256'),('verification.json','verification_sha256'),('core-metrics-episodes.csv','core_metrics_sha256')]:
            assert sha(case/name)==cp[key],f'Case proof drift {layout} {name}'
        for seed in plan['task_seeds']:
            d=case/'primary'/f'seed-{seed}';jobs={r['id']:r for r in source(d/'workload.csv')}
            base={r['id']:r for r in source(d/(campaign.BASE+'-tasks.csv'))}
            base_delivered={r['id'] for r in source(d/(campaign.BASE+'-updates.csv'))}
            base_good={k for k in base_delivered if base[k]['status']=='COMPLETED_ON_TIME'}
            for policy in plan['policies'][1:]:
                out={r['id']:r for r in source(d/(policy+'-tasks.csv'))}
                coverage={r['id']:r for r in source(d/(policy+'-coverage.csv'))}
                delivered={r['id'] for r in source(d/(policy+'-updates.csv'))}
                good={k for k in delivered if out[k]['status']=='COMPLETED_ON_TIME'}
                assert set(jobs)==set(base)==set(out)
                for tid,j in jobs.items():
                    state='retained_success' if tid in good and tid in base_good else 'rescued' if tid in good else 'harmed' if tid in base_good else 'failed_both'
                    changes[policy,state]+=1
                    if state=='harmed':
                        a,b=base[tid],out[tid];c=coverage.get(tid,{})
                        diagnosis=campaign.diagnostic.classify(j,b,c,tid in delivered,cfg)
                        budget=float(j['deadline_s'])-float(j['arrival_s'])
                        harm_rows.append(dict(layout_seed=layout,seed=seed,policy=policy,id=tid,device=j['device'],
                            status=b['status'],route=b['route'],diagnosis=diagnosis,budget_s=budget,
                            local_alone_s=float(j['actual_mi'])/cfg['devices'][int(j['device'])]['mips'],
                            original_local_latency_s=float(a['resolved_s'])-float(j['arrival_s']),
                            planned_upload_s=c.get('planned_upload_s',''),
                            planned_contact_wait_s=float(c['planned_upload_start_s'])-float(j['arrival_s']) if c else '',
                            slant_m=c.get('planned_slant_m',''),
                            connected=cfg['sites'][int(j['device'])]['connected']))
        for row in source(case/'diagnosis/energy-components.csv'):
            energy.append(dict(layout_seed=layout,**row))
    out=root/'analysis';out.mkdir(exist_ok=True)
    counts=[dict(policy=p,**{k:changes[p,k] for k in ('retained_success','rescued','harmed','failed_both')}) for p in plan['policies'][1:]]
    write(out/'paired-policy-task-changes.csv',counts);write(out/'harmed-tasks.csv',harm_rows)
    write(out/'energy-components.csv',energy)
    rows=source(root/'summary.csv')
    lines=['# Diễn giải bổ sung sau campaign','',
        'Phân tích mô tả từ trace đã verified, không chạy thêm simulator, không phải protocol chọn thuật toán mới.',
        '', '| Candidate vs ALL_LOCAL | Retained success | Rescued | Harmed | Failed both |',
        '|---|---:|---:|---:|---:|']
    for r in counts:
        lines.append('| '+r['policy'].replace('ROUND_ROBIN__','')+' | '+' | '.join(str(r[k]) for k in ('retained_success','rescued','harmed','failed_both'))+' |')
    reasons=Counter(r['diagnosis'] for r in harm_rows if r['policy']=='ROUND_ROBIN__ALL_UAV__EDF')
    lines+=['','## Khi nào ALL_UAV gây hại?','']
    for key,n in sorted(reasons.items()):lines.append(f'- {key}: {n} task occurrences.')
    lines+=['','Harmed = cùng task đã được ALL_LOCAL giao đúng hạn nhưng candidate không giao đúng hạn. Rescued là chiều ngược lại.',
        'Không phải cùng ảnh thật được quan sát 10 lần độc lập: đây là cùng workload trên 10 môi trường khác nhau.',
        'Nhóm nguyên nhân dùng lower-bound thời gian thực theo route, không khẳng định nguyên nhân nhân quả duy nhất.',
        '', '## Phân rã năng lượng của ALL_LOCAL và ALL_UAV','',
        '| Mean/episode | ALL_LOCAL J | ALL_UAV J | Δ J |','|---|---:|---:|---:|']
    for key in ('flight_j','hover_j','uav_compute_j','ground_idle_j','ground_compute_j','ground_tx_j','total_j'):
        a=statistics.mean(float(e[key]) for e in energy if e['policy']==campaign.BASE)
        b=statistics.mean(float(e[key]) for e in energy if e['policy']=='ROUND_ROBIN__ALL_UAV__EDF')
        lines.append(f'| {key} | {a:.3f} | {b:.3f} | {b-a:.3f} |')
    lines+=['','Flight/hover là thay thế cho UAV idle_j khi phân rã, không cộng hai lần.',
        'Hiệu quả năng lượng gồm thay đổi thời gian dừng/đường bay; chưa tách isolated compute effect.',
        '', '## Quyết định bước tiếp','',
        'Có bằng chứng robustness của việc cho phép offloading so với chỉ local trong các môi trường đã lấy mẫu.',
        'Tuy nhiên ALL_UAV không phải cơ chế tốt nhất ở mọi chỉ tiêu; cần so với baseline có deadline/energy trước khi tuyên bố cải tiến.',
        'DEADLINE_ENERGY và DELIVERY_AWARE có cùng core metrics ở campaign này; không xem đó là hai bằng chứng độc lập.',
        'Kiểm tra sensitivity CPU/deadline/dwell trước, giữ scheduler EDF. Không coi kiểm tra deadline upload đơn giản là novelty: baseline hiện có đã dùng dự đoán finish/feasibility.',
        'Chưa train DQN, chưa làm cache, chưa có inference RescueNet. Chưa suy ra tăng lifetime khi mọi UAV còn sống đến horizon.']
    (out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        layouts=plan['layout_seeds'];x=list(range(len(layouts)))
        a=[next(float(r['delivered_dvr'])*100 for r in rows if r['layout_seed']==str(l) and r['policy']==campaign.BASE) for l in layouts]
        b=[next(float(r['delivered_dvr'])*100 for r in rows if r['layout_seed']==str(l) and r['policy']=='ROUND_ROBIN__ALL_UAV__EDF') for l in layouts]
        fig,axes=plt.subplots(1,2,figsize=(12,4.4),layout='constrained')
        axes[0].bar([v-.18 for v in x],a,width=.36,label='ALL_LOCAL + EDF',color='#6c7a89')
        axes[0].bar([v+.18 for v in x],b,width=.36,label='ALL_UAV + EDF',color='#2274a5')
        axes[0].set_ylabel('Delivered deadline violation (%)')
        axes[0].set_ylim(0,100);axes[0].legend(frameon=False,fontsize=9)
        axes[1].bar(x,[bb-aa for aa,bb in zip(a,b)],color='#2274a5')
        axes[1].axhline(0,color='black',linewidth=.8)
        axes[1].set_ylabel('ALL_UAV - ALL_LOCAL (percentage points)')
        for ax in axes:
            ax.set_xticks(x,[str(l) for l in layouts]);ax.set_xlabel('Paper environment seed')
            ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        axes[0].set_title('Per-environment mean across 30 workload seeds')
        axes[1].set_title('Paired reduction in delivered DVR')
        fig.suptitle('Near-paper synthetic workload; fixed RR + EDF; exploratory baseline')
        fig.savefig(out/'layout-dvr.png',dpi=170);fig.savefig(out/'layout-dvr.svg');plt.close(fig)
    inputs['verification.json']=sha(root/'verification.json');inputs['plan.json']=sha(root/'plan.json')
    campaign.save(out/'provenance.json',dict(status='ANALYZED_VERIFIED_TRACES',source_root=str(root),
        analysis_script_sha256=sha(Path(__file__)),input_sha256=inputs,
        output_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='provenance.json'}))
    return dict(all_uav_harm_reasons=dict(reasons),policy_counts=counts)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--no-plot',action='store_true')
    a=p.parse_args();print(json.dumps(analyze(a.root,not a.no_plot),indent=2))
