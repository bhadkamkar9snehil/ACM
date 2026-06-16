<#
.SYNOPSIS
  ACM one-command setup for ANY Windows machine.

  Installs prerequisites (Git + Python 3.11, via winget when present, direct
  official installers when not), clones or updates ACM from GitHub, installs
  Python dependencies, detects SQL Server (optional - SQLite is the default
  store), and verifies the install quietly. Full logs go to setup_acm.log;
  the console shows one line per step with live status.

.USAGE
  irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex
#>
param(
    [string]$Repo       = "https://github.com/bhadkamkar9snehil/ACM.git",
    [string]$Branch     = "main",
    [string]$InstallDir = "$HOME\ACM"
)
$ErrorActionPreference = "Stop"
$Log = Join-Path ([System.IO.Path]::GetTempPath()) "setup_acm.log"
"ACM setup $(Get-Date -Format s)" | Out-File $Log

$Sep = "  " + ([string][char]0x2500) * 53   # horizontal rule

function Section($title) {
    Write-Host ""
    Write-Host "  $title" -ForegroundColor DarkGray
}

function Step($name, [scriptblock]$body) {
    # Show in-progress indicator; overwrite with result when done
    Write-Host "    $([char]0x00B7)  $name" -NoNewline
    try {
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 0
        & $body *>> $Log
        $ErrorActionPreference = $oldEAP
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
        Write-Host "`r    " -NoNewline
        Write-Host ([char]0x2713) -ForegroundColor Green -NoNewline
        Write-Host "  $name"
    } catch {
        Write-Host "`r    " -NoNewline
        Write-Host ([char]0x2717) -ForegroundColor Red -NoNewline
        Write-Host "  $name"
        Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "       Log: $Log" -ForegroundColor DarkGray
        throw
    }
}

function Step-Visible($name, [scriptblock]$body) {
    Write-Host "    $([char]0x00B7)  $name"
    try {
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 0
        & $body 2>&1 | Tee-Object -Append -FilePath $Log | ForEach-Object {
            Write-Host "         $_" -ForegroundColor DarkGray
        }
        $ErrorActionPreference = $oldEAP
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
        Write-Host "    $([char]0x2713)  $name (Complete)" -ForegroundColor Green
    } catch {
        Write-Host "    $([char]0x2717)  $name (Failed)" -ForegroundColor Red
        Write-Host "       $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "       Log: $Log" -ForegroundColor DarkGray
        throw
    }
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Ensure-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $v = (& python --version 2>&1) -replace "Python ", ""
        if ([version]$v -ge [version]"3.11") { return }
    }
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Python.Python.3.11 -e --silent `
            --accept-source-agreements --accept-package-agreements
    } else {
        $url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $exe = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
        Invoke-WebRequest $url -OutFile $exe -ErrorAction Stop
        Start-Process $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
    }
    Refresh-Path
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python installed but not on PATH - open a new terminal and re-run."
    }
}

function Ensure-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) { return }
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install --id Git.Git -e --silent `
            --accept-source-agreements --accept-package-agreements
    } else {
        $url = "https://github.com/git-for-windows/git/releases/download/v2.45.2.windows.1/Git-2.45.2-64-bit.exe"
        $exe = Join-Path $env:TEMP "git-installer.exe"
        Invoke-WebRequest $url -OutFile $exe -ErrorAction Stop
        Start-Process $exe -ArgumentList "/VERYSILENT /NORESTART" -Wait
    }
    Refresh-Path
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git installed but not on PATH - open a new terminal and re-run."
    }
}

# --- Header -------------------------------------------------------------------
Write-Host ""
Write-Host "  ACM  $([char]0x00B7)  Asset Condition Monitor" -ForegroundColor Cyan
Write-Host $Sep -ForegroundColor DarkGray

# --- Prerequisites ------------------------------------------------------------
Section "Prerequisites"
Step "Git"          { Ensure-Git }
Step "Python 3.11+" { Ensure-Python }

