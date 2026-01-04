"""
Verify ACM installation completeness

Checks that all required components are properly installed:
- Python dependencies
- SQL Server connectivity
- Database schema (tables, views, stored procedures)
- Configuration files
- Observability stack (optional)

Usage:
    python install/verify_installation.py
    python install/verify_installation.py --verbose
"""

import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse


def check_result(passed: bool, success_msg: str, fail_msg: str) -> bool:
    """Print check result and return status"""
    if passed:
        print(f"[OK]   {success_msg}")
        return True
    else:
        print(f"[FAIL] {fail_msg}")
        return False


def check_python_dependencies() -> List[Tuple[str, bool]]:
    """Check that all required Python packages are installed"""
    print("\n" + "="*50)
    print("Checking Python Dependencies")
    print("="*50)
    
    required_packages = [
        ("numpy", "NumPy"),
        ("pandas", "pandas"),
        ("sklearn", "scikit-learn"),
        ("matplotlib", "Matplotlib"),
        ("yaml", "PyYAML"),
        ("joblib", "joblib"),
        ("seaborn", "Seaborn"),
        ("pyodbc", "pyodbc"),
        ("statsmodels", "statsmodels"),
        ("scipy", "SciPy"),
        ("psutil", "psutil"),
        ("structlog", "structlog"),
        ("rich", "rich"),
    ]
    
    optional_packages = [
        ("opentelemetry.sdk", "OpenTelemetry SDK"),
        ("yappi", "yappi (profiling)"),
    ]
    
    results = []
    
    for module, name in required_packages:
        try:
            __import__(module)
            check_result(True, f"{name} installed", f"{name} missing")
            results.append((name, True))
        except ImportError:
            check_result(False, "", f"{name} not installed (required)")
            results.append((name, False))
    
    print("\nOptional packages:")
    for module, name in optional_packages:
        try:
            __import__(module)
            check_result(True, f"{name} installed", "")
            results.append((name, True))
        except ImportError:
            print(f"[SKIP] {name} not installed (optional)")
            results.append((name, True))  # Don't fail for optional
    
    return results


def check_core_modules() -> List[Tuple[str, bool]]:
    """Check that ACM core modules can be imported"""
    print("\n" + "="*50)
    print("Checking ACM Core Modules")
    print("="*50)
    
    core_modules = [
        ("core.sql_client", "SQLClient"),
        ("core.observability", "Observability"),
        ("core.acm_main", "Main Pipeline"),
        ("core.output_manager", "Output Manager"),
        ("core.fast_features", "Feature Engineering"),
        ("utils.config_dict", "ConfigDict"),
    ]
    
    results = []
    
    for module, name in core_modules:
        try:
            __import__(module)
            check_result(True, f"{name} module loaded", "")
            results.append((name, True))
        except Exception as e:
            check_result(False, "", f"{name} failed to load: {e}")
            results.append((name, False))
    
    return results


def check_sql_connection() -> bool:
    """Check SQL Server connectivity"""
    print("\n" + "="*50)
    print("Checking SQL Server Connection")
    print("="*50)
    
    try:
        from core.sql_client import SQLClient
        
        # Try to create client from ini file
        try:
            client = SQLClient.from_ini("acm")
            check_result(True, "SQL connection configuration loaded", "")
        except Exception as e:
            check_result(False, "", f"Failed to load SQL config: {e}")
            return False
        
        # Try to connect
        try:
            with client.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT @@VERSION")
                version = cur.fetchone()[0]
                print(f"[OK]   Connected to: {version.split(chr(10))[0]}")
                cur.close()
                return True
        except Exception as e:
            check_result(False, "", f"Failed to connect to SQL Server: {e}")
            return False
            
    except Exception as e:
        check_result(False, "", f"SQL client error: {e}")
        return False


