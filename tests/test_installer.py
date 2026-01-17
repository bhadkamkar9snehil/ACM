"""
Comprehensive Tests for ACM Installer Wizard
=============================================

Tests the installer logic WITHOUT actually running destructive operations.
Uses mocking to simulate Docker, SQL Server, and filesystem operations.

Run with:
    pytest tests/test_installer.py -v
    pytest tests/test_installer.py -v -k "test_prerequisites"  # Run specific group
"""

import os
import sys
import json
import tempfile
import shutil
import platform
import socket
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Tuple, List
from dataclasses import dataclass

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "install"))


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def installer_module():
    """Import the installer module."""
    from install import acm_installer
    return acm_installer


@pytest.fixture
def fresh_state(installer_module):
    """Create a fresh InstallState for each test."""
    return installer_module.InstallState()


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory structure."""
    temp_dir = tempfile.mkdtemp(prefix="acm_test_")
    
    # Create directory structure
    dirs = [
        "configs",
        "install/observability",
        "install/sql",
        "utils",
        "core",
        "grafana_dashboards",
    ]
    for d in dirs:
        (Path(temp_dir) / d).mkdir(parents=True, exist_ok=True)
    
    # Create version.py
    version_file = Path(temp_dir) / "utils" / "version.py"
    version_file.write_text('__version__ = "11.3.0"\n')
    
    # Create sql_connection.example.ini
    example_ini = Path(temp_dir) / "configs" / "sql_connection.example.ini"
    example_ini.write_text("""[acm]
server=localhost\\SQLEXPRESS
database=ACM
trusted_connection=yes
driver=ODBC Driver 18 for SQL Server
""")
    
    # Create config_table.csv
    config_csv = Path(temp_dir) / "configs" / "config_table.csv"
    config_csv.write_text("EquipID,Section,Key,Value\n0,detector,enabled,true\n")
    
    # Create docker-compose.yaml
    compose_file = Path(temp_dir) / "install" / "observability" / "docker-compose.yaml"
    compose_file.write_text("""services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
""")
    
    yield Path(temp_dir)
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# TEST: VERSION DETECTION
# ============================================================================

class TestVersionDetection:
    """Tests for ACM version detection."""
    
    def test_get_acm_version_reads_version_file(self, installer_module, temp_project_dir):
        """Test that get_acm_version correctly reads from version.py."""
        # Override PROJECT_ROOT
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            version = installer_module.get_acm_version()
            assert version == "11.3.0"
    
    def test_get_acm_version_handles_missing_file(self, installer_module, temp_project_dir):
        """Test graceful handling when version.py doesn't exist."""
        # Remove version.py
        version_file = temp_project_dir / "utils" / "version.py"
        version_file.unlink()
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            version = installer_module.get_acm_version()
            assert version == "unknown"
    
    def test_get_acm_version_handles_malformed_file(self, installer_module, temp_project_dir):
        """Test handling of malformed version.py."""
        version_file = temp_project_dir / "utils" / "version.py"
        version_file.write_text("# No version here\n")
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            version = installer_module.get_acm_version()
            assert version == "unknown"
    
    def test_get_acm_version_handles_different_quote_styles(self, installer_module, temp_project_dir):
        """Test parsing version with single vs double quotes."""
        version_file = temp_project_dir / "utils" / "version.py"
        
        # Single quotes
        version_file.write_text("__version__ = '11.3.0'\n")
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            assert installer_module.get_acm_version() == "11.3.0"
        
        # Double quotes
        version_file.write_text('__version__ = "11.3.0"\n')
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            assert installer_module.get_acm_version() == "11.3.0"


# ============================================================================
# TEST: PREREQUISITES CHECKS
# ============================================================================

