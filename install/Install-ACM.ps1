<#
.SYNOPSIS
    Comprehensive ACM installer for Windows

.DESCRIPTION
    Installs ACM from scratch, including:
    - Prerequisites verification
    - Python virtual environment creation
    - Python dependencies installation
    - SQL Server database creation
    - SQL schema installation (tables, views, stored procedures)
    - Configuration setup
    - Observability stack (Docker-based, optional)
    - Installation verification

    Prerequisites (must be installed separately):
    - SQL Server instance (any edition)
    - Python 3.11 or later
    - SQL Server ODBC Driver 18
    - Docker Desktop (optional, for observability)

.PARAMETER Server
    SQL Server instance name (e.g., "localhost\SQLEXPRESS")

.PARAMETER Database
    Database name to create/use (default: ACM)

.PARAMETER TrustedConnection
    Use Windows Authentication (recommended)

.PARAMETER SqlUser
    SQL Server username (if not using Windows Auth)

.PARAMETER SqlPassword
    SQL Server password (if not using Windows Auth)

.PARAMETER SkipVenv
    Skip creating a Python virtual environment

.PARAMETER SkipObservability
    Skip observability stack installation

.PARAMETER SkipVerification
    Skip post-install verification

.EXAMPLE
    .\Install-ACM.ps1 -Server "localhost\SQLEXPRESS" -TrustedConnection
    
.EXAMPLE
    .\Install-ACM.ps1 -Server "myserver,1433" -SqlUser "sa" -SqlPassword "MyP@ssw0rd"

.EXAMPLE
    .\Install-ACM.ps1 -Server "localhost" -TrustedConnection -SkipObservability

.NOTES
    Author: ACM Team
    Version: 1.0.0
    Requires: PowerShell 5.1+, Admin rights recommended
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, HelpMessage="SQL Server instance (e.g., localhost\SQLEXPRESS)")]
    [string]$Server,
    
    [Parameter(Mandatory=$false)]
    [string]$Database = "ACM",
    
    [Parameter(Mandatory=$false)]
    [switch]$TrustedConnection,
    
    [Parameter(Mandatory=$false)]
    [string]$SqlUser,
    
    [Parameter(Mandatory=$false)]
    [string]$SqlPassword,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipVenv,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipObservability,
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Script root directory
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptRoot

# Helper functions
function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Warn-Custom {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

# Banner
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ACM Comprehensive Installer" -ForegroundColor Green
Write-Host "  Version 11.0.0" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Info "Installation Directory: $ProjectRoot"
Write-Info "SQL Server: $Server"
Write-Info "Database: $Database"
Write-Host ""

# Step 1: Check Prerequisites
Write-Step "Step 1: Checking Prerequisites"
$prereqScript = Join-Path $ScriptRoot "Test-Prerequisites.ps1"
if (Test-Path $prereqScript) {
    & $prereqScript
    if ($LASTEXITCODE -ne 0) {
        throw "Prerequisites check failed. Please install missing components."
    }
} else {
    Write-Warn-Custom "Prerequisites script not found, skipping check"
}

# Step 2: Create Python Virtual Environment
if (-not $SkipVenv) {
    Write-Step "Step 2: Creating Python Virtual Environment"
    
    $venvPath = Join-Path $ProjectRoot ".venv"
    if (Test-Path $venvPath) {
        Write-Info "Virtual environment already exists at $venvPath"
        $response = Read-Host "Delete and recreate? (y/N)"
        if ($response -eq 'y' -or $response -eq 'Y') {
            Write-Info "Removing existing virtual environment..."
            Remove-Item -Recurse -Force $venvPath
        } else {
            Write-Info "Using existing virtual environment"
        }
    }
    
    if (-not (Test-Path $venvPath)) {
        Write-Info "Creating virtual environment at $venvPath"
        python -m venv $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment"
        }
        Write-Success "Virtual environment created"
    }
    
    # Activate virtual environment
    $activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        Write-Info "Activating virtual environment..."
        & $activateScript
        Write-Success "Virtual environment activated"
    } else {
        throw "Virtual environment activation script not found"
    }
} else {
    Write-Step "Step 2: Skipping Virtual Environment Creation"
}

# Step 3: Install Python Dependencies
Write-Step "Step 3: Installing Python Dependencies"

Write-Info "Upgrading pip..."
python -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip"
}

