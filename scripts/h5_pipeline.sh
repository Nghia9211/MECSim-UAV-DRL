#!/usr/bin/env bash
# Unattended H5a pipeline (PLAN_HUONG_2_3.md section 7). The H5b step (learned UAV scheduling, negative result)
# was removed; the original pipeline is at tag v2-h5-full. Every choice uses validation seeds only; evaluation seeds are
# opened once, at the end, for the final policies. Log: target/rl/pipeline.log
set -u
cd "$(dirname "$0")/.."
PY=.venv-drl/Scripts/python.exe
STEPS=${STEPS:-2000000}
stamp() { echo "[$(date '+%F %T')] $*"; }

# 0. wait for anything started earlier by hand: a batch script or training processes (they share target/rl)
busy() {
  powershell -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like ('*h5_train' + '_batch.sh*') -or \$_.CommandLine -like ('*drl.mec_rl' + ' train*') }).Count"
}
while [ "$(busy | tr -d '[:space:]')" != "0" ]; do
  sleep 60
done
stamp "no other batch running"

# 1. H5a: learned offloading, energy weights 1 and 4, 5 seeds each
bash scripts/h5_train_batch.sh target/rl/h5a "$STEPS" 1 4
$PY -m drl.mec_rl select --runs target/rl/h5a/w*-s* --out target/rl/h5a/selection.json || exit 1
W=$($PY -c "import json; print(json.load(open('target/rl/h5a/selection.json'))['chosen']['energy_weight'])")
stamp "H5a chosen energy weight $W"

# 2. evaluation once, all seeds of the chosen configurations, paired with the H4 baselines
A=$($PY -c "import json; print(' '.join(json.load(open('target/rl/h5a/selection.json'))['chosen']['runs']))")
rm -rf target/mec/h5-rl-eval21
$PY -m drl.mec_rl evaluate --runs $A --out target/mec/h5-rl-eval21 --variant e0-pre-circle \
  --with-baselines target/mec/h4-baselines-eval21 || exit 1
$PY scripts/verify_mec.py target/mec/h5-rl-eval21 > target/rl/h5-verify.txt
$PY scripts/mec_report.py target/mec/h5-rl-eval21 --reference "SHORTEST_FINISH+EDF+NONE"
stamp "PIPELINE DONE"