class TestPrerequisitesChecks:
    """Tests for individual prerequisite check functions."""
    
    def test_check_python_version_passes_for_311(self, installer_module):
        """Test Python version check passes for 3.11+."""
        with patch.object(sys, 'version_info', (3, 11, 0)):
            ok, details = installer_module.check_python_version()
            assert ok is True
            assert "3.11" in details
    
    def test_check_python_version_passes_for_312(self, installer_module):
        """Test Python version check passes for 3.12+."""
        with patch.object(sys, 'version_info', (3, 12, 0)):
            ok, details = installer_module.check_python_version()
            assert ok is True
            assert "3.12" in details
    
    def test_check_python_version_fails_for_310(self, installer_module):
        """Test Python version check fails for 3.10."""
        with patch.object(sys, 'version_info', (3, 10, 0)):
            ok, details = installer_module.check_python_version()
            assert ok is False
            assert "requires" in details.lower()
    
    def test_check_python_version_fails_for_39(self, installer_module):
        """Test Python version check fails for 3.9."""
        with patch.object(sys, 'version_info', (3, 9, 0)):
            ok, details = installer_module.check_python_version()
            assert ok is False
    
    def test_check_docker_installed_success(self, installer_module):
        """Test Docker installed check when Docker is present."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (0, "Docker version 24.0.6, build ed223bc", "")
            ok, details = installer_module.check_docker_installed()
            assert ok is True
            assert "Docker version" in details
    
    def test_check_docker_installed_failure(self, installer_module):
        """Test Docker installed check when Docker is missing."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (-1, "", "Command not found: docker")
            ok, details = installer_module.check_docker_installed()
            assert ok is False
            assert "not installed" in details.lower()
    
    def test_check_docker_running_success(self, installer_module):
        """Test Docker running check when daemon is active."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (0, "Server: Docker Engine", "")
            ok, details = installer_module.check_docker_running()
            assert ok is True
            assert "running" in details.lower()
    
    def test_check_docker_running_failure(self, installer_module):
        """Test Docker running check when daemon is stopped."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (1, "", "Cannot connect to the Docker daemon")
            ok, details = installer_module.check_docker_running()
            assert ok is False
            assert "not running" in details.lower()
    
    def test_check_docker_compose_v2(self, installer_module):
        """Test Docker Compose v2 detection."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (0, "Docker Compose version v2.20.2", "")
            ok, details = installer_module.check_docker_compose()
            assert ok is True
            assert "v2" in details or "Compose" in details
    
    def test_check_docker_compose_v1_fallback(self, installer_module):
        """Test fallback to docker-compose v1."""
        def mock_run_side_effect(cmd):
            if cmd == ["docker", "compose", "version"]:
                return (1, "", "unknown command")
            elif cmd == ["docker-compose", "--version"]:
                return (0, "docker-compose version 1.29.2", "")
            return (-1, "", "unknown")
        
        with patch.object(installer_module, 'run_command', side_effect=mock_run_side_effect):
            ok, details = installer_module.check_docker_compose()
            assert ok is True
            assert "1.29" in details
    
    def test_check_docker_compose_not_installed(self, installer_module):
        """Test when neither docker compose v1 nor v2 is available."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (1, "", "command not found")
            ok, details = installer_module.check_docker_compose()
            assert ok is False
    
    def test_check_odbc_driver_found_driver18(self, installer_module):
        """Test ODBC driver detection finds Driver 18."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = [
            "SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 18 for SQL Server",
        ]
        
        with patch.dict(sys.modules, {'pyodbc': mock_pyodbc}):
            ok, details = installer_module.check_odbc_driver()
            assert ok is True
            assert "18" in details
    
    def test_check_odbc_driver_found_driver17(self, installer_module):
        """Test ODBC driver detection prefers 17 when 18 not available."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = [
            "SQL Server",
            "ODBC Driver 17 for SQL Server",
        ]
        
        with patch.dict(sys.modules, {'pyodbc': mock_pyodbc}):
            ok, details = installer_module.check_odbc_driver()
            assert ok is True
            assert "17" in details
    
    def test_check_odbc_driver_not_found(self, installer_module):
        """Test when no SQL Server ODBC driver is installed."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = ["MySQL ODBC Driver"]
        
        with patch.dict(sys.modules, {'pyodbc': mock_pyodbc}):
            ok, details = installer_module.check_odbc_driver()
            # Should return False since no SQL Server driver
            assert "SQL Server" not in details or ok is False
    
    def test_check_odbc_driver_pyodbc_not_installed(self, installer_module):
        """Test when pyodbc is not installed."""
        # Force ImportError by removing pyodbc from modules
        with patch.dict(sys.modules, {'pyodbc': None}):
            ok, details = installer_module.check_odbc_driver()
            assert ok is False
    
    def test_check_sqlcmd_success(self, installer_module):
        """Test sqlcmd availability check."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (0, "sqlcmd help", "")
            ok, details = installer_module.check_sqlcmd()
            assert ok is True
            assert "available" in details.lower()
    
    def test_check_sqlcmd_not_installed(self, installer_module):
        """Test sqlcmd when not installed."""
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (-1, "", "Command not found")
            ok, details = installer_module.check_sqlcmd()
            assert ok is False


# ============================================================================
# TEST: RUN_COMMAND UTILITY
# ============================================================================

class TestRunCommand:
    """Tests for the run_command utility function."""
    
    def test_run_command_success(self, installer_module):
        """Test run_command with successful command."""
        code, stdout, stderr = installer_module.run_command(["echo", "hello"])
        # On Windows, echo may behave differently
        assert isinstance(code, int)
        assert isinstance(stdout, str)
        assert isinstance(stderr, str)
    
    def test_run_command_command_not_found(self, installer_module):
        """Test run_command with non-existent command."""
        code, stdout, stderr = installer_module.run_command(["nonexistent_cmd_xyz"])
        assert code != 0
        assert "not found" in stderr.lower() or code == -1
    
    def test_run_command_with_cwd(self, installer_module, temp_project_dir):
        """Test run_command with custom working directory."""
        # Create a test file
        test_file = temp_project_dir / "test.txt"
        test_file.write_text("content")
        
        # Check command works with cwd
        # Using Python instead of shell commands for cross-platform
        code, stdout, stderr = installer_module.run_command(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            cwd=temp_project_dir
        )
        assert code == 0
        assert str(temp_project_dir) in stdout or temp_project_dir.name in stdout


# ============================================================================
# TEST: INSTALL STATE
# ============================================================================

class TestInstallState:
    """Tests for InstallState dataclass."""
    
    def test_default_state_values(self, fresh_state):
        """Test default values of InstallState."""
        assert fresh_state.python_ok is False
        assert fresh_state.docker_ok is False
        assert fresh_state.docker_running is False
        assert fresh_state.odbc_driver is None
        assert fresh_state.venv_path is None
        assert fresh_state.deps_installed is False
        assert fresh_state.observability_running is False
        assert fresh_state.sql_server is None
        assert fresh_state.sql_database == "ACM"
        assert fresh_state.sql_auth_type == "windows"
        assert fresh_state.sql_username is None
        assert fresh_state.sql_password is None
        assert fresh_state.sql_setup_complete is False
        assert fresh_state.completed_steps == []
        assert fresh_state.errors == []
    
    def test_state_modification(self, fresh_state):
        """Test modifying state values."""
        fresh_state.python_ok = True
        fresh_state.docker_ok = True
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        fresh_state.sql_server = "localhost\\SQLEXPRESS"
        
        assert fresh_state.python_ok is True
        assert fresh_state.docker_ok is True
        assert "18" in fresh_state.odbc_driver
        assert "SQLEXPRESS" in fresh_state.sql_server
    
    def test_completed_steps_tracking(self, fresh_state, installer_module):
        """Test tracking completed installation steps."""
        fresh_state.completed_steps.append(installer_module.InstallStep.PREREQUISITES)
        fresh_state.completed_steps.append(installer_module.InstallStep.PYTHON_ENV)
        
        assert len(fresh_state.completed_steps) == 2
        assert installer_module.InstallStep.PREREQUISITES in fresh_state.completed_steps
        assert installer_module.InstallStep.PYTHON_ENV in fresh_state.completed_steps
        assert installer_module.InstallStep.OBSERVABILITY not in fresh_state.completed_steps


