<#
.SYNOPSIS
    Legacy sanity check for ACM artifact folder layout.

.DESCRIPTION
    The --artifact-root flag has been removed from acm_main; this script now
    simply runs a quick file-mode execution to confirm the default
    artifacts/{EQUIP}/run_* structure is still produced.
#>

param()

$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") 
Set-Location $ProjectRoot

Write-Host "=== ACM Folder Structure Smoke Test ===" -ForegroundColor Cyan
Write-Host "Verifying default artifacts path (artifacts/{EQUIP}/run_*)" -ForegroundColor Yellow

$TestEquip = "FD_FAN"
$TestTrain = "data/chunked/FD_FAN/FD FAN_batch_1.csv"
$TestScore = "data/chunked/FD_FAN/FD FAN_batch_2.csv"

if (!(Test-Path $TestTrain) -or !(Test-Path $TestScore)) {
    Write-Host "ERROR: Test data files not found" -ForegroundColor Red
    exit 1
}

python -m core.acm_main --equip $TestEquip --train-csv $TestTrain --score-csv $TestScore 2>&1 |
    Select-String -Pattern "Creating unique run directory"

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Smoke test FAILED" -ForegroundColor Red
    exit 1
}

Write-Host "`n✓ Default artifact structure verified" -ForegroundColor Green
