#!/usr/bin/env pwsh
# backup-dashboards.ps1
# =====================
# Exports all Grafana dashboards to JSON files in install/observability/dashboards/backup/
# Run this before any docker compose down -v or before making significant dashboard changes.
#
# Usage:
#   pwsh install/observability/backup-dashboards.ps1
#   pwsh install/observability/backup-dashboards.ps1 -GrafanaUrl http://localhost:3000 -User admin -Pass admin

param(
    [string]$GrafanaUrl = "http://localhost:3000",
    [string]$User = "admin",
    [string]$Pass = "admin"
)

$ErrorActionPreference = "Stop"
$BackupDir = Join-Path $PSScriptRoot "dashboards\backup"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

$Headers = @{
    Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${User}:${Pass}"))
    "Content-Type" = "application/json"
}

Write-Host "Connecting to Grafana at $GrafanaUrl ..."

# List all dashboards
$SearchUrl = "$GrafanaUrl/api/search?type=dash-db&limit=500"
$Dashboards = Invoke-RestMethod -Uri $SearchUrl -Headers $Headers -Method Get

if ($Dashboards.Count -eq 0) {
    Write-Host "No dashboards found." -ForegroundColor Yellow
    exit 0
}

Write-Host "Found $($Dashboards.Count) dashboard(s). Exporting..."

foreach ($Dash in $Dashboards) {
    $Uid = $Dash.uid
    $Title = $Dash.title -replace '[\\/:*?"<>|]', '_'   # sanitize for filename

    $DetailUrl = "$GrafanaUrl/api/dashboards/uid/$Uid"
    $Detail = Invoke-RestMethod -Uri $DetailUrl -Headers $Headers -Method Get

    # Strip server-managed fields so the JSON can be cleanly re-imported
    $Dashboard = $Detail.dashboard
    $Dashboard.PSObject.Properties.Remove("id")
    $Dashboard.PSObject.Properties.Remove("version")

    $FolderTitle = if ($Detail.meta.folderTitle) { $Detail.meta.folderTitle } else { "General" }
    $FolderDir = Join-Path $BackupDir ($FolderTitle -replace '[\\/:*?"<>|]', '_')
    New-Item -ItemType Directory -Force -Path $FolderDir | Out-Null

    $FilePath = Join-Path $FolderDir "$Title.json"
    $Dashboard | ConvertTo-Json -Depth 50 | Set-Content -Path $FilePath -Encoding UTF8

    Write-Host "  [OK] $FolderTitle / $Title  ->  $FilePath"
}

Write-Host ""
Write-Host "Backup complete. $($Dashboards.Count) dashboard(s) saved to:" -ForegroundColor Green
Write-Host "  $BackupDir" -ForegroundColor Green
Write-Host ""
Write-Host "To restore after a volume wipe, use:"
Write-Host "  pwsh install/observability/restore-dashboards.ps1"
