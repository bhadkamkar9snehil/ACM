<#
.SYNOPSIS
  ACM one-command setup for ANY Windows machine. No Docker. Ever.

  Installs prerequisites (Python 3.11+, Git via winget if missing), clones or
  updates ACM from GitHub, installs Python dependencies, detects whether SQL
  Server is available (purely optional — SQLite is the default store), and
  verifies the installation by running the test suite.

.USAGE
  One command, from anywhere:

    irm https://raw.githubusercontent.com/bhadkamkar9snehil/ACM/main/setup_acm.ps1 | iex

  Or with options (clone first, then):

    .\setup_acm.ps1 -InstallDir C:\acm -Branch main
#>
param(
    [string]$Repo       = "https://github.com/bhadkamkar9snehil/ACM.git",
    [string]$Branch     = "main",
    [string]$InstallDir = "$HOME\ACM"
)
$ErrorActionPreference = "Stop"

function Ensure-Tool($name, $wingetId) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "== Installing $name via winget =="
        winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [Environment]::GetEnvironmentVariable("Path", "User")
    }
}

Ensure-Tool git  "Git.Git"
Ensure-Tool python "Python.Python.3.11"

# --- Code ---------------------------------------------------------------
if (Test-Path "$InstallDir\.git") {
    Write-Host "== Updating ACM ($Branch) =="
    git -C $InstallDir fetch origin $Branch
    git -C $InstallDir checkout $Branch
    git -C $InstallDir pull origin $Branch
} else {
    Write-Host "== Cloning ACM ($Branch) -> $InstallDir =="
    git clone --branch $Branch --single-branch $Repo $InstallDir
}
Set-Location $InstallDir

# --- Python dependencies (ML core + store + reports) ---------------------
Write-Host "== Installing Python dependencies =="
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pandas numpy polars pyarrow scikit-learn scipy `
    structlog matplotlib remotezip pytest

# --- SQL Server: OPTIONAL. SQLite is the default store. -------------------
$mssql = $false
try {
    python -c "import pyodbc" 2>$null
    if ($LASTEXITCODE -eq 0) { $mssql = $true }
} catch {}
if (-not $mssql) {
    try { python -m pip install --quiet pyodbc; $mssql = $true } catch {}
}
$drivers = if ($mssql) { python -c "import pyodbc; print(';'.join(d for d in pyodbc.drivers() if 'SQL Server' in d))" 2>$null } else { "" }

# --- Verify ----------------------------------------------------------------
Write-Host "== Verifying installation (test suite) =="
python -m pytest tests/ -q

Write-Host ""
Write-Host "=========================================================="
Write-Host " ACM is ready at $InstallDir"
Write-Host "=========================================================="
if ($drivers) {
    Write-Host " SQL Server ODBC drivers found: $drivers"
    Write-Host "   -> use:  --backend mssql --conn `"DRIVER={...};SERVER=...;DATABASE=ACM`""
} else {
    Write-Host " No SQL Server detected: using SQLite (acm_results.db). Nothing to install."
}
Write-Host ""
Write-Host " Quick start:"
Write-Host "   # benchmark against real labelled wind-farm faults (downloads data)"
Write-Host "   .\scripts\run_care_benchmark.ps1"
Write-Host ""
Write-Host "   # store results in SQL + build the visual report"
Write-Host "   python scripts\acm_store.py ingest --results-dir <results> --farm A --db acm_results.db"
Write-Host "   python scripts\acm_report.py --db acm_results.db --out report.html"
