#!/usr/bin/env bash
# H5 training batch: energy weights x 5 seeds, two runs at a time. Finished runs are skipped, unfinished ones restarted.
# Usage: [CONTROL=offload|schedule] [TEACHER=shortest_finish|edf] bash scripts/h5_train_batch.sh OUT_ROOT STEPS W1 [W2 ...]
set -u
root=$1; steps=$2; shift 2
control=${CONTROL:-offload}; teacher=${TEACHER:-shortest_finish}
mkdir -p "$root"
for w in "$@"; do
  for pair in "0 1" "2 3" "4"; do
    for s in $pair; do
      d="$root/w${w}-s${s}"
      if [ -f "$d/train.json" ] && grep -q '"finished"' "$d/train.json"; then continue; fi
      rm -rf "$d"
      .venv-drl/Scripts/python.exe -m drl.mec_rl train --out "$d" --seed "$s" --energy-weight "$w" --steps "$steps" \
        --control "$control" --teacher "$teacher" --eval-every 200000 > "$root/w${w}-s${s}.log" 2>&1 &
    done
    wait
  done
done
echo "batch finished: $root"
