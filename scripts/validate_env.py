#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D78-1: Env Validator

주어진 환경의 .env 파일을 검증합니다.

Usage:
    python scripts/validate_env.py --env local_dev
    python scripts/validate_env.py --env paper
    python scripts/validate_env.py --env live --verbose

Exit Codes:
    0: OK (모든 필수 필드 존재)
    1: FAIL (필수 필드 누락)
    2: ERROR (내부 오류)
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple


# Add project root to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))


def load_env_file(env_file: Path) -> None:
    """Load .env file into environment"""
    if not env_file.exists():
        return
    
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()


def validate_env(env_name: str, verbose: bool = False) -> Tuple[str, List[str], List[str]]:
    """
    Validate environment configuration
    
    Returns:
        (status, missing_fields, warnings)
        status: "OK", "WARN", or "FAIL"
    """
    from arbitrage.config.settings import get_settings, RuntimeEnv, reload_settings
    
    missing = []
    warnings = []
    
    try:
        # Force reload to pick up env file (skip validation for now)
        os.environ["SKIP_SETTINGS_VALIDATION"] = "1"
        settings = reload_settings()
        del os.environ["SKIP_SETTINGS_VALIDATION"]
        
        # Check if env matches
        if settings.env.value != env_name:
            warnings.append(f"ARBITRAGE_ENV is '{settings.env.value}' but expected '{env_name}'")
        
        # Validate based on environment
        if env_name == "local_dev":
            # Local dev: minimal requirements, warnings only
            if not settings.telegram_bot_token:
                warnings.append("TELEGRAM_BOT_TOKEN not set (optional for local_dev)")
            if not settings.upbit_access_key and not settings.binance_api_key:
                warnings.append("No exchange API keys set (optional for local_dev with mocks)")
        
        elif env_name in ("paper", "live"):
            # Paper/Live: strict validation
            
            # Exchange credentials: at least one required
            has_upbit = settings.upbit_access_key and settings.upbit_secret_key
            has_binance = settings.binance_api_key and settings.binance_api_secret
            
            if not has_upbit and not has_binance:
                missing.append("At least one exchange (Upbit or Binance) with both API key and secret")
            
            # Telegram: required
            if not settings.telegram_bot_token:
                missing.append("TELEGRAM_BOT_TOKEN")
            if not settings.telegram_default_chat_id:
                missing.append("TELEGRAM_CHAT_ID")
            
            # PostgreSQL: required
            if not settings.postgres_dsn and not settings.postgres_host:
                missing.append("PostgreSQL connection (POSTGRES_DSN or POSTGRES_HOST)")
            
            # Redis: required
            if not settings.redis_url and not settings.redis_host:
                missing.append("Redis connection (REDIS_URL or REDIS_HOST)")
            
            # Warnings for suspicious configurations
            if env_name == "live":
                # Check for localhost in live mode
                if settings.postgres_host == "localhost" and not settings.postgres_dsn:
                    warnings.append("PostgreSQL host is 'localhost' in LIVE mode (should be production DB)")
                
                if settings.redis_host == "localhost" and not settings.redis_url:
                    warnings.append("Redis host is 'localhost' in LIVE mode (should be production Redis)")
                
                # Check for test Telegram chat ID (common pattern: small positive numbers)
                if settings.telegram_default_chat_id:
                    try:
                        chat_id = int(settings.telegram_default_chat_id)
                        if 0 < chat_id < 1000000:
                            warnings.append(
                                f"Telegram chat ID '{chat_id}' looks like a test ID (live mode should use production chat)"
                            )
                    except ValueError:
                        pass
        
        # Verbose: show configuration summary
        if verbose:
            config = settings.to_dict()
            print("\n📊 Configuration Summary:")
            for key, value in config.items():
                print(f"   {key}: {value}")
        
        # Determine status
        if missing:
            status = "FAIL"
        elif warnings:
            status = "WARN"
        else:
            status = "OK"
        
        return status, missing, warnings
    
    except ValueError as e:
        # Settings validation error (from Settings.validate())
        error_msg = str(e)
        # Parse error message to extract missing fields
        if "Missing required credentials" in error_msg:
            for line in error_msg.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    missing.append(line[2:])
        
        if not missing:
            missing.append("Settings validation failed (see error above)")
        
        return "FAIL", missing, warnings
    
    except Exception as e:
        print(f"[Error] Internal Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return "ERROR", [str(e)], []


def print_results(env_name: str, status: str, missing: List[str], warnings: List[str]) -> None:
    """Print validation results"""
    
    print(f"\n{'='*70}")
    print(f"[D78-1] Env Validation Results - {env_name.upper()}")
    print(f"{'='*70}")
    print()
    
    if status == "OK":
        print("[OK] Status: OK")
        print("   All required credentials are present.")
    
    elif status == "WARN":
        print("[WARN] Status: WARN")
        print("   Configuration loaded, but some issues detected.")
    
    elif status == "FAIL":
        print("[FAIL] Status: FAIL")
        print("   Missing required credentials!")
    
    else:  # ERROR
        print("[ERROR] Status: ERROR")
        print("   Internal validation error!")
    
    print()
    
    # Missing fields
    if missing:
        print("[X] Missing Required Fields:")
        for field in missing:
            print(f"   - {field}")
        print()
    
    # Warnings
    if warnings:
        print("[!] Warnings:")
        for warning in warnings:
            print(f"   - {warning}")
        print()
    
    # Recommendations
    if status == "FAIL":
        print("[Recommendations]:")
        print(f"   1. Run: python scripts/setup_env.py --env {env_name}")
        print(f"   2. Or manually edit: .env.{env_name}")
        print(f"   3. Use .env.{env_name}.example as a template")
        print()
    
    elif status == "WARN":
        print("[Recommendations]:")
        if env_name == "live":
            print("   - Review warnings carefully for production readiness")
            print("   - Ensure all services use production endpoints (not localhost)")
            print("   - Verify Telegram alerts go to the correct chat")
        else:
            print("   - Review warnings (may be OK for testing)")
        print()
    
    else:  # OK
        print("[SUCCESS] Environment is properly configured!")
        print()
    
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description="D78-1: Env Validator - Validate environment configuration"
    )
    parser.add_argument(
        "--env",
        choices=["local_dev", "paper", "live"],
        default="paper",
        help="Target environment (default: paper)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Custom .env file path (for testing/isolation)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed configuration summary",
    )
    
    args = parser.parse_args()
    env_name = args.env
    
    # Load .env file (custom path or default)
    if args.env_file:
        env_file = args.env_file
    else:
        env_file = project_root / f".env.{env_name}"
    
    if not env_file.exists():
        print(f"[Warning] {env_file.name} not found")
        print(f"   Looking for environment variables only...")
        print()
    else:
        print(f"[Loading] {env_file.name}")
        load_env_file(env_file)
    
    # Set ARBITRAGE_ENV if not already set
    if "ARBITRAGE_ENV" not in os.environ:
        os.environ["ARBITRAGE_ENV"] = env_name
    
    # Validate
    status, missing, warnings = validate_env(env_name, args.verbose)
    
    # Print results
    print_results(env_name, status, missing, warnings)
    
    # Exit with appropriate code
    if status == "OK":
        sys.exit(0)
    elif status == "WARN":
        sys.exit(0)  # Warnings are OK
    elif status == "FAIL":
        sys.exit(1)
    else:  # ERROR
        sys.exit(2)


if __name__ == "__main__":
    main()
