#!/usr/bin/env bash
# Linux server entry point. Run with bash; no sudo, no dataset download.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

workload=synthetic
setup=0
dry_run=0
for arg in "$@"; do
    case "$arg" in
        --setup) setup=1 ;;
        --dry-run) dry_run=1 ;;
        -h|--help)
            cat <<'HELP'
Usage: bash scripts/train-paper-server.sh [WORKLOAD] [--setup] [--dry-run]
  WORKLOAD   A workload id from scenarios.json (synthetic, rescuenet, mixed; legacy alias datasets).
             Default: synthetic.
  --setup    Create .venv-drl (Python 3.11) and install dependencies, then train.
  --dry-run  Print the train command without building, installing or training.
Environment: PYTHON=python3.11 SEED=0 OUT_DIR=target/<unique-run> OFFLINE=0
             SCENARIO=<id> LAYOUT_SEED=<n> POWERED=<n> CONNECTED=<n>
             (unset = defaults from scenarios.json; POWERED/CONNECTED override SCENARIO counts)
Always: DQN, reward=paper, 1,000,000 steps, CPU, one Torch thread.
Dataset workloads read the raw paths in scenarios.json (dataset_defaults).
HELP
            exit 0 ;;
        -*) printf 'Unknown argument: %s\n' "$arg" >&2; exit 2 ;;
        *) [[ "$arg" =~ ^[a-z][a-z0-9_]*$ ]] || { printf 'Invalid workload: %s\n' "$arg" >&2; exit 2; }
           workload="$arg" ;; # checked against scenarios.json before training
    esac
done

SEED="${SEED:-0}"
SCENARIO="${SCENARIO:-}"
LAYOUT_SEED="${LAYOUT_SEED:-}"
POWERED="${POWERED:-}"
CONNECTED="${CONNECTED:-}"
OFFLINE="${OFFLINE:-0}"
for value in "$SEED" "$LAYOUT_SEED" "$POWERED" "$CONNECTED"; do
    [[ -z "$value" || "$value" =~ ^(0|[1-9][0-9]*)$ ]] || { echo 'Seeds/counts must be nonnegative integers without leading zeros.' >&2; exit 2; }
done
(( ${#SEED} <= 10 && ${#LAYOUT_SEED} <= 10 && ${#POWERED} <= 2 && ${#CONNECTED} <= 2 )) || exit 2
(( SEED <= 4294967295 && ${LAYOUT_SEED:-0} <= 4294967295 && ${POWERED:-0} <= 12 && ${CONNECTED:-0} <= 12 )) || {
    echo 'Seeds must fit uint32; powered/connected must be in 0..12.' >&2; exit 2;
}
[[ -z "$SCENARIO" || "$SCENARIO" =~ ^[a-z0-9_]+$ ]] || { echo 'SCENARIO must be an id from scenarios.json.' >&2; exit 2; }
[[ "$OFFLINE" == 0 || "$OFFLINE" == 1 ]] || { echo 'OFFLINE must be 0 or 1.' >&2; exit 2; }

PY="$ROOT/.venv-drl/bin/python"
OUT_DIR="${OUT_DIR:-target/drl-server-$(date -u +%Y%m%d-%H%M%S)-${workload}-s${SEED}-$$}"
# Scenario, layout seed, counts and max slots default to scenarios.json unless set above.
command=("$PY" -u -m drl.run train
    --algorithm DQN --reward paper --steps 1000000 --seed "$SEED"
    --workload "$workload" --device cpu --threads 1
    --eval-freq 10000 --validation-episodes 5 --eval-episodes 30
    --output "$OUT_DIR")
[[ -z "$SCENARIO" ]] || command+=(--scenario "$SCENARIO")
[[ -z "$LAYOUT_SEED" ]] || command+=(--layout-seed "$LAYOUT_SEED")
[[ -z "$POWERED" ]] || command+=(--powered "$POWERED")
[[ -z "$CONNECTED" ]] || command+=(--connected "$CONNECTED")
if (( dry_run )); then
    printf 'Working directory: %s\nCommand: ' "$ROOT"
    printf '%q ' "${command[@]}"
    printf '\n'
    exit 0
fi

for tool in java mvn; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool (JDK 17 + Maven required)" >&2; exit 1; }
done
if (( setup )); then
    bootstrap="${PYTHON:-python3.11}"
    "$bootstrap" -c 'import sys; assert sys.version_info[:2] == (3,11), "Use Python 3.11"'
    if [[ ! -x "$PY" ]]; then
        [[ ! -e .venv-drl ]] || { echo 'Existing .venv-drl is not a Linux venv; use a fresh checkout or move it aside.' >&2; exit 1; }
        "$bootstrap" -m venv .venv-drl
    fi
    "$PY" -m pip install -r drl/requirements.txt
fi
[[ -x "$PY" ]] || { echo 'Run this script with --setup first.' >&2; exit 1; }
# Unknown workload/scenario ids fail here; dataset workloads also need their raw files.
"$PY" - "$workload" "$SCENARIO" <<'PY'
import sys
from pathlib import Path
from drl.registry import ROOT, load
registry = load()
try:
    workload = registry.canonical_workload(sys.argv[1])
    if sys.argv[2]:
        registry.scenario(sys.argv[2])
except ValueError as error:
    sys.exit(str(error))
if registry.workloads[workload]["dataset"]:
    defaults = registry.dataset_defaults
    for key in ("rescuenet.images", "rescuenet.masks", "alibaba.csv"):
        if defaults.get(key) and not (ROOT / defaults[key]).exists():
            sys.exit(f"Missing dataset: {defaults[key]}. Copy raw data to this server first.")
PY
[[ ! -e "$OUT_DIR" && ! -e "${OUT_DIR}.log" ]] || { echo 'Output/log already exists; choose a new OUT_DIR.' >&2; exit 1; }

"$PY" - <<'PY'
import sys
from drl.run import model_options
assert sys.version_info[:2] == (3, 11), 'Use Python 3.11'
p = model_options('DQN')
for key, expected in dict(learning_rate=.0071, gamma=.98, batch_size=16,
                         exploration_initial_eps=1., exploration_final_eps=.05,
                         exploration_fraction=.35).items():
    assert p[key] == expected, f'Paper parameter changed: {key}'
assert p['policy_kwargs']['net_arch'] == [64, 64]
assert p['policy_kwargs']['activation_fn'].__name__ == 'ReLU'
print('Validated published DQN hyperparameters. Additional assumptions: PureEdgeSim/uav/DRL.md', flush=True)
PY

# Resolve classpath and actual Java executable on THIS server; never copy target from Windows.
maven_args=(compile exec:java -Dexec.mainClass=uav.PaperGymBridge -Dexec.classpathScope=compile -Dexec.args=--classpath)
if [[ "$OFFLINE" == 1 ]]; then maven_args=(-o "${maven_args[@]}"); fi
mvn "${maven_args[@]}"
mkdir -p -- "$(dirname -- "$OUT_DIR")"
printf 'Training output: %s\nConsole log: %s.log\n' "$OUT_DIR" "$OUT_DIR"
# pipefail propagates training errors despite tee; -u makes progress visible over SSH.
"${command[@]}" 2>&1 | tee "${OUT_DIR}.log"
