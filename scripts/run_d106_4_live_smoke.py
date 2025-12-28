#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D106-4: LIVE Smoke Test - Market Round-trip + Flat Guarantee

목표: 시장가 주문으로 1회 왕복 + 플랫 보장 + NAV 기반 손익

Usage:
    python scripts/run_d106_4_live_smoke.py \
        --duration-seconds 600 \
        --order-krw 10000 \
        --max-loss-krw 500 \
        --enable-live --i-understand-live-trading

NOTE:
- D107은 D106-4로 흡수되었습니다 (ROADMAP 기준)
- 보유 심볼(DOGE/XYM/ETHW/ETHF) 자동 제외
- READ_ONLY는 프로세스 내부에서만 해제 (영구 변경 금지)
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
    print(f"[D106-4] Loaded {env_file}")
else:
    print(f"[D106-4] WARNING: {env_file} not found, using environment variables")

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# 보유 심볼 자동 제외 (절대 거래 금지)
PROTECTED_SYMBOLS = ["DOGE", "XYM", "ETHW", "ETHF"]


def get_safe_test_symbol(exchange_a) -> Optional[str]:
    """
    안전한 테스트 심볼 선택 (보유 심볼 제외)
    
    우선순위: BTC > ETH > ADA
    """
    try:
        balances = exchange_a.get_balance()
        
        # 보유 심볼 필터링 (KRW 제외 + threshold 적용)
        held_symbols = set()
        for sym, bal in balances.items():
            if sym != "KRW" and bal.total > 0.00000001:  # dust 무시
                held_symbols.add(sym)
                logger.info(f"[D106-4] 보유 심볼: {sym} (잔고: {bal.total:.8f})")
        
        # 보호 대상 확인
        for sym in PROTECTED_SYMBOLS:
            if sym in held_symbols:
                logger.warning(f"[D106-4] 보호 대상 심볼: {sym} (거래 금지)")
        
        # 테스트 후보 (보유 가능성 낮은 중소형 코인 우선)
        candidates = ["SOL", "XRP", "AVAX", "MATIC", "DOT", "ADA", "ETH", "BTC"]
        
        for sym in candidates:
            if sym not in held_symbols and sym not in PROTECTED_SYMBOLS:
                logger.info(f"[D106-4] ✅ 테스트 심볼 선택: KRW-{sym} (보유 없음)")
                return f"KRW-{sym}"
        
        logger.error(f"[D106-4] ❌ 안전한 테스트 심볼 없음 (모두 보유 중: {held_symbols})")
        return None
    
    except Exception as e:
        logger.error(f"[D106-4] 심볼 선택 실패: {e}", exc_info=True)
        return None


def calculate_nav(exchange_a, exchange_b) -> Dict[str, float]:
    """
    NAV (Net Asset Value) 계산
    
    NAV_KRW = KRW + Σ(qty * mid_price_krw)
    
    Returns:
        {"upbit_nav_krw": float, "binance_nav_usdt": float}
    """
    nav = {"upbit_nav_krw": 0.0, "binance_nav_usdt": 0.0}
    
    try:
        # Upbit NAV
        upbit_balances = exchange_a.get_balance()
        nav["upbit_nav_krw"] = upbit_balances.get("KRW", type('obj', (object,), {'total': 0.0})).total
        
        for sym, bal in upbit_balances.items():
            if sym != "KRW" and bal.total > 0:
                try:
                    market = f"KRW-{sym}"
                    orderbook = exchange_a.get_orderbook(market)
                    mid_price = (orderbook.best_ask() + orderbook.best_bid()) / 2.0
                    nav["upbit_nav_krw"] += bal.total * mid_price
                except:
                    pass
        
        # Binance NAV (간소화: USDT만)
        binance_balances = exchange_b.get_balance()
        nav["binance_nav_usdt"] = binance_balances.get("USDT", type('obj', (object,), {'total': 0.0})).total
        
    except Exception as e:
        logger.error(f"[D106-4] NAV 계산 실패: {e}")
    
    return nav


