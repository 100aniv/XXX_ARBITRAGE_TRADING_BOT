#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collectors Module
=================
거래소별 시세 데이터 수집 모듈

**중요**: 이 모듈은 기존 앙상블 트레이딩 봇 프로젝트의 Collector/Exchange 코드를 
재사용/이식하는 것을 목표로 합니다. HTTP 요청/서명 로직을 새로 작성하지 않고,
이미 검증된 코드를 thin wrapper로 감싸는 형태입니다.

책임:
- 업비트 현물 시세 조회
- 바이낸스 선물 시세 조회
- 원시 API 응답을 Ticker 모델로 변환
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any

import httpx

from .models import Ticker

logger = logging.getLogger(__name__)


# ============================================================================
# 업비트 Collector
# ============================================================================

def get_upbit_ticker(symbol: str, config: Dict[str, Any]) -> Optional[Ticker]:
    """
    업비트에서 단일 심볼의 현재가를 조회합니다.
    
    Args:
        symbol: 심볼 코드 (예: "BTC")
        config: 설정 딕셔너리 (base.yml 로딩 결과)
    
    Returns:
        Ticker 객체 (조회 실패 시 None)
    
    Examples:
        >>> ticker = get_upbit_ticker("BTC", config)
        >>> print(ticker.price)  # 50000000.0 (KRW)
    
    TODO (PHASE A-2에서 구현):
    ─────────────────────────────────────────────────────────────────────
    이 함수는 기존 앙상블 트레이딩 봇 프로젝트의 업비트 관련 코드를 이식하여 완성합니다.
    
    [이식 계획]
    
    1. **기존 프로젝트에서 가져올 코드**:
       - 업비트 API 클라이언트 (UpbitExchange 또는 UpbitCollector 클래스)
       - 또는 REST API 호출 함수 (requests 기반)
    
    2. **필요한 API 엔드포인트**:
       - GET /v1/ticker
       - 파라미터: markets=KRW-{symbol} (예: KRW-BTC)
       - 인증: 공개 API이므로 서명 불필요
    
    3. **응답 파싱 예시**:
       ```python
       # 기존 프로젝트의 코드를 붙여 넣는 위치
       # 예시:
       import requests
       
       base_url = config["exchanges"]["upbit"]["base_url"]
       market = f"KRW-{symbol}"
       url = f"{base_url}/v1/ticker"
       params = {"markets": market}
       
       response = requests.get(url, params=params)
       data = response.json()[0]
       
       return Ticker(
           exchange="upbit",
           symbol=symbol,
           price=float(data["trade_price"]),
           timestamp=int(time.time() * 1000),
           volume_24h=float(data.get("acc_trade_volume_24h", 0))
       )
       ```
    
    4. **에러 처리**:
       - API 호출 실패 시 None 반환
       - 로그 출력 (향후 logger 모듈 추가 시)
    
    5. **이식 시 주의사항**:
       - 기존 프로젝트의 에러 핸들링 로직을 최대한 보존
       - Rate Limit 대응 로직이 있다면 그대로 가져오기
       - 기존 코드의 함수/클래스 이름을 주석으로 명시
    ─────────────────────────────────────────────────────────────────────
    """
    base_url = config["exchanges"]["upbit"]["base_url"].rstrip("/")
    market = f"KRW-{symbol}"
    url = f"{base_url}/v1/ticker"
    params = {"markets": market}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if not payload:
            logger.warning("Upbit ticker response was empty for %s", market)
            return None

        raw = payload[0]
        ticker = Ticker(
            exchange="upbit",
            symbol=symbol,
            price=float(raw.get("trade_price", 0)),
            timestamp=int(raw.get("trade_timestamp", time.time() * 1000)),
            volume_24h=float(raw.get("acc_trade_volume_24h", 0)),
        )
        return ticker

    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Upbit ticker fetch failed for %s: %s", symbol, exc)
        return None


# ============================================================================
# 바이낸스 Collector
# ============================================================================

