<#
.SYNOPSIS
    Run ACM for a single equipment with proper folder structure.

.DESCRIPTION
    Standardized runner that enforces correct folder structure:
    artifacts/{EQUIP}/run_{timestamp}/

.PARAMETER Equipment
    Equipment code (e.g., FD_FAN, GAS_TURBINE, COND_PUMP)

.PARAMETER TrainCSV
    Path to training/baseline CSV file (optional)

.PARAMETER ScoreCSV
    Path to scoring/batch CSV file (optional)

.PARAMETER ClearCache
    Force model retraining by clearing cache

.PARAMETER Config
    Custom config file path (optional, auto-discovers if not specified)

.EXAMPLE
    .\run_single_equipment.ps1 -Equipment FD_FAN -TrainCSV "data/FD FAN TRAINING DATA.csv" -ScoreCSV "data/FD FAN TEST DATA.csv"

.EXAMPLE
    .\run_single_equipment.ps1 -Equipment GAS_TURBINE -ClearCache

.NOTES
    CRITICAL: This script enforces the correct folder structure.
    Do NOT pass custom artifact-root paths!
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$Equipment,
    
    [Parameter(Mandatory=$false)]
    [string]$TrainCSV,
    
    [Parameter(Mandatory=$false)]
    [string]$ScoreCSV,
    
    [Parameter(Mandatory=$false)]
    [switch]$ClearCache,
    
    [Parameter(Mandatory=$false)]
    [string]$Config
)

# Ensure we're in the project root
$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") 
Set-Location $ProjectRoot

Write-Host "=== ACM V8 Single Equipment Runner ===" -ForegroundColor Cyan
Write-Host "Equipment: $Equipment" -ForegroundColor Yellow
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray

# ENFORCE CORRECT FOLDER STRUCTURE
# artifacts/{EQUIP}/run_{timestamp}/
$ArtifactRoot = Join-Path "artifacts" $Equipment

Write-Host "Artifact Root: $ArtifactRoot (ENFORCED)" -ForegroundColor Green

# Build command
$cmd = "python -m core.acm_main --equip `"$Equipment`" --artifact-root `"$ArtifactRoot`""

if ($TrainCSV) {
    $cmd += " --train-csv `"$TrainCSV`""
}

if ($ScoreCSV) {
    $cmd += " --score-csv `"$ScoreCSV`""
}

if ($ClearCache) {
    $cmd += " --clear-cache"
}

if ($Config) {
    $cmd += " --config `"$Config`""
}

Write-Host "`nExecuting: $cmd" -ForegroundColor Cyan
Write-Host "---" -ForegroundColor Gray

# Execute
Invoke-Expression $cmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== RUN COMPLETED SUCCESSFULLY ===" -ForegroundColor Green
    
    # Find the latest run directory
    $LatestRun = Get-ChildItem (Join-Path $ArtifactRoot "run_*") -Directory | 
                 Sort-Object LastWriteTime -Descending | 
                 Select-Object -First 1
    
    if ($LatestRun) {
        Write-Host "Output Location: $($LatestRun.FullName)" -ForegroundColor Green
        Write-Host "  - Tables: $(Join-Path $LatestRun.FullName 'tables')" -ForegroundColor Gray
        Write-Host "  - Charts: $(Join-Path $LatestRun.FullName 'charts')" -ForegroundColor Gray
    }
} else {
    Write-Host "`n=== RUN FAILED (Exit Code: $LASTEXITCODE) ===" -ForegroundColor Red
    exit $LASTEXITCODE
}
