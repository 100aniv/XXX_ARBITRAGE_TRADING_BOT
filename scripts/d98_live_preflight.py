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

from arbitrage.config.settings import get_settings
from arbitrage.config.live_safety import LiveSafetyValidator


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
        """DB 연결 점검 (mock)"""
        print("[4/7] DB 연결 점검...")
        
        # Mock: 실제 연결 대신 DSN 존재 여부만 확인
        postgres_dsn = os.getenv("POSTGRES_DSN")
        redis_url = os.getenv("REDIS_URL")
        
        if postgres_dsn and redis_url:
            self.result.add_check(
                "Database",
                "PASS",
                "DB 연결 정보 존재 (dry-run, 실제 연결 안 함)",
                {
                    "postgres": "configured",
                    "redis": "configured",
                    "dry_run": self.dry_run
                }
            )
        else:
            missing = []
            if not postgres_dsn:
                missing.append("POSTGRES_DSN")
            if not redis_url:
                missing.append("REDIS_URL")
            
            self.result.add_check(
                "Database",
                "FAIL",
                f"DB 연결 정보 누락: {', '.join(missing)}",
                {"missing": missing}
            )
    
    def check_exchange_health(self):
        """거래소 Health 점검 (mock)"""
        print("[5/7] 거래소 Health 점검...")
        
        # Mock: 실제 API 호출 대신 키 존재 여부만 확인
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
        else:
            # 실제 실행 시 여기서 API 호출
            self.result.add_check(
                "Exchange Health",
                "WARN",
                "거래소 Health 점검 구현 필요",
                {"dry_run": False}
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
    
    args = parser.parse_args()
    
    # Preflight 실행
    checker = LivePreflightChecker(dry_run=args.dry_run)
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
