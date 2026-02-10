"""
D205-18-4: Rate Limiter (복원)

Purpose: API 요청 속도 제한
"""
import time
from threading import Lock


class RateLimiter:
    """Rate Limiter"""
    
    def __init__(self, requests_per_second: int = 10, burst: int = 2):
        self.requests_per_second = requests_per_second
        self.burst = burst
        self.interval = 1.0 / requests_per_second
        self.capacity = max(1.0, float(requests_per_second + burst))
        self.tokens = float(self.capacity)
        self.last_refill_time = time.time()
        self.lock = Lock()

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self.last_refill_time)
        if elapsed <= 0:
            return
        refill = elapsed * float(self.requests_per_second)
        self.tokens = min(self.capacity, self.tokens + refill)
        self.last_refill_time = now
    
    def acquire(self):
        """요청 허가 획득 (필요시 대기)"""
        with self.lock:
            now = time.time()
            self._refill(now)
            if self.tokens >= 1:
                self.tokens -= 1
                return
            if self.requests_per_second <= 0:
                return
            wait_time = (1.0 - self.tokens) / float(self.requests_per_second)
        if wait_time > 0:
            time.sleep(wait_time)
        with self.lock:
            now = time.time()
            self._refill(now)
            if self.tokens >= 1:
                self.tokens -= 1
    
    def consume(self, tokens: int = 1) -> bool:
        """
        토큰 소비 (rate limit 체크, non-blocking)

        Args:
            tokens: 소비할 토큰 수 (기본값: 1)

        Returns:
            True if allowed, False if rate limited
        """
        tokens = max(1, int(tokens))
        with self.lock:
            now = time.time()
            self._refill(now)
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
