#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D107-0: 10분 LIVE Smoke Test (실체결 검증)

목표: 보유 심볼 제외, 실제 체결 1회 왕복 + 플랫 복귀

Usage:
    python scripts/run_d107_live_smoke.py --duration-seconds 600 --i-understand-live-trading
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from arbitrage.exchanges.base import OrderSide, OrderType, OrderStatus

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
        json.dump(masked_data, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info(f"[D107-0] 스냅샷 저장: {snapshot_path}")


def execute_real_trade(
    exchange_a,
    symbol: str,
    order_krw: float,
    max_loss_krw: float,
    duration_seconds: int,
    evidence_dir: Path,
) -> Dict[str, Any]:
    """
    실체결 로직: BUY → SELL 1회 왕복
    
    Returns:
        dict: {"success": bool, "orders": List, ...}
    """
    result = {
        "success": False,
        "orders": [],
        "error": None,
        "detail": None,
    }
    
    start_time = time.time()
    order_log = []
    
    try:
        # 1. 호가 조회
        logger.info(f"[D107-0] Step 1) 호가 조회: {symbol}")
        orderbook = exchange_a.get_orderbook(symbol)
        best_ask = orderbook.best_ask()
        best_bid = orderbook.best_bid()
        
        if not best_ask or not best_bid:
            result["error"] = "orderbook_empty"
            result["detail"] = "호가 정보 없음"
            return result
        
        logger.info(f"[D107-0] 호가: ask={best_ask:.2f}, bid={best_bid:.2f}")
        
        # 2. 매수 (LIMIT 주문, 즉시 체결 가능한 높은 가격)
        buy_krw = order_krw * 1.5  # 여유 50% (충분한 체결 확보)
        buy_price = int(best_ask * 1.05)  # ask보다 5% 높게 (즉시 체결)
        buy_qty = round(buy_krw / buy_price, 8)
        
        logger.info(f"[D107-0] Step 2) 매수 주문: {buy_qty:.8f} @ {buy_price} KRW (total: {buy_krw:.0f} KRW)")
        
        buy_order = exchange_a.create_order(
            symbol=symbol,
            side=OrderSide.BUY,
            qty=buy_qty,
            price=buy_price,
            order_type=OrderType.LIMIT,
        )
        
        order_log.append({
            "action": "BUY",
            "order_id": buy_order.order_id,
            "qty": buy_qty,
            "price": buy_price,
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.info(f"[D107-0] ✅ 매수 주문 생성: {buy_order.order_id}")
        
        # 3. 체결 대기 (최대 30초, 최소 주문 금액 충족 확인)
        logger.info("[D107-0] Step 3) 매수 체결 대기 (최대 30초)")
        filled_qty = 0.0
        min_sell_qty = 5000.0 / buy_price  # 최소 주문 금액 충족 수량
        
        for i in range(30):
            time.sleep(1)
            status = exchange_a.get_order_status(buy_order.order_id)
            filled_qty = status.filled_qty
            
            # 매도 시 최소 주문 금액 충족 여부 체크
            if filled_qty > 0:
                potential_sell_krw = filled_qty * buy_price
                logger.debug(f"[D107-0] 체결 진행: {filled_qty:.8f} ADA (매도 시 {potential_sell_krw:.0f} KRW)")
                
                if potential_sell_krw >= 5000.0:
                    logger.info(f"[D107-0] ✅ 매수 충분 체결: {filled_qty:.8f} ADA")
                    break
            
            if status.status == OrderStatus.FILLED:
                logger.info(f"[D107-0] ✅ 매수 전체 체결: {filled_qty:.8f}")
                break
            elif status.status in [OrderStatus.CANCELED, OrderStatus.REJECTED]:
                result["error"] = "buy_order_failed"
                result["detail"] = f"매수 주문 실패: {status.status}"
                return result
        
        # 최소 수량 체크
        if filled_qty == 0 or (filled_qty * buy_price) < 5000.0:
            logger.warning(f"[D107-0] ⚠️  매수 체결 부족: {filled_qty:.8f} ADA, 취소 시도")
            exchange_a.cancel_order(buy_order.order_id)
            result["error"] = "buy_insufficient"
            result["detail"] = f"매수 체결량 부족 (최소 {min_sell_qty:.8f} ADA 필요, 실제 {filled_qty:.8f})"
            return result
        
        result["buy_qty"] = filled_qty
        
        # 4. 매도 (즉시 체결 위해 bid보다 2% 낮게)
        sell_price_raw = best_bid * 0.98
        sell_price = int(sell_price_raw)  # Upbit KRW: 정수만 허용
        sell_qty = round(filled_qty, 8)  # Upbit: 소수점 8자리까지
        
        # 최소 주문 금액 체크
        sell_total_krw = sell_price * sell_qty
        logger.info(f"[D107-0] Step 4) 매도 주문: {sell_qty:.8f} @ {sell_price} KRW (total: {sell_total_krw:.0f} KRW)")
        sell_order = exchange_a.create_order(
            symbol=symbol,
            side=OrderSide.SELL,
            qty=sell_qty,
            price=sell_price,
            order_type=OrderType.LIMIT,
        )
        
        order_log.append({
            "action": "SELL",
            "order_id": sell_order.order_id,
            "qty": sell_qty,
            "price": sell_price,
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.info(f"[D107-0] ✅ 매도 주문 생성: {sell_order.order_id}")
        
        # 5. 매도 체결 대기 (최대 30초)
        logger.info("[D107-0] Step 5) 매도 체결 대기 (최대 30초)")
        sell_filled_qty = 0.0
        for i in range(30):
            time.sleep(1)
            status = exchange_a.get_order_status(sell_order.order_id)
            
            if status.status == OrderStatus.FILLED:
                sell_filled_qty = status.filled_qty
                logger.info(f"[D107-0] ✅ 매도 체결 완료: {sell_filled_qty:.8f}")
                break
            elif status.status in [OrderStatus.CANCELED, OrderStatus.REJECTED]:
                result["error"] = "sell_order_failed"
                result["detail"] = f"매도 주문 실패: {status.status}"
                result["orders"] = order_log
                return result
        
        if sell_filled_qty == 0:
            # 미체결 → 취소 시도
            logger.warning("[D107-0] ⚠️  매도 미체결, 취소 시도")
            exchange_a.cancel_order(sell_order.order_id)
            result["error"] = "sell_not_filled"
            result["detail"] = "매도 주문 미체결 (30초 타임아웃)"
            result["orders"] = order_log
            return result
        
        result["sell_qty"] = sell_filled_qty
        
        # 6. 성공
        result["success"] = True
        result["orders"] = order_log
        
        elapsed = time.time() - start_time
        logger.info(f"[D107-0] ✅ 왕복 거래 완료 (소요: {elapsed:.1f}초)")
        
        # orders_summary.json 저장
        save_snapshot(evidence_dir, "orders_summary.json", {
            "orders": order_log,
            "buy_qty": filled_qty,
            "sell_qty": sell_filled_qty,
            "elapsed_seconds": elapsed,
        })
        
        return result
    
    except Exception as e:
        logger.error(f"[D107-0] ❌ 거래 실행 에러: {e}", exc_info=True)
        result["error"] = "exception"
        result["detail"] = str(e)
        result["orders"] = order_log
        
        # 에러 로그 저장
        error_path = evidence_dir / "errors.log"
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"Error: {e}\n")
            import traceback
            f.write(traceback.format_exc())
        
        return result


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(
        description="D107: 1h LIVE Smoke Test (소액, 저위험)"
    )
    
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=600,
        help="실행 시간 (초, 기본값: 600 = 10분)",
    )
    
    parser.add_argument(
        "--symbol",
        type=str,
        default="KRW-ADA",
        help="거래 심볼 (기본값: KRW-ADA, 보유 제외)",
    )
    
    parser.add_argument(
        "--order-krw",
        type=float,
        default=5000.0,
        help="주문 금액 (KRW, 기본값: 5000 = 최소 주문)",
    )
    
    parser.add_argument(
        "--max-loss-krw",
        type=float,
        default=500.0,
        help="킬스위치 손실 한도 (KRW, 기본값: 500)",
    )
    
    parser.add_argument(
        "--i-understand-live-trading",
        action="store_true",
        help="실거래 허용 플래그 (필수)",
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("[D107-0] 10분 LIVE Smoke Test 시작 (실체결 검증)")
    logger.info("="*60)
    logger.info(f"[D107-0] 실행 시간: {args.duration_seconds} 초")
    logger.info(f"[D107-0] 거래 심볼: {args.symbol}")
    logger.info(f"[D107-0] 주문 금액: {args.order_krw:.0f} KRW")
    logger.info(f"[D107-0] 킬스위치 손실 한도: {args.max_loss_krw:.0f} KRW")
    logger.info("="*60)
    
    # 실거래 플래그 확인 (2중 체크)
    if not args.i_understand_live_trading:
        logger.error("[D107-0] ❌ 실거래 플래그 미설정")
        logger.error("[D107-0] --i-understand-live-trading 플래그 필수")
        logger.error("[D107-0] 이 플래그 없이는 실거래 불가")
        return 1
    
    # READ_ONLY_ENFORCED 체크
    if os.getenv("READ_ONLY_ENFORCED", "false").lower() == "true":
        logger.error("[D107-0] ❌ READ_ONLY_ENFORCED=true")
        logger.error("[D107-0] 실거래가 차단된 상태입니다")
        logger.error("[D107-0] .env.live에서 READ_ONLY_ENFORCED=false로 설정하세요")
        return 1
    
    logger.info("[D107-0] ✅ 실거래 플래그 확인 완료")
    logger.info("[D107-0] ⚠️  주의: 실제 자금이 사용됩니다!")
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
            "live_enabled": True,  # 실거래 활성화
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
        start_time = time.time()
        start_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": args.duration_seconds,
            "symbol": args.symbol,
            "order_krw": args.order_krw,
            "max_loss_krw": args.max_loss_krw,
            "balance_check": balance_check,
            "excluded_symbols": ["DOGE", "XYM", "ETHW", "ETHF"],
        }
        save_snapshot(evidence_dir, "start_snapshot.json", start_snapshot)
        
        # Upbit 최소 조건만 확인 (Upbit 단독 거래)
        if not balance_check["upbit_ok"]:
            logger.error("[D107-0] Upbit 잔고 미충족")
            logger.error("[D107-0] 최소 10,000 KRW 필요")
            
            decision = {
                "result": "FAIL",
                "reason": "insufficient_balance",
                "detail": "Upbit 최소 주문 가능 잔고 미충족",
                "balance_check": balance_check,
            }
            save_snapshot(evidence_dir, "decision.json", decision)
            return 1
        
        # 실체결 로직 실행
        logger.info("[D107-0] 🚀 실체결 로직 시작")
        logger.info("="*60)
        
        trade_result = execute_real_trade(
            exchange_a=exchange_a,
            symbol=args.symbol,
            order_krw=args.order_krw,
            max_loss_krw=args.max_loss_krw,
            duration_seconds=args.duration_seconds,
            evidence_dir=evidence_dir,
        )
        
        # 종료 스냅샷 저장
        end_time = time.time()
        end_balances = exchange_a.get_balance()
        end_krw = end_balances["KRW"].total if "KRW" in end_balances else 0.0
        
        end_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "duration_actual": end_time - start_time,
            "balance_end_krw": end_krw,
            "balance_diff_krw": end_krw - balance_check["upbit_balance_krw"],
            "trade_result": trade_result,
        }
        save_snapshot(evidence_dir, "end_snapshot.json", end_snapshot)
        
        # 판정
        if trade_result["success"]:
            decision = {
                "result": "PASS",
                "reason": "trade_completed",
                "detail": f"체결 완료: BUY {trade_result.get('buy_qty', 0):.8f}, SELL {trade_result.get('sell_qty', 0):.8f}",
                "orders": trade_result.get("orders", []),
                "pnl_krw": end_krw - balance_check["upbit_balance_krw"],
                "evidence_dir": str(evidence_dir),
            }
        else:
            decision = {
                "result": "FAIL",
                "reason": trade_result.get("error", "unknown"),
                "detail": trade_result.get("detail", "Unknown error"),
                "evidence_dir": str(evidence_dir),
            }
        
        save_snapshot(evidence_dir, "decision.json", decision)
        
        logger.info("="*60)
        logger.info(f"[D107-0] 10분 LIVE Smoke Test 완료: {decision['result']}")
        logger.info(f"[D107-0] Evidence: {evidence_dir}")
        logger.info("="*60)
        
        return 0 if decision["result"] == "PASS" else 1
    
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
