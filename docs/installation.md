# Installation

## Prerequisites

| Platform | Requirement |
|---|---|
| Linux / macOS | Python 3.11+ already installed |
| Windows | Git + Python 3.11+ (auto-installed by the script if missing) |

---

## One-command install

### Linux / macOS

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup.sh)
```

### Windows (PowerShell as Administrator)

```powershell
irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex
```

---

## What the installer does

1. Clones / updates the ACM repo to `~/ACM`
2. Creates directories: `sim_data/`, `data_cache/`, `configs/`
3. Installs Python packages:
   ```
   pandas numpy polars pyarrow scikit-learn scipy structlog matplotlib
   remotezip pytest httpx fastapi uvicorn python-multipart pydantic
   asyncua paho-mqtt openpyxl
   ```
4. Verifies all imports load correctly (fatal — proves packages installed)
5. Runs an HTTP smoke test (non-fatal)
6. Generates 10 fault CSV datasets in `sim_data/sample/` (non-fatal)
7. Optionally seeds CARE demo wind-farm data
8. Optionally seeds OPC UA simulator asset (requires separate Simulator installation)

---

## Starting the service

```bash
cd ~/ACM
python scripts/acm_service.py
```

Opens at **http://localhost:8765**

Optional flags:
```bash
python scripts/acm_service.py --port 8766          # custom port
python scripts/acm_service.py --db mydb.db          # custom SQLite DB file
python scripts/acm_service.py --backend mssql --conn "..."  # SQL Server
```

---

## Updating

Click **Update ACM** (amber button in the header) from any browser tab, or run:

```bash
cd ~/ACM && git pull --ff-only
```

A service restart is required for code changes to take effect.

---

## Running tests

```bash
cd ~/ACM
python -m pytest tests/ -v                    # all tests
python -m pytest tests/ -m "not slow" -v     # fast tests only (~40s)
```

CI runs automatically on every push — check the [Actions tab](https://github.com/bhadkamkar9snehil/ACM/actions).
