#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REST API Collector
==================
Binance REST API를 통한 데이터 수집

- fetch_history(): 초기 히스토리 로드
- fetch_all_symbols(): 전체 종목 조회
- fetch_exchange_info(): 거래소 정보
"""
from typing import List, Dict, Optional
from collections import deque
import pandas as pd
from binance.client import Client as BinanceClient
import threading

from common.logger import setup_logger

logger = setup_logger('collector', log_type='application')

# ============================================
# Client 싱글톤 (연결 재사용)
# ============================================
_client_instance = None
_client_lock = threading.Lock()

def get_client():
    """BinanceClient 싱글톤 패턴"""
    global _client_instance
    
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                _client_instance = BinanceClient()
                logger.debug("✅ BinanceClient 초기화 (싱글톤)")
    
    return _client_instance


def fetch_history(symbol: str, timeframe: str, limit: int = 500) -> List[Dict]:
    """
    Binance에서 히스토리 캔들 로드 (⭐ Rate Limit 대응)
    
    Args:
        symbol: 심볼 (예: BTCUSDT)
        timeframe: 타임프레임 (예: 5m, 1h)
        limit: 로드할 캔들 개수 (기본 500)
    
    Returns:
        List[Dict]: 캔들 데이터 리스트
        
    Examples:
        >>> candles = fetch_history("BTCUSDT", "5m", 250)
        >>> print(len(candles))  # 250
    """
    import time
    from binance.exceptions import BinanceAPIException
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            client = get_client()
            klines = client.futures_klines(symbol=symbol, interval=timeframe, limit=limit)
            
            # ⭐ Rate Limit 헤더 확인 (가능 시)
            # Note: python-binance 라이브러리는 헤더 직접 노출 안함
            # 향후 requests 직접 사용으로 전환 시 X-MBX-USED-WEIGHT 모니터링 가능
            
            break  # 성공 시 루프 종료
            
        except BinanceAPIException as e:
            if e.code == -1003:  # Rate Limit 초과
                wait_time = 2 ** retry_count  # Exponential backoff: 1초, 2초, 4초
                logger.warning(
                    f"⚠️ [{symbol}] Rate Limit 감지 (재시도 {retry_count + 1}/{max_retries}), "
                    f"{wait_time}초 대기... | 오류: {e.message}"
                )
                time.sleep(wait_time)
                retry_count += 1
                
                if retry_count >= max_retries:
                    logger.error(f"❌ [{symbol}] Rate Limit 최대 재시도 초과, 빈 배열 반환")
                    return []
            else:
                # 다른 API 오류는 즉시 raise
                raise
        except Exception as e:
            # 예상치 못한 오류
            import traceback
            logger.error(f"❌ {symbol} 히스토리 로드 실패:")
            logger.error(f"   에러 타입: {type(e).__name__}")
            logger.error(f"   에러 메시지: {str(e)}")
            logger.error(f"   스택 트레이스:\n{traceback.format_exc()}")
            return []
    
    # 성공 케이스: klines 파싱
    try:
        # klines format: [[time, open, high, low, close, volume, ...], ...]
        df = pd.DataFrame(klines, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base", 
            "taker_buy_quote", "ignore"
        ])
        
        df = df[["time", "open", "high", "low", "close", "volume"]].astype(float)
        
        # ⭐ 성능 개선: iterrows() → itertuples() (20x 빠름)
        candles = []
        for r in df.itertuples():
            candles.append({
                "time": int(r.time),
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": float(r.volume)
            })
        
        logger.info(f"✅ {symbol} 히스토리 로드 완료: {len(candles)}개 캔들")
        return candles
    
    except Exception as e:
        import traceback
        logger.error(f"❌ {symbol} 히스토리 로드 실패:")
        logger.error(f"   에러 타입: {type(e).__name__}")
        logger.error(f"   에러 메시지: {str(e)}")
        logger.error(f"   스택 트레이스:\n{traceback.format_exc()}")
        return []


def bootstrap_history(symbol: str, timeframe: str, lookback: int, buffers: Dict[str, deque]) -> None:
    """
    초기 히스토리를 로드하여 버퍼에 저장 (하위 호환성)
    
    Args:
        symbol: 심볼
        timeframe: 타임프레임
        lookback: 로드할 개수
        buffers: 버퍼 딕셔너리
    """
    candles = fetch_history(symbol, timeframe, lookback)
    
    if symbol not in buffers:
        buffers[symbol] = deque(maxlen=lookback)
    
    for candle in candles:
        buffers[symbol].append(candle)


def fetch_all_symbols(quote_asset: str = "USDT", min_volume_24h: float = 0) -> List[str]:
    """
    전체 거래 가능한 종목 조회 (선물)
    
    Args:
        quote_asset: 기준 통화 (기본 USDT)
        min_volume_24h: 최소 24시간 거래량 (USDT)
    
    Returns:
        List[str]: 종목 리스트
        
    Examples:
        >>> symbols = fetch_all_symbols("USDT", min_volume_24h=1000000)
        >>> print(f"총 {len(symbols)}개 종목")
    """
    try:
        client = get_client()
        
        # 거래소 정보
        exchange_info = client.futures_exchange_info()
        
        # 활성 종목 필터링
        symbols = []
        for s in exchange_info['symbols']:
            # 선물 + USDT 페어 + TRADING 상태
            if (s['quoteAsset'] == quote_asset and 
                s['status'] == 'TRADING' and
                s['contractType'] == 'PERPETUAL'):
                symbols.append(s['symbol'])
        
        # 거래량 필터링
        if min_volume_24h > 0:
            tickers = client.futures_ticker()
            volume_map = {t['symbol']: float(t['quoteVolume']) for t in tickers}
            symbols = [s for s in symbols if volume_map.get(s, 0) >= min_volume_24h]
        
        logger.info(f"✅ 전체 종목 조회 완료: {len(symbols)}개 ({quote_asset} 페어)")
        return sorted(symbols)
    
    except Exception as e:
        logger.error(f"❌ 전체 종목 조회 실패: {e}")
        return []


def fetch_exchange_info() -> Dict:
    """
    거래소 정보 조회
    
    Returns:
        Dict: 거래소 정보 (symbols, filters, rate limits 등)
    """
    try:
        client = get_client()
        info = client.futures_exchange_info()
        logger.info(f"✅ 거래소 정보 조회 완료")
        return info
    
    except Exception as e:
        logger.error(f"❌ 거래소 정보 조회 실패: {e}")
        return {}


def fetch_ticker_24h(symbol: str) -> Optional[Dict]:
    """
    24시간 가격 통계 조회
    
    Args:
        symbol: 심볼
    
    Returns:
        Dict: 24h 통계 (price, volume, change 등)
    """
    try:
        client = get_client()
        ticker = client.futures_ticker(symbol=symbol)
        
        return {
            'symbol': ticker['symbol'],
            'price': float(ticker['lastPrice']),
            'volume_24h': float(ticker['volume']),
            'quote_volume_24h': float(ticker['quoteVolume']),
            'price_change_pct': float(ticker['priceChangePercent']),
            'high_24h': float(ticker['highPrice']),
            'low_24h': float(ticker['lowPrice'])
        }
    
    except Exception as e:
        logger.error(f"❌ {symbol} 티커 조회 실패: {e}")
        return None


def fetch_top_volume_symbols(quote_asset: str = "USDT", top_n: int = 50) -> List[str]:
    """
    거래량 상위 N개 종목 조회
    
    Args:
        quote_asset: 기준 통화
        top_n: 상위 개수
    
    Returns:
        List[str]: 종목 리스트 (거래량 순)
        
    Examples:
        >>> top_symbols = fetch_top_volume_symbols("USDT", 20)
        >>> print(f"거래량 TOP 20: {top_symbols}")
    """
    try:
        # 전체 종목
        all_symbols = fetch_all_symbols(quote_asset)
        
        # 티커 정보
        client = get_client()
        tickers = client.futures_ticker()
        
        # 거래량 기준 정렬
        volume_list = []
        for t in tickers:
            if t['symbol'] in all_symbols:
                volume_list.append({
                    'symbol': t['symbol'],
                    'volume': float(t['quoteVolume'])
                })
        
        # 정렬
        volume_list.sort(key=lambda x: x['volume'], reverse=True)
        
        # 상위 N개
        top_symbols = [v['symbol'] for v in volume_list[:top_n]]
        
        logger.info(f"✅ 거래량 TOP {top_n} 조회 완료")
        return top_symbols
    
    except Exception as e:
        logger.error(f"❌ 거래량 TOP 조회 실패: {e}")
        return []