Write-Info "Installing ACM dependencies..."
$pyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
if (Test-Path $pyprojectPath) {
    python -m pip install -e "$ProjectRoot" --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install ACM dependencies"
    }
    Write-Success "Base dependencies installed"
    
    # Install observability dependencies
    if (-not $SkipObservability) {
        Write-Info "Installing observability dependencies..."
        python -m pip install -e "${ProjectRoot}[observability]" --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Warn-Custom "Failed to install observability dependencies (non-critical)"
        } else {
            Write-Success "Observability dependencies installed"
        }
    }
} else {
    throw "pyproject.toml not found at $pyprojectPath"
}

# Step 4: Create SQL Connection Configuration
Write-Step "Step 4: Configuring SQL Connection"

$configsDir = Join-Path $ProjectRoot "configs"
$sqlConnFile = Join-Path $configsDir "sql_connection.ini"

# Create config content
$configContent = @"
# ACM SQL Server Connection Configuration
# Generated by Install-ACM.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

[acm]
server = $Server
database = $Database
"@

if ($TrustedConnection) {
    $configContent += @"

trusted_connection = yes
"@
} else {
    if (-not $SqlUser -or -not $SqlPassword) {
        throw "SqlUser and SqlPassword are required when not using TrustedConnection"
    }
    $configContent += @"

user = $SqlUser
password = $SqlPassword
"@
}

$configContent += @"

driver = ODBC Driver 18 for SQL Server
TrustServerCertificate = yes
encrypt = no

[historian]
server = $Server
database = XStudio_Historian
"@

if ($TrustedConnection) {
    $configContent += @"

trusted_connection = yes
"@
} else {
    $configContent += @"

user = $SqlUser
password = $SqlPassword
"@
}

$configContent += @"

driver = ODBC Driver 18 for SQL Server
TrustServerCertificate = yes

[dow]
server = $Server
database = XStudio_DOW
"@

if ($TrustedConnection) {
    $configContent += @"

trusted_connection = yes
"@
} else {
    $configContent += @"

user = $SqlUser
password = $SqlPassword
"@
}

$configContent += @"

driver = ODBC Driver 18 for SQL Server
TrustServerCertificate = yes
"@

# Write config file
if (Test-Path $sqlConnFile) {
    Write-Warn-Custom "sql_connection.ini already exists"
    $response = Read-Host "Overwrite? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Keeping existing sql_connection.ini"
    } else {
        $configContent | Out-File -FilePath $sqlConnFile -Encoding UTF8 -Force
        Write-Success "SQL connection configuration updated"
    }
} else {
    $configContent | Out-File -FilePath $sqlConnFile -Encoding UTF8 -Force
    Write-Success "SQL connection configuration created"
}

# Step 5: Create SQL Database and Schema
Write-Step "Step 5: Installing SQL Database Schema"

$installScript = Join-Path $ScriptRoot "install_acm.py"
if (-not (Test-Path $installScript)) {
    throw "install_acm.py not found at $installScript"
}

Write-Info "Running SQL schema installation..."
Write-Info "This may take a few minutes..."

$installArgs = @("--ini-section", "acm")
python $installScript @installArgs

if ($LASTEXITCODE -ne 0) {
    throw "SQL schema installation failed"
}

Write-Success "SQL database and schema installed"

# Step 6: Populate ACM Configuration
Write-Step "Step 6: Populating ACM Configuration"

$populateScript = Join-Path $ProjectRoot "scripts\sql\populate_acm_config.py"
if (Test-Path $populateScript) {
    Write-Info "Syncing config_table.csv to ACM_Config table..."
    python $populateScript
    if ($LASTEXITCODE -ne 0) {
        Write-Warn-Custom "Failed to populate ACM_Config (non-critical, can run manually later)"
    } else {
        Write-Success "ACM_Config table populated"
    }
} else {
    Write-Warn-Custom "populate_acm_config.py not found, skipping"
}

