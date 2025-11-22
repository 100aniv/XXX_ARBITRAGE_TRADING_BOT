"""
D75-3: Rate Limit Manager

Multi-exchange rate limit 관리:
- TokenBucket: Burst 허용, 실시간 시스템 적합
- SlidingWindow: 정확한 윈도우, Weight system 지원
- ExchangeRateLimitProfile: Upbit/Binance 공식 스펙
"""

import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from arbitrage.alerting import AlertManager


class RateLimitPolicy(Enum):
    """Rate limit 정책 종류"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """Rate limit 설정"""
    max_requests: int  # 최대 요청 수
    window_seconds: float  # 시간 윈도우 (초)
    burst_allowance: int = 0  # Burst 허용 (TokenBucket only)
    weight_per_request: int = 1  # 요청당 weight (Binance)


class BaseRateLimiter(ABC):
    """Rate limiter 추상 인터페이스"""
    
    @abstractmethod
    def consume(self, weight: int = 1) -> bool:
        """
        Rate limit 소비 시도.
        
        Args:
            weight: 요청 weight (기본 1)
        
        Returns:
            True: 허용, False: 거부
        """
        pass
    
    @abstractmethod
    def wait_time(self) -> float:
        """
        다음 요청까지 대기 시간 (초).
        
        Returns:
            대기 시간 (초), 0이면 즉시 가능
        """
        pass
    
    @abstractmethod
    def reset(self):
        """Rate limit 상태 리셋"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict:
        """현재 상태 통계"""
        pass


