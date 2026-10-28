"""Produce a conservative result report only after full campaign verification has passed."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def report(root):
    m=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    v=json.loads((root/'verification.json').read_text(encoding='utf-8'))
    if m['status']!='COMPLETE' or v['status']!='PASS' or v['models']!=3 or v['audited_episodes']!=360:
        raise ValueError('All three full-budget models and 360 trace audits must be complete')
    summary=read(root/'summary.csv');runs=read(root/'runs.csv');episodes=read(root/'episodes.csv');counting=read(root/'slot-counting.csv')
    if len(episodes)!=360 or len(counting)!=360:raise ValueError('Unexpected count')
    partial=Counter()
    for r in counting:partial[r['policy']]+=int(r['partial_final_slot'])
    dqn=next(r for r in summary if r['policy']=='DQN')
    mean=float(dqn['mean_of_run_means']);gap=mean-18.3
    lines=['# Synthetic DQN reference: one scenario, three full-budget models','',
           'This campaign evaluates the paper-oriented 24D/12-action environment, not the mobile129D extension.',
           'All 3 models completed 1,000,000 steps and 249,975 optimizer updates each; all 360 evaluation traces passed independent replay.',
           '', '## Protocol and experimental units','',
           '- Synthetic 2–4 MB tasks; 12 devices, 8 powered / 8 connected, 800×800 m.',
           '- Learning/layout pairs: (0,0), (1,1), (2,2). Each model trains on one fixed layout.',
           '- Reference conventions: literal beta dBm; expiry at age>=10; legacy connected-or-completed-upload freshness; A/O captured before step and reward calculated after step; log epsilon1e-6.',
           '- Per model: validation task seeds1,000,000–1,000,004; 30 test task seeds2,000,000–2,000,029. Select the first best checkpoint by mean validation lifetime.',
           '- Test task seeds are held out from this training, but were used in previous developmental studies. They are not a newly sealed confirmatory test set.',
           '- Unit for across-run uncertainty: 3 learning/layout pairs, not 90 independent models/layouts. Learning and layout seed vary together, so their effects are not isolated.',
           '- Default automatic evaluation is repeated with complete traces on the same cases for auditing; duplicate evaluations are not additional samples.',
           '- No RescueNet, Alibaba, Google, C2A, finite CPU scheduling extension or cache in this campaign.','',
           '## Results','',
           '| Policy | Mean of 3 run means (slots) | SD across run means | Maximum observed slots | Mean simulated lifetime (s) |',
           '| --- | ---: | ---: | ---: | ---: |']
    for r in summary:
        lines.append(f"| {r['policy']} | {float(r['mean_of_run_means']):.3f} | {float(r['sd_of_run_means']):.3f} | {r['max_observed_slots']} | {float(r['mean_seconds']):.2f} |")
    lines += ['', '| Learning/layout seed | DQN mean slots | Round Robin | Oldest Data | Random | Best checkpoint step |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for seed in (0,1,2):
        scores={r['policy']:float(r['mean_slots']) for r in runs if int(r['training_seed'])==seed}
        proof=next(r for r in v['checkpoints'] if r['seed']==seed)
        lines.append(f"| {seed} | {scores['DQN']:.3f} | {scores['ROUND_ROBIN']:.3f} | {scores['OLDEST_DATA']:.3f} | {scores['RANDOM']:.3f} | {proof['best_steps']} |")
    lines += ['', '## Best checkpoint versus the end of training','',
              'The models were trained for the full budget, but the primary test uses the validation-selected checkpoint. A best checkpoint selected early is not evidence that the final policy has converged.',
              '', '| Seed | Best validation mean slots | Final validation mean slots at1m | Range of last10 validation means |',
              '| --- | ---: | ---: | --- |']
    for seed in (0,1,2):
        validation=read(root/f'seed-{seed}/validation.csv')
        progress=read(root/f'seed-{seed}/progress.csv')
        losses=[float(r['train/loss']) for r in progress if r.get('train/loss')]
        if not losses or not all(math.isfinite(x) for x in losses):
            raise ValueError(f'Missing/nonfinite logged optimizer loss for seed {seed}')
        best=max(float(r['mean_slots']) for r in validation if int(r['gradient_updates'])>0)
        final=float(validation[-1]['mean_slots']);last=[float(r['mean_slots']) for r in validation[-10:]]
        lines.append(f'| {seed} | {best:.3f} | {final:.3f} | {min(last):.3f}–{max(last):.3f} |')
    secondary=root/'secondary-final-evaluation'
    if (secondary/'protocol.json').exists():
        diagnostic=json.loads((secondary/'protocol.json').read_text())
        if diagnostic['status']!='COMPLETE' or diagnostic['audited_episodes']!=90:
            raise ValueError('Final-checkpoint diagnostic incomplete')
        lines += ['', 'Secondary test of the final1m checkpoint (90 DQN traces independently audited, the same task/layout cases as the primary comparison; not new independent samples):',
                  '', '| Seed | Best-validation checkpoint test mean | Final1m checkpoint test mean | Final − best (slots) |',
                  '| --- | ---: | ---: | ---: |']
        for r in read(secondary/'summary.csv'):
            lines.append(f"| {r['seed']} | {float(r['best_validation_checkpoint_test_mean']):.3f} | {float(r['final_mean_slots']):.3f} | {float(r['final_minus_best']):+.3f} |")
        lines += ['',f"Mean over the 3 final-checkpoint run means: **{diagnostic['mean_of_final_run_means']:.3f} slots**. This diagnostic does not replace validation-based checkpoint selection or establish convergence."]
    lines += ['', '## Comparison to the publication','',
              f'- Table5 at power8/comms8 reports mean18.3 slots; this campaign reports {mean:.3f}, an absolute difference of {gap:+.3f} slots ({gap/18.3*100:+.2f}%).',
              f"- Table6 reports maximum28 for DQN with the final reward at the same availability counts; the maximum observed here is {dqn['max_observed_slots']}. Table5 mean and Table6 maximum are different statistics and must not be interchanged.",
              '- Author seed identities and some transition/reward details are unavailable. Proximity to a table entry is descriptive; it is not a statistical equivalence test or proof of author-code equivalence.',
              '- Only one Table5 cell and one reward/algorithm are evaluated; full Table5/6 and SUMO are not reproduced.','',
              '## Termination and slot counting','',
              '- Primary metric includes the final attempted/partial slot, following the declared implementation convention.',
              '- `slot-counting.csv` also records physically fully elapsed slots; do not silently substitute it when comparing with the paper.','',
              '| Policy | Partial-final episodes /90 | Failure reason counts |','| --- | ---: | --- |']
    for policy in ('DQN','ROUND_ROBIN','OLDEST_DATA','RANDOM'):
        reasons=Counter(r['reason'] for r in episodes if r['policy']==policy)
        text='; '.join(f'{key.replace(chr(124), " / ")}: {value}' for key,value in sorted(reasons.items()))
        lines.append(f'| {policy} | {partial[policy]} | {text} |')
    lines += ['', '## Verification and practical limits','',
              '- Verified source hashes; full budget; finite weights and actual weight changes; checkpoint metadata; replay of best validation score; all action choices and all evaluation physics traces.',
              '- Independent replay checks Java task RNG, full-precision layout generation, slant channel, flight/hover, standby/active energy, battery failure, positions, freshness, expiry, rewards and summary metrics.',
              '- Each DQN action is checked by feeding the saved checkpoint a reconstructed pre-action24D state. This detects checkpoint/trace mismatches; it does not prove the learned policy is optimal.',
              '- Runtime below includes training+validation on concurrent local CPU processes, excluding build/audit and final evaluation. It is not comparable to the publication hardware.','',
              '| Seed | Training + validation (s) | Updates | Max absolute Q-weight change from initialization |',
              '| --- | ---: | ---: | ---: |']
    for proof in sorted(v['checkpoints'],key=lambda r:r['seed']):
        lines.append(f"| {proof['seed']} | {proof['elapsed_s']:.2f} | {proof['gradient_updates']} | {proof['max_abs_weight_change']:.6f} |")
    lines += ['', 'No significance or superiority claim is made from three training/layout pairs. Environment convention sensitivity remains a material limitation.',
              'Next: inspect per-layout failures and convergence, validate the effect of ambiguous freshness/reward semantics using prespecified retraining, then expand the Table5 grid if full reproduction is required.',
              '', 'Machine-readable evidence: `verification.json`, `runs.csv`, `summary.csv`, `paired-run-differences.csv`, `slot-counting.csv`; exact sources/protocol in `source/`.','']
    (root/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    receipt=dict(status='PASS',dqn_mean_slots=mean,difference_from_table5=gap,publication_mean_slots=18.3,
                 experimental_units=3,episodes=360,full_reproduction_claim=False,
                 report_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if (secondary/'protocol.json').exists():receipt['secondary_final_checkpoint_audits']=90
    script=root/'source/scripts/report-paper-reference.py'
    script.parent.mkdir(parents=True,exist_ok=True)
    script.write_bytes(Path(__file__).read_bytes())
    (root/'report-verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);a=p.parse_args()
    print(json.dumps(report(a.run.resolve()),indent=2))
