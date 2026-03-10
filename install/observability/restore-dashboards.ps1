#!/usr/bin/env pwsh
# restore-dashboards.ps1
# ======================
# Re-imports all dashboards from install/observability/dashboards/backup/ into Grafana.
# Run this after a docker compose down -v + docker compose up -d to restore saved dashboards.
#
# Usage:
#   pwsh install/observability/restore-dashboards.ps1
#   pwsh install/observability/restore-dashboards.ps1 -GrafanaUrl http://localhost:3000 -User admin -Pass admin

param(
    [string]$GrafanaUrl = "http://localhost:3000",
    [string]$User = "admin",
    [string]$Pass = "admin"
)

$ErrorActionPreference = "Stop"
$BackupDir = Join-Path $PSScriptRoot "dashboards\backup"

if (-not (Test-Path $BackupDir)) {
    Write-Host "No backup directory found at $BackupDir" -ForegroundColor Red
    Write-Host "Run backup-dashboards.ps1 first."
    exit 1
}

$Headers = @{
    Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Pass}"))
    "Content-Type" = "application/json"
}

# Wait for Grafana to be ready
Write-Host "Waiting for Grafana at $GrafanaUrl ..."
$Retries = 0
while ($Retries -lt 20) {
    try {
        $Health = Invoke-RestMethod -Uri "$GrafanaUrl/api/health" -Headers $Headers -Method Get -TimeoutSec 3
        if ($Health.database -eq "ok") { break }
    } catch {}
    Start-Sleep 3
    $Retries++
}

$JsonFiles = Get-ChildItem -Path $BackupDir -Recurse -Filter "*.json"

if ($JsonFiles.Count -eq 0) {
    Write-Host "No dashboard JSON files found in $BackupDir" -ForegroundColor Yellow
    exit 0
}

Write-Host "Restoring $($JsonFiles.Count) dashboard(s)..."

$Ok = 0
$Fail = 0
foreach ($File in $JsonFiles) {
    try {
        $DashJson = Get-Content $File.FullName -Raw -Encoding UTF8 | ConvertFrom-Json

        # Wrap in import payload — folderId 0 = General
        $Payload = @{
            dashboard = $DashJson
            folderId  = 0
            overwrite = $true
        } | ConvertTo-Json -Depth 50

        $Result = Invoke-RestMethod -Uri "$GrafanaUrl/api/dashboards/db" -Headers $Headers -Method Post -Body $Payload
        Write-Host "  [OK] $($File.Name)  ->  $($Result.url)"
        $Ok++
    } catch {
        Write-Host "  [FAIL] $($File.Name): $_" -ForegroundColor Red
        $Fail++
    }
}

Write-Host ""
if ($Fail -eq 0) {
    Write-Host "Restore complete. $Ok dashboard(s) imported." -ForegroundColor Green
} else {
    Write-Host "Restore finished with errors. OK=$Ok  FAIL=$Fail" -ForegroundColor Yellow
}
