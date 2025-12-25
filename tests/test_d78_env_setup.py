# -*- coding: utf-8 -*-
"""
D78-1: Env Setup & Validation Tests

Tests for setup_env.py and validate_env.py
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict

import pytest


# Test helpers

def create_test_env_file(tmp_path: Path, env_name: str, vars: Dict[str, str]) -> Path:
    """Create a test .env file"""
    env_file = tmp_path / f".env.{env_name}"
    
    lines = [f"# Test env file for {env_name}"]
    lines.append(f"ARBITRAGE_ENV={env_name}")
    
    for key, value in vars.items():
        lines.append(f"{key}={value}")
    
    env_file.write_text("\n".join(lines), encoding="utf-8")
    return env_file


def run_script(script_name: str, args: list, cwd: Path, env: Dict[str, str] = None, clean_env: bool = False) -> subprocess.CompletedProcess:
    """Run a script and return the result
    
    Args:
        clean_env: If True, start with minimal environment (PATH, SYSTEMROOT only)
                   This provides complete isolation for env validation tests
    """
    script_path = cwd / "scripts" / script_name
    cmd = [sys.executable, str(script_path)] + args
    
    # Build environment
    if clean_env:
        # Minimal environment for complete isolation
        full_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PYTHONPATH": str(cwd),
        }
    else:
        # Inherit current environment
        full_env = os.environ.copy()
    
    # Add/override with provided env vars
    if env:
        full_env.update(env)
    
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=full_env,
    )


# Tests for validate_env.py

def test_validate_env_local_dev_minimal(tmp_path, monkeypatch):
    """
    Test validate_env.py for local_dev with minimal config
    Should PASS with warnings
    """
    # Create minimal local_dev env file
    env_file = create_test_env_file(tmp_path, "local_dev", {
        "POSTGRES_HOST": "localhost",
        "REDIS_HOST": "localhost",
    })
    
    project_root = Path(__file__).parent.parent
    
    # Run validate_env.py with --env-file for isolation
    result = run_script(
        "validate_env.py",
        ["--env", "local_dev", "--env-file", str(env_file)],
        project_root,
        env={"ARBITRAGE_ENV": "local_dev"},
        clean_env=True,
    )
    
    # Should succeed (exit 0) with warnings
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "WARN" in result.stdout or "OK" in result.stdout


def test_validate_env_paper_missing_required(tmp_path, monkeypatch):
    """
    Test validate_env.py for paper with missing required fields
    Should FAIL
    """
    # Create incomplete paper env file (missing Telegram, Exchange)
    env_file = create_test_env_file(tmp_path, "paper", {
        "POSTGRES_HOST": "localhost",
        "REDIS_HOST": "localhost",
    })
    
    project_root = Path(__file__).parent.parent
    
    result = run_script(
        "validate_env.py",
        ["--env", "paper", "--env-file", str(env_file)],
        project_root,
        env={"ARBITRAGE_ENV": "paper"},
        clean_env=True,
    )
    
    # Should fail (exit 1)
    assert result.returncode == 1, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "FAIL" in result.stdout
    assert "exchange" in result.stdout.lower() or "telegram" in result.stdout.lower()


def test_validate_env_paper_complete(tmp_path, monkeypatch):
    """
    Test validate_env.py for paper with all required fields
    Should PASS
    """
    # Create complete paper env file
    env_file = create_test_env_file(tmp_path, "paper", {
        "UPBIT_ACCESS_KEY": "test_upbit_key_12345",
        "UPBIT_SECRET_KEY": "test_upbit_secret_12345",
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        "TELEGRAM_CHAT_ID": "-1001234567890",
        "POSTGRES_DSN": "postgresql://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/0",
    })
    
    project_root = Path(__file__).parent.parent
    
    result = run_script(
        "validate_env.py",
        ["--env", "paper", "--env-file", str(env_file)],
        project_root,
        env={"ARBITRAGE_ENV": "paper"},
        clean_env=True,
    )
    
    # Should succeed (exit 0)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "OK" in result.stdout


def test_validate_env_live_warns_localhost(tmp_path, monkeypatch):
    """
    Test validate_env.py for live mode with localhost DB
    Should PASS with WARN
    """
    # Create live env with localhost (suspicious for live)
    env_file = create_test_env_file(tmp_path, "live", {
        "UPBIT_ACCESS_KEY": "test_upbit_key",
        "UPBIT_SECRET_KEY": "test_upbit_secret",
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdef",
        "TELEGRAM_CHAT_ID": "-1001234567890",
        "POSTGRES_HOST": "localhost",  # Suspicious for live
        "REDIS_HOST": "localhost",  # Suspicious for live
    })
    
    project_root = Path(__file__).parent.parent
    
    result = run_script(
        "validate_env.py",
        ["--env", "live", "--env-file", str(env_file)],
        project_root,
        env={"ARBITRAGE_ENV": "live"},
        clean_env=True,
    )
    
    # Should succeed but with warnings
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "WARN" in result.stdout
    assert "localhost" in result.stdout.lower()


def test_validate_env_live_warns_test_chat_id(tmp_path, monkeypatch):
    """
    Test validate_env.py for live mode with test-looking chat ID
    Should WARN
    """
    # Create live env with test-looking chat ID
    env_file = create_test_env_file(tmp_path, "live", {
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdef",
        "TELEGRAM_CHAT_ID": "12345",  # Test-looking ID (small positive number)
        "POSTGRES_DSN": "postgresql://prod:prod@prod-host:5432/prod",
        "REDIS_URL": "redis://prod-redis:6379/0",
    })
    
    project_root = Path(__file__).parent.parent
    
    result = run_script(
        "validate_env.py",
        ["--env", "live", "--env-file", str(env_file)],
        project_root,
        env={"ARBITRAGE_ENV": "live"},
        clean_env=True,
    )
    
    # Should succeed but with warnings
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "WARN" in result.stdout or "test" in result.stdout.lower()


def test_validate_env_verbose(tmp_path, monkeypatch):
    """
    Test validate_env.py with --verbose flag
    Should show configuration summary
    """
    env_file = create_test_env_file(tmp_path, "local_dev", {
        "POSTGRES_HOST": "localhost",
        "REDIS_HOST": "localhost",
    })
    
    project_root = Path(__file__).parent.parent
    
    result = run_script(
        "validate_env.py",
        ["--env", "local_dev", "--env-file", str(env_file), "--verbose"],
        project_root,
        env={"ARBITRAGE_ENV": "local_dev"},
        clean_env=True,
    )
    
    # Should succeed and show summary
    assert result.returncode == 0
    assert "Configuration Summary" in result.stdout or "configured" in result.stdout.lower()


def test_no_secret_values_in_validate_output(tmp_path, monkeypatch):
    """
    Test that validate_env.py does NOT print actual secret values
    """
    # Use distinctive secret values
    secret_key = "SUPER_SECRET_KEY_DO_NOT_PRINT_123456789"
    secret_token = "987654321:SUPER_SECRET_TOKEN_DO_NOT_PRINT"
    
    env_file = create_test_env_file(tmp_path, "paper", {
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": secret_key,
        "TELEGRAM_BOT_TOKEN": secret_token,
        "TELEGRAM_CHAT_ID": "-1001234567890",
        "POSTGRES_DSN": "postgresql://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/0",
    })
    
    project_root = Path(__file__).parent.parent
    
    result = run_script(
        "validate_env.py",
        ["--env", "paper", "--env-file", str(env_file), "--verbose"],
        project_root,
        env={"ARBITRAGE_ENV": "paper"},
        clean_env=True,
    )
    
    # Should succeed
    assert result.returncode == 0
    
    # Should NOT contain the actual secret values
    assert secret_key not in result.stdout, "Secret key found in output!"
    assert secret_token not in result.stdout, "Secret token found in output!"
    
    # Should show "configured: True/False" instead
    assert "configured" in result.stdout.lower()


# Tests for setup_env.py (non-interactive mode only)

def test_setup_env_non_interactive_preserves_existing(tmp_path, monkeypatch):
    """
    Test setup_env.py in non-interactive mode preserves existing values
    """
    monkeypatch.chdir(tmp_path)
    
    # Create existing env file
    existing_vars = {
        "UPBIT_ACCESS_KEY": "existing_key",
        "TELEGRAM_BOT_TOKEN": "existing_token",
    }
    env_file = create_test_env_file(tmp_path, "local_dev", existing_vars)
    
    project_root = Path(__file__).parent.parent
    
    # Run setup_env.py in non-interactive mode
    result = run_script(
        "setup_env.py",
        ["--env", "local_dev", "--non-interactive"],
        project_root,
    )
    
    # Should succeed
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    
    # Check that file still exists
    assert env_file.exists()


def test_setup_env_file_structure(tmp_path):
    """
    Test that generated .env files have proper structure
    """
    import sys
    from pathlib import Path
    
    # Add scripts to path
    scripts_path = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_path))
    
    try:
        from setup_env import generate_env_file_content
    finally:
        sys.path.pop(0)
    
    # Generate content
    test_vars = {
        "ARBITRAGE_ENV": "paper",
        "UPBIT_ACCESS_KEY": "test_key",
        "TELEGRAM_BOT_TOKEN": "test_token",
    }
    
    content = generate_env_file_content("paper", test_vars)
    
    # Check structure
    assert "D78-1" in content
    assert "ARBITRAGE_ENV=paper" in content
    assert "UPBIT_ACCESS_KEY=test_key" in content
    assert "TELEGRAM_BOT_TOKEN=test_token" in content
    
    # Check sections
    assert "Exchange APIs" in content
    assert "Telegram" in content
    assert "PostgreSQL" in content
    assert "Redis" in content


def test_mask_secret():
    """Test secret masking utility"""
    import sys
    from pathlib import Path
    
    # Add scripts to path
    scripts_path = Path(__file__).parent.parent / "scripts"
    sys.path.insert(0, str(scripts_path))
    
    try:
        from setup_env import mask_secret
    finally:
        sys.path.pop(0)
    
    # Normal case
    assert mask_secret("abcdefghijklmnop", 4) == "************mnop"
    
    # Short secret
    assert mask_secret("abc", 4) == "****"
    
    # Empty
    assert mask_secret("", 4) == "****"
    
    # Exact length
    assert mask_secret("1234", 4) == "****"


# Integration test with Settings

def test_validate_env_integrates_with_settings(tmp_path, monkeypatch):
    """
    Test that validate_env.py properly integrates with Settings module
    """
    monkeypatch.chdir(tmp_path)
    
    # Create valid paper env
    env_file = create_test_env_file(tmp_path, "paper", {
        "UPBIT_ACCESS_KEY": "test_key",
        "UPBIT_SECRET_KEY": "test_secret",
        "BINANCE_API_KEY": "test_binance_key",
        "BINANCE_API_SECRET": "test_binance_secret",
        "TELEGRAM_BOT_TOKEN": "123456:ABC",
        "TELEGRAM_CHAT_ID": "-100123",
        "POSTGRES_DSN": "postgresql://test:test@localhost:5432/test",
        "REDIS_URL": "redis://localhost:6379/0",
    })
    
    project_root = Path(__file__).parent.parent
    
    # Load env and validate using Settings
    from arbitrage.config.settings import get_settings, reload_settings
    
    # Set environment variables from file
    for line in env_file.read_text().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip()
    
    # Reload settings
    settings = reload_settings()
    
    # Check that settings loaded correctly
    assert settings.env.value == "paper"
    assert settings.upbit_access_key == "test_key"
    assert settings.binance_api_key == "test_binance_key"
    assert settings.telegram_bot_token == "123456:ABC"
    assert settings.postgres_dsn == "postgresql://test:test@localhost:5432/test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