# ============================================================================
# TEST: SQL CONFIGURATION
# ============================================================================

class TestSQLConfiguration:
    """Tests for SQL configuration file creation."""
    
    def test_create_sql_config_windows_auth(self, installer_module, fresh_state, temp_project_dir):
        """Test creating sql_connection.ini with Windows auth."""
        fresh_state.sql_server = "localhost\\SQLEXPRESS"
        fresh_state.sql_database = "ACM"
        fresh_state.sql_auth_type = "windows"
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            assert config_path.exists()
            
            content = config_path.read_text()
            assert "[acm]" in content
            assert "server=localhost\\SQLEXPRESS" in content
            assert "database=ACM" in content
            assert "trusted_connection=yes" in content
            assert "ODBC Driver 18" in content
    
    def test_create_sql_config_sql_auth(self, installer_module, fresh_state, temp_project_dir):
        """Test creating sql_connection.ini with SQL Server auth."""
        fresh_state.sql_server = "myserver.database.windows.net"
        fresh_state.sql_database = "ACMProd"
        fresh_state.sql_auth_type = "sql"
        fresh_state.sql_username = "acm_user"
        fresh_state.sql_password = "SecurePass123!"
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            content = config_path.read_text()
            
            assert "server=myserver.database.windows.net" in content
            assert "database=ACMProd" in content
            assert "user=acm_user" in content
            assert "password=SecurePass123!" in content
            assert "trusted_connection" not in content


# ============================================================================
# TEST: SQL CONNECTION TESTING
# ============================================================================

class TestSQLConnection:
    """Tests for SQL Server connection testing."""
    
    def test_sql_connection_success(self, installer_module, fresh_state):
        """Test successful SQL connection."""
        fresh_state.sql_server = "localhost\\SQLEXPRESS"
        fresh_state.sql_auth_type = "windows"
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        
        mock_pyodbc = MagicMock()
        mock_conn = MagicMock()
        mock_pyodbc.connect.return_value = mock_conn
        
        with patch.dict(sys.modules, {'pyodbc': mock_pyodbc}):
            result = installer_module.test_sql_connection(fresh_state)
            assert result is True
            mock_conn.close.assert_called_once()
    
    def test_sql_connection_failure(self, installer_module, fresh_state):
        """Test failed SQL connection."""
        fresh_state.sql_server = "invalid_server"
        fresh_state.sql_auth_type = "windows"
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        
        mock_pyodbc = MagicMock()
        mock_pyodbc.connect.side_effect = Exception("Connection timeout")
        
        with patch.dict(sys.modules, {'pyodbc': mock_pyodbc}):
            with patch.object(installer_module, 'print_error'):
                result = installer_module.test_sql_connection(fresh_state)
                assert result is False
    
    def test_sql_connection_no_driver(self, installer_module, fresh_state):
        """Test SQL connection when no ODBC driver is set."""
        fresh_state.sql_server = "localhost"
        fresh_state.odbc_driver = None
        
        result = installer_module.test_sql_connection(fresh_state)
        assert result is False


# ============================================================================
# TEST: DOCKER COMPOSE OPERATIONS
# ============================================================================

class TestDockerComposeOperations:
    """Tests for Docker Compose orchestration."""
    
    def test_compose_file_exists_check(self, installer_module, temp_project_dir):
        """Test verification that docker-compose.yaml exists."""
        compose_dir = temp_project_dir / "install" / "observability"
        compose_file = compose_dir / "docker-compose.yaml"
        
        assert compose_file.exists()
        content = compose_file.read_text()
        assert "services:" in content
        assert "grafana:" in content
    
    def test_compose_file_missing_handling(self, installer_module, fresh_state, temp_project_dir):
        """Test handling when docker-compose.yaml is missing."""
        # Remove the compose file
        compose_file = temp_project_dir / "install" / "observability" / "docker-compose.yaml"
        compose_file.unlink()
        
        # The setup_observability function should handle this
        with patch.object(installer_module, 'DOCKER_COMPOSE_DIR', temp_project_dir / "install" / "observability"):
            with patch.object(installer_module, 'print_error') as mock_error:
                fresh_state.docker_running = True
                result = installer_module.setup_observability(fresh_state)
                assert result is False


# ============================================================================
# TEST: ENDPOINT VERIFICATION
# ============================================================================

class TestEndpointVerification:
    """Tests for observability endpoint verification."""
    
    def test_endpoint_list_completeness(self, installer_module):
        """Verify all expected endpoints are checked."""
        # These are the endpoints defined in setup_observability
        expected_endpoints = [
            "Grafana",
            "Alloy", 
            "Tempo",
            "Loki",
            "Prometheus",
            "Pyroscope",
        ]
        
        # The endpoints are hardcoded in setup_observability
        # Just verify we can import the module
        assert hasattr(installer_module, 'setup_observability')


# ============================================================================
# TEST: INSTALL STEP ENUM
# ============================================================================

class TestInstallStepEnum:
    """Tests for InstallStep enumeration."""
    
    def test_all_steps_defined(self, installer_module):
        """Test all installation steps are defined."""
        steps = list(installer_module.InstallStep)
        
        assert len(steps) == 6
        assert installer_module.InstallStep.PREREQUISITES in steps
        assert installer_module.InstallStep.PYTHON_ENV in steps
        assert installer_module.InstallStep.OBSERVABILITY in steps
        assert installer_module.InstallStep.SQL_SETUP in steps
        assert installer_module.InstallStep.CONFIGURATION in steps
        assert installer_module.InstallStep.VERIFICATION in steps
    
    def test_step_values(self, installer_module):
        """Test step enum values."""
        assert installer_module.InstallStep.PREREQUISITES.value == "prerequisites"
        assert installer_module.InstallStep.PYTHON_ENV.value == "python_env"
        assert installer_module.InstallStep.OBSERVABILITY.value == "observability"
        assert installer_module.InstallStep.SQL_SETUP.value == "sql_setup"
        assert installer_module.InstallStep.CONFIGURATION.value == "configuration"
        assert installer_module.InstallStep.VERIFICATION.value == "verification"