# --- Install ------------------------------------------------------------------
Section "Install"
Step "Clone / update" {
    if (Test-Path "$InstallDir\.git") {
        git -C $InstallDir fetch origin $Branch
        git -C $InstallDir checkout $Branch
        git -C $InstallDir reset --hard origin/$Branch
    } else {
        git clone --branch $Branch --single-branch $Repo $InstallDir
    }
}
Set-Location $InstallDir
Step "Create directories" {
    python -c "
from pathlib import Path
for d in ('sim_data/sample','sim_data/generated','sim_data/uploads','data_cache','configs'):
    Path(d).mkdir(parents=True, exist_ok=True)
    (Path(d) / '.gitkeep').touch()
print('OK')
"
}
Step "Python packages" {
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet pandas numpy polars pyarrow scikit-learn scipy `
        structlog matplotlib remotezip pytest httpx `
        fastapi uvicorn python-multipart pydantic `
        asyncua paho-mqtt openpyxl
}
Step "SQL Server driver (optional)" {
    # pyodbc requires ODBC headers — silently skip if unavailable
    python -m pip install --quiet pyodbc 2>$null; $global:LASTEXITCODE = 0
}
Step "Verify imports" {
    python -c "
import sys; sys.path.insert(0,'.')
import pandas, numpy, polars, sklearn, matplotlib, fastapi, uvicorn
import core.pipeline, scripts.acm_store, scripts.acm_service
from sim.generator_registry import list_generators
from sim.buffer_publisher import BufferPublisher
from sim.sim_adapter import SimAdapter
from scripts.acm_sim_routes import router
print(f'{len(list_generators())} generators, {len(router.routes)} sim routes — OK')
"
}
# Smoke test — verify ACM can start and respond to HTTP (instead of slow pytest)
$_smokeDb  = "$env:TEMP\acm_smoke_$PID.db"
$_smokeOut = "$env:TEMP\acm_smoke_$PID.out"
$_smokeErr = "$env:TEMP\acm_smoke_$PID.err"
Write-Host "    $([char]0x00B7)  Smoke test (ACM starts)" -NoNewline
$_proc = Start-Process python `
    -ArgumentList "scripts\acm_service.py","--port","8766","--db","$_smokeDb" `
    -WorkingDirectory $InstallDir -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput "$_smokeOut" -RedirectStandardError "$_smokeErr"
$_ok = $false
for ($_i = 0; $_i -lt 6; $_i++) {
    Start-Sleep 2
    try {
        $_r = Invoke-WebRequest -Uri "http://127.0.0.1:8766/api/service" `
            -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($_r.StatusCode -eq 200) { $_ok = $true; break }
    } catch {}
}
try { $_proc.Kill() } catch {}
try { Wait-Process -Id $_proc.Id -ErrorAction SilentlyContinue } catch {}
Remove-Item "$_smokeDb","$_smokeOut","$_smokeErr" -ErrorAction SilentlyContinue
if ($_ok) {
    Write-Host "`r    $([char]0x2713)  Smoke test (ACM starts)" -ForegroundColor Green
} else {
    Write-Host "`r    !  Smoke test (non-fatal)" -ForegroundColor Yellow
}

# Show CI status reminder
Write-Host ""
Write-Host "  $([char]0x00B7)  GitHub CI Status" -ForegroundColor DarkGray
Write-Host "    Check test results at: https://github.com/bhadkamkar9snehil/ACM/actions" -ForegroundColor DarkGray
Write-Host "    Run locally: python -m pytest tests/ -v" -ForegroundColor DarkGray

# Fault datasets — non-fatal: CSVs are pre-committed in git; regeneration is a bonus.
Write-Host "    $([char]0x00B7)  Fault datasets"
$faultOut = python -u scripts\generate_fault_dataset.py 2>&1 | ForEach-Object {
    $_ | Out-File $Log -Append
    Write-Host "         $_" -ForegroundColor DarkGray
    $_
}
$faultCode = $LASTEXITCODE
if ($faultCode -eq 0) {
    Write-Host "    $([char]0x2713)  Fault datasets" -ForegroundColor Green
} else {
    Write-Host "    !  Fault datasets (non-fatal — pre-built CSVs already in repo)" -ForegroundColor Yellow
    Write-Host "       Run " -NoNewline -ForegroundColor DarkGray
    Write-Host "python scripts\generate_fault_dataset.py" -ForegroundColor Cyan -NoNewline
    Write-Host " to investigate." -ForegroundColor DarkGray
}

