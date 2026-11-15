#!/usr/bin/env bash
# H5d-2 on a Linux server (same protocol as scripts/h5d2_front.sh; only the launcher differs).
# Usage: PY=/path/to/python PARALLEL=5 bash scripts/h5d2_server.sh
set -u
cd "$(dirname "$0")/.."
PY=${PY:?set PY to the python of the uav-mec environment}
PARALLEL=${PARALLEL:-5}
root=target/rl/h5d2; mkdir -p $root
run_one() {
  w=$1; s=$2; d=$root/w$w-s$s
  if [ -f "$d/train.json" ] && grep -q '"finished"' "$d/train.json"; then return 0; fi
  rm -rf "$d"
  ck=target/rl/h5a-long/w4-s$s/$($PY -c "import json; print(json.load(open('target/rl/h5a-long/w4-s$s/train.json'))['best_checkpoint'])")
  $PY -m drl.mec_rl train --out "$d" --seed $s --energy-weight $w --steps 2000000 --eval-every 200000 \
    --init-from "$ck" --select-rule objective > "$root/w$w-s$s.log" 2>&1
  echo "$w $s rc=$?" >> $root/done.log
}
export -f run_one; export PY root
for w in 0 16 64; do for s in 0 1 2; do echo "$w $s"; done; done | xargs -P "$PARALLEL" -n 2 bash -c 'run_one "$0" "$1"'
runs=$(ls -d $root/w*-s*/ | tr '\n' ' ')
rm -rf target/mec/h5d2-front-eval21
$PY -m drl.mec_rl evaluate --runs $runs --out target/mec/h5d2-front-eval21 --variant e0-pre-circle \
  --with-baselines target/mec/h4-baselines-eval21 || exit 1
$PY scripts/verify_mec.py target/mec/h5d2-front-eval21 > target/rl/h5d2-verify.txt
$PY scripts/mec_report.py target/mec/h5d2-front-eval21 --reference "SHORTEST_FINISH+EDF+NONE"
echo "[$(date -u '+%F %T') UTC] H5D2 DONE"
