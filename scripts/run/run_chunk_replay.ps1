<#
.SYNOPSIS
    Run ACM chunk replay for all equipment with proper folder structure.

.DESCRIPTION
    Standardized chunk replay runner that enforces correct folder structure:
    artifacts/{EQUIP}/run_{timestamp}/

.PARAMETER Equipment
    Equipment codes (e.g., FD_FAN, GAS_TURBINE). Leave empty for all discovered equipment.

.PARAMETER ClearCache
    Force model retraining on first chunk

.PARAMETER MaxWorkers
    Number of equipment to process in parallel (default: 1)

.PARAMETER Resume
    Resume from last successful chunk (skip completed chunks)

.EXAMPLE
    .\run_chunk_replay.ps1 -Equipment FD_FAN,GAS_TURBINE

.EXAMPLE
    .\run_chunk_replay.ps1 -ClearCache -Resume

.NOTES
    CRITICAL: This script enforces the correct folder structure.
    Chunks must be in data/chunked/{EQUIP}/ directory.
#>

param(
    [Parameter(Mandatory=$false)]
    [string[]]$Equipment = @(),
    
    [Parameter(Mandatory=$false)]
    [switch]$ClearCache,
    
    [Parameter(Mandatory=$false)]
    [int]$MaxWorkers = 1,
    
    [Parameter(Mandatory=$false)]
    [switch]$Resume
)

# Ensure we're in the project root
$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") 
Set-Location $ProjectRoot

Write-Host "=== ACM V8 Chunk Replay Runner ===" -ForegroundColor Cyan
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray

# Build command
$cmd = "python scripts/chunk_replay.py"

if ($Equipment.Count -gt 0) {
    $cmd += " --equip " + ($Equipment -join " ")
}

if ($ClearCache) {
    $cmd += " --clear-cache"
}

if ($Resume) {
    $cmd += " --resume"
}

$cmd += " --max-workers $MaxWorkers"

# CRITICAL: Chunk replay script already handles correct folder structure internally
# It creates: artifacts/{EQUIP}/run_{timestamp}/
Write-Host "Artifact Structure: artifacts/{EQUIP}/run_{timestamp}/ (ENFORCED)" -ForegroundColor Green

Write-Host "`nExecuting: $cmd" -ForegroundColor Cyan
Write-Host "---" -ForegroundColor Gray

# Execute
Invoke-Expression $cmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== CHUNK REPLAY COMPLETED SUCCESSFULLY ===" -ForegroundColor Green
    Write-Host "Check artifacts/{EQUIP}/ directories for all runs" -ForegroundColor Gray
} else {
    Write-Host "`n=== CHUNK REPLAY FAILED (Exit Code: $LASTEXITCODE) ===" -ForegroundColor Red
    exit $LASTEXITCODE
}
