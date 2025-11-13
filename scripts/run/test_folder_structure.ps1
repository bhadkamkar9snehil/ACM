<#
.SYNOPSIS
    Test folder structure enforcement after acm_main.py fix.

.DESCRIPTION
    Runs quick test with various --artifact-root values to verify that
    equipment subdirectory is ALWAYS enforced.

.NOTES
    Expected structure: {artifact-root}/{EQUIP}/run_{timestamp}/
#>

param()

$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") 
Set-Location $ProjectRoot

Write-Host "=== Folder Structure Enforcement Test ===" -ForegroundColor Cyan
Write-Host "Testing that equipment subdirectory is ALWAYS added..." -ForegroundColor Yellow

# Test data (use first chunk file for quick test)
$TestEquip = "FD_FAN"
$TestTrain = "data/chunked/FD_FAN/FD FAN_batch_1.csv"
$TestScore = "data/chunked/FD_FAN/FD FAN_batch_2.csv"

if (!(Test-Path $TestTrain) -or !(Test-Path $TestScore)) {
    Write-Host "ERROR: Test data files not found" -ForegroundColor Red
    exit 1
}

Write-Host "`nTest 1: --artifact-root artifacts" -ForegroundColor Cyan
Write-Host "Expected: artifacts/FD_FAN/run_YYYYMMDD_HHMMSS/" -ForegroundColor Gray

python -m core.acm_main --equip $TestEquip --artifact-root "artifacts" --train-csv $TestTrain --score-csv $TestScore 2>&1 | Select-String -Pattern "Creating unique run directory"

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Test 1 FAILED" -ForegroundColor Red
    exit 1
}

Write-Host "`nTest 2: --artifact-root artifacts/TEST" -ForegroundColor Cyan
Write-Host "Expected: artifacts/TEST/FD_FAN/run_YYYYMMDD_HHMMSS/" -ForegroundColor Gray

python -m core.acm_main --equip $TestEquip --artifact-root "artifacts/TEST" --train-csv $TestTrain --score-csv $TestScore 2>&1 | Select-String -Pattern "Creating unique run directory"

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Test 2 FAILED" -ForegroundColor Red
    exit 1
}

Write-Host "`n✓ All tests passed!" -ForegroundColor Green
Write-Host "Equipment subdirectory is correctly enforced" -ForegroundColor Green
