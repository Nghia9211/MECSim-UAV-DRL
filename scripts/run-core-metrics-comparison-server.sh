#!/usr/bin/env bash
# Paired basic policies vs already verified latest methods; no learning/tuning.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Choose fresh target prefix}"
REFERENCE="${REFERENCE_PREFIX:-target/adapted-methods-20261029-v1}"
POLICIES='ALL_LOCAL__FIFO,ALL_UAV__FIFO,ALL_UAV__EDF,ALL_UAV__SPT,SHORTEST_FINISH__EDF,DEADLINE_ENERGY__FIFO,DEADLINE_ENERGY__EDF,DEADLINE_ENERGY__SPT,DEADLINE_ENERGY__PRIORITY'
if [[ "${1:-}" == --dry-run ]]; then
    echo "30 seeds 94000..94029 x 6 cases x 9 basic policies x 2 errors = 3240 new episodes; compare against $REFERENCE"
    exit 0
fi
for suffix in e0 e40; do
    [[ ! -e "${OUT}-${suffix}" && ! -e "${OUT}-compare-${suffix}" ]]
    [[ -f "${REFERENCE}-${suffix}/verification.json" ]]
done
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PY" scripts/test_offloading_metrics.py
mvn -o test
for error in 0 0.4; do
    suffix=e0; [[ "$error" == 0 ]] || suffix=e40
    run="${OUT}-${suffix}"
    mvn -o -q compile exec:java -Dexec.mainClass=uav.offloading.OffloadingBenchmark \
        "-Doffloading.output=$run" -Doffloading.seeds=30 -Doffloading.firstSeed=94000 \
        "-Doffloading.policies=$POLICIES" "-Doffloading.estimateError=$error"
    "$PY" scripts/verify-uav-offloading.py "$run"
    "$PY" scripts/test-uav-offloading-verifier.py "$run"
    "$PY" scripts/offloading_metrics.py "$run" "${REFERENCE}-${suffix}" --output "${OUT}-compare-${suffix}"
done
echo CORE_METRICS_COMPARISON_COMPLETE
