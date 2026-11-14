#!/usr/bin/env bash
# H5a-long (experiments/h5a-long.json): continue each H5a w4 seed for 2M steps, evaluate once.
set -u
cd "$(dirname "$0")/.."
PY=.venv-drl/Scripts/python.exe
root=target/rl/h5a-long; mkdir -p $root
for pair in "0 1" "2 3" "4"; do
  for s in $pair; do
    d=$root/w4-s$s
    if [ -f "$d/train.json" ] && grep -q '"finished"' "$d/train.json"; then continue; fi
    rm -rf "$d"
    ck=target/rl/h5a/w4-s$s/$($PY -c "import json; print(json.load(open('target/rl/h5a/w4-s$s/train.json'))['best_checkpoint'])")
    $PY -m drl.mec_rl train --out "$d" --seed $s --energy-weight 4 --steps 2000000 --eval-every 200000 --init-from "$ck" > "$root/w4-s$s.log" 2>&1 &
  done
  wait
done
$PY -m drl.mec_rl select --runs $root/w4-s*/ --out $root/selection.json || exit 1
rm -rf target/mec/h5a-long-eval21
$PY -m drl.mec_rl evaluate --runs $root/w4-s0 $root/w4-s1 $root/w4-s2 $root/w4-s3 $root/w4-s4 --out target/mec/h5a-long-eval21 \
  --variant e0-pre-circle --with-baselines target/mec/h4-baselines-eval21 || exit 1
$PY scripts/verify_mec.py target/mec/h5a-long-eval21 > target/rl/h5a-long-verify.txt
$PY scripts/mec_report.py target/mec/h5a-long-eval21 --reference "SHORTEST_FINISH+EDF+NONE"
echo "[$(date '+%F %T')] H5A-LONG DONE"
