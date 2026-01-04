<#
.SYNOPSIS
    Test prerequisites for ACM installation

.DESCRIPTION
    Checks that all required prerequisites are installed:
    - Python 3.11 or later
    - SQL Server ODBC Driver 18
    - Docker Desktop (for observability stack)
    - pip package manager

.EXAMPLE
    .\Test-Prerequisites.ps1
    .\Test-Prerequisites.ps1 -Verbose

.NOTES
    Returns $true if all prerequisites are met, $false otherwise
    Exit code 0 = all prerequisites met
    Exit code 1 = one or more prerequisites missing
#>

param(
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message, [string]$Type = "Info")
    
    switch ($Type) {
        "Success" { Write-Host "[OK]   $Message" -ForegroundColor Green }
        "Error"   { Write-Host "[FAIL] $Message" -ForegroundColor Red }
        "Info"    { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
        "Warn"    { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
    }
}

$allPrereqsMet = $true

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  ACM Prerequisites Checker" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python 3.11+
Write-Status "Checking Python version..." "Info"
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+)\.(\d+)\.(\d+)") {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        if ($major -ge 3 -and $minor -ge 11) {
            Write-Status "Python $($matches[1]).$($matches[2]).$($matches[3]) found" "Success"
        } else {
            Write-Status "Python $($matches[1]).$($matches[2]).$($matches[3]) found, but need 3.11+" "Error"
            $allPrereqsMet = $false
        }
    } else {
        Write-Status "Could not determine Python version" "Error"
        $allPrereqsMet = $false
    }
} catch {
    Write-Status "Python not found in PATH" "Error"
    Write-Host "         Install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    $allPrereqsMet = $false
}

# Check pip
Write-Status "Checking pip..." "Info"
try {
    $pipVersion = python -m pip --version 2>&1
    if ($pipVersion -match "pip (\d+\.\d+\.\d+)") {
        Write-Status "pip $($matches[1]) found" "Success"
    } else {
        Write-Status "pip found but version unclear" "Warn"
    }
} catch {
    Write-Status "pip not found" "Error"
    Write-Host "         Run: python -m ensurepip --upgrade" -ForegroundColor Yellow
    $allPrereqsMet = $false
}

# Check SQL Server ODBC Driver 18
Write-Status "Checking SQL Server ODBC Driver..." "Info"
try {
    $odbcDrivers = Get-OdbcDriver -Name "ODBC Driver 18 for SQL Server" -ErrorAction SilentlyContinue
    if ($odbcDrivers) {
        Write-Status "ODBC Driver 18 for SQL Server found" "Success"
    } else {
        # Try older version
        $odbcDrivers17 = Get-OdbcDriver -Name "ODBC Driver 17 for SQL Server" -ErrorAction SilentlyContinue
        if ($odbcDrivers17) {
            Write-Status "ODBC Driver 17 found (will work but 18 recommended)" "Warn"
        } else {
            Write-Status "ODBC Driver 18 for SQL Server not found" "Error"
            Write-Host "         Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server" -ForegroundColor Yellow
            $allPrereqsMet = $false
        }
    }
} catch {
    Write-Status "Could not check ODBC drivers (may need admin rights)" "Warn"
}

# Check Docker Desktop (optional for observability)
Write-Status "Checking Docker Desktop (optional)..." "Info"
try {
    $dockerVersion = docker --version 2>&1
    if ($dockerVersion -match "Docker version") {
        Write-Status "Docker found: $dockerVersion" "Success"
        
        # Check if Docker daemon is running
        try {
            docker ps | Out-Null
            Write-Status "Docker daemon is running" "Success"
        } catch {
            Write-Status "Docker installed but daemon not running" "Warn"
            Write-Host "         Start Docker Desktop to use observability stack" -ForegroundColor Yellow
        }
    } else {
        Write-Status "Docker not found (observability stack will be unavailable)" "Warn"
        Write-Host "         Install Docker Desktop from https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    }
} catch {
    Write-Status "Docker not found (observability stack will be unavailable)" "Warn"
    Write-Host "         Install Docker Desktop from https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
}

# Check Git (optional but recommended)
Write-Status "Checking Git (optional)..." "Info"
try {
    $gitVersion = git --version 2>&1
    if ($gitVersion -match "git version") {
        Write-Status "Git found: $gitVersion" "Success"
    } else {
        Write-Status "Git not found (recommended for updates)" "Warn"
    }
} catch {
    Write-Status "Git not found (recommended for updates)" "Warn"
    Write-Host "         Install from https://git-scm.com/download/win" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan

if ($allPrereqsMet) {
    Write-Host "  All required prerequisites met!" -ForegroundColor Green
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host ""
    exit 0
} else {
    Write-Host "  Some prerequisites are missing" -ForegroundColor Red
    Write-Host "==================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Please install missing prerequisites and run again." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
