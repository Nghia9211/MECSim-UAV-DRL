#!/usr/bin/env bash
# Same Round Robin selector, physical coverage and actual flight power for every policy.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Set fresh target output prefix}"
SEEDS="${SEEDS:-30}"
PROTOCOL="${PROTOCOL:-PureEdgeSim/uav/offloading/mobile-comparison-protocol.json}"
[[ "$OUT" == target/* && "$SEEDS" =~ ^[1-9][0-9]*$ && "$SEEDS" -le 30 ]]
for suffix in e0 e40; do [[ ! -e "${OUT}-${suffix}" ]]; done
if [[ "${1:-}" == --dry-run ]]; then
    echo "$SEEDS seeds from 95000; RR x 9 policy pairs x 8 cases x 2 errors; $((SEEDS*144)) episodes; prefix=$OUT; protocol=$PROTOCOL"
    exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
"$PY" scripts/test_offloading_metrics.py
mvn -o test
for error in 0 0.4; do
    suffix=e0; [[ "$error" == 0 ]] || suffix=e40
    run="${OUT}-${suffix}"
    mvn -o -q compile exec:java -Dexec.mainClass=uav.offloading.MobileServiceBenchmark \
        "-Dmobile.protocol=$PROTOCOL" \
        "-Dmobile.output=$run" "-Dmobile.seeds=$SEEDS" -Dmobile.firstSeed=95000 "-Dmobile.estimateError=$error"
    "$PY" scripts/verify-uav-mobile.py "$run"
    "$PY" scripts/test-uav-mobile-verifier.py "$run"
    "$PY" scripts/test-uav-mobile-risk-verifier.py "$run"
    if [[ "${DELIVERY_AUDIT:-0}" == 1 ]]; then "$PY" scripts/test-uav-delivery-verifier.py "$run"; fi
    if [[ "${WAIT_AUDIT:-0}" == 1 ]]; then "$PY" scripts/test-uav-contact-wait-verifier.py "$run"; fi
done
echo MOBILE_COMPARISON_COMPLETE_AND_VERIFIED