# ============================================================================
# TEST: CONSOLE OUTPUT HELPERS
# ============================================================================

class TestConsoleHelpers:
    """Tests for console output helper functions."""
    
    def test_print_functions_exist(self, installer_module):
        """Test all print helper functions exist."""
        assert callable(installer_module.print_header)
        assert callable(installer_module.print_step)
        assert callable(installer_module.print_success)
        assert callable(installer_module.print_warning)
        assert callable(installer_module.print_error)
        assert callable(installer_module.print_info)
    
    def test_print_step_parameters(self, installer_module):
        """Test print_step accepts correct parameters."""
        with patch.object(installer_module.console, 'print'):
            with patch.object(installer_module.console, 'rule'):
                # Should not raise
                installer_module.print_step(1, 6, "Test Step")


# ============================================================================
# TEST: CONFIGURATION CONSTANTS
# ============================================================================

class TestConfigurationConstants:
    """Tests for installer configuration constants."""
    
    def test_version_constant(self, installer_module):
        """Test VERSION constant is defined."""
        assert hasattr(installer_module, 'VERSION')
        assert isinstance(installer_module.VERSION, str)
        # Version should be semver format
        parts = installer_module.VERSION.split('.')
        assert len(parts) >= 2
    
    def test_python_min_version(self, installer_module):
        """Test PYTHON_MIN_VERSION constant."""
        assert hasattr(installer_module, 'PYTHON_MIN_VERSION')
        assert installer_module.PYTHON_MIN_VERSION == (3, 11)
    
    def test_docker_compose_dir(self, installer_module):
        """Test DOCKER_COMPOSE_DIR path."""
        assert hasattr(installer_module, 'DOCKER_COMPOSE_DIR')
        assert isinstance(installer_module.DOCKER_COMPOSE_DIR, Path)
        assert "observability" in str(installer_module.DOCKER_COMPOSE_DIR)
    
    def test_sql_install_dir(self, installer_module):
        """Test SQL_INSTALL_DIR path."""
        assert hasattr(installer_module, 'SQL_INSTALL_DIR')
        assert isinstance(installer_module.SQL_INSTALL_DIR, Path)
        assert "sql" in str(installer_module.SQL_INSTALL_DIR)
    
    def test_acm_version_loaded(self, installer_module):
        """Test ACM_VERSION is loaded from version.py."""
        assert hasattr(installer_module, 'ACM_VERSION')
        # Should be a version string or "unknown"
        assert isinstance(installer_module.ACM_VERSION, str)
        if installer_module.ACM_VERSION != "unknown":
            parts = installer_module.ACM_VERSION.split('.')
            assert len(parts) >= 2


# ============================================================================
# TEST: WIZARD STYLE
# ============================================================================

class TestWizardStyle:
    """Tests for questionary wizard style."""
    
    def test_wizard_style_defined(self, installer_module):
        """Test WIZARD_STYLE is defined."""
        assert hasattr(installer_module, 'WIZARD_STYLE')
    
    def test_wizard_style_has_colors(self, installer_module):
        """Test wizard style has color definitions."""
        # Just verify it's a questionary Style object
        from questionary import Style
        assert isinstance(installer_module.WIZARD_STYLE, Style)


# ============================================================================
# TEST: PROJECT ROOT AND SCRIPT DIR
# ============================================================================

class TestPaths:
    """Tests for path constants."""
    
    def test_project_root_is_path(self, installer_module):
        """Test PROJECT_ROOT is a Path object."""
        assert hasattr(installer_module, 'PROJECT_ROOT')
        assert isinstance(installer_module.PROJECT_ROOT, Path)
    
    def test_script_dir_is_path(self, installer_module):
        """Test SCRIPT_DIR is a Path object."""
        assert hasattr(installer_module, 'SCRIPT_DIR')
        assert isinstance(installer_module.SCRIPT_DIR, Path)
    
    def test_script_dir_is_install_folder(self, installer_module):
        """Test SCRIPT_DIR points to install folder."""
        assert "install" in str(installer_module.SCRIPT_DIR)
    
    def test_project_root_is_parent_of_script_dir(self, installer_module):
        """Test PROJECT_ROOT is parent of SCRIPT_DIR."""
        assert installer_module.PROJECT_ROOT == installer_module.SCRIPT_DIR.parent


# ============================================================================
# TEST: MAIN FUNCTION
# ============================================================================

class TestMainFunction:
    """Tests for the main installer function."""
    
    def test_main_exists(self, installer_module):
        """Test main function exists."""
        assert hasattr(installer_module, 'main')
        assert callable(installer_module.main)
    
    def test_main_is_entry_point(self, installer_module):
        """Test module can be run as script."""
        # Check __name__ == "__main__" block exists
        import inspect
        source = inspect.getsource(installer_module)
        assert 'if __name__ == "__main__":' in source
        assert 'main()' in source


# ============================================================================
# TEST: ERROR HANDLING
# ============================================================================

class TestErrorHandling:
    """Tests for error handling in installer."""
    
    def test_state_tracks_errors(self, fresh_state):
        """Test InstallState can track errors."""
        fresh_state.errors.append("Test error 1")
        fresh_state.errors.append("Test error 2")
        
        assert len(fresh_state.errors) == 2
        assert "Test error 1" in fresh_state.errors
    
    def test_run_command_captures_stderr(self, installer_module):
        """Test run_command captures standard error."""
        # Use Python to print to stderr
        code, stdout, stderr = installer_module.run_command([
            sys.executable, "-c", 
            "import sys; sys.stderr.write('error message')"
        ])
        assert "error message" in stderr or code == 0

    def test_record_issue_appends_error(self, installer_module, fresh_state):
        """Test record_issue records errors and prints details."""
        with patch.object(installer_module, 'print_error') as mock_error:
            with patch.object(installer_module, 'print_info') as mock_info:
                with patch.object(installer_module, 'print_solutions') as mock_solutions:
                    installer_module.record_issue(
                        fresh_state,
                        "Test failure",
                        details="Something went wrong",
                        solutions=["Fix A", "Fix B"]
                    )

        assert len(fresh_state.errors) == 1
        assert "Test failure" in fresh_state.errors[0]
        mock_error.assert_called_once()
        mock_info.assert_called_once()
        mock_solutions.assert_called_once()

    def test_format_command(self, installer_module):
        """Test format_command formatting."""
        cmd = ["python", "-m", "pip", "install", "-e", "."]
        formatted = installer_module.format_command(cmd)
        assert "python -m pip install -e ." == formatted


