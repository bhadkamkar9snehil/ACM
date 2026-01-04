@echo off
REM ACM Quick Install Launcher for Windows
REM This batch file helps launch the PowerShell installer with prompts

echo.
echo ================================================================
echo   ACM Quick Install Launcher
echo ================================================================
echo.
echo This script will launch the ACM installer.
echo.
echo PREREQUISITES (must be installed first):
echo   1. SQL Server (any edition)
echo   2. Python 3.11 or later
echo   3. SQL Server ODBC Driver 18
echo   4. Docker Desktop (optional, for monitoring)
echo.

REM Check if PowerShell is available
powershell -Command "exit 0" >nul 2>&1
if errorlevel 1 (
    echo ERROR: PowerShell not found. Please run on Windows with PowerShell.
    pause
    exit /b 1
)

echo.
echo Please provide your SQL Server connection details:
echo.

REM Prompt for SQL Server instance
set /p SERVER="SQL Server instance (e.g., localhost\SQLEXPRESS): "
if "%SERVER%"=="" (
    echo ERROR: SQL Server instance is required
    pause
    exit /b 1
)

REM Prompt for database name
set /p DATABASE="Database name (default: ACM): "
if "%DATABASE%"=="" set DATABASE=ACM

REM Prompt for authentication method
echo.
echo Authentication Method:
echo   1. Windows Authentication (recommended)
echo   2. SQL Server Authentication
echo.
set /p AUTH_CHOICE="Select authentication method (1 or 2): "

if "%AUTH_CHOICE%"=="1" (
    set AUTH_PARAMS=-TrustedConnection
    echo.
    echo Using Windows Authentication
) else if "%AUTH_CHOICE%"=="2" (
    set /p SQL_USER="SQL Server username: "
    set /p SQL_PASSWORD="SQL Server password: "
    set AUTH_PARAMS=-SqlUser "%SQL_USER%" -SqlPassword "%SQL_PASSWORD%"
    echo.
    echo Using SQL Server Authentication
) else (
    echo ERROR: Invalid choice. Please select 1 or 2.
    pause
    exit /b 1
)

REM Ask about observability stack
echo.
set /p SKIP_OBS="Skip observability stack installation? (Y/N, default: N): "
if /i "%SKIP_OBS%"=="Y" (
    set OBS_PARAMS=-SkipObservability
) else (
    set OBS_PARAMS=
)

echo.
echo ================================================================
echo   Starting Installation...
echo ================================================================
echo.
echo Server: %SERVER%
echo Database: %DATABASE%
echo.
echo Press Ctrl+C to cancel, or any key to continue...
pause >nul

REM Run the PowerShell installer
powershell -ExecutionPolicy Bypass -File "%~dp0Install-ACM.ps1" -Server "%SERVER%" -Database "%DATABASE%" %AUTH_PARAMS% %OBS_PARAMS%

if errorlevel 1 (
    echo.
    echo ================================================================
    echo   Installation Failed
    echo ================================================================
    echo.
    echo Please check the error messages above.
    echo For help, see install/README.md
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ================================================================
    echo   Installation Complete!
    echo ================================================================
    echo.
    echo See install/README.md for next steps.
    echo.
    pause
    exit /b 0
)
