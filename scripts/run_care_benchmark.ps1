<#
.SYNOPSIS
  One-command CARE benchmark for ACM's unsupervised ML core (Windows).

  1. Clones (or pulls) the ACM repo at the given branch
  2. Installs the Python dependencies the ML core needs (no SQL Server, no
     observability stack required)
  3. Downloads the requested CARE_To_Compare wind farm(s) from Zenodo
  4. Runs the benchmark over every event dataset and prints the KPI verdict

.EXAMPLE
  # Full Wind Farm A benchmark (22 events, ~20 min)
  .\run_care_benchmark.ps1

  # Quick targeted run against known faults
  .\run_care_benchmark.ps1 -Datasets "40 10 68"

  # All three farms (95 events; B/C are larger downloads and slower runs)
  .\run_care_benchmark.ps1 -Farms "A","B","C"
#>
param(
    [string]$Repo      = "https://github.com/bhadkamkar9snehil/ACM.git",
    [string]$Branch    = "claude/charming-cerf-3mt13j",
    [string]$WorkDir   = "$PWD\acm_care_bench",
    [string[]]$Farms   = @("A"),
    [string]$Datasets  = "",     # space-separated event IDs; empty = all
)

$ErrorActionPreference = "Stop"

# 1. Code
if (Test-Path "$WorkDir\ACM\.git") {
    Write-Host "== Updating ACM ($Branch) =="
    git -C "$WorkDir\ACM" fetch origin $Branch
    git -C "$WorkDir\ACM" checkout $Branch
    git -C "$WorkDir\ACM" pull origin $Branch
} else {
    Write-Host "== Cloning ACM ($Branch) =="
    New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
    git clone --branch $Branch --single-branch $Repo "$WorkDir\ACM"
}
Set-Location "$WorkDir\ACM"

# 2. Dependencies (ML core only)
Write-Host "== Installing Python dependencies =="
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pandas numpy polars pyarrow scikit-learn scipy structlog remotezip

# 3. Dataset
Write-Host "== Downloading CARE_To_Compare farm(s): $($Farms -join ', ') =="
python scripts/download_care_dataset.py --dest "$WorkDir\care_data" --farms @Farms

# 4. Benchmark
foreach ($farm in $Farms) {
    $dataDir = "$WorkDir\care_data\CARE_To_Compare\Wind Farm $farm"
    $outDir  = "$WorkDir\results\farm_$farm"
    Write-Host "`n== Benchmarking Wind Farm $farm =="
    $extra = @()
    if ($Datasets -ne "") { $extra = @("--datasets") + ($Datasets -split " ") }
    python scripts/care_benchmark.py --data-dir $dataDir --out $outDir @extra
    Write-Host "Results: $outDir\results.csv | $outDir\summary.json"
}
