"""
Test installer scripts for syntax and basic functionality
"""

import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_python_syntax():
    """Test that all Python installer scripts have valid syntax"""
    scripts = [
        ROOT / "install" / "verify_installation.py",
        ROOT / "install" / "install_acm.py",
        ROOT / "install" / "generate_install_scripts.py",
    ]
    
    for script in scripts:
        if not script.exists():
            print(f"[SKIP] {script.name} not found")
            continue
            
        try:
            with open(script, encoding='utf-8') as f:
                compile(f.read(), script.name, 'exec')
            print(f"[OK] {script.name} has valid syntax")
        except SyntaxError as e:
            print(f"[FAIL] {script.name} has syntax error: {e}")
            return False
    
    return True


def test_powershell_syntax():
    """Test that PowerShell scripts exist and have basic structure"""
    scripts = [
        ROOT / "install" / "Install-ACM.ps1",
        ROOT / "install" / "Test-Prerequisites.ps1",
    ]
    
    for script in scripts:
        if not script.exists():
            print(f"[SKIP] {script.name} not found")
            continue
            
        try:
            with open(script, encoding='utf-8') as f:
                content = f.read()
                # Basic checks for PowerShell structure
                if 'param(' in content or 'function ' in content or 'Write-Host' in content:
                    print(f"[OK] {script.name} appears to be valid PowerShell")
                else:
                    print(f"[WARN] {script.name} may not be a valid PowerShell script")
        except Exception as e:
            print(f"[FAIL] Could not read {script.name}: {e}")
            return False
    
    return True


def test_batch_syntax():
    """Test that batch files exist"""
    scripts = [
        ROOT / "install" / "QuickInstall.bat",
    ]
    
    for script in scripts:
        if not script.exists():
            print(f"[SKIP] {script.name} not found")
            continue
            
        try:
            with open(script, encoding='utf-8') as f:
                content = f.read()
                if '@echo off' in content or 'echo' in content:
                    print(f"[OK] {script.name} appears to be valid batch file")
                else:
                    print(f"[WARN] {script.name} may not be a valid batch file")
        except Exception as e:
            print(f"[FAIL] Could not read {script.name}: {e}")
            return False
    
    return True


def test_documentation():
    """Test that documentation files exist"""
    docs = [
        ROOT / "install" / "README.md",
        ROOT / "README.md",
    ]
    
    for doc in docs:
        if not doc.exists():
            print(f"[FAIL] {doc.name} not found")
            return False
        else:
            print(f"[OK] {doc.name} exists")
    
    return True


def test_sql_scripts():
    """Test that SQL installation scripts exist"""
    sql_dir = ROOT / "install" / "sql"
    
    if not sql_dir.exists():
        print(f"[FAIL] install/sql directory not found")
        return False
    
    required_scripts = [
        "00_create_database.sql",
        "10_tables.sql",
        "15_unique_constraints.sql",
        "20_foreign_keys.sql",
        "30_indexes.sql",
        "40_views.sql",
        "50_procedures.sql",
    ]
    
    all_found = True
    for script_name in required_scripts:
        script_path = sql_dir / script_name
        if script_path.exists():
            print(f"[OK] SQL script {script_name} exists")
        else:
            print(f"[FAIL] SQL script {script_name} missing")
            all_found = False
    
    return all_found


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Testing ACM Installer Components")
    print("="*60)
    
    all_passed = True
    
    print("\nPython Scripts:")
    all_passed &= test_python_syntax()
    
    print("\nPowerShell Scripts:")
    all_passed &= test_powershell_syntax()
    
    print("\nBatch Files:")
    all_passed &= test_batch_syntax()
    
    print("\nDocumentation:")
    all_passed &= test_documentation()
    
    print("\nSQL Scripts:")
    all_passed &= test_sql_scripts()
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL INSTALLER TESTS PASSED")
        print("="*60)
        return 0
    else:
        print("SOME INSTALLER TESTS FAILED")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
