"""Final stdlib artifact/count/hash and documentation-link check after campaign trace replay."""
import ast
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def verify(root):
    m=json.loads((root/'manifest.json').read_text());v=json.loads((root/'verification.json').read_text())
    post=json.loads((root/'postprocess-verification.json').read_text())
    assert m['status']=='COMPLETE' and v['status']==post['status']=='PASS'
    assert sorted((r['seed'],r['exit_code']) for r in m['runs'])==[(0,0),(1,0),(2,0)]
    rows=read(root/'episodes.csv');summary=read(root/'summary.csv');assert len(rows)==360
    for policy in ('DQN','ROUND_ROBIN','OLDEST_DATA','RANDOM'):
        means=[]
        for seed in (0,1,2):
            group=[r for r in rows if r['policy']==policy and int(r['training_seed'])==seed]
            assert len(group)==30 and {int(r['task_seed']) for r in group}==set(range(2000000,2000030))
            means.append(sum(int(r['slots']) for r in group)/len(group))
        out=next(r for r in summary if r['policy']==policy)
        assert math.isclose(float(out['mean_of_run_means']),sum(means)/3)
    for proof in v['checkpoints']:
        for filename,key in [('best_model.zip','best_sha256'),('final_model.zip','final_sha256')]:
            assert hashlib.sha256((root/f"seed-{proof['seed']}"/filename).read_bytes()).hexdigest()==proof[key]
    for rel,h in m['source_sha256'].items():
        assert hashlib.sha256((root/'source'/rel).read_bytes()).hexdigest()==h,rel
        if rel.endswith(('.py','.java')):assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==h,rel
    secondary=json.loads((root/'secondary-final-evaluation/protocol.json').read_text())
    assert secondary['status']=='COMPLETE' and secondary['audited_episodes']==90
    assert len(read(root/'secondary-final-evaluation/episodes.csv'))==90
    for f in ['PureEdgeSim/uav/PAPER_REFERENCE_RESULTS.md','PureEdgeSim/uav/PAPER_ALIGNMENT.md',
              'PureEdgeSim/uav/PROJECT_OVERVIEW.md','PureEdgeSim/uav/README.md','README.md']:
        p=ROOT/f;text=re.sub(r'```[\s\S]*?```','',p.read_text(encoding='utf-8'))
        missing=[s for s in re.findall(r'\]\(([^)]+)\)',text) if not re.match(r'https?://',s) and not (p.parent/s.split('#')[0]).exists()]
        assert not missing,(f,missing)
    for f in ('drl/paper_reference.py','drl/test_paper_reference.py','scripts/report-paper-reference.py',
              'scripts/evaluate-paper-final.py','scripts/finish-paper-reference.py'):
        ast.parse((ROOT/f).read_text(encoding='utf-8'))
    new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    trailing=[(f,i) for f in new for i,line in enumerate((ROOT/f).read_text(encoding='utf-8').splitlines(),1) if line.rstrip()!=line]
    assert not trailing,trailing
    receipt=dict(status='PASS',primary_rows=360,secondary_rows=90,independent_summary_recount=True,
                 checkpoint_hashes_verified=True,source_hashes_verified=True,doc_links_valid=True,
                 script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (root/'final-artifact-check.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    target=root/'source/scripts/verify-paper-reference-artifacts.py';target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(Path(__file__).read_bytes())
    return receipt


if __name__=='__main__':
    assert len(sys.argv)==2,'Usage: python scripts/verify-paper-reference-artifacts.py CAMPAIGN_DIR'
    print(json.dumps(verify(Path(sys.argv[1]).resolve()),indent=2))