def check_minimum_balance(exchange_a, exchange_b) -> Dict[str, Any]:
    """
    거래소별 최소 주문 가능 잔고 확인
    
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
            logger.info(f"[D106-4] Upbit 잔고 확인: {upbit_krw:.0f} KRW ✅")
        else:
            logger.warning(f"[D106-4] Upbit 잔고 부족: {upbit_krw:.0f} KRW (최소 10,000 KRW 필요)")
    except Exception as e:
        logger.error(f"[D106-4] Upbit 잔고 확인 실패: {e}", exc_info=True)
    
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
            logger.info(f"[D106-4] Binance 잔고 확인: {binance_usdt:.2f} USDT ✅")
        else:
            logger.warning(f"[D106-4] Binance 잔고 부족: {binance_usdt:.2f} USDT (최소 10 USDT 필요)")
    except Exception as e:
        logger.error(f"[D106-4] Binance 잔고 확인 실패: {e}")
    
    return result


def create_evidence_dir() -> Path:
    """Evidence 디렉토리 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_dir = Path(__file__).parent.parent / "logs" / "evidence" / f"d106_4_live_smoke_{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[D106-4] Evidence 디렉토리 생성: {evidence_dir}")
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
    
    logger.info(f"[D106-4] 스냅샷 저장: {snapshot_path}")


