<#
.SYNOPSIS
    SQL Batch Runner - Continuous ACM processing from SQL historian with smart coldstart.

.DESCRIPTION
    Runs ACM continuously from SQL mode, handling:
    1. Cold start - repeatedly calls ACM until coldstart completes successfully
    2. Batch processing - processes all available data in tick-sized windows
    3. Progress tracking - resumes from last successful batch

.PARAMETER Equipment
    Equipment codes to process (e.g., FD_FAN, GAS_TURBINE)

.PARAMETER SQLServer
    SQL Server instance (default: localhost\B19CL3PCQLSERVER)

.PARAMETER SQLDatabase
    SQL database name (default: ACM)

.PARAMETER TickMinutes
    Batch window size in minutes (default: 30)

.PARAMETER MaxColdstartAttempts
    Maximum coldstart retry attempts (default: 10)

.PARAMETER MaxWorkers
    Number of equipment to process in parallel (default: 1)

.PARAMETER Resume
    Resume from last successful batch

.PARAMETER DryRun
    Print commands without running

.EXAMPLE
    .\run_sql_batch.ps1 -Equipment FD_FAN

.EXAMPLE
    .\run_sql_batch.ps1 -Equipment FD_FAN,GAS_TURBINE -MaxWorkers 2

.EXAMPLE
    .\run_sql_batch.ps1 -Equipment FD_FAN -Resume

.EXAMPLE
    .\run_sql_batch.ps1 -Equipment FD_FAN -DryRun

.NOTES
    Processing Flow:
      1. COLDSTART PHASE: Repeatedly calls ACM until coldstart completes
         - Auto-detects data cadence
         - Loads from earliest available data
         - Retries with exponential window expansion
         - Tracks progress in ACM_ColdstartState table
      
      2. BATCH PHASE: Processes all available data in tick-sized windows
         - Continues from coldstart end point
         - Processes batches sequentially
         - Tracks progress in .sql_batch_progress.json
#>

param(
    [Parameter(Mandatory=$true)]
    [string[]]$Equipment,
    
    [Parameter(Mandatory=$false)]
    [string]$SQLServer = "localhost\B19CL3PCQLSERVER",
    
    [Parameter(Mandatory=$false)]
    [string]$SQLDatabase = "ACM",
    
    [Parameter(Mandatory=$false)]
    [int]$TickMinutes = 30,
    
    [Parameter(Mandatory=$false)]
    [int]$MaxColdstartAttempts = 10,
    
    [Parameter(Mandatory=$false)]
    [int]$MaxWorkers = 1,
    
    [Parameter(Mandatory=$false)]
    [switch]$Resume,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,

    [Parameter(Mandatory=$false)]
    [int]$MaxBatches,

    [Parameter(Mandatory=$false)]
    [switch]$StartFromBeginning
)

# Ensure we're in the project root
$OutputEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$ScriptDir = Split-Path -Parent $PSCommandPath
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..") 
Set-Location $ProjectRoot

Write-Host "=== SQL Batch Runner - Continuous ACM Processing ===" -ForegroundColor Cyan
Write-Host "Equipment: $($Equipment -join ', ')" -ForegroundColor Yellow
Write-Host "SQL Server: $SQLServer/$SQLDatabase" -ForegroundColor Gray
Write-Host "Tick Window: $TickMinutes minutes" -ForegroundColor Gray
Write-Host "Max Workers: $MaxWorkers" -ForegroundColor Gray
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Gray

# Build command
$cmd = "python scripts/sql_batch_runner.py"
$cmd += " --equip " + ($Equipment -join " ")
$cmd += " --sql-server `"$SQLServer`""
$cmd += " --sql-database `"$SQLDatabase`""
$cmd += " --tick-minutes $TickMinutes"
$cmd += " --max-coldstart-attempts $MaxColdstartAttempts"
$cmd += " --max-workers $MaxWorkers"

if ($MaxBatches) { $cmd += " --max-batches $MaxBatches" }
if ($StartFromBeginning) { $cmd += " --start-from-beginning" }

if ($Resume) {
    $cmd += " --resume"
}

if ($DryRun) {
    $cmd += " --dry-run"
}

Write-Host "`nExecuting: $cmd" -ForegroundColor Cyan
Write-Host "---" -ForegroundColor Gray

# Execute
Invoke-Expression $cmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== BATCH RUNNER COMPLETED SUCCESSFULLY ===" -ForegroundColor Green
} else {
    Write-Host "`n=== BATCH RUNNER FAILED (Exit Code: $LASTEXITCODE) ===" -ForegroundColor Red
    exit $LASTEXITCODE
}
