"""Independent final recount, source/model hashes and reused-model consistency checks."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def verify(root):
    m=json.loads((root/'manifest.json').read_text());v=json.loads((root/'verification.json').read_text());p=m['protocol']
    assert m['status']=='COMPLETE' and v['status']=='PASS'
    assert v['trained_new_models']==2 and v['reused_models']==1 and v['total_trace_audits']==270
    assert sorted((r['seed'],r['exit_code']) for r in m['runs'] if not r['reused'])==[(1,0),(2,0)]
    assert sum(r['reused'] for r in m['runs'])==1
    rows=read(root/'episodes.csv');assert len(rows)==270
    assert len({r['layout_sha256'] for r in rows})==1
    for proof in v['checkpoints']:
        source=Path(next(r['run'] for r in m['runs'] if r['seed']==proof['seed']))
        assert proof['layout_seed']==0 and proof['steps']==1000000 and proof['updates']==249975
        assert sha(source/'best_model.zip')==proof['best_sha256'] and sha(source/'final_model.zip')==proof['final_sha256']
    reused_cfg=json.loads((ROOT/p['reused_campaign']/p['reused_run']/'config.json').read_text())
    for run in m['runs']:
        cfg=json.loads((Path(run['run'])/'config.json').read_text())
        assert cfg['packages']==reused_cfg['packages'] and cfg['python']==reused_cfg['python'],'Runtime differs from reused run'
    for rel,h in m['source_sha256'].items():
        assert sha(root/'source'/rel)==h,rel
        if rel.endswith(('.py','.java')):assert sha(ROOT/rel)==h,rel
    keys={(r['policy'],r['checkpoint'],r['training_seed'],r['task_seed']) for r in rows};assert len(keys)==270
    for seed in (0,1,2):
        for cp in ('best','final'):
            g=[r for r in rows if r['policy']=='DQN' and int(r['training_seed'])==seed and r['checkpoint']==cp]
            assert len(g)==30 and {int(r['task_seed']) for r in g}==set(range(2000000,2000030))
    for policy in p['heuristics']:
        g=[r for r in rows if r['policy']==policy]
        assert len(g)==30 and {int(r['training_seed']) for r in g}=={-1}
    for r in read(root/'summary.csv'):
        if r['policy']=='DQN':
            means=[statistics.mean(int(x['slots']) for x in rows if x['policy']=='DQN' and int(x['training_seed'])==seed and x['checkpoint']==r['checkpoint']) for seed in (0,1,2)]
            assert math.isclose(float(r['mean_slots']),statistics.mean(means))
            assert math.isclose(float(r['sd_across_learning_run_means']),statistics.stdev(means))
        else:
            assert math.isclose(float(r['mean_slots']),statistics.mean(int(x['slots']) for x in rows if x['policy']==r['policy']))
    previous=ROOT/p['reused_campaign'];old=read(previous/'episodes.csv');old_final=read(previous/'secondary-final-evaluation/episodes.csv')
    parity=0
    for r in rows:
        if r['policy']=='DQN' and r['training_seed']=='0':
            reference=old if r['checkpoint']=='best' else old_final
            o=next(x for x in reference if x['policy']=='DQN' and x['training_seed']=='0' and x['task_seed']==r['task_seed'])
        elif r['policy']!='DQN':
            o=next(x for x in old if x['policy']==r['policy'] and x['training_seed']=='0' and x['task_seed']==r['task_seed'])
        else:continue
        assert r['slots']==o['slots'] and r['reason']==o['reason']
        assert math.isclose(float(r['seconds']),float(o['seconds']),abs_tol=1e-7)
        parity+=1
    assert parity==150
    receipt=dict(status='PASS',rows=270,unique_layouts=1,new_full_budget_runs=2,reused_full_budget_runs=1,
                 baseline_cases_not_duplicated=True,independent_summary_recount=True,checkpoint_source_hashes_verified=True,
                 runtime_versions_match_reused_run=True,
                 historical_episode_parity_cases=parity,script_sha256=sha(Path(__file__)))
    (root/'final-artifact-check.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    dest=root/'source/scripts/verify-paper-seed-isolation-artifacts.py';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(Path(__file__).read_bytes())
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('campaign',type=Path);a=p.parse_args()
    print(json.dumps(verify(a.campaign.resolve()),indent=2))
