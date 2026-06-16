#!/usr/bin/env bash
# setup.sh — one-command ACM setup for Linux / macOS
#
# Usage:
#   bash <(curl -fsSL https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup.sh)
# Or after cloning:
#   bash setup.sh

set -euo pipefail

REPO="https://github.com/bhadkamkar9snehil/ACM.git"
BRANCH="main"
INSTALL_DIR="${INSTALL_DIR:-$HOME/ACM}"
LOG="/tmp/setup_acm.log"

SEP="  $(printf '─%.0s' {1..53})"
GRN='\033[32m'; RED='\033[31m'; YEL='\033[33m'; DIM='\033[2m'; RST='\033[0m'

echo "ACM setup $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$LOG"

step() {
    local name="$1"; shift
    printf "    ·  %s" "$name"
    if "$@" >> "$LOG" 2>&1; then
        printf "\r    ${GRN}✓${RST}  %s\n" "$name"
    else
        printf "\r    ${RED}✗${RST}  %s\n" "$name"
        echo "       Log: $LOG"
        exit 1
    fi
}

warn_step() {
    local name="$1"; shift
    printf "    ·  %s" "$name"
    if "$@" >> "$LOG" 2>&1; then
        printf "\r    ${GRN}✓${RST}  %s\n" "$name"
    else
        printf "\r    ${YEL}!${RST}  %s (non-fatal)\n" "$name"
    fi
}

# ── Prerequisites ─────────────────────────────────────────────────────────────
echo ""
echo "  ${DIM}ACM — Asset Condition Monitor${RST}"
echo "${DIM}${SEP}${RST}"

if ! command -v python3 &>/dev/null; then
    echo "  ${RED}Python 3.11+ is required. Install it and re-run.${RST}"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=${PY_VER%%.*}
