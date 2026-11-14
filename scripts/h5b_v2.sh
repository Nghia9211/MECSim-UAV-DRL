#!/usr/bin/env bash
# H5b-v2 (experiments/h5b-v2-sched.json): retrain the learned UAV scheduler with exploration, select, evaluate once.
set -u
cd "$(dirname "$0")/.."
PY=.venv-drl/Scripts/python.exe
CONTROL=schedule TEACHER=edf EXTRA="--bc-smoothing 0.3 --ent-coef 0.01" bash scripts/h5_train_batch.sh target/rl/h5b2 2000000 4
$PY -m drl.mec_rl select --runs target/rl/h5b2/w*-s*/ --out target/rl/h5b2/selection.json || exit 1
B=$($PY -c "import json; print(' '.join(json.load(open('target/rl/h5b2/selection.json'))['chosen']['runs']))")
rm -rf target/mec/h5b2-rl-eval21
$PY -m drl.mec_rl evaluate --runs $B --out target/mec/h5b2-rl-eval21 --variant e0-pre-circle \
  --with-baselines target/mec/h4-baselines-eval21 || exit 1
$PY scripts/verify_mec.py target/mec/h5b2-rl-eval21 > target/rl/h5b2-verify.txt
$PY scripts/mec_report.py target/mec/h5b2-rl-eval21 --reference "SHORTEST_FINISH+EDF+NONE"
echo "[$(date '+%F %T')] H5B2 DONE"
