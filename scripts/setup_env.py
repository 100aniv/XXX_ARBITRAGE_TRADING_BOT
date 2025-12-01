#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D78-1: Env Setup Wizard

대화형 마법사를 통해 .env 파일을 생성/업데이트합니다.

Usage:
    python scripts/setup_env.py --env local_dev
    python scripts/setup_env.py --env paper
    python scripts/setup_env.py --env live
    python scripts/setup_env.py --env paper --non-interactive
"""

import os
import sys
import argparse
import getpass
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from pathlib import Path


# Field definitions: (key, label, description, required_for_envs)
ENV_FIELDS: List[Tuple[str, str, str, List[str]]] = [
    # Exchange credentials
    ("UPBIT_ACCESS_KEY", "Upbit Access Key", "Upbit REST API access key (READ-ONLY 권장)", ["paper", "live"]),
    ("UPBIT_SECRET_KEY", "Upbit Secret Key", "Upbit REST API secret key", ["paper", "live"]),
    ("BINANCE_API_KEY", "Binance API Key", "Binance REST API key (READ-ONLY 권장)", ["paper", "live"]),
    ("BINANCE_API_SECRET", "Binance API Secret", "Binance REST API secret", ["paper", "live"]),
    
    # Telegram
    ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token", "Telegram bot token (from @BotFather)", ["paper", "live"]),
    ("TELEGRAM_CHAT_ID", "Telegram Chat ID", "Telegram chat/group ID (negative for groups)", ["paper", "live"]),
    
    # PostgreSQL
    ("POSTGRES_DSN", "PostgreSQL DSN", "Full connection string (postgresql://user:pass@host:port/db) - 권장", ["paper", "live"]),
    ("POSTGRES_HOST", "PostgreSQL Host", "PostgreSQL server hostname (if not using DSN)", []),
    ("POSTGRES_PORT", "PostgreSQL Port", "PostgreSQL server port (default: 5432)", []),
    ("POSTGRES_DB", "PostgreSQL Database", "PostgreSQL database name (default: arbitrage)", []),
    ("POSTGRES_USER", "PostgreSQL User", "PostgreSQL username (default: arbitrage)", []),
    ("POSTGRES_PASSWORD", "PostgreSQL Password", "PostgreSQL user password", []),
    
    # Redis
    ("REDIS_URL", "Redis URL", "Full Redis URL (redis://host:port/db) - 권장", ["paper", "live"]),
    ("REDIS_HOST", "Redis Host", "Redis server hostname (if not using URL)", []),
    ("REDIS_PORT", "Redis Port", "Redis server port (default: 6379)", []),
    ("REDIS_DB", "Redis Database", "Redis database number (default: 0)", []),
    
    # Email (Optional)
    ("SMTP_HOST", "SMTP Host", "SMTP server hostname (e.g., smtp.gmail.com)", []),
    ("SMTP_PORT", "SMTP Port", "SMTP server port (default: 587)", []),
    ("SMTP_USER", "SMTP Username", "SMTP username/email", []),
    ("SMTP_PASSWORD", "SMTP Password", "SMTP password (app-specific password for Gmail)", []),
    ("SMTP_USE_TLS", "SMTP Use TLS", "Use TLS for SMTP (default: true)", []),
    
    # Slack (Optional)
    ("SLACK_WEBHOOK_URL", "Slack Webhook URL", "Slack incoming webhook URL", []),
    
    # Monitoring
    ("PROMETHEUS_ENABLED", "Prometheus Enabled", "Enable Prometheus metrics (default: true)", []),
    ("PROMETHEUS_PORT", "Prometheus Port", "Prometheus metrics port (default: 9100)", []),
    ("GRAFANA_ENABLED", "Grafana Enabled", "Enable Grafana integration (default: true)", []),
]


def mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask secret value, showing only last N characters"""
    if not value or len(value) <= show_chars:
        return "****"
    return "*" * (len(value) - show_chars) + value[-show_chars:]


def load_existing_env(env_file: Path) -> Dict[str, str]:
    """Load existing .env file into dict"""
    env_vars = {}
    if not env_file.exists():
        return env_vars
    
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if "=" in line:
                    key, _, value = line.partition("=")
                    env_vars[key.strip()] = value.strip()
    except Exception as e:
        print(f"[Warning] Failed to read {env_file}: {e}")
    
    return env_vars