PY_MINOR=${PY_VER##*.}
if [[ "$PY_MAJOR" -lt 3 || ("$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 11) ]]; then
    echo "  ${RED}Python 3.11+ required (found $PY_VER). Install it and re-run.${RST}"
    exit 1
fi
echo "  Python $PY_VER  ✓"

PYTHON=$(command -v python3)

# ── Clone / update ────────────────────────────────────────────────────────────
echo ""
echo "  ${DIM}Repository${RST}"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    step "Update ACM" git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
    step "Clone ACM" git clone --branch "$BRANCH" "$REPO" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# ── Python dependencies ───────────────────────────────────────────────────────
echo ""
echo "  ${DIM}Python packages${RST}"

step "Upgrade pip" "$PYTHON" -m pip install --quiet --upgrade pip
step "Python packages" "$PYTHON" -m pip install --quiet \
    pandas numpy polars pyarrow scikit-learn scipy \
    structlog matplotlib remotezip pytest httpx \
    fastapi uvicorn python-multipart pydantic \
    asyncua paho-mqtt openpyxl
# pyodbc requires ODBC headers — skip silently on systems without them
"$PYTHON" -m pip install --quiet pyodbc >> "$LOG" 2>&1 || true

# ── Directories ───────────────────────────────────────────────────────────────
step "Create directories" "$PYTHON" -c "
from pathlib import Path
for d in ('sim_data/sample','sim_data/generated','sim_data/uploads','data_cache','configs'):
    Path(d).mkdir(parents=True, exist_ok=True)
    (Path(d) / '.gitkeep').touch()
print('OK')
"

# ── Verify imports ────────────────────────────────────────────────────────────
echo ""
echo "  ${DIM}Verification${RST}"

step "Verify imports" "$PYTHON" -c "
import sys; sys.path.insert(0,'.')
import pandas, numpy, polars, sklearn, matplotlib, fastapi, uvicorn
import core.pipeline, scripts.acm_store, scripts.acm_service
from sim.generator_registry import list_generators
from sim.buffer_publisher import BufferPublisher
from sim.sim_adapter import SimAdapter
from scripts.acm_sim_routes import router
print(f'{len(list_generators())} generators, {len(router.routes)} sim routes — OK')
"

# Smoke test — verify ACM can start and respond to HTTP (instead of slow pytest)
warn_step "Smoke test (ACM starts)" bash -c '
  export PYTHONPATH="."
  _smoke_db="/tmp/acm_smoke_$$.db"
  _smoke_log="/tmp/acm_smoke_$$.log"
  "$1" scripts/acm_service.py --port 8766 --db "$_smoke_db" > "$_smoke_log" 2>&1 &
  _pid=$!
  _ok=0
  for _i in 1 2 3 4 5 6; do
    sleep 2
    _code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8766/api/service 2>/dev/null)
    [ "$_code" = "200" ] && _ok=1 && break
  done
  kill "$_pid" 2>/dev/null
  wait "$_pid" 2>/dev/null
  rm -f "$_smoke_db" "$_smoke_log"
  [ $_ok -eq 1 ]
' - "$PYTHON"

# Show CI status reminder
echo ""
printf "  ${DIM}GitHub CI Status${RST}\n"
printf "    Check test results at: https://github.com/bhadkamkar9snehil/ACM/actions\n"
printf "    Run locally: python -m pytest tests/ -v\n"

warn_step "Fault datasets" "$PYTHON" scripts/generate_fault_dataset.py

# ── Optional: Simulator ───────────────────────────────────────────────────────
echo ""
SIM_DIR="${SIMULATOR_DIR:-$HOME/Simulator}"
if [[ -d "$SIM_DIR" ]]; then
    echo "  ${DIM}Simulator detected at $SIM_DIR${RST}"
    read -rp "  [1/2]  Seed Simulator OPC UA asset into ACM? [y/N] " ans
    if [[ "$ans" =~ ^[yY] ]]; then
        step "Seed simulator asset" "$PYTHON" scripts/acm_seed_demo.py \
            --opcua opc.tcp://localhost:4840/simulator --db acm_results.db
    fi
else
    echo "  ${DIM}Simulator not found at $SIM_DIR — skipping${RST}"
fi

# ── Optional: CARE data ───────────────────────────────────────────────────────
echo ""
if ls sim_data/sample/care_farmA_*.csv 1>/dev/null 2>&1; then
    echo "  [2/2]  CARE-to-Compare data — already downloaded, refreshing asset paths."
    step "Register CARE assets" "$PYTHON" scripts/acm_seed_demo.py \
        --care-dir sim_data/sample --db acm_results.db
else
    read -rp "  [2/2]  CARE-to-Compare data — 10 Farm A turbines (~360 MB)? [y/N] " ans
    if [[ "$ans" =~ ^[yY] ]]; then
        step "Download CARE events" "$PYTHON" scripts/download_care_dataset.py \
            --farms A --count 10
        step "Register CARE assets" "$PYTHON" scripts/acm_seed_demo.py \
            --care-dir sim_data/sample --db acm_results.db
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "${DIM}${SEP}${RST}"
printf "  ${GRN}✓${RST}  %s\n" "$INSTALL_DIR"
echo "${DIM}${SEP}${RST}"
YLW='\033[1;33m'
echo ""
echo "${YLW}  ╔══════════════════════════════════════════════════════════╗${RST}"
echo "${YLW}  ║                    NEXT STEPS                           ║${RST}"
echo "${YLW}  ╠══════════════════════════════════════════════════════════╣${RST}"
echo "${YLW}  ║                                                          ║${RST}"
echo "${YLW}  ║  1.  START THE SERVICE                                   ║${RST}"
echo "${YLW}  ║                                                          ║${RST}"
printf "${YLW}  ║      ${GRN}python scripts/acm_service.py${YLW}                    ║${RST}\n"
echo "${YLW}  ║                                                          ║${RST}"
printf "${YLW}  ║      Then open: ${GRN}http://localhost:8765${YLW}                   ║${RST}\n"
echo "${YLW}  ║                                                          ║${RST}"
echo "${YLW}  ║  2.  Click  RUN NOW  in the UI to start scoring         ║${RST}"
echo "${YLW}  ║      CARE turbine CSVs pre-loaded in Simulate → Files   ║${RST}"
echo "${YLW}  ║                                                          ║${RST}"
echo "${YLW}  ║  Boot at startup: systemd  or  cron @reboot             ║${RST}"
echo "${YLW}  ╚══════════════════════════════════════════════════════════╝${RST}"
echo ""
