#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Engine Module
=============
스프레드 계산 및 진입/청산 시그널 생성

책임:
- 업비트/바이낸스 Ticker를 입력으로 스프레드 계산
- FX 정규화 (USDT → KRW 변환)
- 수수료/슬리피지 반영한 순 스프레드(net spread) 계산
- 진입/청산 조건 판단 및 TradeSignal 생성
"""

import logging
from typing import Optional, Dict
from .models import Ticker, SpreadOpportunity, TradeSignal
from .normalizer import to_krw_price

logger = logging.getLogger("arbitrage.engine")

def compute_spread_opportunity(
    upbit_ticker: Ticker,
    binance_ticker: Ticker,
    config: Dict,
    symbol: str = None
) -> Optional[SpreadOpportunity]:
    """업비트/바이낸스 시세를 비교하여 스프레드 기회 계산 (FX 정규화 포함)
    
    Args:
        upbit_ticker: 업비트 시세 (KRW 기준)
        binance_ticker: 바이낸스 시세 (USDT 기준)
        config: 글로벌 설정 (fx 설정 포함)
        symbol: 심볼명 (다중 심볼 지원, 기본값: upbit_ticker.symbol)
    
    동작:
    - binance_price_krw = binance_price_usdt * fx_rate_krw
    - FX 변환은 normalizer.to_krw_price()에서 처리
    - 스프레드 = (upbit_price - binance_price_krw) / mid_price * 100
    - 순 스프레드 = 스프레드 - (수수료 + 슬리피지)
    """
    symbol = symbol or upbit_ticker.symbol
    
    # 심볼별 설정 병합 (심볼별 설정 > 글로벌 설정)
    symbol_config = _get_symbol_config(symbol, config)
    
    # FX 정규화: USDT → KRW 변환 (fx.get_usdkrw() 호출)
    binance_price_krw = to_krw_price(binance_ticker, config)
    
    # 스프레드 계산
    mid_price = (upbit_ticker.price + binance_price_krw) / 2 if binance_price_krw else upbit_ticker.price
    spread_pct = ((upbit_ticker.price - binance_price_krw) / mid_price) * 100 if mid_price else 0.0

    # 비용 계산 (수수료 + 슬리피지)
    fees = config.get("fees", {})
    slippage = config.get("slippage", {})
    total_cost = (
        fees.get("upbit_taker", 0.0)
        + fees.get("binance_taker", 0.0)
        + slippage.get("upbit", 0.0)
        + slippage.get("binance", 0.0)
    )
    net_spread_pct = spread_pct - total_cost

    # 진입 조건 판단
    threshold = symbol_config.get("spread", {}).get("min_net_spread_pct", 0.0)
    is_opportunity = net_spread_pct >= threshold

    logger.debug(
        "spread_calc symbol=%s upbit=%.0f binance_usdt=%.2f binance_krw=%.0f "
        "spread=%.2f%% net=%.2f%% threshold=%.2f%% opportunity=%s",
        symbol,
        upbit_ticker.price,
        binance_ticker.price,
        binance_price_krw,
        spread_pct,
        net_spread_pct,
        threshold,
        is_opportunity,
    )

    return SpreadOpportunity(
        symbol=symbol,
        upbit_price=upbit_ticker.price,
        binance_price=binance_ticker.price,
        binance_price_krw=binance_price_krw,
        spread_pct=spread_pct,
        net_spread_pct=net_spread_pct,
        timestamp=upbit_ticker.timestamp,
        is_opportunity=is_opportunity,
    )


def _get_symbol_config(symbol: str, config: Dict) -> Dict:
    """심볼별 설정 조회 (심볼별 설정 > 글로벌 설정)"""
    symbols_list = config.get("symbols", [])
    
    # 심볼별 설정이 있으면 반환
    for sym_cfg in symbols_list:
        if isinstance(sym_cfg, dict) and sym_cfg.get("name") == symbol:
            # 심볼별 설정과 글로벌 설정 병합
            merged = {
                "spread": {**config.get("spread", {}), **sym_cfg.get("spread", {})},
                "sizing": {**config.get("sizing", {}), **sym_cfg.get("sizing", {})},
            }
            return merged
    
    # 심볼별 설정이 없으면 글로벌 설정 반환
    return config


def generate_signal(
    opportunity: SpreadOpportunity,
    current_position: Optional[Dict],
    config: Dict
) -> TradeSignal:
    """
    스프레드 기회로부터 거래 시그널 생성
    
    Args:
        opportunity: SpreadOpportunity 객체
        current_position: 현재 포지션 정보 (None이면 포지션 없음)
        config: 설정 딕셔너리
    
    Returns:
        TradeSignal 객체 ("enter", "exit", "hold")
    
    TODO (PHASE A-3):
    ─────────────────────────────────────────────────────────────────────
    [구현 계획]
    
    1. **진입 시그널**:
       - 포지션이 없고, is_opportunity=True면 "enter"
       ```python
       if current_position is None and opportunity.is_opportunity:
           direction = "long_upbit_short_binance" if opportunity.spread_pct > 0 else "long_binance_short_upbit"
           return TradeSignal(
               symbol=opportunity.symbol,
               action="enter",
               direction=direction,
               spread_opportunity=opportunity,
               reason=f"Net spread {opportunity.net_spread_pct:.2f}% >= threshold",
               timestamp=opportunity.timestamp
           )
       ```
    
    2. **청산 시그널**:
       - 포지션이 있고, 스프레드가 특정 조건(예: 0% 이하)이면 "exit"
       ```python
       if current_position is not None and opportunity.net_spread_pct <= 0:
           return TradeSignal(
               symbol=opportunity.symbol,
               action="exit",
               spread_opportunity=opportunity,
               reason=f"Net spread {opportunity.net_spread_pct:.2f}% <= 0",
               timestamp=opportunity.timestamp
           )
       ```
    
    3. **홀드 시그널**:
       - 위 조건 모두 불만족 시 "hold"
       ```python
       return TradeSignal(
           symbol=opportunity.symbol,
           action="hold",
           spread_opportunity=opportunity,
           reason="No action required",
           timestamp=opportunity.timestamp
       )
       ```
    ─────────────────────────────────────────────────────────────────────
    """
    raise NotImplementedError("generate_signal 미구현 (PHASE A-3)")
