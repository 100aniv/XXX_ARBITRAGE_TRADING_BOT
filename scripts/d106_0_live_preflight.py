"""
D106-0: Live Preflight Dry-run (M6 Live Ramp 준비)

목표:
- .env.live 로딩 및 필수 키 검증
- 환경변수 placeholder(${...}) 검출 → FAIL
- 업비트/바이낸스 API 연결 dry-run (주문 없이 읽기만)
- PostgreSQL/Redis 연결 확인
- 결과를 evidence에 저장

ROADMAP:
- M6 (Live Ramp): D106 소액 LIVE 스모크 준비
- D99-20 완료 (Full Regression 0 FAIL) 기반으로 LIVE 진입

주의:
- 실제 주문 절대 금지 (READ_ONLY_ENFORCED=true 강제)
- Dry-run 목적: 연결 검증만 (잔고, 서버시간, 심볼 조회)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env.live file
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
env_file = project_root / ".env.live"

if not env_file.exists():
    print(f"[FAIL] .env.live not found at {env_file}")
    print("   Create .env.live from .env.live.example")
    sys.exit(1)

print(f"[Loading] {env_file.name}")
load_dotenv(env_file)

# D106-0: READ_ONLY_ENFORCED 강제 설정 (실주문 0건 보장)
os.environ["READ_ONLY_ENFORCED"] = "true"

# Imports
from arbitrage.config.settings import get_settings
from arbitrage.config.readonly_guard import is_readonly_mode


class D106PreflightResult:
    """D106 Preflight 점검 결과"""
    
    def __init__(self):
        self.checks: List[Dict[str, Any]] = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add_check(self, name: str, status: str, message: str, details: Dict[str, Any] = None):
        """점검 항목 추가"""
        self.checks.append({
            "name": name,
            "status": status,  # PASS, FAIL, WARN
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        elif status == "WARN":
            self.warnings += 1
    
    def is_ready(self) -> bool:
        """LIVE 실행 준비 완료 여부"""
        return self.failed == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """결과를 dict로 변환"""
        return {
            "summary": {
                "total_checks": len(self.checks),
                "passed": self.passed,
                "failed": self.failed,
                "warnings": self.warnings,
                "ready_for_live": self.is_ready()
            },
            "checks": self.checks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class D106LivePreflightChecker:
    """D106 LIVE 모드 사전 점검기 (Dry-run)"""
    
    def __init__(self):
        self.result = D106PreflightResult()
    
    def check_env_file_loaded(self) -> None:
        """1. .env.live 로딩 확인"""
        try:
            arbitrage_env = os.getenv("ARBITRAGE_ENV", "")
            
            if arbitrage_env != "live":
                self.result.add_check(
                    name="ENV_FILE_LOAD",
                    status="FAIL",
                    message=f"ARBITRAGE_ENV is '{arbitrage_env}', expected 'live'",
                    details={"arbitrage_env": arbitrage_env}
                )
            else:
                self.result.add_check(
                    name="ENV_FILE_LOAD",
                    status="PASS",
                    message=".env.live loaded successfully",
                    details={"arbitrage_env": arbitrage_env}
                )
        except Exception as e:
            self.result.add_check(
                name="ENV_FILE_LOAD",
                status="FAIL",
                message=f"Error loading .env.live: {e}",
                details={"error": str(e)}
            )
    
    def check_required_keys(self) -> None:
        """2. 필수 환경변수 존재 확인 (placeholder 검출)"""
        required_keys = {
            "UPBIT_ACCESS_KEY": "Upbit Access Key",
            "UPBIT_SECRET_KEY": "Upbit Secret Key",
            "BINANCE_API_KEY": "Binance API Key",
            "BINANCE_API_SECRET": "Binance API Secret",
            "TELEGRAM_BOT_TOKEN": "Telegram Bot Token",
            "TELEGRAM_CHAT_ID": "Telegram Chat ID",
            "POSTGRES_DSN": "PostgreSQL DSN",
            "REDIS_URL": "Redis URL"
        }
        
        missing = []
        placeholders = []
        
        for key, description in required_keys.items():
            value = os.getenv(key, "")
            
            # 누락 체크
            if not value:
                missing.append(f"{key} ({description})")
                continue
            
            # Placeholder 체크 (${...} 패턴)
            if value.startswith("${") and value.endswith("}"):
                placeholders.append(f"{key} = {value}")
            
            # "your_" 접두사 체크 (example 파일 기본값)
            if value.startswith("your_"):
                placeholders.append(f"{key} = {value} (example default)")
        
        if missing:
            self.result.add_check(
                name="REQUIRED_KEYS",
                status="FAIL",
                message=f"Missing required keys: {', '.join(missing)}",
                details={"missing_keys": missing}
            )
        elif placeholders:
            self.result.add_check(
                name="REQUIRED_KEYS",
                status="FAIL",
                message=f"Placeholder values detected: {', '.join(placeholders)}",
                details={"placeholders": placeholders}
            )
        else:
            self.result.add_check(
                name="REQUIRED_KEYS",
                status="PASS",
                message="All required keys present (no placeholders)",
                details={"checked_keys": list(required_keys.keys())}
            )
    
    def check_readonly_mode(self) -> None:
        """3. READ_ONLY_ENFORCED 확인"""
        try:
            readonly = is_readonly_mode()
            
            if not readonly:
                self.result.add_check(
                    name="READONLY_MODE",
                    status="FAIL",
                    message="READ_ONLY_ENFORCED not activated (unsafe for preflight)",
                    details={"readonly": readonly}
                )
            else:
                self.result.add_check(
                    name="READONLY_MODE",
                    status="PASS",
                    message="READ_ONLY_ENFORCED active (orders blocked)",
                    details={"readonly": readonly}
                )
        except Exception as e:
            self.result.add_check(
                name="READONLY_MODE",
                status="FAIL",
                message=f"Error checking readonly mode: {e}",
                details={"error": str(e)}
            )
    
    def check_upbit_connection(self) -> None:
        """4. 업비트 API 연결 확인 (dry-run)"""
        try:
            from arbitrage.exchanges.upbit_spot import UpbitSpotAdapter
            
            upbit = UpbitSpotAdapter()
            
            # Dry-run: 계좌 조회 (주문 아님)
            balances = upbit.get_balances()
            
            self.result.add_check(
                name="UPBIT_CONNECTION",
                status="PASS",
                message=f"Upbit connection OK (balances: {len(balances)} assets)",
                details={
                    "balance_count": len(balances),
                    "method": "get_balances (read-only)"
                }
            )
        except Exception as e:
            self.result.add_check(
                name="UPBIT_CONNECTION",
                status="FAIL",
                message=f"Upbit connection failed: {e}",
                details={"error": str(e)}
            )
    
    def check_binance_connection(self) -> None:
        """5. 바이낸스 API 연결 확인 (dry-run)"""
        try:
            from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
            
            binance = BinanceFuturesExchange()
            
            # Dry-run: 계좌 조회 (주문 아님)
            balance = binance.get_balance()
            
            self.result.add_check(
                name="BINANCE_CONNECTION",
                status="PASS",
                message=f"Binance connection OK (balance: {balance})",
                details={
                    "balance": str(balance),
                    "method": "get_balance (read-only)"
                }
            )
        except Exception as e:
            self.result.add_check(
                name="BINANCE_CONNECTION",
                status="FAIL",
                message=f"Binance connection failed: {e}",
                details={"error": str(e)}
            )
    
    def check_postgres_connection(self) -> None:
        """6. PostgreSQL 연결 확인"""
        try:
            import psycopg2
            from urllib.parse import urlparse
            
            postgres_dsn = os.getenv("POSTGRES_DSN", "")
            
            if not postgres_dsn:
                self.result.add_check(
                    name="POSTGRES_CONNECTION",
                    status="FAIL",
                    message="POSTGRES_DSN not set",
                    details={}
                )
                return
            
            # Parse DSN
            parsed = urlparse(postgres_dsn)
            
            # Connect (timeout 5s)
            conn = psycopg2.connect(postgres_dsn, connect_timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            self.result.add_check(
                name="POSTGRES_CONNECTION",
                status="PASS",
                message=f"PostgreSQL connection OK",
                details={
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "database": parsed.path.lstrip("/"),
                    "version": version[:50]  # 처음 50자만
                }
            )
        except Exception as e:
            self.result.add_check(
                name="POSTGRES_CONNECTION",
                status="FAIL",
                message=f"PostgreSQL connection failed: {e}",
                details={"error": str(e)}
            )
    
    def check_redis_connection(self) -> None:
        """7. Redis 연결 확인"""
        try:
            import redis
            from urllib.parse import urlparse
            
            redis_url = os.getenv("REDIS_URL", "")
            
            if not redis_url:
                self.result.add_check(
                    name="REDIS_CONNECTION",
                    status="FAIL",
                    message="REDIS_URL not set",
                    details={}
                )
                return
            
            # Parse URL
            parsed = urlparse(redis_url)
            
            # Connect (timeout 5s)
            r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
            r.ping()
            
            self.result.add_check(
                name="REDIS_CONNECTION",
                status="PASS",
                message=f"Redis connection OK",
                details={
                    "host": parsed.hostname,
                    "port": parsed.port,
                    "db": parsed.path.lstrip("/") or "0"
                }
            )
        except Exception as e:
            self.result.add_check(
                name="REDIS_CONNECTION",
                status="FAIL",
                message=f"Redis connection failed: {e}",
                details={"error": str(e)}
            )
    
    def run_all_checks(self) -> D106PreflightResult:
        """모든 점검 실행"""
        print("\n" + "="*70)
        print("[D106-0] Live Preflight Dry-run - M6 Live Ramp 준비")
        print("="*70)
        print()
        
        # 1. ENV 로딩
        print("[1/7] Checking .env.live load...")
        self.check_env_file_loaded()
        
        # 2. 필수 키
        print("[2/7] Checking required keys (placeholder detection)...")
        self.check_required_keys()
        
        # 3. READ_ONLY 모드
        print("[3/7] Checking READ_ONLY_ENFORCED...")
        self.check_readonly_mode()
        
        # 4. Upbit 연결
        print("[4/7] Checking Upbit API connection (dry-run)...")
        self.check_upbit_connection()
        
        # 5. Binance 연결
        print("[5/7] Checking Binance API connection (dry-run)...")
        self.check_binance_connection()
        
        # 6. PostgreSQL 연결
        print("[6/7] Checking PostgreSQL connection...")
        self.check_postgres_connection()
        
        # 7. Redis 연결
        print("[7/7] Checking Redis connection...")
        self.check_redis_connection()
        
        print()
        return self.result


def print_summary(result: D106PreflightResult) -> None:
    """결과 요약 출력"""
    print("="*70)
    print("[D106-0] Preflight Results Summary")
    print("="*70)
    print()
    
    summary = result.to_dict()["summary"]
    
    print(f"Total Checks:  {summary['total_checks']}")
    print(f"Passed:        {summary['passed']} [OK]")
    print(f"Failed:        {summary['failed']} [FAIL]")
    print(f"Warnings:      {summary['warnings']} [WARN]")
    print()
    
    if summary["ready_for_live"]:
        print("[READY] All checks passed. Ready for LIVE.")
    else:
        print("[NOT READY] Some checks failed. Fix issues before LIVE.")
    
    print()
    print("="*70)
    print()


def save_results(result: D106PreflightResult, output_path: Path) -> None:
    """결과를 JSON으로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    print(f"[Saved] Results saved to: {output_path}")


def main():
    """Main entry point"""
    
    # Evidence 디렉토리
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_dir = project_root / "logs" / "evidence" / f"d106_0_live_preflight_{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Preflight 실행
    checker = D106LivePreflightChecker()
    result = checker.run_all_checks()
    
    # 결과 출력
    print_summary(result)
    
    # 결과 저장
    output_path = evidence_dir / "d106_0_preflight_result.json"
    save_results(result, output_path)
    
    # 상세 로그 저장
    detail_path = evidence_dir / "d106_0_preflight_detail.txt"
    with open(detail_path, "w", encoding="utf-8") as f:
        f.write("="*70 + "\n")
        f.write("[D106-0] Live Preflight Dry-run - Detailed Results\n")
        f.write("="*70 + "\n\n")
        
        for check in result.checks:
            f.write(f"[{check['status']}] {check['name']}\n")
            f.write(f"   Message: {check['message']}\n")
            if check['details']:
                f.write(f"   Details: {json.dumps(check['details'], indent=6, ensure_ascii=False)}\n")
            f.write(f"   Time: {check['timestamp']}\n")
            f.write("\n")
    
    print(f"[Saved] Details saved to: {detail_path}")
    print()
    
    # Exit code
    if result.is_ready():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