def get_binance_futures_ticker(symbol: str, config: Dict[str, Any]) -> Optional[Ticker]:
    """
    바이낸스 선물에서 단일 심볼의 현재가를 조회합니다.
    
    Args:
        symbol: 심볼 코드 (예: "BTC")
        config: 설정 딕셔너리 (base.yml 로딩 결과)
    
    Returns:
        Ticker 객체 (조회 실패 시 None)
    
    Examples:
        >>> ticker = get_binance_futures_ticker("BTC", config)
        >>> print(ticker.price)  # 37000.0 (USDT)
    
    TODO (PHASE A-2에서 구현):
    ─────────────────────────────────────────────────────────────────────
    이 함수는 기존 앙상블 트레이딩 봇 프로젝트의 바이낸스 Collector를 이식하여 완성합니다.
    
    [이식 계획]
    
    1. **기존 프로젝트에서 가져올 코드**:
       - refer/rest_collector.py의 fetch_ticker_24h() 함수
       - 또는 python-binance 라이브러리 사용 코드
       - 또는 직접 REST API 호출 (requests 기반)
    
    2. **필요한 API 엔드포인트**:
       - GET /fapi/v1/ticker/price (현재가만)
       - 또는 GET /fapi/v1/ticker/24hr (24시간 통계 포함)
       - 파라미터: symbol={symbol}USDT (예: BTCUSDT)
       - 인증: 공개 API이므로 서명 불필요
    
    3. **응답 파싱 예시**:
       ```python
       # 기존 프로젝트의 코드를 붙여 넣는 위치
       # 
       # 방법 1: python-binance 라이브러리 사용
       # (refer/rest_collector.py의 get_client() 함수 참고)
       from binance.client import Client
       
       client = Client()  # 공개 API는 키 불필요
       ticker = client.futures_ticker(symbol=f"{symbol}USDT")
       
       return Ticker(
           exchange="binance_futures",
           symbol=symbol,
           price=float(ticker["lastPrice"]),
           timestamp=int(time.time() * 1000),
           volume_24h=float(ticker.get("volume", 0))
       )
       
       # 방법 2: requests 직접 사용
       import requests
       
       base_url = config["exchanges"]["binance_futures"]["base_url"]
       url = f"{base_url}/fapi/v1/ticker/price"
       params = {"symbol": f"{symbol}USDT"}
       
       response = requests.get(url, params=params)
       data = response.json()
       
       return Ticker(
           exchange="binance_futures",
           symbol=symbol,
           price=float(data["price"]),
           timestamp=int(time.time() * 1000)
       )
       ```
    
    4. **에러 처리**:
       - API 호출 실패 시 None 반환
       - Rate Limit 대응 (기존 프로젝트의 fetch_history() 참고)
    
    5. **이식 시 주의사항**:
       - refer/rest_collector.py의 get_client() 싱글톤 패턴 활용 가능
       - BinanceAPIException 처리 로직 보존
       - Rate Limit 헤더 모니터링 로직 포함 (선택)
    ─────────────────────────────────────────────────────────────────────
    """
    base_url = config["exchanges"]["binance_futures"]["base_url"].rstrip("/")
    symbol_pair = f"{symbol}USDT"
    price_url = f"{base_url}/fapi/v1/ticker/price"
    stats_url = f"{base_url}/fapi/v1/ticker/24hr"

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(price_url, params={"symbol": symbol_pair})
            response.raise_for_status()
            price_data = response.json()

            stats_resp = client.get(stats_url, params={"symbol": symbol_pair})
            stats_resp.raise_for_status()
            stats_data = stats_resp.json()

        price = float(price_data.get("price", 0))
        ticker = Ticker(
            exchange="binance_futures",
            symbol=symbol,
            price=price,
            timestamp=int(time.time() * 1000),
            volume_24h=float(stats_data.get("volume", 0)),
        )
        return ticker

    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Binance futures ticker fetch failed for %s: %s", symbol, exc)
        return None


# ============================================================================
# 향후 확장: WebSocket 기반 실시간 시세 수집
# ============================================================================

def start_websocket_collector(symbols: list, config: Dict) -> Any:
    """
    WebSocket 기반 실시간 시세 수집기 시작 (향후 구현)
    
    Args:
        symbols: 심볼 리스트 (예: ["BTC", "ETH"])
        config: 설정 딕셔너리
    
    Returns:
        WebSocketCollector 인스턴스 또는 유사 객체
    
    TODO (PHASE A-3 이후):
    ─────────────────────────────────────────────────────────────────────
    현재는 REST API 폴링 방식으로 시세를 수집하지만, 향후 WebSocket 기반으로 전환 가능합니다.
    
    [이식 계획]
    
    1. **기존 프로젝트에서 가져올 코드**:
       - refer/websocket_collector.py의 WebSocketCollector 클래스
       - 실시간 캔들 수신, dedup, backfill 로직
    
    2. **이식 방식**:
       - WebSocketCollector를 이 프로젝트에 thin wrapper로 감싸기
       - 캔들 데이터를 Ticker 모델로 변환
       - 콜백 함수로 실시간 시세 전달
    
    3. **예시 코드**:
       ```python
       from refer.websocket_collector import WebSocketCollector
       
       ws = WebSocketCollector(
           symbols=[f"{s}USDT" for s in symbols],
           timeframe="1m"
       )
       
       def on_candle(symbol, candle, is_closed, timeframe):
           if is_closed:
               # Ticker로 변환하여 처리
               ticker = Ticker(
                   exchange="binance_futures",
                   symbol=symbol.replace("USDT", ""),
                   price=candle["close"],
                   timestamp=candle["closed_at"]
               )
               # ... 처리
       
       ws.on_candle(on_candle)
       ws.start()
       return ws
       ```
    
    4. **주의사항**:
       - 업비트는 WebSocket API가 다르므로 별도 구현 필요
       - 또는 업비트는 REST 폴링, 바이낸스만 WebSocket 사용 (하이브리드)
    ─────────────────────────────────────────────────────────────────────
    """
    raise NotImplementedError(
        "WebSocket 기반 실시간 시세 수집 미구현. "
        "PHASE A-3 이후 refer/websocket_collector.py를 이식하여 구현하세요."
    )
