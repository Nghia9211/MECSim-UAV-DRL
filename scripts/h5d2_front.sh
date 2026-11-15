#!/usr/bin/env bash
# H5d-2 (experiments/h5d-offload-ext.json): energy-weight sweep warm-started from H5a-long, evaluated once.
set -u
cd "$(dirname "$0")/.."
PY=.venv-drl/Scripts/python.exe
root=target/rl/h5d2; mkdir -p $root
jobs=()
for w in 0 16 64; do for s in 0 1 2; do jobs+=("$w $s"); done; done
for ((i = 0; i < ${#jobs[@]}; i += 2)); do
  for j in "${jobs[@]:i:2}"; do
    set -- $j; w=$1; s=$2; d=$root/w$w-s$s
    if [ -f "$d/train.json" ] && grep -q '"finished"' "$d/train.json"; then continue; fi
    rm -rf "$d"
    ck=target/rl/h5a-long/w4-s$s/$($PY -c "import json; print(json.load(open('target/rl/h5a-long/w4-s$s/train.json'))['best_checkpoint'])")
    $PY -m drl.mec_rl train --out "$d" --seed $s --energy-weight $w --steps 2000000 --eval-every 200000 \
      --init-from "$ck" --select-rule objective > "$root/w$w-s$s.log" 2>&1 &
  done
  wait
done
runs=$(ls -d $root/w*-s*/ | tr '\n' ' ')
rm -rf target/mec/h5d2-front-eval21
$PY -m drl.mec_rl evaluate --runs $runs --out target/mec/h5d2-front-eval21 --variant e0-pre-circle \
  --with-baselines target/mec/h4-baselines-eval21 || exit 1
$PY scripts/verify_mec.py target/mec/h5d2-front-eval21 > target/rl/h5d2-verify.txt
$PY scripts/mec_report.py target/mec/h5d2-front-eval21 --reference "SHORTEST_FINISH+EDF+NONE"
echo "[$(date '+%F %T')] H5D2 DONE"
