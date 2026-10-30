#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Set fresh target output}"
[[ "$OUT" == target/* && ! -e "$OUT" && ! -e "${OUT}-smoke" ]]
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mvn -o test compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath
"$PY" -m unittest drl.test_service12 drl.test_contact drl.test_joint drl.test_mobile -v
"$PY" scripts/test_offloading_metrics.py
"$PY" -u -m drl.service12_campaign campaign --smoke --output "${OUT}-smoke"
"$PY" -u -m drl.service12_campaign campaign --output "$OUT"
echo SERVICE12_SERVER_COMPLETE_AND_VERIFIED
