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
        self.last_request_time = 0.0
        self.lock = Lock()
    
    def acquire(self):
        """요청 허가 획득 (필요시 대기)"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                time.sleep(wait_time)
            
            self.last_request_time = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        토큰 소비 (rate limit 체크)
        
        Args:
            tokens: 소비할 토큰 수 (기본값: 1)
            
        Returns:
            True if allowed, False if rate limited
        """
        self.acquire()
        return True