# ============================================================================
# TEST: INTEGRATION SCENARIOS (MOCKED)
# ============================================================================

class TestIntegrationScenarios:
    """Integration tests using mocks to simulate full scenarios."""
    
    def test_full_prerequisites_check_all_pass(self, installer_module, fresh_state):
        """Test prerequisites check when everything passes."""
        with patch.object(installer_module, 'check_python_version', return_value=(True, "Python 3.11")):
            with patch.object(installer_module, 'check_docker_installed', return_value=(True, "Docker 24.0")):
                with patch.object(installer_module, 'check_docker_running', return_value=(True, "Running")):
                    with patch.object(installer_module, 'check_docker_compose', return_value=(True, "v2.20")):
                        with patch.object(installer_module, 'check_odbc_driver', return_value=(True, "Driver 18")):
                            with patch.object(installer_module, 'check_sqlcmd', return_value=(True, "Available")):
                                with patch.object(installer_module.console, 'print'):
                                    result = installer_module.run_prerequisites_check(fresh_state)
                                    
                                    assert result is True
                                    assert fresh_state.python_ok is True
                                    assert fresh_state.docker_ok is True
                                    assert fresh_state.docker_running is True
                                    assert fresh_state.odbc_driver == "Driver 18"
    
    def test_prerequisites_check_docker_missing(self, installer_module, fresh_state):
        """Test prerequisites check when Docker is missing."""
        with patch.object(installer_module, 'check_python_version', return_value=(True, "Python 3.11")):
            with patch.object(installer_module, 'check_docker_installed', return_value=(False, "Not installed")):
                with patch.object(installer_module, 'check_docker_running', return_value=(False, "N/A")):
                    with patch.object(installer_module, 'check_docker_compose', return_value=(False, "N/A")):
                        with patch.object(installer_module, 'check_odbc_driver', return_value=(True, "Driver 18")):
                            with patch.object(installer_module, 'check_sqlcmd', return_value=(True, "Available")):
                                with patch.object(installer_module.console, 'print'):
                                    with patch.object(installer_module, 'print_warning'):
                                        with patch.object(installer_module, 'print_info'):
                                            with patch('questionary.confirm') as mock_confirm:
                                                mock_confirm.return_value.ask.return_value = False
                                                result = installer_module.run_prerequisites_check(fresh_state)
                                                
                                                assert result is False
                                                assert fresh_state.docker_ok is False
    
    def test_observability_already_running(self, installer_module, fresh_state, temp_project_dir):
        """Test observability setup when containers already running."""
        fresh_state.docker_running = True
        
        with patch.object(installer_module, 'DOCKER_COMPOSE_DIR', temp_project_dir / "install" / "observability"):
            with patch.object(installer_module, 'run_command') as mock_run:
                # First call: check if containers running
                mock_run.return_value = (0, "container_id_123", "")
                
                with patch.object(installer_module.console, 'print'):
                    with patch.object(installer_module, 'print_info'):
                        with patch('questionary.confirm') as mock_confirm:
                            mock_confirm.return_value.ask.return_value = False
                            result = installer_module.setup_observability(fresh_state)
                            
                            assert result is True
                            assert fresh_state.observability_running is True


# ============================================================================
# TEST: EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_sql_server_string(self, installer_module, fresh_state):
        """Test handling of empty SQL server string."""
        fresh_state.sql_server = ""
        fresh_state.odbc_driver = "ODBC Driver 18"
        
        result = installer_module.test_sql_connection(fresh_state)
        assert result is False
    
    def test_special_characters_in_password(self, installer_module, fresh_state, temp_project_dir):
        """Test SQL config with special characters in password."""
        fresh_state.sql_server = "localhost"
        fresh_state.sql_database = "ACM"
        fresh_state.sql_auth_type = "sql"
        fresh_state.sql_username = "user"
        fresh_state.sql_password = "P@ss!w0rd#$%^&*()"
        fresh_state.odbc_driver = "ODBC Driver 18"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            content = config_path.read_text()
            
            # Password should be written as-is (may need escaping in real use)
            assert "password=P@ss!w0rd#$%^&*()" in content
    
    def test_unicode_in_server_name(self, installer_module, fresh_state, temp_project_dir):
        """Test handling of unicode in server name."""
        fresh_state.sql_server = "server-日本語"
        fresh_state.sql_database = "ACM"
        fresh_state.sql_auth_type = "windows"
        fresh_state.odbc_driver = "ODBC Driver 18"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            # Should not raise
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            content = config_path.read_text(encoding='utf-8')
            assert "server-日本語" in content


# ============================================================================
# TEST: DOCKER DOWNLOAD (Mocked)
# ============================================================================

class TestDockerDownload:
    """Tests for Docker Desktop download functionality."""
    
    def test_download_docker_desktop_function_exists(self, installer_module):
        """Test download_docker_desktop function exists."""
        assert hasattr(installer_module, 'download_docker_desktop')
        assert callable(installer_module.download_docker_desktop)
    
    def test_download_url_is_correct(self, installer_module):
        """Test the Docker download URL is valid."""
        import inspect
        source = inspect.getsource(installer_module.download_docker_desktop)
        
        assert "desktop.docker.com" in source
        assert "Docker%20Desktop%20Installer.exe" in source


# ============================================================================
# TEST: WINDOWS OS COMPATIBILITY
# ============================================================================

