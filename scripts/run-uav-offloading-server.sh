#!/usr/bin/env bash
# Linux baseline entry point: no GPU, package installation or dataset download.
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

seeds=30
first_seed=41000
estimate_error=0
offline=0
dry_run=0
output="${OUT_DIR:-}"
while (( $# )); do
    case "$1" in
        --seeds|--first-seed|--estimate-error|--output)
            (( $# >= 2 )) || { echo "Missing value for $1" >&2; exit 2; }
            case "$1" in
                --seeds) seeds="$2" ;;
                --first-seed) first_seed="$2" ;;
                --estimate-error) estimate_error="$2" ;;
                --output) output="$2" ;;
            esac
            shift 2 ;;
        --offline) offline=1; shift ;;
        --dry-run) dry_run=1; shift ;;
        -h|--help)
            cat <<'HELP'
Usage: bash scripts/run-uav-offloading-server.sh [options]
  --seeds N             Default 30 (1..1000).
  --first-seed N        Default 41000 (0..2147483647).
  --estimate-error F    Relative uniform estimate noise, default 0; 0 <= F < 1.
  --output DIR         New output directory (or OUT_DIR environment variable).
  --offline            Use cached Maven dependencies only.
  --dry-run            Print commands without running tests or the benchmark.
Environment: PYTHON=python3; Java 17/JDK and Maven must be on PATH.
Runs Java tests, 4 offloaders x 5 schedulers x 3 loads x 2 UAV batteries,
then the independent verifier and its adversarial checks. CPU only.
HELP
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
[[ "$seeds" =~ ^[1-9][0-9]{0,3}$ && "$first_seed" =~ ^(0|[1-9][0-9]{0,9})$ ]] || {
    echo 'Invalid seeds/counts; use nonnegative integers without leading zeros.' >&2; exit 2;
}
(( seeds <= 1000 && first_seed <= 2147483647 )) || { echo 'Seeds/counts out of range.' >&2; exit 2; }
[[ "$estimate_error" =~ ^0(\.[0-9]+)?$ ]] || { echo 'Use an estimate error such as 0 or 0.4, below 1.' >&2; exit 2; }
PY="${PYTHON:-python3}"
output="${output:-target/offloading-server-$(date -u +%Y%m%d-%H%M%S)-$$}"
maven=()
if (( offline )); then maven+=(-o); fi
test_command=(mvn "${maven[@]}" test)
run_command=(mvn "${maven[@]}" compile exec:java
    -Dexec.mainClass=uav.offloading.OffloadingBenchmark -Dexec.classpathScope=compile
    "-Doffloading.seeds=$seeds" "-Doffloading.firstSeed=$first_seed"
    "-Doffloading.estimateError=$estimate_error" "-Doffloading.output=$output")
if (( dry_run )); then
    printf 'Working directory: %s\n' "$ROOT"
    printf '%q ' "${test_command[@]}"; printf '\n'
    printf '%q ' "${run_command[@]}"; printf '\n'
    printf '%q ' "$PY" scripts/verify-uav-offloading.py "$output"; printf '\n'
    printf '%q ' "$PY" scripts/test-uav-offloading-verifier.py "$output"; printf '\n'
    exit 0
fi
for tool in java javac mvn "$PY"; do
    command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool. Activate the server JDK/Maven/Python environment first." >&2; exit 1; }
done
for path in datasets/raw/rescuenet/validation/val-org-img datasets/raw/rescuenet/validation/val-label-img datasets/raw/alibaba2018/batch_task.csv; do
    [[ -e "$path" ]] || { echo "Missing raw dataset: $path" >&2; exit 1; }
done
[[ ! -e "$output" && ! -e "${output}.log" ]] || { echo 'Output/log exists; choose a new output.' >&2; exit 1; }
"$PY" -c 'import sys; assert sys.version_info >= (3,10), "Use Python >=3.10"'
mkdir -p -- "$(dirname -- "$output")"
export MAVEN_OPTS="${MAVEN_OPTS:--Xmx2g}"
{
    java -version
    "$PY" --version
    "${test_command[@]}"
    "${run_command[@]}"
    "$PY" scripts/verify-uav-offloading.py "$output"
    "$PY" scripts/test-uav-offloading-verifier.py "$output"
    printf 'Completed and verified: %s\n' "$output"
} 2>&1 | tee "${output}.log"
