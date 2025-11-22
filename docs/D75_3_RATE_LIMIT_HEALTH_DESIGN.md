# D75-3: Rate Limit Manager + Exchange Health Monitor 설계

**작성일:** 2025-11-22  
**단계:** D75-3 (Infrastructure Layer)  
**목표:** Multi-exchange 대비 Rate Limit & Health Monitoring 인프라 구축  
**전략:** Plug-in 방식, 엔진 로직 변경 없음, ±1ms latency 제약

---

## 📋 Executive Summary

**D75-3 핵심 목표:**
- Rate Limit Manager: 거래소별 API rate limit 관리 (REST/WebSocket 분리)
- Exchange Health Monitor: 실시간 거래소 상태 추적 및 Failover 기준 설정
- **엔진 외부 인프라 계층** 구축 (Core Engine 로직 절대 변경 금지)
- D75-5 (WebSocket), D76 (Multi-Process)와의 확장성 보장

**제약사항:**
- Loop latency 변화 ±1ms 이내
- 엔진/스프레드/RiskGuard 로직 불변
- 성능 개선 목표 없음 (D75-5 이후)
- Plug-in 방식으로 기존 코드 최소 수정

---

## 🔧 1. Rate Limit Manager 설계

### 1.1 Upbit/Binance Rate Limit 공식 스펙

#### Upbit REST API Limits
| Endpoint Type | Limit | Window | Weight |
|---------------|-------|--------|--------|
| Public (Orderbook) | 10 req/sec | 1s | 1 |
| Public (Ticker) | 10 req/sec | 1s | 1 |
| Private (Balance) | 8 req/sec | 1s | 1 |
| Private (Order) | 8 req/sec | 1s | 5 |
| **Global** | **600 req/min** | **1min** | - |

**특징:**
- IP 기반 제한
- 초과 시 HTTP 429 (Too Many Requests)
- Retry-After header 제공

#### Binance REST API Limits
| Endpoint Type | Limit | Window | Weight |
|---------------|-------|--------|--------|
| Public (Orderbook) | 1200 req/min | 1min | 5~20 (depth) |
| Public (Ticker) | 1200 req/min | 1min | 1 |
| Private (Balance) | 1200 req/min | 1min | 10 |
| Private (Order) | 1200 req/min | 1min | 1~5 |
| **Order Rate** | **10 orders/sec** | **1s** | - |
| **Daily Order** | **200,000** | **24h** | - |

**특징:**
- Weight-based system
- X-MBX-USED-WEIGHT header 제공
- IP ban on severe violations (5~15min)

#### WebSocket Limits
| Exchange | Connection Limit | Message Rate | Reconnect |
|----------|------------------|--------------|-----------|
| Upbit | 5 connections/IP | Unlimited | 5s cooldown |
| Binance | 300 connections/IP | 5 msg/sec (订阅) | 5s cooldown |

---

### 1.2 Rate Limit 추상화 설계

#### BaseRateLimiter (Abstract Interface)
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

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
```

#### TokenBucketRateLimiter
```python
import time
from threading import Lock

class TokenBucketRateLimiter(BaseRateLimiter):
    """
    Token Bucket 알고리즘 기반 rate limiter.
    
    특징:
    - Burst 허용
    - 일정 속도로 token refill
    - 실시간 시스템에 적합
    """
    
    def __init__(self, config: RateLimitConfig):
        self.max_tokens = config.max_requests + config.burst_allowance
        self.refill_rate = config.max_requests / config.window_seconds  # tokens/sec
        self.tokens = self.max_tokens
        self.last_refill = time.time()
        self._lock = Lock()
    
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
                return True
            return False
    
    def wait_time(self) -> float:
        with self._lock:
            self._refill()
            if self.tokens >= 1:
                return 0.0
            # 1 token refill까지 대기 시간
            return (1 - self.tokens) / self.refill_rate
```

#### SlidingWindowRateLimiter
```python
from collections import deque

class SlidingWindowRateLimiter(BaseRateLimiter):
    """
    Sliding Window 알고리즘 기반 rate limiter.
    
    특징:
    - 정확한 시간 윈도우
    - Memory overhead (request history 저장)
    - Binance-style weight system 지원
    """
    
    def __init__(self, config: RateLimitConfig):
        self.max_requests = config.max_requests
        self.window_seconds = config.window_seconds
        self.weight_per_request = config.weight_per_request
        self.requests = deque()  # [(timestamp, weight), ...]
        self._lock = Lock()
    
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
                return True
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
            return (oldest_time + self.window_seconds) - time.time()
```

---

### 1.3 ExchangeRateLimitProfile

```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class ExchangeRateLimitProfile:
    """거래소별 rate limit 프로파일"""
    exchange_name: str
    rest_limits: Dict[str, RateLimitConfig]  # endpoint_type -> config
    ws_limits: Dict[str, RateLimitConfig]
    
    # Rate limiter instances
    rest_limiters: Dict[str, BaseRateLimiter] = None
    ws_limiters: Dict[str, BaseRateLimiter] = None

# Upbit Profile
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

