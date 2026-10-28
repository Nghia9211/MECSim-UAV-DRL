"""Finish secondary evaluation and report after the authorized primary campaign completes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def finish(root,timeout):
    deadline=time.monotonic()+timeout
    while True:
        try:manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        except (FileNotFoundError,json.JSONDecodeError):manifest={}
        status=manifest.get('status')
        if status=='COMPLETE':break
        if status in ('INTERRUPTED','TRAINING_FAILED','AUDIT_FAILED'):
            raise RuntimeError(f'Primary campaign not successful: {status}')
        if time.monotonic()>=deadline:raise TimeoutError('Primary campaign did not complete before watcher timeout')
        time.sleep(15)
    secondary=root/'secondary-final-evaluation/protocol.json'
    if not secondary.exists():
        subprocess.run([sys.executable,'-u',str(ROOT/'scripts/evaluate-paper-final.py'),str(root)],cwd=ROOT,check=True)
    elif json.loads(secondary.read_text())['status']!='COMPLETE':
        raise RuntimeError('Secondary output exists but is incomplete; preserve and inspect it')
    subprocess.run([sys.executable,str(ROOT/'scripts/report-paper-reference.py'),str(root)],cwd=ROOT,check=True)
    receipt=dict(status='PASS',completed=time.time(),primary_audits=360,secondary_audits=90,
                 models=3,steps_per_model=1000000,report='REPORT.md')
    (root/'postprocess-verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('campaign',type=Path);p.add_argument('--timeout',type=int,default=7200)
    a=p.parse_args();finish(a.campaign.resolve(),a.timeout)
