#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Risk Management Module
======================
리스크 관리 및 포지션 크기 결정

책임:
- 최대 노출 한도 체크
- 1회 주문 금액 제한
- 동시 포지션 수 제한
- 포지션 크기 계산
"""

from datetime import datetime
from typing import Dict, Optional, List, Tuple

from .models import Position, SpreadOpportunity


def check_max_positions(current_positions: List[Position], config: Dict) -> bool:
    """현재 열려있는 포지션 수가 최대치보다 작으면 True."""

    max_positions = int(config.get("sizing", {}).get("max_open_positions", 1))
    open_positions = [p for p in current_positions if p.status == "OPEN"]
    return len(open_positions) < max_positions


def compute_position_size_krw(config: Dict, price_krw: float) -> float:
    """max_notional_krw를 기준으로 베이스 자산(size)를 계산."""

    if price_krw <= 0:
        return 0.0

    max_notional = float(config.get("sizing", {}).get("max_notional_krw", 0))
    if max_notional <= 0:
        return 0.0

    return max_notional / price_krw


def can_open_new_position(
    config: Dict,
    current_positions: List[Position],
    opp: SpreadOpportunity,
    symbol: str = None,
) -> Tuple[bool, str]:
    """진입 조건 검증 (심볼별 + 포트폴리오 레벨)
    
    Args:
        config: 글로벌 설정
        current_positions: 현재 포지션 리스트
        opp: 스프레드 기회
        symbol: 심볼명 (기본값: opp.symbol)
    """
    symbol = symbol or opp.symbol

    if not opp.is_opportunity:
        return False, "OPPORTUNITY_FLAG"

    # 심볼별 설정 조회
    symbol_config = _get_symbol_config_for_risk(symbol, config)
    min_net = float(symbol_config.get("spread", {}).get("min_net_spread_pct", 0.0))
    if opp.net_spread_pct < min_net:
        return False, "NET_SPREAD_THRESHOLD"

    # 심볼별 최대 포지션 체크
    symbol_max = int(symbol_config.get("sizing", {}).get("max_open_positions", 1))
    symbol_open = [p for p in current_positions if p.status == "OPEN" and p.symbol == symbol]
    if len(symbol_open) >= symbol_max:
        return False, "MAX_POSITIONS_SYMBOL"

    # 포트폴리오 전체 최대 포지션 체크
    portfolio_max = int(config.get("sizing", {}).get("max_open_positions", 2))
    all_open = [p for p in current_positions if p.status == "OPEN"]
    if len(all_open) >= portfolio_max:
        return False, "MAX_POSITIONS_PORTFOLIO"

    return True, "ENTRY_OK"


def _get_symbol_config_for_risk(symbol: str, config: Dict) -> Dict:
    """리스크 모듈용 심볼별 설정 조회"""
    symbols_list = config.get("symbols", [])
    
    for sym_cfg in symbols_list:
        if isinstance(sym_cfg, dict) and sym_cfg.get("name") == symbol:
            merged = {
                "spread": {**config.get("spread", {}), **sym_cfg.get("spread", {})},
                "sizing": {**config.get("sizing", {}), **sym_cfg.get("sizing", {})},
            }
            return merged
    
    return config


def should_close_position(
    config: Dict,
    position: Position,
    opp: SpreadOpportunity,
    now: datetime,
) -> Tuple[bool, str]:
    """청산 조건 체크"""

    exit_threshold = float(config.get("spread", {}).get("exit_net_spread_pct", 0.0))
    holding_limit = float(config.get("spread", {}).get("max_holding_seconds", 0))

    holding_seconds = (now - position.timestamp_open).total_seconds()
    if opp.net_spread_pct <= exit_threshold:
        return True, "EXIT_SPREAD_MEAN_REVERTED"

    if holding_limit > 0 and holding_seconds >= holding_limit:
        return True, "EXIT_MAX_HOLDING_TIME"

    return False, "HOLD"


def validate_order(
    symbol: str,
    size: float,
    price: float,
    config: Dict
) -> tuple[bool, str]:
    """
    주문 유효성 검증
    
    Args:
        symbol: 심볼
        size: 주문 수량
        price: 주문 가격
        config: 설정 딕셔너리
    
    Returns:
        (is_valid, reason): (유효 여부, 사유)
    
    TODO (PHASE A-4):
    ─────────────────────────────────────────────────────────────────────
    [구현 계획]
    
    1. **최소 주문 금액 체크**:
       ```python
       notional = size * price
       if notional < 5000:  # 예: 최소 5,000 KRW
           return False, "주문 금액이 최소값보다 작음"
       ```
    
    2. **최대 주문 금액 체크**:
       ```python
       max_notional = config["sizing"]["max_notional_krw"]
       if notional > max_notional:
           return False, f"주문 금액이 최대값({max_notional} KRW) 초과"
       ```
    
    3. **수량 정밀도 체크** (향후):
       - 거래소별 수량 단위 체크
    
    4. **성공 케이스**:
       ```python
       return True, "OK"
       ```
    ─────────────────────────────────────────────────────────────────────
    """
    raise NotImplementedError("validate_order 미구현 (PHASE A-4)")


def calculate_pnl(
    position: Position,
    exit_upbit_price: float,
    exit_binance_price: float,
    usdkrw: float
) -> Tuple[float, float]:
    """포지션의 long_upbit_short_binance/반대 포지션 손익 계산"""

    upbit_leg = (exit_upbit_price - position.entry_upbit_price) * position.size
    if position.direction == "upbit_short_binance_long":
        upbit_leg = (position.entry_upbit_price - exit_upbit_price) * position.size

    binance_leg_usdt = (position.entry_binance_price - exit_binance_price) * position.size
    if position.direction == "upbit_short_binance_long":
        binance_leg_usdt = (exit_binance_price - position.entry_binance_price) * position.size

    binance_leg_krw = binance_leg_usdt * usdkrw
    total_pnl_krw = upbit_leg + binance_leg_krw
    notional = position.entry_upbit_price * position.size
    pnl_pct = (total_pnl_krw / notional * 100) if notional else 0.0

    return total_pnl_krw, pnl_pct
