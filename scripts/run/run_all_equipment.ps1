<#
.SYNOPSIS
    Run ACM for all 3 standard equipment types.

.DESCRIPTION
    Convenience script to run ACM for FD_FAN, GAS_TURBINE, and COND_PUMP
    with proper folder structure enforcement.

.PARAMETER Mode
    Run mode: 'full' (train+score), 'chunks' (chunk replay), or 'cache' (use cached models)

.PARAMETER ClearCache
    Force model retraining (applies to all equipment)

.EXAMPLE
    .\run_all_equipment.ps1 -Mode full

.EXAMPLE
    .\run_all_equipment.ps1 -Mode chunks -ClearCache

.NOTES
    Uses standardized data paths:
    - FD_FAN: data/FD FAN TRAINING DATA.csv + data/FD FAN TEST DATA.csv
    - GAS_TURBINE: data/GAS_TURBINE_BASELINE_DATA.csv + data/GAS_TURBINE_BATCH_DATA.csv  
    - COND_PUMP: data/Cond Pump Motor Training Set.csv + data/Cond Pump Motor Fault Set.csv
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('full', 'chunks', 'cache')]
    [string]$Mode = 'full',
    
    [Parameter(Mandatory=$false)]
    [switch]$ClearCache
)

# Ensure we're in the project root
$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") 
Set-Location $ProjectRoot

Write-Host "=== ACM V8 All Equipment Runner ===" -ForegroundColor Cyan
Write-Host "Mode: $Mode" -ForegroundColor Yellow
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray

$Equipment = @(
    @{
        Name = "FD_FAN"
        Train = "data/FD FAN TRAINING DATA.csv"
        Score = "data/FD FAN TEST DATA.csv"
    },
    @{
        Name = "GAS_TURBINE"
        Train = "data/GAS_TURBINE_BASELINE_DATA.csv"
        Score = "data/GAS_TURBINE_BATCH_DATA.csv"
    },
    @{
        Name = "COND_PUMP"
        Train = "data/Cond Pump Motor Training Set.csv"
        Score = "data/Cond Pump Motor Fault Set.csv"
    }
)

if ($Mode -eq 'chunks') {
    Write-Host "`nRunning chunk replay mode..." -ForegroundColor Cyan
    $cmd = ".\scripts\run\run_chunk_replay.ps1 -Equipment FD_FAN,GAS_TURBINE"
    if ($ClearCache) {
        $cmd += " -ClearCache"
    }
    Invoke-Expression $cmd
    exit $LASTEXITCODE
}

$FailedEquipment = @()
$SuccessCount = 0

foreach ($equip in $Equipment) {
    Write-Host "`n=====================================" -ForegroundColor Cyan
    Write-Host "Processing: $($equip.Name)" -ForegroundColor Yellow
    Write-Host "=====================================" -ForegroundColor Cyan
    
    $cmd = ".\scripts\run\run_single_equipment.ps1 -Equipment `"$($equip.Name)`""
    
    if ($Mode -eq 'full') {
        # Check if files exist
        if (Test-Path $equip.Train) {
            $cmd += " -TrainCSV `"$($equip.Train)`""
        } else {
            Write-Host "WARNING: Training file not found: $($equip.Train)" -ForegroundColor Yellow
        }
        
        if (Test-Path $equip.Score) {
            $cmd += " -ScoreCSV `"$($equip.Score)`""
        } else {
            Write-Host "WARNING: Score file not found: $($equip.Score)" -ForegroundColor Yellow
        }
    }
    
    if ($ClearCache) {
        $cmd += " -ClearCache"
    }
    
    try {
        Invoke-Expression $cmd
        if ($LASTEXITCODE -eq 0) {
            $SuccessCount++
            Write-Host "✓ $($equip.Name) completed successfully" -ForegroundColor Green
        } else {
            $FailedEquipment += $equip.Name
            Write-Host "✗ $($equip.Name) failed with exit code $LASTEXITCODE" -ForegroundColor Red
        }
    } catch {
        $FailedEquipment += $equip.Name
        Write-Host "✗ $($equip.Name) failed with exception: $_" -ForegroundColor Red
    }
}

Write-Host "`n=====================================" -ForegroundColor Cyan
Write-Host "SUMMARY" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Successful: $SuccessCount / $($Equipment.Count)" -ForegroundColor $(if($SuccessCount -eq $Equipment.Count){"Green"}else{"Yellow"})
if ($FailedEquipment.Count -gt 0) {
    Write-Host "Failed: $($FailedEquipment -join ', ')" -ForegroundColor Red
    exit 1
} else {
    Write-Host "All equipment processed successfully!" -ForegroundColor Green
    exit 0
}
