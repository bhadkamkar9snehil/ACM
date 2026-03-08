# ACM Developer Tools Installer
# Run as: pwsh -ExecutionPolicy Bypass -File scripts/install_dev_tools.ps1
# Or right-click -> "Run with PowerShell" as Administrator

param(
    [switch]$NoAdmin
)

Write-Host "ACM Developer Tools Setup" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

# --- 1. Python LSP (pylsp) for VS Code / Claude Code codebase navigation ---
Write-Host "`n[1/3] Installing Python Language Server (pylsp)..." -ForegroundColor Yellow
pip install "python-lsp-server[all]" pylsp-mypy python-lsp-black 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  pylsp installed." -ForegroundColor Green
} else {
    Write-Host "  pylsp install failed. Try: pip install python-lsp-server" -ForegroundColor Red
}

# --- 2. Pyright (Microsoft static type checker + LSP) ---
Write-Host "`n[2/3] Installing Pyright via npm..." -ForegroundColor Yellow
npm install -g pyright 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  pyright installed." -ForegroundColor Green
} else {
    Write-Host "  npm install failed. Trying pip..." -ForegroundColor Yellow
    pip install pyright 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  pyright installed via pip." -ForegroundColor Green
    } else {
        Write-Host "  pyright install failed." -ForegroundColor Red
    }
}

# --- 3. Useful analysis tools ---
Write-Host "`n[3/3] Installing analysis tools..." -ForegroundColor Yellow
pip install ruff mypy types-pyodbc 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ruff, mypy, stubs installed." -ForegroundColor Green
}

Write-Host "`nDone. Verify with:" -ForegroundColor Cyan
Write-Host "  pylsp --version"
Write-Host "  pyright --version"
Write-Host "  ruff --version"
Write-Host ""
Write-Host "VS Code: Install 'Pylance' extension (uses pyright internally)." -ForegroundColor Cyan
Write-Host "Claude Code: No extra config needed — pylsp works via the editor LSP bridge." -ForegroundColor Cyan
