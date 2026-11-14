#!/usr/bin/env bash
# After scripts/h5_pipeline.sh: evaluate the already-chosen final policies on robustness variants (nothing is selected
# here). Variants match H4: e40-pre-circle (estimates +-40%) and e0-pre-static-centre (UAV hovers at the centre).
set -u
cd "$(dirname "$0")/.."
PY=.venv-drl/Scripts/python.exe
until grep -q "PIPELINE DONE" target/rl/pipeline.log 2>/dev/null; do sleep 120; done
A=$($PY -c "import json; print(' '.join(json.load(open('target/rl/h5a/selection.json'))['chosen']['runs']))")
B=$($PY -c "import json; print(' '.join(json.load(open('target/rl/h5b/selection.json'))['chosen']['runs']))")
for spec in 'e40-pre-circle|{"estimate_error": 0.4}' 'e0-pre-static-centre|{"trajectory": {"type": "STATIC"}}'; do
  v=${spec%%|*}; patch=${spec#*|}
  out=target/mec/h5-rl-robust-$v
  rm -rf "$out"
  $PY -m drl.mec_rl evaluate --runs $A $B --out "$out" --variant "$v" --model-patch "$patch" \
    --with-baselines target/mec/h4-baselines-eval21 || exit 1
  $PY scripts/verify_mec.py "$out" > "$out.verify.txt"
  $PY scripts/mec_report.py "$out" --reference "SHORTEST_FINISH+EDF+NONE"
done
echo "[$(date '+%F %T')] ROBUSTNESS DONE"