# Binance Profile
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
```

---

## 🏥 2. Exchange Health Monitor 설계

### 2.1 Health Metrics 정의

#### HealthMetrics
```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class HealthMetrics:
    """거래소 건강 상태 메트릭"""
    
    # Latency
    rest_latency_ms: float = 0.0  # REST API 평균 latency (ms)
    rest_latency_p99_ms: float = 0.0  # REST API p99 latency (ms)
    ws_latency_ms: float = 0.0  # WebSocket message latency (ms)
    
    # Freshness
    orderbook_age_ms: float = 0.0  # Orderbook 데이터 나이 (ms)
    last_update_timestamp: float = 0.0  # 마지막 업데이트 시각
    
    # Error Ratio
    error_4xx_count: int = 0  # 4xx 에러 수 (client error)
    error_5xx_count: int = 0  # 5xx 에러 수 (server error)
    total_requests: int = 0  # 총 요청 수
    error_ratio: float = 0.0  # 전체 에러 비율
    
    # Rate Limit
    rate_limit_near_exhausted: bool = False  # Rate limit 임박
    rate_limit_remaining: int = 0  # 남은 요청 수 (API header 기반)
    
    # Connection
    ws_connected: bool = True  # WebSocket 연결 상태
    ws_reconnect_count: int = 0  # WebSocket 재연결 횟수
```

#### ExchangeHealthStatus
```python
from enum import Enum

class ExchangeHealthStatus(Enum):
    """거래소 건강 상태"""
    HEALTHY = "healthy"  # 정상
    DEGRADED = "degraded"  # 성능 저하
    DOWN = "down"  # 다운
    FROZEN = "frozen"  # API 응답 없음
```

---

### 2.2 HealthMonitor 구현

```python
import time
from collections import deque
from threading import Lock

class HealthMonitor:
    """
    거래소 건강 상태 모니터.
    
    역할:
    - REST latency, error ratio 추적
    - Orderbook freshness 계산
    - Health status 판단 (HEALTHY/DEGRADED/DOWN)
    - Failover 기준 제공
    """
    
    def __init__(self, exchange_name: str):
        self.exchange_name = exchange_name
        self.metrics = HealthMetrics()
        self._latency_history = deque(maxlen=100)  # 최근 100개 latency
        self._error_history = deque(maxlen=1000)  # 최근 1000개 요청
        self._lock = Lock()
    
    def update_latency(self, latency_ms: float):
        """REST API latency 업데이트"""
        with self._lock:
            self._latency_history.append(latency_ms)
            if self._latency_history:
                self.metrics.rest_latency_ms = sum(self._latency_history) / len(self._latency_history)
                sorted_latency = sorted(self._latency_history)
                p99_idx = int(len(sorted_latency) * 0.99)
                self.metrics.rest_latency_p99_ms = sorted_latency[p99_idx]
    
    def update_error(self, status_code: int):
        """HTTP 에러 업데이트"""
        with self._lock:
            self._error_history.append(status_code)
            self.metrics.total_requests = len(self._error_history)
            self.metrics.error_4xx_count = sum(1 for code in self._error_history if 400 <= code < 500)
            self.metrics.error_5xx_count = sum(1 for code in self._error_history if 500 <= code < 600)
            error_count = self.metrics.error_4xx_count + self.metrics.error_5xx_count
            self.metrics.error_ratio = error_count / self.metrics.total_requests if self.metrics.total_requests > 0 else 0.0
    
    def update_orderbook_freshness(self, snapshot_timestamp: float):
        """Orderbook freshness 업데이트"""
        with self._lock:
            now = time.time()
            self.metrics.orderbook_age_ms = (now - snapshot_timestamp) * 1000
            self.metrics.last_update_timestamp = snapshot_timestamp
    
    def get_health_status(self) -> ExchangeHealthStatus:
        """
        현재 건강 상태 판단.
        
        기준:
        - HEALTHY: latency < 100ms, error_ratio < 1%, orderbook < 1s
        - DEGRADED: latency 100~500ms, error_ratio 1~5%, orderbook 1~3s
        - DOWN: latency > 500ms, error_ratio > 5%, orderbook > 3s
        - FROZEN: latency > 2000ms or no update > 10s
        """
        with self._lock:
            # FROZEN: 응답 없음
            if self.metrics.rest_latency_ms > 2000 or self.metrics.orderbook_age_ms > 10000:
                return ExchangeHealthStatus.FROZEN
            
            # DOWN: 심각한 문제
            if (self.metrics.rest_latency_ms > 500 or 
                self.metrics.error_ratio > 0.05 or 
                self.metrics.orderbook_age_ms > 3000):
                return ExchangeHealthStatus.DOWN
            
            # DEGRADED: 성능 저하
            if (self.metrics.rest_latency_ms > 100 or 
                self.metrics.error_ratio > 0.01 or 
                self.metrics.orderbook_age_ms > 1000):
                return ExchangeHealthStatus.DEGRADED
            
            # HEALTHY
            return ExchangeHealthStatus.HEALTHY
    
    def should_failover(self) -> bool:
        """
        Failover 실행 여부 판단.
        
        기준:
        - DOWN 상태 5분 이상 지속
        - FROZEN 상태 1분 이상 지속
        - Error ratio > 10% (1분 이상)
        """
        status = self.get_health_status()
        
        # FROZEN: 즉시 failover
        if status == ExchangeHealthStatus.FROZEN:
            return True
        
        # DOWN: 5분 이상 지속 시 failover (실제 구현 시 timestamp 추적 필요)
        if status == ExchangeHealthStatus.DOWN:
            return True  # Simplified for now
        
        return False
