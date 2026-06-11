#!/usr/bin/env bash
# One-command CARE benchmark for ACM's unsupervised ML core (Linux/macOS).
#
#   1. Clones (or pulls) the ACM repo at the given branch
#   2. Installs the Python dependencies the ML core needs (no SQL Server,
#      no observability stack required)
#   3. Downloads the requested CARE_To_Compare wind farm(s) from Zenodo
#   4. Runs the benchmark over every event dataset and prints the KPI verdict
#
# Usage:
#   ./run_care_benchmark.sh                          # full Wind Farm A (22 events)
#   DATASETS="40 10 68" ./run_care_benchmark.sh      # targeted known faults
#   FARMS="A B C" ./run_care_benchmark.sh            # all 95 events
set -euo pipefail

REPO="${REPO:-https://github.com/bhadkamkar9snehil/ACM.git}"
BRANCH="${BRANCH:-claude/charming-cerf-3mt13j}"
WORKDIR="${WORKDIR:-$PWD/acm_care_bench}"
FARMS="${FARMS:-A}"
DATASETS="${DATASETS:-}"
ALERT_Z="${ALERT_Z:-3.0}"
PERSIST="${PERSIST:-6}"

# 1. Code
if [ -d "$WORKDIR/ACM/.git" ]; then
    echo "== Updating ACM ($BRANCH) =="
    git -C "$WORKDIR/ACM" fetch origin "$BRANCH"
    git -C "$WORKDIR/ACM" checkout "$BRANCH"
    git -C "$WORKDIR/ACM" pull origin "$BRANCH"
else
    echo "== Cloning ACM ($BRANCH) =="
    mkdir -p "$WORKDIR"
    git clone --branch "$BRANCH" --single-branch "$REPO" "$WORKDIR/ACM"
fi
cd "$WORKDIR/ACM"

# 2. Dependencies (ML core only)
echo "== Installing Python dependencies =="
python3 -m pip install --quiet --upgrade pip
python3 -m pip install --quiet pandas numpy polars pyarrow scikit-learn scipy structlog remotezip

# 3. Dataset
echo "== Downloading CARE_To_Compare farm(s): $FARMS =="
# shellcheck disable=SC2086
python3 scripts/download_care_dataset.py --dest "$WORKDIR/care_data" --farms $FARMS

# 4. Benchmark
for farm in $FARMS; do
    DATA_DIR="$WORKDIR/care_data/CARE_To_Compare/Wind Farm $farm"
    OUT_DIR="$WORKDIR/results/farm_$farm"
    echo ""
    echo "== Benchmarking Wind Farm $farm =="
    EXTRA=()
    if [ -n "$DATASETS" ]; then
        # shellcheck disable=SC2206
        EXTRA=(--datasets $DATASETS)
    fi
    python3 scripts/care_benchmark.py --data-dir "$DATA_DIR" --out "$OUT_DIR" \
        --alert-z "$ALERT_Z" --persist "$PERSIST" "${EXTRA[@]}"
    echo "Results: $OUT_DIR/results.csv | $OUT_DIR/summary.json"
done
