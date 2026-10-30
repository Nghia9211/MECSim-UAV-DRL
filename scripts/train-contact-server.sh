#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Set fresh target output}"
[[ "$OUT" == target/* && ! -e "$OUT" && ! -e "${OUT}-smoke" ]]
if [[ "${1:-}" == --dry-run ]]; then
    echo 'Contact MaskablePPO: 3 seeds x32768 steps, 179D/108 actions; smoke9 + full2560 audited episodes'
    exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PY" -c 'import importlib.metadata; assert importlib.metadata.version("sb3-contrib")=="2.6.0"'
mvn -o test compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath
"$PY" -m unittest drl.test_contact drl.test_joint drl.test_mobile drl.test_extended_state -v
"$PY" scripts/test_offloading_metrics.py
"$PY" -u -m drl.contact_campaign campaign --smoke --output "${OUT}-smoke"
"$PY" -u -m drl.contact_campaign campaign --output "$OUT"
echo CONTACT_SERVER_COMPLETE_AND_VERIFIED
