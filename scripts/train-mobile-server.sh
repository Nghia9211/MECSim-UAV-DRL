#!/usr/bin/env bash
# Linux entrypoint for the ADAPTED mobile DQN; not the paper training command.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
dry=0
offline=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) dry=1 ;;
        --offline) offline=1 ;;
        -h|--help)
            cat <<'HELP'
Usage: bash scripts/train-mobile-server.sh [--offline] [--dry-run]
Uses the existing Linux venv and raw datasets. No sudo/download/setup.
Environment: PYTHON=.venv-drl/bin/python STEPS=10000 SEED=0 LAYOUT_SEED=42
             LOCAL_MIPS=500 AREA=250 OFFLOADING=ALL_UAV SCHEDULER=EDF
             EVAL_FREQ=1000 VALIDATION_EPISODES=5 EVAL_EPISODES=10 OUT_DIR=target/<unique>
CPU, one Torch thread. New 129-feature environment/reward, NOT paper reproduction.
HELP
            exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
    esac
done
PY="${PYTHON:-.venv-drl/bin/python}"
OUT_DIR="${OUT_DIR:-target/mobile-dqn-$(date -u +%Y%m%d-%H%M%S)-s${SEED:-0}-$$}"
train=("$PY" -u -m drl.mobile_run train --steps "${STEPS:-10000}" --seed "${SEED:-0}"
    --layout-seed "${LAYOUT_SEED:-42}" --local-mips "${LOCAL_MIPS:-500}" --area "${AREA:-250}"
    --offloading "${OFFLOADING:-ALL_UAV}" --scheduler "${SCHEDULER:-EDF}"
    --eval-freq "${EVAL_FREQ:-1000}" --validation-episodes "${VALIDATION_EPISODES:-5}"
    --eval-episodes "${EVAL_EPISODES:-10}" --output "$OUT_DIR")
if (( dry )); then
    printf 'Working directory: %s\nCommand: ' "$ROOT"
    printf '%q ' "${train[@]}"
    printf '\n'
    exit 0
fi
for tool in java mvn "$PY"; do
    command -v "$tool" >/dev/null || { printf 'Missing prerequisite: %s\n' "$tool" >&2; exit 1; }
done
[[ ! -e "$OUT_DIR" && ! -e "${OUT_DIR}.log" ]] || { echo 'Choose a new OUT_DIR; output/log exists.' >&2; exit 1; }
"$PY" -c 'import torch, gymnasium, stable_baselines3; print("Dependencies available")'
maven=(test compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath)
if (( offline )); then maven=(-o "${maven[@]}"); fi
mvn "${maven[@]}"
"$PY" -m unittest drl.test_mobile -v
mkdir -p -- "$(dirname -- "$OUT_DIR")"
"${train[@]}" 2>&1 | tee "${OUT_DIR}.log"
