#!/usr/bin/env bash
# Synthetic paired state ablation. No package installation, raw data or GPU.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Set a fresh OUT_DIR under target/}"
[[ ! -e "$OUT" ]] || { echo 'Output exists; refusing overwrite'; exit 2; }
if [[ "${1:-}" == --dry-run ]]; then
    printf '%s\n' "CPU: 6 models, 3 simultaneous, 1m steps/model; output=$OUT"
    exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mvn -o test compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath
"$PY" -m unittest drl.test_extended_state drl.test_drl drl.test_paper_conventions -v
"$PY" -u -m drl.paper_state_campaign --output "${OUT}-smoke" --smoke
"$PY" -u -m drl.paper_state_campaign --output "$OUT"