# Step 7: Setup Observability Stack
if (-not $SkipObservability) {
    Write-Step "Step 7: Setting Up Observability Stack"
    
    # Check if Docker is available
    try {
        docker --version | Out-Null
        docker ps | Out-Null
        
        $dockerComposeFile = Join-Path $ScriptRoot "observability\docker-compose.yaml"
        if (Test-Path $dockerComposeFile) {
            Write-Info "Starting observability stack with Docker Compose..."
            Push-Location (Join-Path $ScriptRoot "observability")
            try {
                docker compose up -d
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Observability stack started"
                    Write-Info "Waiting for services to be ready (30 seconds)..."
                    Start-Sleep -Seconds 30
                    
                    Write-Host ""
                    Write-Info "Observability Endpoints:"
                    Write-Host "  Grafana:    http://localhost:3000 (admin/admin)" -ForegroundColor White
                    Write-Host "  Prometheus: http://localhost:9090" -ForegroundColor White
                    Write-Host "  Tempo:      http://localhost:3200" -ForegroundColor White
                    Write-Host "  Loki:       http://localhost:3100" -ForegroundColor White
                    Write-Host "  Pyroscope:  http://localhost:4040" -ForegroundColor White
                    Write-Host ""
                } else {
                    Write-Warn-Custom "Failed to start observability stack"
                }
            } finally {
                Pop-Location
            }
        } else {
            Write-Warn-Custom "docker-compose.yaml not found, skipping observability setup"
        }
    } catch {
        Write-Warn-Custom "Docker not available, skipping observability stack"
        Write-Info "Install Docker Desktop to enable observability features"
    }
} else {
    Write-Step "Step 7: Skipping Observability Stack"
}

# Step 8: Verification
if (-not $SkipVerification) {
    Write-Step "Step 8: Verifying Installation"
    
    $verifyScript = Join-Path $ProjectRoot "scripts\sql\verify_acm_connection.py"
    if (Test-Path $verifyScript) {
        Write-Info "Testing SQL connection and schema..."
        python $verifyScript
        if ($LASTEXITCODE -eq 0) {
            Write-Success "SQL connection and schema verified"
        } else {
            Write-Warn-Custom "Verification warnings detected (may be non-critical)"
        }
    } else {
        Write-Warn-Custom "verify_acm_connection.py not found, skipping verification"
    }
    
    # Test Python imports
    Write-Info "Testing Python imports..."
    $testImportScript = Join-Path $ScriptRoot "test_imports.py"
    $testImportContent = @"
import sys
sys.path.insert(0, r'$ProjectRoot')

try:
    from core.acm_main import main
    from core.sql_client import SQLClient
    from core.observability import Console
    from utils.config_dict import ConfigDict
    print('[OK] All critical imports successful')
    sys.exit(0)
except Exception as e:
    print(f'[FAIL] Import failed: {e}')
    sys.exit(1)
"@
    $testImportContent | Out-File -FilePath $testImportScript -Encoding UTF8 -Force
    
    python $testImportScript
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Python imports verified"
    } else {
        Write-Error-Custom "Python imports failed"
    }
    
    Remove-Item $testImportScript -Force -ErrorAction SilentlyContinue
} else {
    Write-Step "Step 8: Skipping Verification"
}

# Final Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Activate the virtual environment (if not already active):" -ForegroundColor Cyan
Write-Host "   .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "2. Test ACM with a single equipment run:" -ForegroundColor Cyan
Write-Host "   python -m core.acm_main --equip YOUR_EQUIPMENT_NAME" -ForegroundColor White
Write-Host ""
Write-Host "3. Run batch processing:" -ForegroundColor Cyan
Write-Host "   python scripts\sql_batch_runner.py --equip EQUIP1 EQUIP2 --tick-minutes 1440" -ForegroundColor White
Write-Host ""

if (-not $SkipObservability) {
    Write-Host "4. Access Grafana dashboards:" -ForegroundColor Cyan
    Write-Host "   http://localhost:3000 (admin/admin)" -ForegroundColor White
    Write-Host ""
    Write-Host "5. Import ACM dashboards from grafana_dashboards/ folder" -ForegroundColor Cyan
    Write-Host ""
}

Write-Host "Documentation:" -ForegroundColor Yellow
Write-Host "  README.md              - Quick start guide" -ForegroundColor White
Write-Host "  docs/ACM_SYSTEM_OVERVIEW.md - Complete system documentation" -ForegroundColor White
Write-Host "  install/README.md      - Installation details" -ForegroundColor White
Write-Host ""

Write-Host "Configuration Files:" -ForegroundColor Yellow
Write-Host "  configs/sql_connection.ini - SQL Server connection" -ForegroundColor White
Write-Host "  configs/config_table.csv   - ACM parameters" -ForegroundColor White
Write-Host ""

Write-Host "For help, see: https://github.com/bhadkamkar9snehil/ACM" -ForegroundColor Cyan
Write-Host ""

exit 0
