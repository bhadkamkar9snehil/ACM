<#
.SYNOPSIS
  ACM one-command setup for ANY Windows machine.

  Installs prerequisites (Git + Python 3.11, via winget when present, direct
  official installers when not), clones or updates ACM from GitHub, installs
  Python dependencies, detects SQL Server (optional — SQLite is the default
  store), and verifies the install quietly. Full logs go to setup_acm.log;
  the console gets one line per step.

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

function Step($name, [scriptblock]$body) {
    Write-Host ("  {0,-46}" -f $name) -NoNewline
    try {
        $oldEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $global:LASTEXITCODE = 0
        & $body *>> $Log
        $ErrorActionPreference = $oldEAP
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
        Write-Host "OK" -ForegroundColor Green
    } catch {
        Write-Host "FAILED" -ForegroundColor Red
        Write-Host "  -> $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  -> full log: $Log"
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
        # No winget (Server editions, stripped images): official installer
        $url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $exe = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
        Invoke-WebRequest $url -OutFile $exe -ErrorAction Stop
        Start-Process $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
    }
    Refresh-Path
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python installed but not on PATH - open a NEW terminal and re-run."
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
        throw "Git installed but not on PATH - open a NEW terminal and re-run."
    }
}

Write-Host ""
Write-Host "ACM setup" -ForegroundColor Cyan
Step "Git"               { Ensure-Git }
Step "Python 3.11+"      { Ensure-Python }
Step "Clone/update ACM"  {
    if (Test-Path "$InstallDir\.git") {
        git -C $InstallDir fetch origin $Branch
        git -C $InstallDir checkout $Branch
        git -C $InstallDir pull origin $Branch
    } else {
        git clone --branch $Branch --single-branch $Repo $InstallDir
    }
}
Set-Location $InstallDir
Step "Python packages"   {
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet pandas numpy polars pyarrow scikit-learn scipy `
        structlog matplotlib remotezip pytest fastapi uvicorn httpx
}
Step "Verify imports"    {
    python -c "import pandas, numpy, polars, sklearn, matplotlib, fastapi, uvicorn; import core.pipeline, scripts.acm_store, scripts.acm_service"
}
Step "Self-test (quiet)" {
    python -m pytest tests/ -q --no-header -p no:warnings --basetemp="$InstallDir\.pytest_basetemp" 2>&1 | Select-Object -Last 1
}

$drivers = ""
try {
    python -m pip install --quiet pyodbc *>> $Log
    $drivers = python -c "import pyodbc; print(';'.join(d for d in pyodbc.drivers() if 'SQL Server' in d))" 2>$null
} catch {}

Write-Host ""
Write-Host "ACM is ready at $InstallDir" -ForegroundColor Green
if ($drivers) {
    Write-Host "SQL Server drivers found ($drivers) - mssql backend available."
} else {
    Write-Host "No SQL Server detected - using SQLite (zero setup). That is fine."
}
Write-Host ""
Write-Host "Start the always-on service (scheduler + control panel):"
Write-Host "  python scripts\acm_service.py"
Write-Host "  then open http://localhost:8765 and onboard assets from the Admin tab."
Write-Host "  (run at boot: Task Scheduler 'At startup' task, or wrap with NSSM)"
Write-Host ""
Write-Host "One-shot scoring on your own data:"
Write-Host "  python scripts\acm_run.py --csv your_asset.csv --timestamp-col time --score-days 30 --report report.html"
Write-Host "Or reproduce the public wind-farm benchmark:"
Write-Host "  .\scripts\run_care_benchmark.ps1"
