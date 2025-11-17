#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalizer Module
=================
거래소별 시세를 공통 포맷으로 정규화

책임:
- 업비트/바이낸스의 원시 API 응답을 Ticker 모델로 변환
- 환율 적용 (USDT → KRW)
- 타임스탬프 정규화
"""

from typing import Dict
import time

from .models import Ticker
from . import fx


def normalize_upbit_ticker(raw_data: Dict, symbol: str) -> Ticker:
    """업비트 API 응답을 Ticker 모델로 변환"""

    timestamp = int(raw_data.get("trade_timestamp") or time.time() * 1000)
    volume_24h = float(raw_data.get("acc_trade_volume_24h", 0))

    return Ticker(
        exchange="upbit",
        symbol=symbol,
        price=float(raw_data.get("trade_price", 0)),
        timestamp=timestamp,
        volume_24h=volume_24h,
    )


def normalize_binance_ticker(raw_data: Dict, symbol: str) -> Ticker:
    """바이낸스 API 응답을 Ticker 모델로 변환"""

    timestamp = int(time.time() * 1000)
    volume_24h = float(raw_data.get("volume", 0))

    return Ticker(
        exchange="binance_futures",
        symbol=symbol,
        price=float(raw_data.get("price") or raw_data.get("lastPrice", 0)),
        timestamp=timestamp,
        volume_24h=volume_24h,
    )


def apply_exchange_rate(price_usdt: float, usdkrw: float) -> float:
    """USDT 가격을 KRW로 환산"""

    return price_usdt * usdkrw


def to_krw_price(ticker: Ticker, config: Dict) -> float:
    """Ticker를 KRW 기준 가격으로 환산
    
    Args:
        ticker: 원본 Ticker 객체
        config: 글로벌 설정 (fx 모듈에서 환율 조회)
    
    Returns:
        float: KRW 기준 가격
    
    동작:
    - binance_futures: fx.get_usdkrw()로 환율 조회 후 환산
    - 그 외: 원본 가격 반환 (이미 KRW 기준)
    """
    if ticker.exchange == "binance_futures":
        usdkrw = fx.get_usdkrw(config)
        return apply_exchange_rate(ticker.price, usdkrw)

    return ticker.price
