"""
D205-12: Admin Control CLI (얇은 명령 전달 계층)

책임:
- CLI 인자 파싱
- AdminControl 명령 호출
- 결과 출력 (JSON)

금지:
- 엔진 로직 구현 (AdminControl 모듈에 위임)
- UI/웹 구현 (D206-4 영역)
"""

import argparse
import json
import sys
import redis
from pathlib import Path

# arbitrage/v2/core/admin_control.py import
sys.path.insert(0, str(Path(__file__).parent.parent))
from arbitrage.v2.core.admin_control import AdminControl


def main():
    parser = argparse.ArgumentParser(description="D205-12 Admin Control CLI")
    parser.add_argument("--run-id", required=True, help="Run ID (예: d205_12_test)")
    parser.add_argument("--env", default="prod", help="Environment (dev/test/prod)")
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6380, help="Redis port")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # pause
    pause_parser = subparsers.add_parser("pause", help="엔진 일시 정지")
    pause_parser.add_argument("--reason", required=True, help="일시 정지 이유")
    pause_parser.add_argument("--actor", default="admin", help="명령 실행자")
    
    # resume
    resume_parser = subparsers.add_parser("resume", help="엔진 재개")
    resume_parser.add_argument("--reason", required=True, help="재개 이유")
    resume_parser.add_argument("--actor", default="admin", help="명령 실행자")
    
    # stop
    stop_parser = subparsers.add_parser("stop", help="엔진 정지")
    stop_parser.add_argument("--reason", required=True, help="정지 이유")
    stop_parser.add_argument("--actor", default="admin", help="명령 실행자")
    
    # panic
    panic_parser = subparsers.add_parser("panic", help="긴급 중단")
    panic_parser.add_argument("--reason", required=True, help="긴급 중단 이유")
    panic_parser.add_argument("--actor", default="admin", help="명령 실행자")
    
    # emergency_close
    emergency_parser = subparsers.add_parser("emergency_close", help="긴급 포지션 청산")
    emergency_parser.add_argument("--reason", required=True, help="긴급 청산 이유")
    emergency_parser.add_argument("--actor", default="admin", help="명령 실행자")
    
    # blacklist_add
    blacklist_add_parser = subparsers.add_parser("blacklist_add", help="심볼 블랙리스트 추가")
    blacklist_add_parser.add_argument("--symbol", required=True, help="블랙리스트 심볼 (예: BTC/KRW)")
    blacklist_add_parser.add_argument("--reason", required=True, help="블랙리스트 이유")
    blacklist_add_parser.add_argument("--actor", default="admin", help="명령 실행자")
    
    # blacklist_remove
    blacklist_remove_parser = subparsers.add_parser("blacklist_remove", help="심볼 블랙리스트 제거")
    blacklist_remove_parser.add_argument("--symbol", required=True, help="제거할 심볼 (예: BTC/KRW)")
    blacklist_remove_parser.add_argument("--reason", required=True, help="제거 이유")
    blacklist_remove_parser.add_argument("--actor", default="admin", help="명령 실행자")
    
    # status
    status_parser = subparsers.add_parser("status", help="현재 상태 조회")
    
    args = parser.parse_args()
    
    # Redis 연결
    try:
        redis_client = redis.Redis(
            host=args.redis_host,
            port=args.redis_port,
            db=0,
            decode_responses=True,
        )
        redis_client.ping()
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Redis connection failed: {e}"}))
        sys.exit(1)
    
    # AdminControl 초기화
    admin_control = AdminControl(
        redis_client=redis_client,
        run_id=args.run_id,
        env=args.env,
    )
    
    # 명령 실행
    result = None
    try:
        if args.command == "pause":
            result = admin_control.pause(reason=args.reason, actor=args.actor)
        elif args.command == "resume":
            result = admin_control.resume(reason=args.reason, actor=args.actor)
        elif args.command == "stop":
            result = admin_control.stop(reason=args.reason, actor=args.actor)
        elif args.command == "panic":
            result = admin_control.panic(reason=args.reason, actor=args.actor)
        elif args.command == "emergency_close":
            result = admin_control.emergency_close(reason=args.reason, actor=args.actor)
        elif args.command == "blacklist_add":
            result = admin_control.blacklist_add(symbol=args.symbol, reason=args.reason, actor=args.actor)
        elif args.command == "blacklist_remove":
            result = admin_control.blacklist_remove(symbol=args.symbol, reason=args.reason, actor=args.actor)
        elif args.command == "status":
            result = admin_control.status()
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result.get("status") in ["ok", None] else 1)
    
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