class TokenBucketRateLimiter(BaseRateLimiter):
    """
    Token Bucket 알고리즘 기반 rate limiter.
    
    특징:
    - Burst 허용
    - 일정 속도로 token refill
    - 실시간 시스템에 적합
    
    Example:
        >>> config = RateLimitConfig(max_requests=10, window_seconds=1.0, burst_allowance=5)
        >>> limiter = TokenBucketRateLimiter(config)
        >>> limiter.consume()  # True
        >>> limiter.wait_time()  # 0.0 (즉시 가능)
    """
    
    def __init__(self, config: RateLimitConfig, alert_manager: Optional["AlertManager"] = None):
        self.max_tokens = config.max_requests + config.burst_allowance
        self.refill_rate = config.max_requests / config.window_seconds  # tokens/sec
        self.tokens = float(self.max_tokens)
        self.last_refill = time.time()
        self._lock = Lock()
        self._consume_count = 0
        self._reject_count = 0
        self._alert_manager = alert_manager
        self._last_alert_time = 0.0  # Rate limit alert throttling
    
    def _refill(self):
        """Token refill (시간 경과에 따라)"""
        now = time.time()
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.max_tokens, self.tokens + new_tokens)
        self.last_refill = now
    
    def consume(self, weight: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= weight:
                self.tokens -= weight
                self._consume_count += 1
                return True
            self._reject_count += 1
            self._send_rate_limit_alert()
            return False
    
    def _send_rate_limit_alert(self):
        """Send rate limit exhaustion alert (throttled to once per minute)"""
        if not self._alert_manager:
            return
        
        now = time.time()
        if now - self._last_alert_time < 60:  # Throttle: 1 alert per minute
            return
        
        self._last_alert_time = now
        
        try:
            from arbitrage.alerting import AlertSeverity, AlertSource
            self._alert_manager.send_alert(
                severity=AlertSeverity.P2,
                source=AlertSource.RATE_LIMITER,
                title="Rate Limit Near Exhaustion",
                message=f"Rate limiter tokens exhausted. Reject count: {self._reject_count}",
                metadata={
                    "tokens": self.tokens,
                    "max_tokens": self.max_tokens,
                    "reject_count": self._reject_count,
                    "reject_ratio": self._reject_count / (self._consume_count + self._reject_count),
                }
            )
        except Exception as e:
            # Don't fail the consume() call if alert fails
            pass
    
    def wait_time(self) -> float:
        with self._lock:
            self._refill()
            if self.tokens >= 1:
                return 0.0
            # 1 token refill까지 대기 시간
            shortage = 1 - self.tokens
            return shortage / self.refill_rate
    
    def reset(self):
        with self._lock:
            self.tokens = float(self.max_tokens)
            self.last_refill = time.time()
            self._consume_count = 0
            self._reject_count = 0
    
    def get_stats(self) -> Dict:
        with self._lock:
            self._refill()
            total = self._consume_count + self._reject_count
            return {
                "tokens": self.tokens,
                "max_tokens": self.max_tokens,
                "refill_rate": self.refill_rate,
                "consume_count": self._consume_count,
                "reject_count": self._reject_count,
                "reject_ratio": self._reject_count / total if total > 0 else 0.0,
            }


class SlidingWindowRateLimiter(BaseRateLimiter):
    """
    Sliding Window 알고리즘 기반 rate limiter.
    
    특징:
    - 정확한 시간 윈도우
    - Memory overhead (request history 저장)
    - Binance-style weight system 지원
    
    Example:
        >>> config = RateLimitConfig(max_requests=1200, window_seconds=60.0, weight_per_request=5)
        >>> limiter = SlidingWindowRateLimiter(config)
        >>> limiter.consume(weight=5)  # Binance orderbook (weight=5)
    """
    
    def __init__(self, config: RateLimitConfig):
        self.max_requests = config.max_requests
        self.window_seconds = config.window_seconds
        self.weight_per_request = config.weight_per_request
        self.requests = deque()  # [(timestamp, weight), ...]
        self._lock = Lock()
        self._consume_count = 0
        self._reject_count = 0
    
    def _cleanup_old_requests(self):
        """윈도우 밖 요청 제거"""
        now = time.time()
        cutoff = now - self.window_seconds
        while self.requests and self.requests[0][0] < cutoff:
            self.requests.popleft()
    
    def _current_weight(self) -> int:
        """현재 윈도우 내 총 weight"""
        return sum(weight for _, weight in self.requests)
    
    def consume(self, weight: int = 1) -> bool:
        with self._lock:
            self._cleanup_old_requests()
            current = self._current_weight()
            if current + weight <= self.max_requests:
                self.requests.append((time.time(), weight))
                self._consume_count += 1
                return True
            self._reject_count += 1
            return False
    
    def wait_time(self) -> float:
        with self._lock:
            self._cleanup_old_requests()
            if not self.requests:
                return 0.0
            current = self._current_weight()
            if current < self.max_requests:
                return 0.0
            # 가장 오래된 요청이 윈도우 밖으로 나갈 때까지 대기
            oldest_time = self.requests[0][0]
            wait = (oldest_time + self.window_seconds) - time.time()
            return max(0.0, wait)
    
    def reset(self):
        with self._lock:
            self.requests.clear()
            self._consume_count = 0
            self._reject_count = 0
    
    def get_stats(self) -> Dict:
        with self._lock:
            self._cleanup_old_requests()
            current_weight = self._current_weight()
            total = self._consume_count + self._reject_count
            return {
                "current_weight": current_weight,
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "request_count": len(self.requests),
                "consume_count": self._consume_count,
                "reject_count": self._reject_count,
                "reject_ratio": self._reject_count / total if total > 0 else 0.0,
            }


@dataclass
class ExchangeRateLimitProfile:
    """거래소별 rate limit 프로파일"""
    exchange_name: str
    rest_limits: Dict[str, RateLimitConfig]  # endpoint_type -> config
    ws_limits: Dict[str, RateLimitConfig]
    
    # Rate limiter instances (lazy init)
    rest_limiters: Dict[str, BaseRateLimiter] = field(default_factory=dict)
    ws_limiters: Dict[str, BaseRateLimiter] = field(default_factory=dict)
    
    def get_rest_limiter(self, endpoint_type: str, policy: RateLimitPolicy = RateLimitPolicy.TOKEN_BUCKET) -> Optional[BaseRateLimiter]:
        """
        REST endpoint용 rate limiter 가져오기 (lazy init).
        
        Args:
            endpoint_type: "public_orderbook", "private_order" 등
            policy: 사용할 정책 (TOKEN_BUCKET or SLIDING_WINDOW)
        
        Returns:
            BaseRateLimiter 또는 None (설정 없음)
        """
        if endpoint_type not in self.rest_limits:
            return None
        
        if endpoint_type not in self.rest_limiters:
            config = self.rest_limits[endpoint_type]
            if policy == RateLimitPolicy.TOKEN_BUCKET:
                self.rest_limiters[endpoint_type] = TokenBucketRateLimiter(config)
            elif policy == RateLimitPolicy.SLIDING_WINDOW:
                self.rest_limiters[endpoint_type] = SlidingWindowRateLimiter(config)
            else:
                raise ValueError(f"Unsupported policy: {policy}")
        
        return self.rest_limiters[endpoint_type]


# Upbit Profile (공식 스펙 기반)
UPBIT_PROFILE = ExchangeRateLimitProfile(
    exchange_name="UPBIT",
    rest_limits={
        "public_orderbook": RateLimitConfig(max_requests=10, window_seconds=1.0),
        "public_ticker": RateLimitConfig(max_requests=10, window_seconds=1.0),
        "private_balance": RateLimitConfig(max_requests=8, window_seconds=1.0),
        "private_order": RateLimitConfig(max_requests=8, window_seconds=1.0, weight_per_request=5),
        "global": RateLimitConfig(max_requests=600, window_seconds=60.0),
    },
    ws_limits={
        "connection": RateLimitConfig(max_requests=5, window_seconds=60.0),
    }
)

# Binance Profile (공식 스펙 기반)
BINANCE_PROFILE = ExchangeRateLimitProfile(
    exchange_name="BINANCE",
    rest_limits={
        "public_orderbook": RateLimitConfig(max_requests=1200, window_seconds=60.0, weight_per_request=5),
        "public_ticker": RateLimitConfig(max_requests=1200, window_seconds=60.0, weight_per_request=1),
        "private_balance": RateLimitConfig(max_requests=1200, window_seconds=60.0, weight_per_request=10),
        "private_order": RateLimitConfig(max_requests=1200, window_seconds=60.0, weight_per_request=1),
        "order_rate": RateLimitConfig(max_requests=10, window_seconds=1.0),
    },
    ws_limits={
        "connection": RateLimitConfig(max_requests=300, window_seconds=60.0),
        "subscription": RateLimitConfig(max_requests=5, window_seconds=1.0),
    }
)