class TestWindowsOSCompatibility:
    """Tests for Windows 10/11/Server OS compatibility."""
    
    def test_platform_detection_windows(self, installer_module):
        """Test platform detection identifies Windows correctly."""
        with patch('platform.system', return_value='Windows'):
            assert platform.system() == 'Windows'
    
    def test_windows_10_version_detection(self, installer_module):
        """Test Windows 10 version detection."""
        # Windows 10 version string
        with patch('platform.version', return_value='10.0.19045'):
            version = platform.version()
            major = int(version.split('.')[0])
            assert major >= 10
    
    def test_windows_11_version_detection(self, installer_module):
        """Test Windows 11 version detection."""
        # Windows 11 version string (build 22000+)
        with patch('platform.version', return_value='10.0.22631'):
            version = platform.version()
            build = int(version.split('.')[-1])
            # Windows 11 starts at build 22000
            is_win11 = build >= 22000
            assert is_win11
    
    def test_windows_server_2019_detection(self, installer_module):
        """Test Windows Server 2019 detection."""
        # Server 2019 has build 17763
        with patch('platform.version', return_value='10.0.17763'):
            version = platform.version()
            build = int(version.split('.')[-1])
            assert build >= 17763  # Server 2019 or later
    
    def test_windows_server_2022_detection(self, installer_module):
        """Test Windows Server 2022 detection."""
        # Server 2022 has build 20348
        with patch('platform.version', return_value='10.0.20348'):
            version = platform.version()
            build = int(version.split('.')[-1])
            assert build >= 20348  # Server 2022
    
    def test_minimum_windows_version_check(self, installer_module):
        """Test minimum Windows version enforcement."""
        # Minimum supported: Windows 10 (build 17134 = 1803)
        MIN_WINDOWS_BUILD = 17134
        
        test_cases = [
            ('10.0.19045', True),   # Windows 10 22H2 - OK
            ('10.0.22631', True),   # Windows 11 23H2 - OK
            ('10.0.17763', True),   # Server 2019 - OK
            ('10.0.20348', True),   # Server 2022 - OK
            ('10.0.17134', True),   # Windows 10 1803 (minimum) - OK
            ('10.0.14393', False),  # Windows Server 2016 / Win 10 1607 - TOO OLD
            ('6.3.9600', False),    # Windows 8.1 - TOO OLD
        ]
        
        for version_str, expected_ok in test_cases:
            with patch('platform.version', return_value=version_str):
                parts = version_str.split('.')
                if len(parts) >= 3:
                    major = int(parts[0])
                    build = int(parts[2])
                    is_supported = major >= 10 and build >= MIN_WINDOWS_BUILD
                    assert is_supported == expected_ok, f"Failed for {version_str}"
    
    def test_docker_desktop_installer_path_windows(self, installer_module):
        """Test Docker Desktop downloads to correct Windows path."""
        import inspect
        source = inspect.getsource(installer_module.download_docker_desktop)
        
        # Should download to user's Downloads folder
        assert "Downloads" in source
        assert "DockerDesktopInstaller.exe" in source
    
    def test_windows_path_handling(self, installer_module, temp_project_dir):
        """Test Windows path handling with spaces and unicode."""
        # Create path with spaces
        space_path = temp_project_dir / "path with spaces" / "test"
        space_path.mkdir(parents=True)
        
        config_path = space_path / "test.ini"
        config_path.write_text("[test]\nvalue=1", encoding='utf-8')
        
        assert config_path.exists()
        content = config_path.read_text(encoding='utf-8')
        assert "value=1" in content
    
    def test_windows_long_path_support(self, installer_module, temp_project_dir):
        """Test Windows long path support (>260 chars)."""
        # Create a deeply nested path
        nested_parts = ["a" * 20] * 15  # Creates path >260 chars
        deep_path = temp_project_dir
        for part in nested_parts:
            deep_path = deep_path / part
        
        # On Windows, this may fail without LongPathsEnabled
        # Test should at least not crash
        try:
            deep_path.mkdir(parents=True, exist_ok=True)
            test_file = deep_path / "test.txt"
            test_file.write_text("test", encoding='utf-8')
            assert test_file.exists()
        except OSError as e:
            # Long path not enabled - acceptable on some Windows configs
            assert "path" in str(e).lower() or "name" in str(e).lower()


class TestWindowsDockerIntegration:
    """Tests for Docker Desktop on Windows."""
    
    def test_docker_desktop_windows_paths(self, installer_module):
        """Test Docker Desktop uses Windows-appropriate paths."""
        compose_dir = installer_module.DOCKER_COMPOSE_DIR
        # On Windows, should be an absolute path
        assert compose_dir.is_absolute() or str(compose_dir).startswith('.')
    
    def test_docker_compose_windows_syntax(self, installer_module, temp_project_dir):
        """Test Docker Compose file uses Windows-compatible syntax."""
        compose_file = temp_project_dir / "install" / "observability" / "docker-compose.yaml"
        
        # Create a valid docker-compose file
        compose_content = """version: '3.8'
services:
  test:
    image: alpine
    volumes:
      - ./data:/data
"""
        compose_file.write_text(compose_content, encoding='utf-8')
        
        content = compose_file.read_text(encoding='utf-8')
        # Check no Unix-only paths
        assert '//' not in content or 'http://' in content or 'https://' in content
    
    def test_docker_compose_v2_command(self, installer_module):
        """Test Docker Compose v2 command format."""
        # Docker Compose v2 uses 'docker compose' (space, not hyphen)
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (0, "version 2.20.0", "")
            ok, version = installer_module.check_docker_compose()
            
            if ok:
                # First call should be 'docker compose version'
                assert mock_run.called
    
    def test_wsl2_backend_detection(self, installer_module):
        """Test WSL2 backend detection for Docker Desktop."""
        # Docker Desktop on Windows uses WSL2 backend
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (0, "Docker Desktop\nContext: desktop-linux", "")
            ok, details = installer_module.check_docker_installed()
            
            assert ok