def backup_file(file_path: Path) -> Optional[Path]:
    """Create a backup of the file"""
    if not file_path.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = file_path.with_suffix(f"{file_path.suffix}.bak.{timestamp}")
    
    try:
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"[OK] Backup created: {backup_path.name}")
        return backup_path
    except Exception as e:
        print(f"[Warning] Failed to create backup: {e}")
        return None


def prompt_field(
    key: str,
    label: str,
    description: str,
    existing_value: Optional[str],
    required: bool,
    is_secret: bool = True,
) -> Optional[str]:
    """Prompt user for a single field value"""
    
    print(f"\n[Field] {label}")
    print(f"   {description}")
    
    if existing_value:
        masked = mask_secret(existing_value) if is_secret else existing_value
        keep = input(f"   Current: {masked} - Keep? [Y/n]: ").strip().lower()
        if keep in ("", "y", "yes"):
            return existing_value
    
    if required:
        prompt_text = f"   Enter value (REQUIRED): "
    else:
        prompt_text = f"   Enter value (optional, press Enter to skip): "
    
    # For secret fields, use getpass to hide input
    if is_secret and sys.stdin.isatty():
        value = getpass.getpass(prompt_text)
    else:
        value = input(prompt_text)
    
    return value.strip() if value.strip() else None


def prompt_user_for_env(
    env_name: str,
    existing_vars: Dict[str, str],
    non_interactive: bool = False,
) -> Dict[str, str]:
    """Prompt user for all required/optional fields"""
    
    if non_interactive:
        print("[Non-interactive mode] Using existing values only")
        return existing_vars
    
    new_vars = {}
    
    # Always set ARBITRAGE_ENV
    new_vars["ARBITRAGE_ENV"] = env_name
    
    # Determine which fields are required for this env
    required_fields = {
        key for key, _, _, required_envs in ENV_FIELDS
        if env_name in required_envs
    }
    
    print(f"\n{'='*70}")
    print(f"🔧 Environment: {env_name.upper()}")
    print(f"{'='*70}")
    
    # Special handling for exchanges: at least one required
    exchange_fields = ["UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY", "BINANCE_API_KEY", "BINANCE_API_SECRET"]
    at_least_one_exchange = env_name in ["paper", "live"]
    
    # Prompt for each field
    for key, label, description, required_envs in ENV_FIELDS:
        required = key in required_fields
        existing = existing_vars.get(key)
        
        # Secret fields: anything with KEY, TOKEN, PASSWORD, SECRET, etc.
        is_secret = any(word in key for word in ["KEY", "TOKEN", "PASSWORD", "SECRET", "DSN", "URL"])
        
        value = prompt_field(key, label, description, existing, required, is_secret)
        
        if value:
            new_vars[key] = value
    
    # Validate: at least one exchange for paper/live
    if at_least_one_exchange:
        has_upbit = new_vars.get("UPBIT_ACCESS_KEY") and new_vars.get("UPBIT_SECRET_KEY")
        has_binance = new_vars.get("BINANCE_API_KEY") and new_vars.get("BINANCE_API_SECRET")
        
        if not has_upbit and not has_binance:
            print("\n[Error] At least one exchange (Upbit or Binance) is required for paper/live mode!")
            sys.exit(1)
    
    # Validate: Telegram required for paper/live
    if env_name in ["paper", "live"]:
        if not new_vars.get("TELEGRAM_BOT_TOKEN") or not new_vars.get("TELEGRAM_CHAT_ID"):
            print("\n[Error] Telegram bot token and chat ID are required for paper/live mode!")
            sys.exit(1)
        
        # Validate: PostgreSQL required
        if not new_vars.get("POSTGRES_DSN") and not new_vars.get("POSTGRES_HOST"):
            print("\n[Error] PostgreSQL connection (DSN or HOST) is required for paper/live mode!")
            sys.exit(1)
        
        # Validate: Redis required
        if not new_vars.get("REDIS_URL") and not new_vars.get("REDIS_HOST"):
            print("\n[Error] Redis connection (URL or HOST) is required for paper/live mode!")
            sys.exit(1)
    
    return new_vars


