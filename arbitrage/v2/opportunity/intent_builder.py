"""
D203-3: Opportunity → OrderIntent Bridge

얇은 어댑터: OpportunityCandidate를 2개 OrderIntent(매수/매도)로 변환.

Reuse-First:
- OrderIntent (arbitrage/v2/core/order_intent.py)
- OpportunityCandidate (arbitrage/v2/opportunity/detector.py)
- BreakEvenParams (arbitrage/v2/domain/break_even.py)
"""

from typing import List, Optional

from arbitrage.v2.core.order_intent import OrderIntent, OrderSide, OrderType
from arbitrage.v2.opportunity.detector import (
    OpportunityCandidate,
    OpportunityDirection,
    detect_candidates,
)
from arbitrage.v2.domain.break_even import BreakEvenParams


def build_candidate(
    symbol: str,
    exchange_a: str,
    exchange_b: str,
    price_a: float,
    price_b: float,
    params: BreakEvenParams,
) -> Optional[OpportunityCandidate]:
    """
    Build OpportunityCandidate from 2 exchange prices.
    
    Args:
        symbol: Trading pair (e.g., "BTC/KRW")
        exchange_a: Exchange A name (e.g., "upbit")
        exchange_b: Exchange B name (e.g., "binance")
        price_a: Exchange A price (normalized to same currency)
        price_b: Exchange B price (normalized to same currency)
        params: BreakEvenParams (fee_model, slippage_bps, buffer_bps)
        
    Returns:
        OpportunityCandidate or None (if invalid price)
        
    Reuse:
        - detect_candidates() from arbitrage/v2/opportunity/detector.py
    """
    return detect_candidates(
        symbol=symbol,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        price_a=price_a,
        price_b=price_b,
        params=params,
    )


def candidate_to_order_intents(
    candidate: OpportunityCandidate,
    base_qty: Optional[float] = None,
    quote_amount: Optional[float] = None,
    order_type: OrderType = OrderType.MARKET,
    limit_price_a: Optional[float] = None,
    limit_price_b: Optional[float] = None,
) -> List[OrderIntent]:
    """
    Convert OpportunityCandidate to 2 OrderIntents (BUY + SELL).
    
    Policy (SSOT):
        - unprofitable (edge_bps <= 0) → 빈 리스트 (주문 생성 금지)
        - direction == NONE → 빈 리스트
        - direction == BUY_A_SELL_B → [BUY(A), SELL(B)]
        - direction == BUY_B_SELL_A → [BUY(B), SELL(A)]
    
    Args:
        candidate: OpportunityCandidate (from build_candidate or detect_candidates)
        base_qty: Base asset quantity (for SELL orders)
        quote_amount: Quote asset amount (for BUY orders)
        order_type: MARKET or LIMIT (default: MARKET)
        limit_price_a: Limit price for exchange A (if LIMIT)
        limit_price_b: Limit price for exchange B (if LIMIT)
        
    Returns:
        List of OrderIntent (empty if unprofitable or NONE direction)
        
    Logic:
        1. Check profitable (edge_bps > 0)
        2. Check direction != NONE
        3. Create BUY intent (exchange with lower price)
        4. Create SELL intent (exchange with higher price)
        
    Note:
        - For MARKET orders: BUY requires quote_amount, SELL requires base_qty
        - For LIMIT orders: both require limit_price
    """
    # Policy: unprofitable → 빈 리스트
    if not candidate.profitable:
        return []
    
    # Policy: direction NONE → 빈 리스트
    if candidate.direction == OpportunityDirection.NONE:
        return []
    
    intents = []
    
    if candidate.direction == OpportunityDirection.BUY_A_SELL_B:
        # A가 저렴 → A에서 사고 B에서 팔기
        buy_exchange = candidate.exchange_a
        sell_exchange = candidate.exchange_b
        buy_price = candidate.price_a
        sell_price = candidate.price_b
    else:
        # direction == BUY_B_SELL_A
        # B가 저렴 → B에서 사고 A에서 팔기
        buy_exchange = candidate.exchange_b
        sell_exchange = candidate.exchange_a
        buy_price = candidate.price_b
        sell_price = candidate.price_a
    
    # 1. BUY Intent
    if order_type == OrderType.MARKET:
        buy_intent = OrderIntent(
            exchange=buy_exchange,
            symbol=candidate.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=quote_amount,
        )
    else:
        # LIMIT
        limit_price = limit_price_a if buy_exchange == candidate.exchange_a else limit_price_b
        buy_intent = OrderIntent(
            exchange=buy_exchange,
            symbol=candidate.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quote_amount=quote_amount,
            limit_price=limit_price or buy_price,  # fallback to market price
        )
    
    # 2. SELL Intent
    if order_type == OrderType.MARKET:
        sell_intent = OrderIntent(
            exchange=sell_exchange,
            symbol=candidate.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            base_qty=base_qty,
        )
    else:
        # LIMIT
        limit_price = limit_price_b if sell_exchange == candidate.exchange_b else limit_price_a
        sell_intent = OrderIntent(
            exchange=sell_exchange,
            symbol=candidate.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            base_qty=base_qty,
            limit_price=limit_price or sell_price,  # fallback to market price
        )
    
    intents.append(buy_intent)
    intents.append(sell_intent)
    
    return intents


def build_and_convert(
    symbol: str,
    exchange_a: str,
    exchange_b: str,
    price_a: float,
    price_b: float,
    params: BreakEvenParams,
    base_qty: Optional[float] = None,
    quote_amount: Optional[float] = None,
    order_type: OrderType = OrderType.MARKET,
) -> List[OrderIntent]:
    """
    Convenience function: build_candidate() + candidate_to_order_intents().
    
    Args:
        symbol: Trading pair
        exchange_a: Exchange A name
        exchange_b: Exchange B name
        price_a: Exchange A price
        price_b: Exchange B price
        params: BreakEvenParams
        base_qty: Base asset quantity (for SELL)
        quote_amount: Quote asset amount (for BUY)
        order_type: MARKET or LIMIT
        
    Returns:
        List of OrderIntent (empty if invalid/unprofitable)
    """
    candidate = build_candidate(
        symbol=symbol,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        price_a=price_a,
        price_b=price_b,
        params=params,
    )
    
    if not candidate:
        return []
    
    return candidate_to_order_intents(
        candidate=candidate,
        base_qty=base_qty,
        quote_amount=quote_amount,
        order_type=order_type,
    )
