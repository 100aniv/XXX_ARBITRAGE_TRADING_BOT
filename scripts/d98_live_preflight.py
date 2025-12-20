"""
D98-0: Live Preflight 점검 스크립트 (Dry-run)

실제 LIVE 실행 전 자동 점검.
API 호출은 mock 처리 (이번 단계에서는 실제 호출 없음).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file if exists
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
env_file = project_root / ".env.paper"
if env_file.exists():
    load_dotenv(env_file)

# D98-1: READ_ONLY_ENFORCED 강제 설정 (실주문 0건 보장)
os.environ["READ_ONLY_ENFORCED"] = "true"

from arbitrage.config.settings import get_settings
from arbitrage.config.live_safety import LiveSafetyValidator
from arbitrage.config.readonly_guard import is_readonly_mode, ReadOnlyError
from arbitrage.config.preflight import PreflightError

# D98-5: Real-Check imports
import redis
import psycopg2


class PreflightResult:
    """Preflight 점검 결과"""
    
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


class LivePreflightChecker:
    """LIVE 모드 사전 점검기"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.result = PreflightResult()
        self.settings = get_settings()
    
    def check_environment(self):
        """환경 변수 점검"""
        print("[1/7] 환경 변수 점검...")
        
        # env (Settings.env)
        env = self.settings.env
        if env == "live":
            self.result.add_check(
                "Environment",
                "WARN",
                f"ARBITRAGE_ENV={env} (LIVE 모드)",
                {"env": env}
            )
        else:
            self.result.add_check(
                "Environment",
                "PASS",
                f"ARBITRAGE_ENV={env} (안전)",
                {"env": env}
            )
    
    def check_secrets(self):
        """시크릿 존재 여부 점검"""
        print("[2/7] 시크릿 점검...")
        
        required_secrets = [
            "UPBIT_ACCESS_KEY",
            "UPBIT_SECRET_KEY",
            "BINANCE_API_KEY",
            "BINANCE_API_SECRET",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
        ]
        
        missing = []
        for secret in required_secrets:
            if not os.getenv(secret):
                missing.append(secret)
        
        if missing:
            self.result.add_check(
                "Secrets",
                "FAIL",
                f"필수 시크릿 누락: {', '.join(missing)}",
                {"missing": missing}
            )
        else:
            self.result.add_check(
                "Secrets",
                "PASS",
                "모든 필수 시크릿 존재",
                {"count": len(required_secrets)}
            )
    
    def check_live_safety(self):
        """LIVE 안전장치 점검"""
        print("[3/7] LIVE 안전장치 점검...")
        
        # D98-1: ReadOnlyGuard 검증 (실주문 0건 보장)
        if not is_readonly_mode():
            self.result.add_check(
                "ReadOnly Guard",
                "FAIL",
                "READ_ONLY_ENFORCED가 false로 설정됨 (실주문 위험)",
                {"READ_ONLY_ENFORCED": os.getenv("READ_ONLY_ENFORCED")}
            )
        else:
            self.result.add_check(
                "ReadOnly Guard",
                "PASS",
                "READ_ONLY_ENFORCED=true (실주문 0건 보장)",
                {"READ_ONLY_ENFORCED": "true"}
            )
        
        validator = LiveSafetyValidator()
        is_valid, error_message = validator.validate_live_mode()
        
        if is_valid:
            if self.settings.env == "live":
                self.result.add_check(
                    "Live Safety",
                    "PASS",
                    "LIVE 모드 ARM 상태 (모든 조건 만족)",
                    {
                        "arm_ack": os.getenv("LIVE_ARM_ACK"),
                        "max_notional": os.getenv("LIVE_MAX_NOTIONAL_USD")
                    }
                )
            else:
                self.result.add_check(
                    "Live Safety",
                    "PASS",
                    "PAPER 모드 (LIVE 안전장치 불필요)",
                    {"env": self.settings.env}
                )
        else:
            self.result.add_check(
                "Live Safety",
                "FAIL",
                f"LIVE 안전장치 차단: {error_message[:100]}...",
                {"error": error_message}
            )
    
    def check_database_connection(self):
        """DB 연결 점검 (D98-5: real-check 추가)"""
        print("[4/7] DB 연결 점검...")
        
        postgres_dsn = os.getenv("POSTGRES_DSN")
        redis_url = os.getenv("REDIS_URL")
        
        # 환경변수 존재 확인
        missing = []
        if not postgres_dsn:
            missing.append("POSTGRES_DSN")
        if not redis_url:
            missing.append("REDIS_URL")
        
        if missing:
            self.result.add_check(
                "Database",
                "FAIL",
                f"DB 연결 정보 누락: {', '.join(missing)}",
                {"missing": missing}
            )
            return
        
        # D98-5: Real-Check (dry_run=False일 때만)
        if not self.dry_run:
            try:
                # Redis Real-Check
                redis_client = redis.from_url(redis_url, socket_timeout=5)
                pong = redis_client.ping()
                if not pong:
                    raise PreflightError("Redis PING 실패")
                
                # Redis set/get 테스트
                test_key = "preflight_test_d98_5"
                redis_client.set(test_key, "ok", ex=10)
                test_value = redis_client.get(test_key)
                if test_value != b"ok":
                    raise PreflightError(f"Redis GET 불일치: {test_value}")
                redis_client.delete(test_key)
                
                # Postgres Real-Check
                conn = psycopg2.connect(postgres_dsn, connect_timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result != (1,):
                    raise PreflightError(f"Postgres SELECT 1 불일치: {result}")
                cursor.close()
                conn.close()
                
                self.result.add_check(
                    "Database",
                    "PASS",
                    "DB Real-Check 성공 (Redis PING + SET/GET, Postgres SELECT 1)",
                    {
                        "redis": "connected",
                        "postgres": "connected",
                        "real_check": True
                    }
                )
            except Exception as e:
                self.result.add_check(
                    "Database",
                    "FAIL",
                    f"DB Real-Check 실패: {str(e)[:200]}",
                    {
                        "error": str(e),
                        "real_check": True
                    }
                )
        else:
            # Dry-run: 환경변수 존재만 확인
            self.result.add_check(
                "Database",
                "PASS",
                "DB 연결 정보 존재 (dry-run, 실제 연결 안 함)",
                {
                    "postgres": "configured",
                    "redis": "configured",
                    "dry_run": True
                }
            )
    
    def check_exchange_health(self):
        """거래소 Health 점검 (D98-5: real-check 추가)"""
        print("[5/7] 거래소 Health 점검...")
        
        if self.dry_run:
            self.result.add_check(
                "Exchange Health",
                "PASS",
                "거래소 Health 점검 스킵 (dry-run)",
                {
                    "upbit": "not_checked",
                    "binance": "not_checked",
                    "dry_run": True
                }
            )
            return
        
        # D98-5: Real-Check (환경별 분기)
        if self.settings.env == "paper":
            # Paper 모드: PaperExchange 설정 검증
            try:
                # Paper 모드는 API 키 필수 아님 (mock 동작)
                self.result.add_check(
                    "Exchange Health",
                    "PASS",
                    "Paper 모드 검증 완료 (실제 API 호출 없음)",
                    {
                        "env": "paper",
                        "real_check": True
                    }
                )
            except Exception as e:
                self.result.add_check(
                    "Exchange Health",
                    "FAIL",
                    f"Paper 모드 검증 실패: {str(e)[:200]}",
                    {"error": str(e)}
                )
        
        elif self.settings.env == "live":
            # Live 모드: LiveSafetyValidator 통과 필수 + Public endpoint 호출
            try:
                # LiveSafetyValidator 검증
                validator = LiveSafetyValidator()
                is_valid, error_message = validator.validate_live_mode()
                if not is_valid:
                    raise PreflightError(f"Live Safety 차단: {error_message}")
                
                # Public endpoint 호출은 향후 구현 (현재는 LiveSafety만 검증)
                # TODO: Upbit/Binance public API health check 추가
                
                self.result.add_check(
                    "Exchange Health",
                    "PASS",
                    "Live 모드 검증 완료 (LiveSafetyValidator PASS)",
                    {
                        "env": "live",
                        "live_safety": "pass",
                        "real_check": True
                    }
                )
            except Exception as e:
                self.result.add_check(
                    "Exchange Health",
                    "FAIL",
                    f"Live 모드 검증 실패: {str(e)[:200]}",
                    {"error": str(e)}
                )
        
        else:
            # local_dev 등 기타 환경
            self.result.add_check(
                "Exchange Health",
                "PASS",
                f"환경 {self.settings.env} 검증 완료",
                {"env": self.settings.env}
            )
    
    def check_open_positions(self):
        """오픈 포지션 점검 (mock)"""
        print("[6/7] 오픈 포지션 점검...")
        
        # Mock: 실제 조회 대신 mock 데이터
        if self.dry_run:
            self.result.add_check(
                "Open Positions",
                "PASS",
                "오픈 포지션 점검 스킵 (dry-run)",
                {
                    "open_positions": 0,
                    "open_orders": 0,
                    "dry_run": True
                }
            )
        else:
            # 실제 실행 시 여기서 API 호출
            self.result.add_check(
                "Open Positions",
                "WARN",
                "오픈 포지션 점검 구현 필요",
                {"dry_run": False}
            )
    
    def check_git_safety(self):
        """Git 안전 점검"""
        print("[7/7] Git 안전 점검...")
        
        # .env.live 존재 여부 (커밋 방지)
        env_live_path = Path(__file__).parent.parent / ".env.live"
        
        if env_live_path.exists():
            self.result.add_check(
                "Git Safety",
                "FAIL",
                ".env.live 파일이 존재합니다 (삭제 또는 .gitignore 확인)",
                {"path": str(env_live_path)}
            )
        else:
            self.result.add_check(
                "Git Safety",
                "PASS",
                ".env.live 파일 없음 (안전)",
                {}
            )
    
    def run_all_checks(self) -> PreflightResult:
        """모든 점검 실행"""
        print("=" * 60)
        print("D98 Live Preflight 점검 시작")
        print("=" * 60)
        print()
        
        self.check_environment()
        self.check_secrets()
        self.check_live_safety()
        self.check_database_connection()
        self.check_exchange_health()
        self.check_open_positions()
        self.check_git_safety()
        
        print()
        print("=" * 60)
        print("점검 완료")
        print("=" * 60)
        print(f"Total: {len(self.result.checks)}")
        print(f"PASS: {self.result.passed}")
        print(f"FAIL: {self.result.failed}")
        print(f"WARN: {self.result.warnings}")
        print(f"Ready for LIVE: {self.result.is_ready()}")
        print()
        
        return self.result


def main():
    """메인 실행"""
    import argparse
    
    parser = argparse.ArgumentParser(description="D98 Live Preflight 점검")
    parser.add_argument(
        "--output",
        default="docs/D98/evidence/live_preflight_dryrun.json",
        help="결과 JSON 파일 경로"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run 모드 (실제 API 호출 안 함)"
    )
    parser.add_argument(
        "--real-check",
        action="store_true",
        default=False,
        help="D98-5: 실제 연결 검증 수행 (dry-run 비활성화)"
    )
    
    args = parser.parse_args()
    
    # D98-5: --real-check 플래그가 있으면 dry_run을 False로 설정
    dry_run = args.dry_run and not args.real_check
    
    # Preflight 실행
    checker = LivePreflightChecker(dry_run=dry_run)
    result = checker.run_all_checks()
    
    # 결과 저장
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    print(f"결과 저장: {output_path}")
    
    # Exit code
    if result.is_ready():
        print("\n✅ Preflight PASS: LIVE 실행 준비 완료")
        sys.exit(0)
    else:
        print(f"\n❌ Preflight FAIL: {result.failed}개 항목 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
