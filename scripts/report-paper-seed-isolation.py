"""Compare the fixed-layout diagnostic with the earlier coupled learning/layout experiment."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def report(root):
    m=json.loads((root/'manifest.json').read_text());v=json.loads((root/'verification.json').read_text())
    check=json.loads((root/'final-artifact-check.json').read_text())
    assert m['status']=='COMPLETE' and v['status']==check['status']=='PASS'
    p=m['protocol'];runs=read(root/'runs.csv');summary=read(root/'summary.csv');old=read(ROOT/p['reused_campaign']/'runs.csv')
    comparisons=[]
    for seed in (0,1,2):
        previous=next(r for r in old if int(r['training_seed'])==seed and r['policy']=='DQN')
        best=next(r for r in runs if int(r['seed'])==seed and r['checkpoint']=='best')
        final=next(r for r in runs if int(r['seed'])==seed and r['checkpoint']=='final')
        comparisons.append(dict(learning_seed=seed,old_layout_seed=seed,fixed_layout_seed=0,
                                old_best_mean_slots=float(previous['mean_slots']),fixed_best_mean_slots=float(best['mean_slots']),
                                fixed_final_mean_slots=float(final['mean_slots']),
                                fixed_minus_old=float(best['mean_slots'])-float(previous['mean_slots'])))
    with (root/'matched-learning-seed-layout-comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=comparisons[0]);writer.writeheader();writer.writerows(comparisons)
    before_sd=statistics.stdev(r['old_best_mean_slots'] for r in comparisons)
    after_sd=statistics.stdev(r['fixed_best_mean_slots'] for r in comparisons)
    lines=['# Kết quả đối chứng seed huấn luyện trên layout0','',
           '**Đã hoàn tất và kiểm chứng:**2model train mới ×1triệu bước, dùng lại1model seed0/layout0 đã audit;270trace được replay độc lập.',
           'Geometry, hardware/task type, capacity và outage masks cùng layout0. Không đổi radio, expiry, reward, deadline/CPU model hoặc hyperparameters của paper.','',
           '| Learning seed | Trước: layout riêng, best mean slots | Cùng layout0: best mean slots | Cùng layout0: final1m mean slots |',
           '| --- | ---: | ---: | ---: |']
    for r in comparisons:
        lines.append(f"| {r['learning_seed']} | {r['old_best_mean_slots']:.3f} | {r['fixed_best_mean_slots']:.3f} | {r['fixed_final_mean_slots']:.3f} |")
    lines+=['',f'SD giữa3run means của thí nghiệm thay cả learning/layout: **{before_sd:.3f}slot**. SD giữa3run means trên cùng layout0: **{after_sd:.3f}slot**.',
            'Đây là hai mô tả trên mẫu development nhỏ, không phải phân rã phương sai hoặc ước lượng tỷ lệ biến thiên do layout. Các bố trí trước khác cả hardware, task, battery và masks, không chỉ tọa độ.',
            '', '| Policy/checkpoint | Mean slots | SD giữa learning-run means | Số episode trong bảng |','| --- | ---: | ---: | ---: |']
    for r in summary:
        sd=r['sd_across_learning_run_means'];sd=f'{float(sd):.3f}' if sd else 'không áp dụng'
        lines.append(f"| {r['policy']} / {r['checkpoint']} | {float(r['mean_slots']):.3f} | {sd} | {r['episodes']} |")
    lines+=['','## Diễn giải được phép','',
            '- Có thể mô tả mức biến thiên do cả quá trình học có điều kiện trên layout0; không phải độ bất ổn trên mọi layout.',
            '- Learning seed còn thay exploration, minibatches và training task sequence. Chưa tách riêng weight initialization.',
            '- Best checkpoint theo validation5case, không chọn bằng test30case. Final1m là diagnostic bổ sung trên cùng case.',
            '- Baseline chỉ lấy một lần/case trong bảng chính; không nhân mẫu theo số learner. Automatic evaluation của trainer có case trùng nhưng không được tính thêm.',
            '- Seed0/layout0 được dùng lại và đã quan sát; layout0 không là tập test mới hoặc một layout đại diện được chọn mù.',
            '- Kết quả này không xác nhận full-paper reproduction, superiority có ý nghĩa thống kê hoặc generalization. Không chọn convention để ép khớp Table5.',
            '', '## Evidence','',
            '- `verification.json`:270physical/action replay audits;2new +1reused model đủ1m/249.975updates.',
            '- `final-artifact-check.json`: summary recount, checkpoint/source hashes, runtime-version parity,150historical episode parity cases.',
            '- `episodes.csv`, `runs.csv`, `summary.csv`, `fixed-layout.json`, `slot-counting.csv` và source snapshot.',
            '- `matched-learning-seed-layout-comparison.csv`: so cùng learning seed giữa hai thiết kế; không gọi là ablation chỉ thay position.',
            '', 'Bước kế tiếp đã được viết riêng trong PAPER_RETRAIN_PLAN.md: retrain từng quy ước reward/freshness có kiểm soát; chưa có model của các biến thể đó trong đợt này.','']
    (root/'COMPARISON_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    receipt=dict(status='PASS',coupled_run_mean_sd=before_sd,fixed_layout_learning_mean_sd=after_sd,
                 learning_seed_effect_is_conditional=True,variance_decomposition_claim=False,
                 script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (root/'comparison-report-verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    dest=root/'source/scripts/report-paper-seed-isolation.py';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(Path(__file__).read_bytes())
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('campaign',type=Path);args=parser.parse_args()
    print(json.dumps(report(args.campaign.resolve()),indent=2))
