#!/usr/bin/env bash
# Apply paper-inspired mechanisms to the existing fixed-UAV setting. No training/setup downloads.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Set fresh output prefix under target/}"
[[ ! -e "${OUT}-e0" && ! -e "${OUT}-e40" ]] || exit 2
if [[ "${1:-}" == --dry-run ]]; then
    echo "30 seeds 94000..94029; 8 policies x 6 load/battery cases x 2 errors = 2880 episodes. prefix=$OUT"
    exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mvn -o test
for error in 0 0.4; do
    suffix=e0
    [[ "$error" == 0 ]] || suffix=e40
    run="${OUT}-${suffix}"
    mvn -o -q compile exec:java -Dexec.mainClass=uav.offloading.QueueImpactBenchmark \
        "-Dqios.output=$run" -Dqios.seeds=30 -Dqios.firstSeed=94000 -Dqios.paperInspired=true "-Dqios.estimateError=$error"
    "$PY" scripts/verify-deadline-risk.py "$run"
done
echo 'ALL_ADAPTED_METHODS_COMPLETE_AND_VERIFIED'
