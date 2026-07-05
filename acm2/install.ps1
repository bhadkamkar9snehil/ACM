# ACM2 one-command install + start (Windows).
# Resilient by inheritance: warn on non-critical failures, never abort a
# working install. Air-gapped installs: bring uv + a wheel cache; the
# committed uv.lock pins everything.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "ACM2 install" -ForegroundColor Cyan

# 1) uv (the only bootstrap dependency)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  installing uv..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2) environment from the committed lockfile
Set-Location $here
uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

# 3) self-test (non-fatal: a red test is a warning, not a broken install)
uv run pytest tests -m "not statistical" -q --tb=no 2>&1 | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ! self-test reported failures (non-fatal) - run" `
        "'uv run pytest tests' to investigate" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "ACM2 ready. Start the service:" -ForegroundColor Green
Write-Host "  cd $here"
Write-Host "  uv run python -m acm2.service --root ../acm2_data --port 8899"
Write-Host "  -> http://127.0.0.1:8899"
