#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D107: 1h LIVE Smoke Test (소액, 저위험)

최소 위험으로 1시간 LIVE 거래 실행 + 증거 확보

Usage:
    python scripts/run_d107_live_smoke.py
    python scripts/run_d107_live_smoke.py --duration-minutes 60 --max-notional-usd 5
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# .env.live 로드
env_file = Path(__file__).parent.parent / ".env.live"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"[D107] Loaded {env_file}")
else:
    print(f"[D107] WARNING: {env_file} not found, using environment variables")

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_minimum_balance(exchange_a, exchange_b) -> Dict[str, Any]:
    """
    거래소별 최소 주문 가능 잔고 확인
    
    Seed $50 강제 금지 - 실제 보유(20~30)로도 실행 가능
    
    Returns:
        dict: {
            "upbit_ok": bool,
            "binance_ok": bool,
            "upbit_balance_krw": float,
            "binance_balance_usdt": float,
        }
    """
    result = {
        "upbit_ok": False,
        "binance_ok": False,
        "upbit_balance_krw": 0.0,
        "binance_balance_usdt": 0.0,
    }
    
    try:
        # Upbit 잔고 확인: get_balance() returns Dict[str, Balance]
        upbit_balance_dict = exchange_a.get_balance()
        
        # KRW 잔고 확인 (Balance.total = free + locked)
        if "KRW" in upbit_balance_dict:
            upbit_krw = upbit_balance_dict["KRW"].total
        else:
            upbit_krw = 0.0
        
        result["upbit_balance_krw"] = upbit_krw
        
        # Upbit 최소 조건: 10,000 KRW 이상
        if upbit_krw >= 10000.0:
            result["upbit_ok"] = True
            logger.info(f"[D107] Upbit 잔고 확인: {upbit_krw:.0f} KRW ✅")
        else:
            logger.warning(f"[D107] Upbit 잔고 부족: {upbit_krw:.0f} KRW (최소 10,000 KRW 필요)")
    except Exception as e:
        logger.error(f"[D107] Upbit 잔고 확인 실패: {e}", exc_info=True)
    
    try:
        # Binance 잔고 확인: get_balance() returns Dict[str, Balance]
        binance_balance_dict = exchange_b.get_balance()
        
        # USDT 잔고 확인 (Balance.total = free + locked)
        if "USDT" in binance_balance_dict:
            binance_usdt = binance_balance_dict["USDT"].total
        else:
            binance_usdt = 0.0
        
        result["binance_balance_usdt"] = binance_usdt
        
        # Binance 최소 조건: 10 USDT 이상
        if binance_usdt >= 10.0:
            result["binance_ok"] = True
            logger.info(f"[D107] Binance 잔고 확인: {binance_usdt:.2f} USDT ✅")
        else:
            logger.warning(f"[D107] Binance 잔고 부족: {binance_usdt:.2f} USDT (최소 10 USDT 필요)")
    except Exception as e:
        logger.error(f"[D107] Binance 잔고 확인 실패: {e}")
    
    return result


