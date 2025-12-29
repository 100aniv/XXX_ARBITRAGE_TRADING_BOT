"""
D202-1: MarketData Redis Cache (TTL 100ms)

V2 계약:
- Key: v2:{env}:{run_id}:market:{exchange}:{symbol}:{data_type}
- TTL: 100ms (market data)
- JSON 직렬화
"""

import json
import logging
import redis
from typing import Optional
from arbitrage.v2.marketdata.interfaces import Ticker, Orderbook

logger = logging.getLogger(__name__)


class MarketDataCache:
    """
    MarketData Redis 캐시
    
    책임:
    - market data Redis 저장/조회
    - TTL 100ms 강제
    - JSON 직렬화
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        env: str = "dev",
        run_id: str = "default",
        ttl_ms: int = 100,
    ):
        """
        Args:
            redis_client: Redis 클라이언트
            env: 환경 (dev/test/prod)
            run_id: 실행 세션 ID
            ttl_ms: TTL (밀리초, 기본값: 100ms)
        """
        self.redis = redis_client
        self.env = env
        self.run_id = run_id
        self.ttl_ms = ttl_ms
    
    def _make_key(self, exchange: str, symbol: str, data_type: str) -> str:
        """Redis key 생성 (SSOT 규칙)"""
        return f"v2:{self.env}:{self.run_id}:market:{exchange}:{symbol}:{data_type}"
    
    def set_ticker(self, ticker: Ticker) -> None:
        """Ticker 저장 (TTL 100ms)"""
        key = self._make_key(ticker.exchange, ticker.symbol, "ticker")
        value = json.dumps({
            "timestamp": ticker.timestamp.isoformat(),
            "bid": ticker.bid,
            "ask": ticker.ask,
            "last": ticker.last,
            "volume": ticker.volume,
        })
        self.redis.psetex(key, self.ttl_ms, value)  # PSETEX: 밀리초 단위 TTL
        logger.debug(f"[D202-1_CACHE] Ticker cached: {key}")
    
    def get_ticker(self, exchange: str, symbol: str) -> Optional[Ticker]:
        """Ticker 조회"""
        key = self._make_key(exchange, symbol, "ticker")
        value = self.redis.get(key)
        if not value:
            return None
        
        data = json.loads(value)
        from datetime import datetime
        return Ticker(
            exchange=exchange,
            symbol=symbol,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            bid=data["bid"],
            ask=data["ask"],
            last=data["last"],
            volume=data["volume"],
        )
    
    def set_orderbook(self, orderbook: Orderbook) -> None:
        """Orderbook 저장 (TTL 100ms)"""
        key = self._make_key(orderbook.exchange, orderbook.symbol, "orderbook")
        value = json.dumps({
            "timestamp": orderbook.timestamp.isoformat(),
            "bids": [[level.price, level.quantity] for level in orderbook.bids],
            "asks": [[level.price, level.quantity] for level in orderbook.asks],
        })
        self.redis.psetex(key, self.ttl_ms, value)  # PSETEX: 밀리초 단위 TTL
        logger.debug(f"[D202-1_CACHE] Orderbook cached: {key}")
    
    def get_orderbook(self, exchange: str, symbol: str) -> Optional[Orderbook]:
        """Orderbook 조회"""
        key = self._make_key(exchange, symbol, "orderbook")
        value = self.redis.get(key)
        if not value:
            return None
        
        data = json.loads(value)
        from datetime import datetime
        from arbitrage.v2.marketdata.interfaces import OrderbookLevel
        return Orderbook(
            exchange=exchange,
            symbol=symbol,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            bids=[OrderbookLevel(price=b[0], quantity=b[1]) for b in data["bids"]],
            asks=[OrderbookLevel(price=a[0], quantity=a[1]) for a in data["asks"]],
        )
