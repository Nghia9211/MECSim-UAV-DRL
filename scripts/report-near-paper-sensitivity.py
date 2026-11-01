"""Summarize and visualize completed locked near-paper sensitivity; no new simulations."""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics as st
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sensitivity_report_runner',ROOT/'scripts/near-paper-sensitivity.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
LABELS={'reference':'Reference: CPU 2 MB/s, deadline 600s, dwell 60s',
 'cpu-low':'CPU 0.5 MB/s','cpu-high':'CPU 8 MB/s','deadline-low':'Deadline 300s',
 'deadline-high':'Deadline 900s','dwell-low':'Dwell 15s','dwell-high':'Dwell 180s'}
def report(root,plot=True):
    p=s.validate(root);proof=json.loads((root/'verification.json').read_text())
    assert proof['status']=='PASS' and json.loads((root/'campaign-status.json').read_text())['status']=='COMPLETE'
    assert s.sha(root/'summary.csv')==proof['summary_sha256']
    assert s.sha(root/'episodes-core.csv')==proof['episode_metrics_sha256']
    rows=s.read(root/'summary.csv');table=[r for r in rows if r['layout']=='ALL']
    aggregate={(r['setting'],r['policy']):r for r in table}
    fmt=lambda x:'NA' if x in ('',None) else f'{float(x):.2f}'
    def param(factor,tag):
        anchor={'cpu':2,'deadline':600,'dwell':60}
        if tag=='reference':return anchor[factor]
        value=s.FACTORS[factor][1 if tag=='low' else 2]
        return value/1e6 if factor=='cpu' else value
    new_outcomes=0;proof_hashes={}
    for factor in p['phase_order']:
        r=json.loads((root/(factor+'-review.json')).read_text())
        assert s.sha(root/(factor+'-review.json'))==proof['phase_review_sha256'][factor]
        for key,hashes in r['case_proofs'].items():
            case=root/'runs'/key.split('/')[0]/('layout-'+key.split('/')[1])
            for name,h in hashes.items():assert s.sha(case/name)==h
            v=json.loads((case/'verification.json').read_text());new_outcomes+=v['task_outcomes']
            proof_hashes[key]=hashes
    # Runtime is kernel wall time, not policy decision latency. Keep the executed sample subset.
    runtime=[];queue=[]
    reference=Path(p['reference'])
    settings=['reference']+[f+'-'+tag for f in p['phase_order'] for tag in ('low','high')]
    for setting in settings:
        for layout in p['layouts']:
            case=reference/'runs'/f'layout-{layout}' if setting=='reference' else root/'runs'/setting/f'layout-{layout}'
            for r in s.read(case/'episodes.csv'):
                if int(r['seed']) in p['seeds'] and r['policy'] in p['policies']:
                    runtime.append(dict(setting=setting,layout=layout,seed=r['seed'],policy=r['policy'],wall_ms=r['wall_ms']))
                    d=case/r['scenario']/('seed-'+r['seed'])
                    jobs={j['id']:j for j in s.read(d/'workload.csv')}
                    outcomes={o['id']:o for o in s.read(d/(r['policy']+'-tasks.csv'))}
                    queue.append(dict(setting=setting,layout=layout,seed=r['seed'],policy=r['policy'],
                        **s.c.single_report.queue_counts(jobs,outcomes)))

    s.write(root/'queue-opportunities.csv',queue)
    s.write(root/'runtime-episodes.csv',runtime)
    runtime_summary=[]
    import math
    for setting in settings:
        for policy in p['policies']:
            values=sorted(float(r['wall_ms']) for r in runtime if r['setting']==setting and r['policy']==policy)
            runtime_summary.append(dict(setting=setting,policy=policy,cases=len(values),
                mean_wall_ms=st.mean(values),p95_wall_ms=values[math.ceil(.95*len(values))-1],
                scope='Java kernel wall time on local Windows; excludes startup IO audit; not per-decision latency'))
    s.write(root/'runtime.csv',runtime_summary)
    # Explain observed non-monotonic CPU effect without inventing a hardware claim.
    cpu_changes=[];visit_changes=0;cpu_gained=0;cpu_lost=0
    strong=p['policies'][2]
    for layout in p['layouts']:
        for seed in p['seeds']:
            a=reference/'runs'/f'layout-{layout}'/'primary'/f'seed-{seed}'
            b=root/'runs/cpu-high'/f'layout-{layout}'/'primary'/f'seed-{seed}'
            left={r['id']:r for r in s.read(a/(strong+'-tasks.csv'))}
            right={r['id']:r for r in s.read(b/(strong+'-tasks.csv'))}
            ga={r['id'] for r in s.read(a/(strong+'-updates.csv')) if left[r['id']]['status']=='COMPLETED_ON_TIME'}
            gb={r['id'] for r in s.read(b/(strong+'-updates.csv')) if right[r['id']]['status']=='COMPLETED_ON_TIME'}
            cpu_gained+=len(gb-ga);cpu_lost+=len(ga-gb)
            visit_changes+=int(s.read(a/(strong+'-visits.csv'))!=s.read(b/(strong+'-visits.csv')))
            for tid in left:
                if left[tid]['route']!=right[tid]['route']:
                    cpu_changes.append(dict(layout=layout,seed=seed,id=tid,reference_route=left[tid]['route'],
                        faster_cpu_route=right[tid]['route'],reference_status=left[tid]['status'],faster_cpu_status=right[tid]['status']))
    if cpu_changes:s.write(root/'cpu-high-route-changes.csv',cpu_changes)
    s.save(root/'cpu-nonmonotonic-diagnosis.json',dict(policy=strong,
        cpu_high_vs_reference_route_changes=len(cpu_changes),episodes_with_changed_visit_trace=visit_changes,
        delivered_gained=cpu_gained,delivered_lost=cpu_lost,
        scope='Observed paired trace changes; faster CPU also changes policy forecasts/routes and pinned contact itinerary. Not a monotonic-performance guarantee.'))
    lines=['# Sensitivity CPU, deadline và dwell — kết quả đầy đủ','',
        f"Hoàn tất tuần tự CPU → deadline → dwell. {p['new_episodes']} episode mới; {p['reused_episodes']} reference episode tái sử dụng; {new_outcomes} task outcomes mới, tất cả audit PASS.",
        f"{len(p['layouts'])} environments × {len(p['seeds'])} shared workload seeds × 3 policies. Không rerun reference; không cộng smoke vào full sample.",
        'Physical/radio/battery/arrival model giữ nguyên; CPU watts cố định 20 W khi đổi throughput. RR + EDF cố định.',
        'Các mức là giả định sensitivity, không phải số đo hardware hoặc SLA thực. Task synthetic 2–4 MB; không background/RescueNet inference.',
        '', '| Setting | Policy | Compute DVR % | Delivered DVR % | J/ảnh delivered | Mean/P95 delivered s | Total/UAV kJ | Delivered ontime | UAV censored/cases |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    settings=['reference']+[f+'-'+tag for f in p['phase_order'] for tag in ('low','high')]
    for setting in settings:
        for policy in p['policies']:
            r=aggregate[setting,policy]
            lines.append(f"| {LABELS[setting]} | {policy.replace('ROUND_ROBIN__','')} | {float(r['image_dvr'])*100:.2f} | {float(r['delivered_dvr'])*100:.2f} | {fmt(r['j_per_delivered'])} | {fmt(r['delivered_mean_latency_s'])}/{fmt(r['delivered_mean_episode_p95_s'])} | {float(r['total_energy_j'])/1000:.2f}/{float(r['uav_energy_j'])/1000:.2f} | {r['delivered_ontime_images']} | {r['censored_cases']}/{r['cases']} |")
    lines+=['','DVR macro mean theo episode; P95 là mean episode P95, gồm task muộn đã giao; không gán drops thành latency.',
        'J/ảnh = ratio tổng energy / tổng successes; pin chưa cạn ở horizon là censored. Background DVR NA.',
        'summary.csv có cả completed mean/P95, restricted UAV time, compute/delivery counts và từng environment.',
        '', '## Effect của tham số trên DEADLINE_ENERGY','',
        '| Factor | Mức | Δ delivered DVR vs reference, điểm % [CI 95%] | J/ảnh delivered |',
        '|---|---|---:|---:|']
    policy=p['policies'][2]
    for factor in p['phase_order']:
        contrasts=s.read(root/'phases'/factor/'contrasts.csv')
        for tag in ('low','high'):
            setting=factor+'-'+tag
            c=next(r for r in contrasts if r['kind']=='factor_effect' and r['candidate_setting']==setting and r['candidate_policy']==policy)
            a=aggregate[setting,policy]
            lines.append(f"| {factor} | {param(factor,tag)} | {100*float(c['delta']):.2f} [{100*float(c['ci95_low']):.2f}, {100*float(c['ci95_high']):.2f}] | {fmt(a['j_per_delivered'])} |")
    lines+=['','CI exploratory crossed bootstrap 5.000 lần trên environments và shared workload seeds. Không coi policy episodes độc lập; không multiple-testing-corrected confirmatory claims.',
        'Các phase/contrasts.csv còn chứa routing effect so với ALL_LOCAL và DEADLINE_ENERGY so với ALL_UAV cùng setting.',
        '', '## Cách đọc đúng','',
        f'CPU-high vs reference, DEADLINE_ENERGY: {len(cpu_changes)} route changes, {visit_changes} episode đổi visit trace, {cpu_gained} task được cứu và {cpu_lost} task mất delivered ontime. Không diễn giải CPU nhanh hơn là hardware kém đi.','',
        '- CPU: thay throughput UAV ở watts cố định; hiệu ứng nhỏ không có nghĩa CPU luôn vô ích ngoài grid/tải đã thử.',
        '- Deadline: nới deadline là thay yêu cầu chấp nhận task, không phải thuật toán chạy nhanh hơn. Latency trên tập completed có thể đổi vì censoring/selection.',
        '- Dwell: không chỉ thay thời gian chờ; nó đổi chu kỳ thăm, contact opportunity, flight/hover và upload pin stop. Không kết luận tiết kiệm compute từ toàn bộ energy change.',
        '- 10 environment seed còn thay hardware/vision task/pin/connectivity. Chưa có fresh holdout hay kết luận ngoài simulator.',
        '- Cơ chế local-result collection, downlink cost và shared bandwidth vẫn chưa được mô hình hóa.',
        '- Giữ baseline DEADLINE_ENERGY, không coi feasibility check có sẵn là novelty mới.',
        '', 'runtime.csv ghi wall time kernel Java trên máy local; không phải thời gian mỗi quyết định hoặc benchmark server. Reference timing tái sử dụng từ process cũ, không dùng để xếp hạng tốc độ giữa settings.',
        'Không thay cấu hình chính theo mức có metric đẹp nhất. Giữ reference làm mốc và dùng sensitivity để chọn giả thuyết cần kiểm chứng tiếp.']
    (root/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,3,figsize=(13,7),layout='constrained')
        colors=['#7f8c8d','#2980b9','#c06024']
        for col,factor in enumerate(p['phase_order']):
            tags=['low','reference','high'];xs=[param(factor,t) for t in tags]
            keys=[factor+'-low','reference',factor+'-high']
            for policy,color in zip(p['policies'],colors):
                rr=[aggregate[k,policy] for k in keys]
                for row,metric,mult in [(0,'delivered_dvr',100),(1,'j_per_delivered',.001)]:
                    yy=[float(r[metric])*mult if r[metric] else float('nan') for r in rr]
                    axes[row,col].plot(range(3),yy,marker='o',label=policy.replace('ROUND_ROBIN__','').replace('__EDF',''),color=color)
                    axes[row,col].set_xticks(range(3),[str(x) for x in xs])
                    axes[row,col].grid(alpha=.2);axes[row,col].spines[['top','right']].set_visible(False)
            axes[0,col].set_title(factor.upper()+' sensitivity')
            axes[1,col].set_xlabel({'cpu':'UAV throughput (MB/s), fixed 20W','deadline':'Deadline budget (s)','dwell':'Minimum dwell (s)'}[factor])
        axes[0,0].set_ylabel('Delivered DVR (%)')
        axes[1,0].set_ylabel('System kJ / on-time delivered image')
        axes[0,0].legend(frameon=False,fontsize=8)
        fig.suptitle('One-factor-at-a-time; same 10 environments x 30 workloads; synthetic near-paper model')
        fig.savefig(root/'sensitivity.png',dpi=170);fig.savefig(root/'sensitivity.svg');plt.close(fig)
    s.save(root/'analysis-provenance.json',dict(status='ANALYZED_VERIFIED_SENSITIVITY',
        new_task_outcomes=new_outcomes,script_sha256=s.sha(Path(__file__)),plan_sha256=s.sha(root/'plan.json'),
        proof_sha256=s.sha(root/'verification.json'),case_proofs=proof_hashes,
        output_sha256={name:s.sha(root/name) for name in ['RESULTS.md','sensitivity.png','sensitivity.svg'] if (root/name).exists()}))
    return dict(new_task_outcomes=new_outcomes,settings=len(settings),summary_rows=len(rows))
if __name__=='__main__':
    q=argparse.ArgumentParser(description=__doc__);q.add_argument('root',type=Path);q.add_argument('--no-plot',action='store_true')
    a=q.parse_args();print(json.dumps(report(a.root,not a.no_plot),indent=2))