def check_database_schema(verbose: bool = False) -> List[Tuple[str, bool]]:
    """Check that database schema is properly installed"""
    print("\n" + "="*50)
    print("Checking Database Schema")
    print("="*50)
    
    results = []
    
    try:
        from core.sql_client import SQLClient
        client = SQLClient.from_ini("acm")
        
        with client.get_connection() as conn:
            cur = conn.cursor()
            
            # Check critical tables
            critical_tables = [
                "Equipment",
                "ACM_Runs",
                "ACM_Scores_Wide",
                "ACM_HealthTimeline",
                "ACM_RUL",
                "ACM_Config",
                "ACM_RunLogs",
                "ACM_Anomaly_Events",
            ]
            
            for table in critical_tables:
                cur.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?",
                    (table,)
                )
                exists = cur.fetchone()[0] > 0
                if exists:
                    check_result(True, f"Table {table} exists", "")
                    results.append((table, True))
                else:
                    check_result(False, "", f"Table {table} missing")
                    results.append((table, False))
            
            # Check views
            critical_views = [
                "vw_AnomalyEvents",
                "vw_Scores",
                "vw_RunSummary",
            ]
            
            print("\nChecking Views:")
            for view in critical_views:
                cur.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.VIEWS "
                    "WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?",
                    (view,)
                )
                exists = cur.fetchone()[0] > 0
                if exists:
                    check_result(True, f"View {view} exists", "")
                    results.append((view, True))
                else:
                    print(f"[SKIP] View {view} missing (may be optional)")
                    results.append((view, True))  # Don't fail
            
            # Check stored procedures
            critical_sps = [
                "usp_ACM_StartRun",
                "usp_ACM_FinalizeRun",
                "usp_ACM_GetHistorianData_TEMP",
            ]
            
            print("\nChecking Stored Procedures:")
            for sp in critical_sps:
                cur.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_SCHEMA='dbo' AND ROUTINE_NAME=?",
                    (sp,)
                )
                exists = cur.fetchone()[0] > 0
                if exists:
                    check_result(True, f"Procedure {sp} exists", "")
                    results.append((sp, True))
                else:
                    print(f"[SKIP] Procedure {sp} missing (may be optional)")
                    results.append((sp, True))  # Don't fail
            
            cur.close()
            
    except Exception as e:
        check_result(False, "", f"Database schema check failed: {e}")
        results.append(("Database Schema", False))
    
    return results


def check_configuration_files() -> List[Tuple[str, bool]]:
    """Check that configuration files exist"""
    print("\n" + "="*50)
    print("Checking Configuration Files")
    print("="*50)
    
    results = []
    
    config_files = [
        (ROOT / "configs" / "sql_connection.ini", "SQL Connection Config", True),
        (ROOT / "configs" / "config_table.csv", "ACM Config Table", True),
        (ROOT / "pyproject.toml", "Python Project Config", True),
        (ROOT / ".venv", "Virtual Environment", False),
    ]
    
    for path, name, required in config_files:
        if path.exists():
            check_result(True, f"{name} found", "")
            results.append((name, True))
        else:
            if required:
                check_result(False, "", f"{name} missing")
                results.append((name, False))
            else:
                print(f"[SKIP] {name} not found (optional)")
                results.append((name, True))
    
    return results


def check_observability_stack() -> bool:
    """Check if observability stack is running (optional)"""
    print("\n" + "="*50)
    print("Checking Observability Stack (Optional)")
    print("="*50)
    
    try:
        import urllib.request
        
        endpoints = [
            ("http://localhost:3000", "Grafana"),
            ("http://localhost:3200/ready", "Tempo"),
            ("http://localhost:3100/ready", "Loki"),
            ("http://localhost:9090/-/ready", "Prometheus"),
            ("http://localhost:4040/ready", "Pyroscope"),
        ]
        
        any_running = False
        for url, name in endpoints:
            try:
                req = urllib.request.Request(url, method="GET")
                urllib.request.urlopen(req, timeout=2)
                check_result(True, f"{name} is running", "")
                any_running = True
            except:
                print(f"[SKIP] {name} not running")
        
        if not any_running:
            print("\n[INFO] Observability stack not running (optional)")
            print("       Start with: cd install/observability; docker compose up -d")
        
        return True  # Don't fail if observability is down
        
    except Exception as e:
        print(f"[SKIP] Could not check observability stack: {e}")
        return True


def main():
    parser = argparse.ArgumentParser(description="Verify ACM installation")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("ACM Installation Verification")
    print("="*50)
    
    all_checks = []
    
    # Run all checks
    all_checks.extend(check_python_dependencies())
    all_checks.extend(check_core_modules())
    all_checks.append(("SQL Connection", check_sql_connection()))
    all_checks.extend(check_database_schema(args.verbose))
    all_checks.extend(check_configuration_files())
    all_checks.append(("Observability Stack", check_observability_stack()))
    
    # Summary
    print("\n" + "="*50)
    print("Verification Summary")
    print("="*50)
    
    total = len(all_checks)
    passed = sum(1 for _, result in all_checks if result)
    failed = total - passed
    
    print(f"\nTotal Checks: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n" + "="*50)
        print("ALL CHECKS PASSED")
        print("="*50)
        print("\nACM is properly installed and ready to use!")
        print("\nNext steps:")
        print("  1. Run: python -m core.acm_main --equip YOUR_EQUIPMENT")
        print("  2. See README.md for usage examples")
        print("")
        return 0
    else:
        print("\n" + "="*50)
        print(f"INSTALLATION INCOMPLETE ({failed} issues)")
        print("="*50)
        print("\nPlease fix the issues above and run verification again.")
        print("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