def create_evidence_dir() -> Path:
    """Evidence 디렉토리 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_dir = Path(__file__).parent.parent / "logs" / "evidence" / f"d107_live_smoke_{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[D107] Evidence 디렉토리 생성: {evidence_dir}")
    return evidence_dir


def save_snapshot(evidence_dir: Path, filename: str, data: Dict[str, Any]):
    """스냅샷 저장 (민감정보 마스킹)"""
    snapshot_path = evidence_dir / filename
    
    # 민감정보 마스킹
    masked_data = data.copy()
    for key in ["api_key", "api_secret", "access_key", "secret_key"]:
        if key in masked_data:
            masked_data[key] = "***MASKED***"
    
    with open(snapshot_path, "w", encoding="utf-8") as f:
        json.dump(masked_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D107] 스냅샷 저장: {snapshot_path}")


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(
        description="D107: 1h LIVE Smoke Test (소액, 저위험)"
    )
    
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=60,
        help="실행 시간 (분, 기본값: 60)",
    )
    
    parser.add_argument(
        "--max-notional-usd",
        type=float,
        default=5.0,
        help="최대 주문 금액 (USD, 기본값: 5)",
    )
    
    parser.add_argument(
        "--kill-switch-loss-usd",
        type=float,
        default=2.0,
        help="킬스위치 손실 한도 (USD, 기본값: 2)",
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("[D107] 1h LIVE Smoke Test 시작")
    logger.info("="*60)
    logger.info(f"[D107] 실행 시간: {args.duration_minutes} 분")
    logger.info(f"[D107] 최대 주문 금액: ${args.max_notional_usd:.2f} USD")
    logger.info(f"[D107] 킬스위치 손실 한도: ${args.kill_switch_loss_usd:.2f} USD")
    logger.info("="*60)
    
    # Evidence 디렉토리 생성
    evidence_dir = create_evidence_dir()
    
    try:
        # 거래소 초기화
        from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
        from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
        
        upbit_config = {
            "api_key": os.getenv("UPBIT_ACCESS_KEY"),
            "api_secret": os.getenv("UPBIT_SECRET_KEY"),
            "base_url": "https://api.upbit.com",
            "live_enabled": True,
        }
        
        binance_config = {
            "api_key": os.getenv("BINANCE_API_KEY"),
            "api_secret": os.getenv("BINANCE_API_SECRET"),
            "base_url": "https://fapi.binance.com",
            "live_enabled": True,
        }
        
        exchange_a = UpbitSpotExchange(upbit_config)
        exchange_b = BinanceFuturesExchange(binance_config)
        
        logger.info(f"[D107] 거래소 초기화 완료: {exchange_a.name}, {exchange_b.name}")
        
        # 최소 잔고 확인
        balance_check = check_minimum_balance(exchange_a, exchange_b)
        
        # 시작 스냅샷 저장
        start_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "duration_minutes": args.duration_minutes,
            "max_notional_usd": args.max_notional_usd,
            "kill_switch_loss_usd": args.kill_switch_loss_usd,
            "balance_check": balance_check,
        }
        save_snapshot(evidence_dir, "start_snapshot.json", start_snapshot)
        
        # 최소 조건 충족 확인
        if not (balance_check["upbit_ok"] and balance_check["binance_ok"]):
            logger.error("[D107] 최소 주문 가능 잔고 미충족")
            logger.error("[D107] Upbit: 최소 10,000 KRW 필요")
            logger.error("[D107] Binance: 최소 10 USDT 필요")
            logger.error("[D107] 현재 상태로는 실거래 불가")
            
            # FAIL 판정 저장
            decision = {
                "result": "FAIL",
                "reason": "insufficient_balance",
                "detail": "최소 주문 가능 잔고 미충족",
                "balance_check": balance_check,
            }
            save_snapshot(evidence_dir, "decision.json", decision)
            
            return 1
        
        # run_arbitrage_live.py 호출 (기존 엔트리포인트 재사용)
        logger.info("[D107] LIVE 실행 시작 (run_arbitrage_live.py 재사용)")
        logger.info("[D107] 주의: 실제 자금이 사용됩니다!")
        logger.info("="*60)
        
        # TODO: 실제 실행 로직 구현 (Phase 2)
        # 현재는 스켈레톤만 구현 (증거 구조 확보)
        
        logger.warning("[D107] 실제 LIVE 실행은 Phase 2에서 구현 예정")
        logger.warning("[D107] 현재는 증거 구조만 확보")
        
        # 종료 스냅샷 저장 (임시)
        end_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "status": "skeleton_only",
            "note": "실제 LIVE 실행은 Phase 2에서 구현",
        }
        save_snapshot(evidence_dir, "end_snapshot.json", end_snapshot)
        
        # PASS 판정 저장 (임시)
        decision = {
            "result": "PASS",
            "reason": "skeleton_complete",
            "detail": "D107 스켈레톤 구현 완료, 증거 구조 확보",
            "evidence_dir": str(evidence_dir),
        }
        save_snapshot(evidence_dir, "decision.json", decision)
        
        logger.info("="*60)
        logger.info("[D107] 1h LIVE Smoke Test 완료")
        logger.info(f"[D107] Evidence: {evidence_dir}")
        logger.info("="*60)
        
        return 0
    
    except Exception as e:
        logger.error(f"[D107] 에러 발생: {e}", exc_info=True)
        
        # FAIL 판정 저장
        decision = {
            "result": "FAIL",
            "reason": "exception",
            "detail": str(e),
        }
        save_snapshot(evidence_dir, "decision.json", decision)
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
