"""
D202-1: Rate Limit Counter (Redis)

V2 계약:
- Key: v2:{env}:{run_id}:ratelimit:{exchange}:{endpoint}
- TTL: 1s (sliding window)
- INCR + EXPIRE (원자적 카운터)
"""

import logging
import redis
from typing import Dict

logger = logging.getLogger(__name__)


class RateLimitCounter:
    """
    Rate Limit Redis 카운터
    
    책임:
    - API endpoint별 카운터 관리
    - Sliding window 기반 (TTL 1s)
    - Upbit/Binance 레이트리밋 준수
    """
    
    # 거래소별 레이트리밋 (req/s)
    LIMITS: Dict[str, Dict[str, int]] = {
        "upbit": {
            "orders": 8,        # 8 req/s (API 문서)
            "market_data": 30,  # 30 req/s (추정)
        },
        "binance": {
            "orders": 20,       # 20 req/s (추정, 실제는 1200 req/min)
            "market_data": 100, # 100 req/s (추정)
        },
    }
    
    def __init__(
        self,
        redis_client: redis.Redis,
        env: str = "dev",
        run_id: str = "default",
    ):
        """
        Args:
            redis_client: Redis 클라이언트
            env: 환경 (dev/test/prod)
            run_id: 실행 세션 ID
        """
        self.redis = redis_client
        self.env = env
        self.run_id = run_id
    
    def _make_key(self, exchange: str, endpoint: str) -> str:
        """Redis key 생성 (SSOT 규칙)"""
        return f"v2:{self.env}:{self.run_id}:ratelimit:{exchange}:{endpoint}"
    
    def check(self, exchange: str, endpoint: str) -> bool:
        """
        Rate limit 체크 (sliding window)
        
        Args:
            exchange: 거래소 이름
            endpoint: API endpoint
        
        Returns:
            bool: True (허용), False (차단)
        """
        limit = self.LIMITS.get(exchange, {}).get(endpoint, 30)  # 기본값 30 req/s
        key = self._make_key(exchange, endpoint)
        
        # INCR + EXPIRE (원자적)
        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, 1)  # 1s TTL
        
        allowed = current <= limit
        
        if not allowed:
            logger.warning(
                f"[D202-1_RATELIMIT] Rate limit exceeded: "
                f"{exchange}/{endpoint} ({current}/{limit})"
            )
        
        return allowed
    
    def get_current_count(self, exchange: str, endpoint: str) -> int:
        """현재 카운트 조회 (모니터링용)"""
        key = self._make_key(exchange, endpoint)
        value = self.redis.get(key)
        return int(value) if value else 0