def generate_env_file_content(env_name: str, env_vars: Dict[str, str]) -> str:
    """Generate .env file content with comments"""
    
    lines = []
    
    # Header
    lines.append("# " + "="*77)
    lines.append(f"# D78-1: {env_name.upper()} Environment Configuration")
    lines.append("# " + "="*77)
    lines.append("#")
    lines.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"# Environment: {env_name}")
    lines.append("#")
    
    if env_name == "local_dev":
        lines.append("# [WARNING] LOCAL DEVELOPMENT MODE")
        lines.append("# Most credentials are optional for local testing with mocks.")
    elif env_name == "paper":
        lines.append("# [WARNING] PAPER TRADING MODE")
        lines.append("# Real market data + simulated trading (NO real orders).")
        lines.append("# Requires real API keys for market data access.")
    elif env_name == "live":
        lines.append("# [CRITICAL] LIVE TRADING MODE - REAL MONEY AT RISK!")
        lines.append("# All credentials must be production-ready.")
        lines.append("# NEVER commit this file to Git!")
    
    lines.append("#")
    lines.append("# " + "="*77)
    lines.append("")
    
    # Environment
    lines.append("# Environment")
    lines.append(f"ARBITRAGE_ENV={env_vars.get('ARBITRAGE_ENV', env_name)}")
    lines.append("")
    
    # Exchange credentials
    lines.append("# " + "-"*77)
    lines.append("# Exchange APIs")
    lines.append("# " + "-"*77)
    lines.append("# Upbit")
    lines.append(f"UPBIT_ACCESS_KEY={env_vars.get('UPBIT_ACCESS_KEY', '')}")
    lines.append(f"UPBIT_SECRET_KEY={env_vars.get('UPBIT_SECRET_KEY', '')}")
    lines.append("")
    lines.append("# Binance")
    lines.append(f"BINANCE_API_KEY={env_vars.get('BINANCE_API_KEY', '')}")
    lines.append(f"BINANCE_API_SECRET={env_vars.get('BINANCE_API_SECRET', '')}")
    lines.append("")
    
    # Telegram
    lines.append("# " + "-"*77)
    lines.append("# Telegram Bot (Alerting)")
    lines.append("# " + "-"*77)
    lines.append(f"TELEGRAM_BOT_TOKEN={env_vars.get('TELEGRAM_BOT_TOKEN', '')}")
    lines.append(f"TELEGRAM_CHAT_ID={env_vars.get('TELEGRAM_CHAT_ID', '')}")
    lines.append("")
    
    # PostgreSQL
    lines.append("# " + "-"*77)
    lines.append("# PostgreSQL (State Persistence)")
    lines.append("# " + "-"*77)
    if env_vars.get("POSTGRES_DSN"):
        lines.append(f"POSTGRES_DSN={env_vars['POSTGRES_DSN']}")
    else:
        lines.append(f"# POSTGRES_DSN=postgresql://user:password@host:port/db")
    
    if env_vars.get("POSTGRES_HOST"):
        lines.append(f"POSTGRES_HOST={env_vars['POSTGRES_HOST']}")
        lines.append(f"POSTGRES_PORT={env_vars.get('POSTGRES_PORT', '5432')}")
        lines.append(f"POSTGRES_DB={env_vars.get('POSTGRES_DB', 'arbitrage')}")
        lines.append(f"POSTGRES_USER={env_vars.get('POSTGRES_USER', 'arbitrage')}")
        lines.append(f"POSTGRES_PASSWORD={env_vars.get('POSTGRES_PASSWORD', '')}")
    else:
        lines.append("# POSTGRES_HOST=localhost")
        lines.append("# POSTGRES_PORT=5432")
        lines.append("# POSTGRES_DB=arbitrage")
        lines.append("# POSTGRES_USER=arbitrage")
        lines.append("# POSTGRES_PASSWORD=your_password")
    lines.append("")
    
    # Redis
    lines.append("# " + "-"*77)
    lines.append("# Redis (Caching & State)")
    lines.append("# " + "-"*77)
    if env_vars.get("REDIS_URL"):
        lines.append(f"REDIS_URL={env_vars['REDIS_URL']}")
    else:
        lines.append("# REDIS_URL=redis://localhost:6379/0")
    
    if env_vars.get("REDIS_HOST"):
        lines.append(f"REDIS_HOST={env_vars['REDIS_HOST']}")
        lines.append(f"REDIS_PORT={env_vars.get('REDIS_PORT', '6379')}")
        lines.append(f"REDIS_DB={env_vars.get('REDIS_DB', '0')}")
    else:
        lines.append("# REDIS_HOST=localhost")
        lines.append("# REDIS_PORT=6379")
        lines.append("# REDIS_DB=0")
    lines.append("")
    
    # Email (Optional)
    lines.append("# " + "-"*77)
    lines.append("# Email (Optional - for daily reports)")
    lines.append("# " + "-"*77)
    if env_vars.get("SMTP_HOST"):
        lines.append(f"SMTP_HOST={env_vars['SMTP_HOST']}")
        lines.append(f"SMTP_PORT={env_vars.get('SMTP_PORT', '587')}")
        lines.append(f"SMTP_USER={env_vars.get('SMTP_USER', '')}")
        lines.append(f"SMTP_PASSWORD={env_vars.get('SMTP_PASSWORD', '')}")
        lines.append(f"SMTP_USE_TLS={env_vars.get('SMTP_USE_TLS', 'true')}")
    else:
        lines.append("# SMTP_HOST=smtp.gmail.com")
        lines.append("# SMTP_PORT=587")
        lines.append("# SMTP_USER=your_email@gmail.com")
        lines.append("# SMTP_PASSWORD=your_app_password")
        lines.append("# SMTP_USE_TLS=true")
    lines.append("")
    
    # Slack (Optional)
    lines.append("# " + "-"*77)
    lines.append("# Slack (Optional - for additional alerts)")
    lines.append("# " + "-"*77)
    if env_vars.get("SLACK_WEBHOOK_URL"):
        lines.append(f"SLACK_WEBHOOK_URL={env_vars['SLACK_WEBHOOK_URL']}")
    else:
        lines.append("# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL")
    lines.append("")
    
    # Monitoring
    lines.append("# " + "-"*77)
    lines.append("# Monitoring")
    lines.append("# " + "-"*77)
    lines.append(f"PROMETHEUS_ENABLED={env_vars.get('PROMETHEUS_ENABLED', 'true')}")
    lines.append(f"PROMETHEUS_PORT={env_vars.get('PROMETHEUS_PORT', '9100')}")
    lines.append(f"GRAFANA_ENABLED={env_vars.get('GRAFANA_ENABLED', 'true')}")
    lines.append("")
    
    # Backward compatibility
    lines.append("# " + "-"*77)
    lines.append("# Backward Compatibility")
    lines.append("# " + "-"*77)
    env_map = {"local_dev": "development", "paper": "staging", "live": "production"}
    lines.append(f"APP_ENV={env_map.get(env_name, 'development')}")
    lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="D78-1: Env Setup Wizard - Create/update .env files interactively"
    )
    parser.add_argument(
        "--env",
        choices=["local_dev", "paper", "live"],
        default="local_dev",
        help="Target environment (default: local_dev)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode (use existing values only, for CI)",
    )
    
    args = parser.parse_args()
    env_name = args.env
    
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_file = project_root / f".env.{env_name}"
    
    print(f"\n{'='*70}")
    print(f"[D78-1] Env Setup Wizard - {env_name.upper()}")
    print(f"{'='*70}")
    print(f"Target file: {env_file}")
    print()
    
    # Check if file exists
    if env_file.exists():
        print(f"[Warning] File already exists: {env_file.name}")
        if not args.non_interactive:
            action = input("Choose: (K)eep existing, (U)pdate, (B)ackup+Update? [K/u/b]: ").strip().lower()
            
            if action in ("", "k", "keep"):
                print("[OK] Keeping existing file. Exiting.")
                return
            elif action in ("b", "backup"):
                backup_file(env_file)
            elif action not in ("u", "update"):
                print("[Error] Invalid choice. Exiting.")
                return
    
    # Load existing values
    existing_vars = load_existing_env(env_file)
    
    # Prompt user
    env_vars = prompt_user_for_env(env_name, existing_vars, args.non_interactive)
    
    # Generate content
    content = generate_env_file_content(env_name, env_vars)
    
    # Write file
    try:
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"\n{'='*70}")
        print(f"[OK] .env.{env_name} saved successfully!")
        print(f"{'='*70}")
        print(f"\nNext steps:")
        print(f"  1. Review the file: {env_file}")
        print(f"  2. Validate: python scripts/validate_env.py --env {env_name}")
        print(f"  3. Test: Set ARBITRAGE_ENV={env_name} and run your application")
        print()
        
        if env_name == "live":
            print("[CRITICAL] Never commit .env.live to Git!")
            print("   Add it to .gitignore if not already present.")
            print()
    
    except Exception as e:
        print(f"\n[Error] Failed to write {env_file}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