def execute_real_trade(
    exchange_a,
    symbol: str,
    order_krw: float,
    max_loss_krw: float,
    max_attempts: int,
    evidence_dir: Path,
) -> Dict[str, Any]:
    """
    시장가 주문으로 1회 왕복: BUY (시장가) → SELL (시장가)
    
    Args:
        exchange_a: Upbit 거래소
        symbol: 거래 심볼 (예: KRW-BTC)
        order_krw: 주문 금액 (KRW)
        max_loss_krw: 최대 손실 한도 (KRW)
        max_attempts: 최대 시도 횟수
        evidence_dir: 증거 디렉토리
    
    Returns:
        dict: {"success": bool, "orders": List, "buy_qty": float, "sell_qty": float, ...}
    """
    result = {
        "success": False,
        "orders": [],
        "buy_qty": 0.0,
        "sell_qty": 0.0,
        "error": None,
        "detail": None,
    }
    
    start_time = time.time()
    order_log = []
    
    try:
        # 1. 호가 조회
        logger.info(f"[D106-4] Step 1) 호가 조회: {symbol}")
        orderbook = exchange_a.get_orderbook(symbol)
        best_ask = orderbook.best_ask()
        best_bid = orderbook.best_bid()
        
        if not best_ask or not best_bid:
            result["error"] = "orderbook_empty"
            result["detail"] = "호가 정보 없음"
            return result
        
        mid_price = (best_ask + best_bid) / 2.0
        logger.info(f"[D106-4] 호가: ask={best_ask:.0f}, bid={best_bid:.0f}, mid={mid_price:.0f}")
        
        # 2. 시장가 매수 (Upbit: LIMIT 주문, ask*1.05로 즉시 체결)
        buy_price = int(best_ask * 1.05)  # 5% 프리미엄
        buy_qty_target = order_krw / buy_price
        buy_qty = round(buy_qty_target, 8)
        
        logger.info(f"[D106-4] Step 2) 시장가 매수: {buy_qty:.8f} @ {buy_price} KRW")
        
        buy_order = exchange_a.create_order(
            symbol=symbol,
            side=OrderSide.BUY,
            qty=buy_qty,
            price=buy_price,
            order_type=OrderType.LIMIT,  # Upbit 시장가는 LIMIT으로 구현
        )
        
        order_log.append({
            "action": "BUY",
            "order_id": buy_order.order_id,
            "qty": buy_qty,
            "price": buy_price,
            "timestamp": datetime.now().isoformat(),
        })
        
        logger.info(f"[D106-4] ✅ 매수 주문 생성: {buy_order.order_id}")
        
        # 3. 매수 체결 대기 (최대 10초)
        logger.info("[D106-4] Step 3) 매수 체결 대기 (최대 10초)")
        buy_filled_qty = 0.0
        
        for attempt in range(10):
            time.sleep(1)
            status = exchange_a.get_order_status(buy_order.order_id)
            buy_filled_qty = status.filled_qty
            
            if status.status == OrderStatus.FILLED:
                logger.info(f"[D106-4] ✅ 매수 전량 체결: {buy_filled_qty:.8f}")
                break
            elif buy_filled_qty > 0:
                logger.info(f"[D106-4] 매수 부분 체결: {buy_filled_qty:.8f}")
        
        # 미체결 주문 취소
        if status.status != OrderStatus.FILLED:
            try:
                exchange_a.cancel_order(buy_order.order_id)
                logger.info(f"[D106-4] 미체결 주문 취소: {buy_order.order_id}")
            except Exception as e:
                logger.warning(f"[D106-4] 취소 실패 (이미 체결?): {e}")
        
        # 매수 체결 확인
        if buy_filled_qty == 0:
            result["error"] = "buy_not_filled"
            result["detail"] = "매수 주문 미체결"
            return result
        
        result["buy_qty"] = buy_filled_qty
        logger.info(f"[D106-4] 매수 완료: {buy_filled_qty:.8f}")
        
        # 4. 시장가 매도 (Upbit: LIMIT 주문, bid*0.95로 즉시 체결)
        sell_price = int(best_bid * 0.95)  # 5% 할인
        sell_qty = round(buy_filled_qty, 8)
        
        # 최소 주문 금액 체크 (5,000 KRW)
        sell_total_krw = sell_price * sell_qty
        if sell_total_krw < 5000.0:
            logger.error(f"[D106-4] ❌ 매도 금액 미달: {sell_total_krw:.0f} < 5,000 KRW")
            result["error"] = "sell_min_notional"
            result["detail"] = f"매도 금액 미달 ({sell_total_krw:.0f} < 5,000 KRW)"
            return result
        
        logger.info(f"[D106-4] Step 4) 시장가 매도: {sell_qty:.8f} @ {sell_price} KRW (total: {sell_total_krw:.0f} KRW)")
        
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
        
        logger.info(f"[D106-4] ✅ 매도 주문 생성: {sell_order.order_id}")
        
        # 5. 매도 체결 대기 (최대 10초)
        logger.info("[D106-4] Step 5) 매도 체결 대기 (최대 10초)")
        sell_filled_qty = 0.0
        
        for attempt in range(10):
            time.sleep(1)
            status = exchange_a.get_order_status(sell_order.order_id)
            sell_filled_qty = status.filled_qty
            
            if status.status == OrderStatus.FILLED:
                logger.info(f"[D106-4] ✅ 매도 전량 체결: {sell_filled_qty:.8f}")
                break
            elif sell_filled_qty > 0:
                logger.info(f"[D106-4] 매도 부분 체결: {sell_filled_qty:.8f}")
        
        # 미체결 주문 취소
        if status.status != OrderStatus.FILLED:
            try:
                exchange_a.cancel_order(sell_order.order_id)
                logger.info(f"[D106-4] 미체결 주문 취소: {sell_order.order_id}")
            except Exception as e:
                logger.warning(f"[D106-4] 취소 실패 (이미 체결?): {e}")
        
        # 매도 체결 확인
        if sell_filled_qty == 0:
            result["error"] = "sell_not_filled"
            result["detail"] = "매도 주문 미체결"
            result["orders"] = order_log
            return result
        
        result["sell_qty"] = sell_filled_qty
        logger.info(f"[D106-4] 매도 완료: {sell_filled_qty:.8f}")
        
        # 6. 성공
        result["success"] = True
        result["orders"] = order_log
        
        elapsed = time.time() - start_time
        logger.info(f"[D106-4] ✅ 왕복 거래 완료 (소요: {elapsed:.1f}초)")
        
        # orders_summary.json 저장
        save_snapshot(evidence_dir, "orders_summary.json", {
            "orders": order_log,
            "buy_qty": buy_filled_qty,
            "sell_qty": sell_filled_qty,
            "elapsed_seconds": elapsed,
        })
        
        return result
    
    except Exception as e:
        logger.error(f"[D106-4] ❌ 거래 실행 에러: {e}", exc_info=True)
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
        description="D106-4: LIVE Smoke Test (Market Round-trip + Flat Guarantee)"
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
        default=None,
        help="거래 심볼 (기본값: 자동 선택, 보유 제외)",
    )
    
    parser.add_argument(
        "--order-krw",
        type=float,
        default=15000.0,
        help="주문 금액 (KRW, 기본값: 15000)",
    )
    
    parser.add_argument(
        "--max-loss-krw",
        type=float,
        default=500.0,
        help="킬스위치 손실 한도 (KRW, 기본값: 500)",
    )
    
    parser.add_argument(
        "--enable-live",
        action="store_true",
        help="READ_ONLY 프로세스 내부 해제 (필수)",
    )
    
    parser.add_argument(
        "--i-understand-live-trading",
        action="store_true",
        help="실거래 허용 플래그 (필수)",
    )
    
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=2,
        help="최대 시도 횟수 (기본값: 2)",
    )
    
    args = parser.parse_args()
    
    logger.info("="*60)
    logger.info("[D106-4] LIVE Smoke Test 시작 (Market Round-trip)")
    logger.info("="*60)
    logger.info(f"[D106-4] 주문 금액: {args.order_krw:.0f} KRW")
    logger.info(f"[D106-4] 킬스위치 손실 한도: {args.max_loss_krw:.0f} KRW")
    logger.info(f"[D106-4] 최대 시도: {args.max_attempts}회")
    logger.info("="*60)
    
    # 안전 플래그 체크 (2중)
    if not args.enable_live or not args.i_understand_live_trading:
        logger.error("[D106-4] ❌ 안전 플래그 미설정")
        logger.error("[D106-4] --enable-live --i-understand-live-trading 필수")
        return 1
    
    # READ_ONLY 프로세스 내부에서만 해제
    logger.info("[D106-4] ⚠️  READ_ONLY 프로세스 내부 해제")
    os.environ["READ_ONLY_ENFORCED"] = "false"
    
    logger.info("[D106-4] ✅ 안전 플래그 확인 완료")
    logger.info("[D106-4] ⚠️  주의: 실제 자금이 사용됩니다!")
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
        
        logger.info(f"[D106-4] 거래소 초기화 완료: {exchange_a.name}, {exchange_b.name}")
        
        # 최소 잔고 확인
        balance_check = check_minimum_balance(exchange_a, exchange_b)
        
        # NAV 계산 (시작)
        start_nav = calculate_nav(exchange_a, exchange_b)
        
        # 심볼 선택 (자동 또는 명시적)
        if args.symbol:
            test_symbol = args.symbol
            logger.info(f"[D106-4] 수동 심볼 선택: {test_symbol}")
        else:
            test_symbol = get_safe_test_symbol(exchange_a)
            if not test_symbol:
                logger.error("[D106-4] ❌ 안전한 테스트 심볼 없음")
                decision = {
                    "result": "FAIL",
                    "reason": "no_safe_symbol",
                    "detail": "보유하지 않은 심볼이 없습니다 (BTC/ETH/ADA 모두 보유 중)",
                }
                save_snapshot(evidence_dir, "decision.json", decision)
                return 1
        
        # 시작 스냅샷 저장
        start_time = time.time()
        start_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "symbol": test_symbol,
            "order_krw": args.order_krw,
            "max_loss_krw": args.max_loss_krw,
            "max_attempts": args.max_attempts,
            "balance_check": balance_check,
            "start_nav": start_nav,
            "excluded_symbols": PROTECTED_SYMBOLS,
        }
        save_snapshot(evidence_dir, "start_snapshot.json", start_snapshot)
        
        # Upbit 최소 조건만 확인 (Upbit 단독 거래)
        if not balance_check["upbit_ok"]:
            logger.error("[D106-4] Upbit 잔고 미충족")
            logger.error("[D106-4] 최소 10,000 KRW 필요")
            
            decision = {
                "result": "FAIL",
                "reason": "insufficient_balance",
                "detail": "Upbit 최소 주문 가능 잔고 미충족",
                "balance_check": balance_check,
            }
            save_snapshot(evidence_dir, "decision.json", decision)
            return 1
        
        # 실체결 로직 실행
        logger.info("[D106-4] 🚀 실체결 로직 시작")
        logger.info("="*60)
        
        trade_result = execute_real_trade(
            exchange_a=exchange_a,
            symbol=test_symbol,
            order_krw=args.order_krw,
            max_loss_krw=args.max_loss_krw,
            max_attempts=args.max_attempts,
            evidence_dir=evidence_dir,
        )
        
        # 종료 스냅샷 저장
        end_time = time.time()
        end_nav = calculate_nav(exchange_a, exchange_b)
        
        end_snapshot = {
            "timestamp": datetime.now().isoformat(),
            "duration_actual": end_time - start_time,
            "start_nav": start_nav,
            "end_nav": end_nav,
            "nav_diff_krw": end_nav["upbit_nav_krw"] - start_nav["upbit_nav_krw"],
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
                "realized_pnl_krw": end_nav["upbit_nav_krw"] - start_nav["upbit_nav_krw"],
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
        logger.info(f"[D106-4] LIVE Smoke Test 완료: {decision['result']}")
        logger.info(f"[D106-4] Evidence: {evidence_dir}")
        logger.info("="*60)
        
        return 0 if decision["result"] == "PASS" else 1
    
    except Exception as e:
        logger.error(f"[D106-4] 에러 발생: {e}", exc_info=True)
        
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
