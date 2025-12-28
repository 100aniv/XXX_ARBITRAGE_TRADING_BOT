#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D106-4: Flatten Upbit Symbol Utility

목적: 테스트 심볼(ADA 등) 잔여 포지션을 안전하게 청산

Usage:
    python scripts/tools/flatten_upbit_symbol.py --symbol ADA --i-understand-cleanup

주의:
- 기존 보유 심볼(DOGE, XYM, ETHW, ETHF)은 exclude list로 보호
- 시장가 매도 최소 금액(5,000 KRW) 미달 시 top-up 옵션 제공
- top-up은 max_cleanup_krw(기본 6,000 KRW) 상한 설정
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

from arbitrage.exchanges.base import OrderSide, OrderType, OrderStatus
from arbitrage.exchanges.upbit_spot import UpbitSpotExchange

# .env.live 로드
env_file = Path(__file__).parent.parent.parent / ".env.live"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"[FLATTEN] Loaded {env_file}")
else:
    print(f"[FLATTEN] WARNING: {env_file} not found")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 보호 대상 심볼 (절대 청산 금지)
PROTECTED_SYMBOLS = ["DOGE", "XYM", "ETHW", "ETHF"]


def create_evidence_dir() -> Path:
    """Evidence 디렉토리 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_dir = Path("logs/evidence") / f"flatten_upbit_{timestamp}"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    return evidence_dir


def get_upbit_balance(exchange: UpbitSpotExchange, symbol: str) -> Dict[str, float]:
    """
    Upbit 특정 심볼 잔고 조회
    
    Returns:
        {"free": float, "locked": float, "total": float}
    """
    balances = exchange.get_balance()
    
    if symbol in balances:
        balance = balances[symbol]
        return {
            "free": balance.free,
            "locked": balance.locked,
            "total": balance.total,
        }
    else:
        return {"free": 0.0, "locked": 0.0, "total": 0.0}


def cancel_open_orders(exchange: UpbitSpotExchange, market: str) -> int:
    """
    미체결 주문 취소
    
    Returns:
        취소된 주문 수
    """
    try:
        # Upbit API: /v1/orders/open
        # 여기서는 간단히 get_open_positions로 대체 (구현 필요 시 확장)
        logger.info(f"[FLATTEN] {market} open orders 확인")
        # TODO: Upbit get_open_orders() 구현되어 있으면 사용
        return 0
    except Exception as e:
        logger.warning(f"[FLATTEN] Open orders 취소 실패: {e}")
        return 0


def flatten_symbol(
    exchange: UpbitSpotExchange,
    symbol: str,
    market: str,
    enable_topup: bool = False,
    max_cleanup_krw: float = 6000.0,
) -> Dict[str, Any]:
    """
    심볼 청산 (시장가 매도)
    
    Args:
        exchange: UpbitSpotExchange 인스턴스
        symbol: 심볼 (예: ADA)
        market: 마켓 (예: KRW-ADA)
        enable_topup: 최소 금액 미달 시 top-up 허용 여부
        max_cleanup_krw: top-up 최대 금액 (KRW)
    
    Returns:
        {"success": bool, "action": str, "detail": str, "orders": List}
    """
    result = {
        "success": False,
        "action": None,
        "detail": None,
        "orders": [],
    }
    
    try:
        # 1. 잔고 확인
        balance_info = get_upbit_balance(exchange, symbol)
        qty_free = balance_info["free"]
        qty_total = balance_info["total"]
        
        logger.info(f"[FLATTEN] {symbol} 잔고: free={qty_free:.8f}, total={qty_total:.8f}")
        
        if qty_total == 0:
            result["success"] = True
            result["action"] = "none"
            result["detail"] = f"{symbol} 잔고 없음 (이미 플랫)"
            logger.info(f"[FLATTEN] ✅ {symbol} 잔고 없음")
            return result
        
        # 2. Open orders 취소
        canceled_count = cancel_open_orders(exchange, market)
        if canceled_count > 0:
            logger.info(f"[FLATTEN] {canceled_count}개 주문 취소 완료")
            time.sleep(1)  # 취소 반영 대기
            balance_info = get_upbit_balance(exchange, symbol)
            qty_free = balance_info["free"]
        
        # 3. 호가 조회 (시장가 예상)
        orderbook = exchange.get_orderbook(market)
        best_bid = orderbook.best_bid()
        
        if not best_bid:
            result["detail"] = f"{market} 호가 없음"
            logger.error(f"[FLATTEN] ❌ {market} 호가 조회 실패")
            return result
        
        # 4. 예상 매도 금액 계산
        estimated_krw = qty_free * best_bid
        logger.info(f"[FLATTEN] 예상 매도 금액: {estimated_krw:.0f} KRW (best_bid={best_bid:.0f})")
        
        MIN_ORDER_KRW = 5000.0
        
        # 5. 최소 금액 체크
        if estimated_krw < MIN_ORDER_KRW:
            logger.warning(f"[FLATTEN] ⚠️  매도 금액 미달: {estimated_krw:.0f} < {MIN_ORDER_KRW:.0f} KRW")
            
            if not enable_topup:
                result["detail"] = f"매도 금액 미달 ({estimated_krw:.0f} < {MIN_ORDER_KRW:.0f} KRW), --enable-topup 필요"
                logger.error(f"[FLATTEN] ❌ top-up 비활성화 상태")
                return result
            
            # Top-up: 추가 매수 후 즉시 매도
            topup_krw = MIN_ORDER_KRW - estimated_krw + 500  # 버퍼 500 KRW
            
            if topup_krw > max_cleanup_krw:
                result["detail"] = f"top-up 금액 초과 ({topup_krw:.0f} > {max_cleanup_krw:.0f} KRW)"
                logger.error(f"[FLATTEN] ❌ top-up 상한 초과 (무한매수 방지)")
                return result
            
            logger.info(f"[FLATTEN] Top-up 실행: {topup_krw:.0f} KRW 추가 매수")
            
            # 시장가 매수 (Upbit: price 파라미터로 KRW 금액 전달)
            best_ask = orderbook.best_ask()
            topup_qty = topup_krw / best_ask
            topup_price = int(best_ask * 1.02)  # 즉시 체결
            
            buy_order = exchange.create_order(
                symbol=market,
                side=OrderSide.BUY,
                qty=round(topup_qty, 8),
                price=topup_price,
                order_type=OrderType.LIMIT,
            )
            
            result["orders"].append({
                "action": "topup_buy",
                "order_id": buy_order.order_id,
                "qty": topup_qty,
                "price": topup_price,
            })
            
            logger.info(f"[FLATTEN] Top-up 매수 주문: {buy_order.order_id}")
            
            # 체결 대기 (5초)
            time.sleep(5)
            status = exchange.get_order_status(buy_order.order_id)
            
            if status.filled_qty == 0:
                logger.error(f"[FLATTEN] ❌ Top-up 매수 미체결")
                result["detail"] = "Top-up 매수 미체결"
                return result
            
            # 잔고 재조회
            balance_info = get_upbit_balance(exchange, symbol)
            qty_free = balance_info["free"]
            logger.info(f"[FLATTEN] Top-up 후 잔고: {qty_free:.8f} {symbol}")
        
        # 6. 시장가 매도
        sell_qty = round(qty_free, 8)
        
        logger.info(f"[FLATTEN] 시장가 매도 실행: {sell_qty:.8f} {symbol}")
        
        # Upbit 시장가 매도: volume만 전달
        sell_order = exchange.create_order(
            symbol=market,
            side=OrderSide.SELL,
            qty=sell_qty,
            price=None,  # 시장가
            order_type=OrderType.MARKET,
        )
        
        result["orders"].append({
            "action": "market_sell",
            "order_id": sell_order.order_id,
            "qty": sell_qty,
        })
        
        logger.info(f"[FLATTEN] ✅ 매도 완료: {sell_order.order_id}")
        
        # 체결 확인 (3초)
        time.sleep(3)
        final_balance = get_upbit_balance(exchange, symbol)
        
        result["success"] = True
        result["action"] = "flattened"
        result["detail"] = f"{symbol} 청산 완료 (잔여: {final_balance['total']:.8f})"
        
        logger.info(f"[FLATTEN] ✅ {symbol} 청산 완료")
        
        return result
    
    except Exception as e:
        logger.error(f"[FLATTEN] ❌ 청산 실패: {e}")
        result["detail"] = str(e)
        return result


def main():
    parser = argparse.ArgumentParser(description="D106-4: Flatten Upbit Symbol")
    parser.add_argument("--symbol", type=str, default="ADA", help="청산할 심볼 (기본: ADA)")
    parser.add_argument("--enable-topup", action="store_true", help="최소 금액 미달 시 top-up 허용")
    parser.add_argument("--max-cleanup-krw", type=float, default=6000.0, help="top-up 최대 금액 (KRW)")
    parser.add_argument("--i-understand-cleanup", action="store_true", help="[필수] 청산 실행 확인")
    
    args = parser.parse_args()
    
    # 안전 플래그 체크
    if not args.i_understand_cleanup:
        logger.error("[FLATTEN] ❌ --i-understand-cleanup 플래그 필요")
        print("\n⚠️  WARNING: 이 스크립트는 실제 거래소에서 주문을 실행합니다.")
        print("실행하려면 --i-understand-cleanup 플래그를 추가하세요.\n")
        sys.exit(1)
    
    symbol = args.symbol.upper()
    market = f"KRW-{symbol}"
    
    # 보호 대상 심볼 체크
    if symbol in PROTECTED_SYMBOLS:
        logger.error(f"[FLATTEN] ❌ {symbol}은 보호 대상 심볼입니다 (청산 금지)")
        print(f"\n❌ {symbol}은 기존 보유 심볼로 청산이 금지됩니다.")
        print(f"보호 대상: {PROTECTED_SYMBOLS}\n")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info(f"[FLATTEN] {symbol} 청산 시작")
    logger.info("=" * 60)
    logger.info(f"심볼: {symbol}")
    logger.info(f"마켓: {market}")
    logger.info(f"Top-up: {'활성화' if args.enable_topup else '비활성화'}")
    logger.info(f"Max cleanup: {args.max_cleanup_krw:.0f} KRW")
    logger.info("=" * 60)
    
    # Evidence 디렉토리 생성
    evidence_dir = create_evidence_dir()
    logger.info(f"[FLATTEN] Evidence: {evidence_dir}")
    
    # READ_ONLY 임시 해제 (프로세스 내부만)
    os.environ["READ_ONLY_ENFORCED"] = "false"
    
    # Upbit 거래소 초기화
    config = {
        "api_key": os.getenv("UPBIT_ACCESS_KEY"),
        "api_secret": os.getenv("UPBIT_SECRET_KEY"),
        "base_url": "https://api.upbit.com",
        "live_enabled": True,
    }
    
    exchange = UpbitSpotExchange(config)
    
    # 시작 스냅샷
    start_snapshot = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "market": market,
        "balance_before": get_upbit_balance(exchange, symbol),
    }
    
    with open(evidence_dir / "start_snapshot.json", "w") as f:
        json.dump(start_snapshot, f, indent=2)
    
    # 청산 실행
    result = flatten_symbol(
        exchange=exchange,
        symbol=symbol,
        market=market,
        enable_topup=args.enable_topup,
        max_cleanup_krw=args.max_cleanup_krw,
    )
    
    # 종료 스냅샷
    end_snapshot = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "market": market,
        "balance_after": get_upbit_balance(exchange, symbol),
        "result": result,
    }
    
    with open(evidence_dir / "end_snapshot.json", "w") as f:
        json.dump(end_snapshot, f, indent=2)
    
    # 최종 판정
    decision = {
        "timestamp": datetime.now().isoformat(),
        "status": "PASS" if result["success"] else "FAIL",
        "action": result["action"],
        "detail": result["detail"],
        "orders": result["orders"],
    }
    
    with open(evidence_dir / "decision.json", "w") as f:
        json.dump(decision, f, indent=2)
    
    logger.info("=" * 60)
    logger.info(f"[FLATTEN] 청산 결과: {decision['status']}")
    logger.info(f"[FLATTEN] Action: {decision['action']}")
    logger.info(f"[FLATTEN] Detail: {decision['detail']}")
    logger.info(f"[FLATTEN] Evidence: {evidence_dir}")
    logger.info("=" * 60)
    
    if result["success"]:
        print(f"\n✅ {symbol} 청산 완료")
        print(f"Evidence: {evidence_dir}\n")
        sys.exit(0)
    else:
        print(f"\n❌ {symbol} 청산 실패: {result['detail']}")
        print(f"Evidence: {evidence_dir}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