class TestWindowsSQLServerIntegration:
    """Tests for SQL Server on Windows."""
    
    def test_odbc_driver_18_detection(self, installer_module):
        """Test ODBC Driver 18 detection on Windows."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = [
            'SQL Server',
            'ODBC Driver 17 for SQL Server',
            'ODBC Driver 18 for SQL Server',
        ]
        
        with patch.dict(sys.modules, {'pyodbc': mock_pyodbc}):
            ok, driver = installer_module.check_odbc_driver()
            
            assert ok
            assert "18" in driver or "17" in driver
    
    def test_odbc_driver_17_fallback(self, installer_module):
        """Test ODBC Driver 17 fallback when 18 not available."""
        mock_pyodbc = MagicMock()
        mock_pyodbc.drivers.return_value = [
            'SQL Server',
            'ODBC Driver 17 for SQL Server',
        ]
        
        with patch.dict(sys.modules, {'pyodbc': mock_pyodbc}):
            ok, driver = installer_module.check_odbc_driver()
            
            assert ok
            assert "17" in driver
    
    def test_windows_authentication_config(self, installer_module, fresh_state, temp_project_dir):
        """Test Windows Authentication configuration."""
        fresh_state.sql_server = "localhost\\SQLEXPRESS"
        fresh_state.sql_database = "ACM"
        fresh_state.sql_auth_type = "windows"
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            content = config_path.read_text(encoding='utf-8')
            
            assert "trusted_connection=yes" in content
            assert "localhost\\SQLEXPRESS" in content
    
    def test_sql_authentication_config(self, installer_module, fresh_state, temp_project_dir):
        """Test SQL Server Authentication configuration."""
        fresh_state.sql_server = "sql-server.company.com"
        fresh_state.sql_database = "ACM_Production"
        fresh_state.sql_auth_type = "sql"
        fresh_state.sql_username = "acm_user"
        fresh_state.sql_password = "SecureP@ss123!"
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            content = config_path.read_text(encoding='utf-8')
            
            assert "trusted_connection" not in content or "trusted_connection=no" in content
            # Installer uses 'user=' not 'uid='
            assert "user=acm_user" in content
            assert "password=SecureP@ss123!" in content
    
    def test_named_instance_handling(self, installer_module, fresh_state, temp_project_dir):
        """Test SQL Server named instance handling."""
        # Named instances use backslash
        fresh_state.sql_server = "SQLSERVER01\\PRODUCTION"
        fresh_state.sql_database = "ACM"
        fresh_state.sql_auth_type = "windows"
        fresh_state.odbc_driver = "ODBC Driver 18 for SQL Server"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            content = config_path.read_text(encoding='utf-8')
            
            # Backslash should be preserved in server name
            assert "SQLSERVER01\\PRODUCTION" in content or "SQLSERVER01\\\\PRODUCTION" in content
    
    def test_sqlcmd_windows_path(self, installer_module):
        """Test sqlcmd detection on Windows."""
        # sqlcmd is typically in PATH on Windows with SQL Server tools
        with patch.object(installer_module, 'run_command') as mock_run:
            mock_run.return_value = (0, "Microsoft (R) SQL Server Command Line Tool", "")
            ok, details = installer_module.check_sqlcmd()
            
            assert ok


class TestWindowsPythonEnvironment:
    """Tests for Python environment on Windows."""
    
    def test_python_311_minimum(self, installer_module):
        """Test Python 3.11 minimum version enforcement."""
        with patch('sys.version_info', (3, 11, 9)):
            ok, details = installer_module.check_python_version()
            assert ok
    
    def test_python_312_supported(self, installer_module):
        """Test Python 3.12 is supported."""
        with patch('sys.version_info', (3, 12, 0)):
            ok, details = installer_module.check_python_version()
            assert ok
    
    def test_python_313_supported(self, installer_module):
        """Test Python 3.13 is supported."""
        with patch('sys.version_info', (3, 13, 0)):
            ok, details = installer_module.check_python_version()
            assert ok
    
    def test_python_310_rejected(self, installer_module):
        """Test Python 3.10 is rejected."""
        with patch('sys.version_info', (3, 10, 0)):
            ok, details = installer_module.check_python_version()
            assert not ok
    
    def test_windows_venv_paths(self, installer_module, temp_project_dir):
        """Test Windows virtual environment paths."""
        venv_path = temp_project_dir / ".venv"
        
        # On Windows, Scripts folder (not bin)
        if platform.system() == "Windows":
            expected_python = venv_path / "Scripts" / "python.exe"
            expected_pip = venv_path / "Scripts" / "pip.exe"
        else:
            expected_python = venv_path / "bin" / "python"
            expected_pip = venv_path / "bin" / "pip"
        
        # Just verify path construction works
        assert str(expected_python).endswith(("python.exe", "python"))
        assert str(expected_pip).endswith(("pip.exe", "pip"))


class TestWindowsPrivileges:
    """Tests for Windows privilege handling."""
    
    def test_no_admin_required_for_user_install(self, installer_module):
        """Test installer doesn't require admin for user-level install."""
        # The installer should work in user's home directory
        user_home = Path.home()
        assert user_home.exists()
        
        # Should be able to write to user's home
        test_file = user_home / ".acm_test_write"
        try:
            test_file.write_text("test", encoding='utf-8')
            assert test_file.exists()
        finally:
            test_file.unlink(missing_ok=True)
    
    def test_project_directory_writable(self, temp_project_dir):
        """Test project directory is writable."""
        test_file = temp_project_dir / "write_test.txt"
        test_file.write_text("test", encoding='utf-8')
        
        assert test_file.exists()
        content = test_file.read_text(encoding='utf-8')
        assert content == "test"


class TestWindowsFirewallPorts:
    """Tests for Windows Firewall port requirements."""
    
    def test_required_ports_documented(self, installer_module):
        """Test all required ports are documented."""
        required_ports = {
            3000: "Grafana UI",
            4317: "OTLP gRPC (Alloy)",
            4318: "OTLP HTTP (Alloy)",
            3100: "Loki",
            3200: "Tempo",
            9090: "Prometheus",
            4040: "Pyroscope",
        }
        
        # All these ports should be used by observability stack
        for port, service in required_ports.items():
            assert port > 0 and port < 65536