```

---

## 🔌 3. Live Runner 통합

### 3.1 통합 전략

**원칙:**
- 최소 변경 (Plug-in 방식)
- latency overhead < 1ms
- 의미론 변경 없음

**통합 포인트:**
1. `build_snapshot()` 호출 직전: RateLimiter.consume()
2. `build_snapshot()` 완료 직후: HealthMonitor.update_latency()
3. HTTP 에러 발생 시: HealthMonitor.update_error()

### 3.2 코드 수정 예시

```python
# arbitrage/live_runner.py

from arbitrage.infrastructure.rate_limiter import TokenBucketRateLimiter, UPBIT_PROFILE, BINANCE_PROFILE
from arbitrage.infrastructure.exchange_health import HealthMonitor, ExchangeHealthStatus

class ArbitrageLiveRunner:
    def __init__(self, ...):
        # ... existing init ...
        
        # D75-3: Rate Limit & Health Monitor
        self._rate_limiter_a = self._create_rate_limiter(self.config.exchange_a_name)
        self._rate_limiter_b = self._create_rate_limiter(self.config.exchange_b_name)
        self._health_monitor_a = HealthMonitor(self.config.exchange_a_name)
        self._health_monitor_b = HealthMonitor(self.config.exchange_b_name)
    
    def _create_rate_limiter(self, exchange_name: str):
        """거래소별 rate limiter 생성"""
        if exchange_name.upper() == "UPBIT":
            profile = UPBIT_PROFILE
        elif exchange_name.upper() == "BINANCE":
            profile = BINANCE_PROFILE
        else:
            return None
        
        # Orderbook endpoint용 limiter 생성
        config = profile.rest_limits.get("public_orderbook")
        return TokenBucketRateLimiter(config) if config else None
    
    def build_snapshot(self) -> Optional[OrderBookSnapshot]:
        """
        D75-3: Rate limit & health monitoring 통합.
        """
        # Rate limit check (non-blocking, < 0.1ms)
        if self._rate_limiter_a and not self._rate_limiter_a.consume():
            logger.warning(f"[D75-3] Rate limit reached for {self.config.exchange_a_name}")
            # Optional: wait or skip
            # time.sleep(self._rate_limiter_a.wait_time())
        
        # Existing build_snapshot logic
        start = time.perf_counter()
        try:
            snapshot = self._build_snapshot_core()
            
            # Health monitoring update (< 0.1ms)
            latency_ms = (time.perf_counter() - start) * 1000
            if self._health_monitor_a:
                self._health_monitor_a.update_latency(latency_ms)
            
            return snapshot
        
        except Exception as e:
            # Health monitoring: error tracking
            if self._health_monitor_a:
                self._health_monitor_a.update_error(500)  # Assume server error
            raise
```

---

## 🧪 4. 테스트 전략

### 4.1 Unit Tests

**test_rate_limiter.py:**
- TokenBucket refill 정확성
- SlidingWindow window cleanup
- Burst handling
- Weight-based consumption

**test_exchange_health.py:**
- Latency tracking (avg, p99)
- Error ratio 계산
- Health status transition
- Failover 기준 검증

### 4.2 Integration Tests

**run_d75_3_integration.py:**
- Multi-symbol engine + Rate Limiter
- Simulated rate limit 초과
- Health degradation → Failover
- Latency overhead 측정 (< 1ms)

---

## 🎯 5. Acceptance Criteria

| 항목 | 기준 | 검증 방법 |
|------|------|-----------|
| Rate limiter 정확성 | 100% (burst, refill) | Unit test |
| Health status 정확성 | 100% (HEALTHY/DEGRADED/DOWN) | Unit test |
| Latency overhead | < 1ms | Integration test |
| Loop latency 변화 | ±1ms | Integration test (Top10, 1분) |
| 의미론 변경 | 없음 | Regression test |
| 문서 완성도 | 100% | Manual review |

---

## 🚀 6. D75-5/D76 연결성

### 6.1 D75-5 (WebSocket Market Stream)
- Rate Limiter: WebSocket connection/subscription limits
- Health Monitor: WebSocket latency/reconnect tracking
- 기존 REST rate limit과 분리 관리

### 6.2 D76 (Multi-Process Architecture)
- Rate Limiter: Process-safe implementation (shared memory/Redis)
- Health Monitor: Cross-process aggregation
- Failover: Process-level isolation

### 6.3 TO-BE 18개 항목 반영
- ✅ #2: Rate Limit Manager
- ✅ #3: Exchange Health Monitor
- 🔄 #5: WebSocket Market Stream (D75-5)
- 🔄 #9: Failover & Resume (D76)

---

**Status:** ⏳ **D75-3 설계 완료, 구현 시작**
