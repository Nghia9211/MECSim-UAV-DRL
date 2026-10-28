"""Secondary final-checkpoint diagnostic after the frozen best-validation campaign. No model selection."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from stable_baselines3 import DQN
from drl.environment import EnvConfig,PaperEnv
from drl.paper_reference import constants,layout,read,save
from drl.run import episode,write_csv


def evaluate(root):
    m=json.loads((root/'manifest.json').read_text());v=json.loads((root/'verification.json').read_text())
    if m['status']!='COMPLETE' or v['status']!='PASS':raise ValueError('Complete primary campaign required')
    out=root/'secondary-final-evaluation';out.mkdir(exist_ok=False)
    protocol=dict(schema='paper-final-checkpoint-diagnostic-v1',status='RUNNING',checkpoint='final_model.zip',
                  purpose='Secondary diagnostic; the primary checkpoint is still selected only on validation.',
                  task_seeds=list(range(2000000,2000030)),same_cases_as_primary=True,additional_independent_samples=False,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    save(out/'protocol.json',protocol);(out/'evaluate-paper-final.py').write_bytes(Path(__file__).read_bytes())
    spec=importlib.util.spec_from_file_location('final_checkpoint_audit',ROOT/'scripts/verify-paper-conventions.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    torch.set_num_threads(1);rows=[];counts=[]
    for seed in (0,1,2):
        run=root/f'seed-{seed}';cfg=json.loads((run/'config.json').read_text());envcfg=EnvConfig(**cfg['environment'])
        model=DQN.load(run/'final_model.zip',device='cpu')
        if model.num_timesteps!=1000000 or model._n_updates!=249975:raise AssertionError('Final checkpoint budget')
        ds=layout(envcfg.layout_seed,8,8,audit.JavaRandom)
        conventions=json.loads((run/'environment/conventions.json').read_text())
        am=dict(constants=constants(),profiles=dict(REFERENCE=conventions),max_slots=200)
        with PaperEnv(envcfg) as env:
            for task in range(2000000,2000030):
                trace=out/f'seed-{seed}'/f'task-{task}'
                r=episode(env,model=model,task_seed=task,trace=trace)
                slots=read(trace/'slots.csv');devices=read(trace/'devices.csv');by={}
                for d in devices:by.setdefault(int(d['slot']),{})[int(d['device'])]=d
                batteries=[1.]*12;ages=[0.]*12;actions=[]
                for k,s in enumerate(slots,1):
                    actions.append(int(model.predict(np.asarray(batteries+ages,np.float32),deterministic=True)[0]))
                    batteries=[float(by[k][j]['battery_j'])/ds[j]['capacity_j'] for j in range(12)]
                    ages=[float(by[k][j]['data_age']) for j in range(12)]
                row=dict(profile='REFERENCE',scenario='p8-c8',seed=seed,task_seed=task,policy='DQN',trace=str(trace.relative_to(root)),
                         slots=r['slots'],seconds=r['seconds'],reason=r['reason'],truncated=str(r['truncated']).lower(),reward=r['reward'],
                         uav_energy_j=1600000-float(slots[-1]['uav_battery_j']),ground_energy_j=sum(float(d['energy_used_j']) for d in devices),
                         cap_slots=sum(float(s['duration_s'])>=600-1e-6 for s in slots),capped_items=sum(int(s['capped_work_items']) for s in slots))
                audit.replay(root,row,am,counts,layout_override=ds,expected_actions=actions)
                rows.append(dict(training_seed=seed,**r,trace=row['trace']))
        print(f'Final checkpoint audited: seed={seed}',flush=True)
    write_csv(out/'episodes.csv',rows);write_csv(out/'slot-counting.csv',counts)
    primary=read(root/'runs.csv');summary=[]
    for seed in (0,1,2):
        g=[r for r in rows if r['training_seed']==seed];best=next(float(r['mean_slots']) for r in primary if int(r['training_seed'])==seed and r['policy']=='DQN')
        values=[r['slots'] for r in g];summary.append(dict(seed=seed,episodes=len(g),final_mean_slots=statistics.mean(values),
                                                       best_validation_checkpoint_test_mean=best,final_minus_best=statistics.mean(values)-best,
                                                       final_sd_slots=statistics.stdev(values),final_max_slots=max(values)))
    write_csv(out/'summary.csv',summary)
    protocol.update(status='COMPLETE',audited_episodes=len(rows),mean_of_final_run_means=statistics.mean(r['final_mean_slots'] for r in summary),
                    sd_of_final_run_means=statistics.stdev(r['final_mean_slots'] for r in summary),
                    note='Best/final evaluated on identical cases; diagnostic comparison only. No extra training or checkpoint selection.')
    save(out/'protocol.json',protocol);print(json.dumps(summary,indent=2));return protocol


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('campaign',type=Path);args=p.parse_args()
    evaluate(args.campaign.resolve())
