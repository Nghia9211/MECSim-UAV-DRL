#!/usr/bin/env bash
# Development policy-selection PPO/DQN; shared mobile physics, CPU only.
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
PY="${PYTHON:-.venv-drl/bin/python}"
OUT="${OUT_DIR:?Set fresh target output directory}"
[[ "$OUT" == target/* && ! -e "$OUT" && ! -e "${OUT}-smoke" ]]
if [[ "${1:-}" == --dry-run ]]; then
    echo "PPO+DQN x 3 seeds x 32768 steps; 3 CPU workers; 3680 audited evaluation episodes; output=$OUT"
    exit 0
fi
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mvn -o test compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath
"$PY" -m unittest drl.test_joint drl.test_mobile drl.test_extended_state -v
"$PY" scripts/test_offloading_metrics.py
"$PY" -u -m drl.joint_campaign campaign --smoke --output "${OUT}-smoke"
"$PY" -u -m drl.joint_campaign campaign --output "$OUT"
echo JOINT_SERVER_COMPLETE_AND_VERIFIED
