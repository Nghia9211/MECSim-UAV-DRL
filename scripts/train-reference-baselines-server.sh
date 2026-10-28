#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Set a new OUT_DIR}"
REF="${REFERENCE_DIR:?Set completed REFERENCE campaign directory}"
[[ ! -e "$OUT" && -f "$REF/verification.json" ]] || exit 2
if [[ "${1:-}" == --dry-run ]]; then
    printf '%s\n' "PPO/A2C x 3 seeds, requested 1m steps/model; reference=$REF output=$OUT"
    exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mvn -o test compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath
"$PY" -m unittest drl.test_drl drl.test_paper_conventions drl.test_reference_state_plan -v
"$PY" -u -m drl.paper_rl_baselines --reference "$REF" --output "${OUT}-smoke" --smoke
"$PY" -u -m drl.paper_rl_baselines --reference "$REF" --output "$OUT"