# --- Backend detection --------------------------------------------------------
$backendLabel = "SQLite  $([char]0x00B7)  zero-config default"
$hasSql = $false
try {
    python -m pip install --quiet pyodbc *>> $Log
    $rawDrivers = python -c "import pyodbc; print(';'.join(d for d in pyodbc.drivers() if 'SQL Server' in d))" 2>$null
    if ($rawDrivers) {
        $versions = ($rawDrivers -split ";") | ForEach-Object {
            if ($_ -match "ODBC Driver (\d+)") { $Matches[1] }
        } | Where-Object { $_ }
        $backendLabel = if ($versions) {
            "SQL Server  $([char]0x00B7)  ODBC Driver " + ($versions -join ", ")
        } else { "SQL Server" }
        $hasSql = $true
    }
} catch {}

# --- Optional Integrations ----------------------------------------------------
$setupCare = $false

Section "Optional Integrations"
Write-Host ""

if (Test-Path "sim_data\sample\care_farmA_0.csv") {
    Write-Host "  [1/1]  CARE-to-Compare demo data — already downloaded, refreshing asset paths." -ForegroundColor DarkGray
    Step "Register CARE assets" {
        python scripts\acm_seed_demo.py --care-dir sim_data\sample --db acm_results.db
    }
    $setupCare = $true
} else {
    $ans = Read-Host "  [1/1]  CARE-to-Compare demo data — real wind-turbine SCADA data, score immediately`n         Download 10 events from Farm A (~360 MB)? [y/N]"
    if ($ans -match '^[yY]') {
        Step-Visible "Download CARE events" {
            python scripts\download_care_dataset.py --farms A --count 10
        }
        Step "Register CARE assets" {
            python scripts\acm_seed_demo.py --care-dir sim_data\sample --db acm_results.db
        }
        $setupCare = $true
    }
}

# --- Summary ------------------------------------------------------------------
Write-Host ""
Write-Host $Sep -ForegroundColor DarkGray
Write-Host "  " -NoNewline
Write-Host ([char]0x2713) -ForegroundColor Green -NoNewline
Write-Host "  $InstallDir"
Write-Host "  " -NoNewline
Write-Host ([char]0x25B8) -ForegroundColor DarkGray -NoNewline
Write-Host "  $backendLabel" -ForegroundColor DarkGray
Write-Host $Sep -ForegroundColor DarkGray

# --- Next steps ---------------------------------------------------------------
$NL = [System.Environment]::NewLine
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "  ║                    NEXT STEPS                           ║" -ForegroundColor Yellow
Write-Host "  ╠══════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
Write-Host "  ║                                                          ║" -ForegroundColor Yellow
Write-Host "  ║  1.  START THE SERVICE                                   ║" -ForegroundColor Yellow
Write-Host "  ║                                                          ║" -ForegroundColor Yellow
Write-Host "  ║      " -NoNewline -ForegroundColor Yellow
Write-Host "python scripts\acm_service.py" -NoNewline -ForegroundColor Cyan
Write-Host "                    ║" -ForegroundColor Yellow
Write-Host "  ║                                                          ║" -ForegroundColor Yellow
Write-Host "  ║      Then open: " -NoNewline -ForegroundColor Yellow
Write-Host "http://localhost:8765" -NoNewline -ForegroundColor Cyan
Write-Host "                   ║" -ForegroundColor Yellow
Write-Host "  ║                                                          ║" -ForegroundColor Yellow
if ($setupCare) {
Write-Host "  ║  2.  Score CARE assets: click  RUN NOW  in the UI       ║" -ForegroundColor Yellow
Write-Host "  ║      (10 wind-turbine assets pre-registered)             ║" -ForegroundColor Yellow
Write-Host "  ║                                                          ║" -ForegroundColor Yellow
}
if (-not $setupCare) {
Write-Host "  ║  2.  One-shot batch run:                                 ║" -ForegroundColor Yellow
Write-Host "  ║      python scripts\acm_run.py --csv data.csv           ║" -ForegroundColor Yellow
Write-Host "  ║                                                          ║" -ForegroundColor Yellow
}
Write-Host "  ║  Boot at startup: Task Scheduler  or  NSSM              ║" -ForegroundColor Yellow
Write-Host "  ╚══════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
