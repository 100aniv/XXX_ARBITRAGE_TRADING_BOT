#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92 v3.2: Required Secrets Checker

Gate 10m 테스트 실행 전 필수 시크릿이 모두 설정되어 있는지 검증합니다.

Exit Codes:
    0: 모든 필수 시크릿 존재
    2: 필수 시크릿 누락 (명확한 에러 메시지와 함께)
    
Usage:
    python scripts/check_required_secrets.py
    python scripts/check_required_secrets.py --env paper
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_secrets() -> Tuple[bool, List[str]]:
    """
    필수 시크릿 검증
    
    Returns:
        (all_present, missing_vars)
    """
    # .env.paper 로드 시도
    env_name = os.getenv("ARBITRAGE_ENV", "paper")
    env_file = Path(__file__).parent.parent / f".env.{env_name}"
    
    try:
        from dotenv import load_dotenv
        if env_file.exists():
            load_dotenv(env_file, override=True)
            print(f"[INFO] Loaded {env_file}")
        else:
            print(f"[WARN] {env_file} not found")
            return False, [f"{env_file} 파일이 없습니다"]
    except ImportError:
        print("[ERROR] python-dotenv not installed")
        return False, ["python-dotenv 패키지가 필요합니다"]
    
    # 환경변수 직접 검증
    missing = []
    
    # 1. Exchange API Keys
    upbit_key = os.getenv("UPBIT_ACCESS_KEY")
    upbit_secret = os.getenv("UPBIT_SECRET_KEY")
    binance_key = os.getenv("BINANCE_API_KEY")
    binance_secret = os.getenv("BINANCE_API_SECRET")
    
    has_upbit = bool(upbit_key and upbit_secret)
    has_binance = bool(binance_key and binance_secret)
    
    if not has_upbit and not has_binance:
        missing.append("UPBIT_ACCESS_KEY + UPBIT_SECRET_KEY (또는 BINANCE_API_KEY + BINANCE_API_SECRET)")
    
    # 2. Telegram (PAPER 모드에서는 선택, LIVE는 필수)
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat = os.getenv("TELEGRAM_CHAT_ID")
    
    if env_name == "live":
        if not telegram_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not telegram_chat:
            missing.append("TELEGRAM_CHAT_ID")
    
    # 3. PostgreSQL
    postgres_dsn = os.getenv("POSTGRES_DSN")
    postgres_host = os.getenv("POSTGRES_HOST")
    
    if not postgres_dsn and not postgres_host:
        missing.append("POSTGRES_DSN (또는 POSTGRES_HOST)")
    
    # 4. Redis
    redis_url = os.getenv("REDIS_URL")
    redis_host = os.getenv("REDIS_HOST")
    
    if not redis_url and not redis_host:
        missing.append("REDIS_URL (또는 REDIS_HOST)")
    
    return len(missing) == 0, missing


def main() -> int:
    """Main entry point"""
    print("=" * 70)
    print("D92 v3.2: Required Secrets Checker")
    print("=" * 70)
    print()
    
    all_present, missing = check_secrets()
    
    if all_present:
        print("[OK] 모든 필수 시크릿이 설정되어 있습니다.")
        print()
        print("검증된 항목:")
        print("  - Exchange API Keys (Upbit 또는 Binance)")
        print("  - PostgreSQL DSN")
        print("  - Redis URL")
        print()
        return 0
    else:
        print("[FAIL] 필수 시크릿이 누락되었습니다.")
        print()
        print("누락된 변수:")
        for var in missing:
            print(f"  - {var}")
        print()
        
        env_name = os.getenv("ARBITRAGE_ENV", "paper")
        env_file = Path(__file__).parent.parent / f".env.{env_name}"
        
        print("해결 방법:")
        print(f"  1. {env_file} 파일을 열어서 위 변수를 설정하세요.")
        print(f"  2. 템플릿: {env_file}.example")
        print(f"  3. 설정 후 다시 실행: python scripts/check_required_secrets.py")
        print()
        print("[중요] 실제 API 키 값은 절대 커밋하지 마세요!")
        print()
        
        return 2


if __name__ == "__main__":
    sys.exit(main())