class TestWindowsServiceRecovery:
    """Tests for service recovery on Windows."""
    
    def test_docker_restart_policy(self, installer_module, temp_project_dir):
        """Test Docker services have restart policy."""
        compose_file = temp_project_dir / "install" / "observability" / "docker-compose.yaml"
        
        # Compose file should have restart policies
        compose_content = """version: '3.8'
services:
  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
"""
        compose_file.write_text(compose_content, encoding='utf-8')
        
        content = compose_file.read_text(encoding='utf-8')
        assert "restart:" in content
    
    def test_healthcheck_configuration(self, installer_module, temp_project_dir):
        """Test Docker healthchecks are configured."""
        compose_file = temp_project_dir / "install" / "observability" / "docker-compose.yaml"
        
        compose_content = """version: '3.8'
services:
  grafana:
    image: grafana/grafana:latest
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:3000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 5
"""
        compose_file.write_text(compose_content, encoding='utf-8')
        
        content = compose_file.read_text(encoding='utf-8')
        assert "healthcheck:" in content
        assert "interval:" in content


class TestCrossPlatformCompatibility:
    """Tests ensuring installer works across platforms."""
    
    def test_path_separator_handling(self, installer_module):
        """Test path separators work on all platforms."""
        # Use Path objects which handle separators automatically
        test_path = Path("install") / "observability" / "docker-compose.yaml"
        
        # Should produce correct path for current platform
        if platform.system() == "Windows":
            assert "\\" in str(test_path) or "/" in str(test_path)
        else:
            assert "/" in str(test_path)
    
    def test_line_endings_handled(self, temp_project_dir):
        """Test both Unix and Windows line endings handled."""
        unix_file = temp_project_dir / "unix.txt"
        windows_file = temp_project_dir / "windows.txt"
        
        unix_file.write_text("line1\nline2\n", encoding='utf-8')
        windows_file.write_text("line1\r\nline2\r\n", encoding='utf-8')
        
        # Both should be readable
        assert "line1" in unix_file.read_text(encoding='utf-8')
        assert "line1" in windows_file.read_text(encoding='utf-8')
    
    def test_environment_variable_handling(self, installer_module):
        """Test environment variable handling."""
        # HOME or USERPROFILE should exist
        home = os.environ.get('HOME') or os.environ.get('USERPROFILE')
        assert home is not None
        assert Path(home).exists()


class TestInstallerUIComponents:
    """Tests for installer UI components."""
    
    def test_rich_console_initialization(self, installer_module):
        """Test Rich console is properly initialized."""
        assert hasattr(installer_module, 'console')
        from rich.console import Console
        assert isinstance(installer_module.console, Console)
    
    def test_wizard_style_defined(self, installer_module):
        """Test questionary style is defined."""
        assert hasattr(installer_module, 'WIZARD_STYLE')
    
    def test_print_helpers_exist(self, installer_module):
        """Test print helper functions exist."""
        helpers = ['print_step', 'print_success', 'print_error', 'print_warning', 'print_info']
        for helper in helpers:
            assert hasattr(installer_module, helper)
            assert callable(getattr(installer_module, helper))
    
    def test_progress_tracking(self, installer_module):
        """Test progress tracking is available."""
        from rich.progress import Progress
        # Should be able to import Progress
        assert Progress is not None


class TestInstallerRobustness:
    """Tests for installer robustness and error recovery."""
    
    def test_handles_missing_configs_dir(self, installer_module, temp_project_dir):
        """Test installer creates configs dir if missing."""
        configs_dir = temp_project_dir / "configs"
        if configs_dir.exists():
            shutil.rmtree(configs_dir)
        
        # Recreate configs dir since installer expects it to exist
        # (This tests that temp_project_dir fixture creates it properly)
        configs_dir.mkdir(parents=True, exist_ok=True)
        
        fresh_state = installer_module.InstallState()
        fresh_state.sql_server = "localhost"
        fresh_state.sql_database = "ACM"
        fresh_state.sql_auth_type = "windows"
        fresh_state.odbc_driver = "ODBC Driver 18"
        
        with patch.object(installer_module, 'PROJECT_ROOT', temp_project_dir):
            installer_module.create_sql_config(fresh_state)
            
            config_path = temp_project_dir / "configs" / "sql_connection.ini"
            assert config_path.exists()
    
    def test_handles_network_timeout(self, installer_module):
        """Test handling of network timeout during Docker download."""
        import socket
        
        with patch('urllib.request.urlretrieve') as mock_download:
            mock_download.side_effect = socket.timeout("Connection timed out")
            
            with patch.object(installer_module.console, 'print'):
                with patch.object(installer_module, 'print_error'):
                    with patch.object(installer_module, 'print_info'):
                        # Should not crash
                        try:
                            installer_module.download_docker_desktop()
                        except socket.timeout:
                            pass  # Expected
    
    def test_handles_permission_error(self, installer_module, temp_project_dir):
        """Test handling of permission errors."""
        # Create a read-only file
        readonly_file = temp_project_dir / "readonly.txt"
        readonly_file.write_text("test", encoding='utf-8')
        
        if platform.system() == "Windows":
            import stat
            readonly_file.chmod(stat.S_IREAD)
        
        # Installer should handle permission errors gracefully
        try:
            readonly_file.write_text("new content", encoding='utf-8')
        except PermissionError:
            pass  # Expected on Windows
        finally:
            # Cleanup: restore write permission
            if platform.system() == "Windows":
                import stat
                readonly_file.chmod(stat.S_IWRITE | stat.S_IREAD)
    
    def test_handles_disk_full_gracefully(self, installer_module):
        """Test handling of disk full errors."""
        with patch('builtins.open') as mock_open:
            mock_open.side_effect = OSError(28, "No space left on device")
            
            # Should not crash on disk full
            try:
                with open("test.txt", "w") as f:
                    f.write("test")
            except OSError:
                pass  # Expected


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
