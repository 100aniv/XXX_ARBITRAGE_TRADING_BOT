"""
D75-3: Rate Limiter Unit Tests

TokenBucket, SlidingWindow rate limiter 검증:
- Refill 정확성
- Burst handling
- Weight-based consumption
- Window cleanup
"""

import time
import pytest
from arbitrage.infrastructure.rate_limiter import (
    RateLimitConfig,
    TokenBucketRateLimiter,
    SlidingWindowRateLimiter,
    UPBIT_PROFILE,
    BINANCE_PROFILE,
)


class TestTokenBucketRateLimiter:
    """TokenBucket rate limiter 테스트"""
    
    def test_basic_consumption(self):
        """기본 consume 동작"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = TokenBucketRateLimiter(config)
        
        # 10개 요청 허용
        for _ in range(10):
            assert limiter.consume() is True
        
        # 11번째 요청 거부
        assert limiter.consume() is False
    
    def test_refill_over_time(self):
        """시간 경과에 따른 refill"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = TokenBucketRateLimiter(config)
        
        # 모든 토큰 소비
        for _ in range(10):
            limiter.consume()
        
        assert limiter.consume() is False
        
        # 0.5초 대기 (5개 토큰 refill)
        time.sleep(0.5)
        
        for _ in range(5):
            assert limiter.consume() is True
        
        assert limiter.consume() is False
    
    def test_burst_allowance(self):
        """Burst 허용"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0, burst_allowance=5)
        limiter = TokenBucketRateLimiter(config)
        
        # 15개 요청 허용 (10 + 5 burst)
        for _ in range(15):
            assert limiter.consume() is True
        
        # 16번째 요청 거부
        assert limiter.consume() is False
    
    def test_weight_based_consumption(self):
        """Weight 기반 소비"""
        config = RateLimitConfig(max_requests=100, window_seconds=1.0)
        limiter = TokenBucketRateLimiter(config)
        
        # Weight=10인 요청 10개 (총 100 소비)
        for _ in range(10):
            assert limiter.consume(weight=10) is True
        
        # 더 이상 허용 안 됨
        assert limiter.consume(weight=1) is False
    
    def test_wait_time_calculation(self):
        """대기 시간 계산"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = TokenBucketRateLimiter(config)
        
        # 모든 토큰 소비
        for _ in range(10):
            limiter.consume()
        
        # 대기 시간 확인 (약 0.1초, 1 token refill)
        wait = limiter.wait_time()
        assert 0.05 < wait < 0.15
    
    def test_reset(self):
        """리셋 기능"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = TokenBucketRateLimiter(config)
        
        # 모든 토큰 소비
        for _ in range(10):
            limiter.consume()
        
        assert limiter.consume() is False
        
        # 리셋
        limiter.reset()
        
        # 다시 10개 허용
        for _ in range(10):
            assert limiter.consume() is True
    
    def test_stats(self):
        """통계 정보"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = TokenBucketRateLimiter(config)
        
        # 5개 성공, 1개 실패
        for _ in range(5):
            limiter.consume()
        
        for _ in range(6):
            limiter.consume()
        
        stats = limiter.get_stats()
        assert stats["consume_count"] == 10
        assert stats["reject_count"] == 1
        assert stats["reject_ratio"] > 0.0


class TestSlidingWindowRateLimiter:
    """SlidingWindow rate limiter 테스트"""
    
    def test_basic_consumption(self):
        """기본 consume 동작"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = SlidingWindowRateLimiter(config)
        
        # 10개 요청 허용
        for _ in range(10):
            assert limiter.consume() is True
        
        # 11번째 요청 거부
        assert limiter.consume() is False
    
    def test_sliding_window_cleanup(self):
        """Sliding window 자동 cleanup"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = SlidingWindowRateLimiter(config)
        
        # 10개 요청
        for _ in range(10):
            limiter.consume()
        
        assert limiter.consume() is False
        
        # 1.1초 대기 (윈도우 밖으로)
        time.sleep(1.1)
        
        # 다시 10개 허용
        for _ in range(10):
            assert limiter.consume() is True
    
    def test_weight_based_consumption(self):
        """Weight 기반 소비 (Binance 스타일)"""
        config = RateLimitConfig(max_requests=1200, window_seconds=60.0, weight_per_request=5)
        limiter = SlidingWindowRateLimiter(config)
        
        # Weight=5인 요청 240개 (총 1200 소비)
        for _ in range(240):
            assert limiter.consume(weight=5) is True
        
        # 더 이상 허용 안 됨
        assert limiter.consume(weight=5) is False
    
    def test_partial_window_refill(self):
        """부분 윈도우 refill"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = SlidingWindowRateLimiter(config)
        
        # 5개 요청
        for _ in range(5):
            limiter.consume()
        
        # 0.6초 대기
        time.sleep(0.6)
        
        # 5개 더 요청 (첫 5개는 아직 윈도우 내)
        for _ in range(5):
            assert limiter.consume() is True
        
        # 11번째 거부
        assert limiter.consume() is False
        
        # 0.5초 더 대기 (첫 5개 윈도우 밖으로)
        time.sleep(0.5)
        
        # 다시 5개 허용
        for _ in range(5):
            assert limiter.consume() is True
    
    def test_stats(self):
        """통계 정보"""
        config = RateLimitConfig(max_requests=10, window_seconds=1.0)
        limiter = SlidingWindowRateLimiter(config)
        
        # 10개 성공, 1개 실패
        for _ in range(11):
            limiter.consume()
        
        stats = limiter.get_stats()
        assert stats["consume_count"] == 10
        assert stats["reject_count"] == 1
        assert stats["current_weight"] == 10  # 윈도우 내 weight


class TestExchangeRateLimitProfile:
    """거래소 프로파일 테스트"""
    
    def test_upbit_profile(self):
        """Upbit 프로파일"""
        assert UPBIT_PROFILE.exchange_name == "UPBIT"
        assert "public_orderbook" in UPBIT_PROFILE.rest_limits
        assert "global" in UPBIT_PROFILE.rest_limits
        
        # Orderbook limit: 10 req/sec
        config = UPBIT_PROFILE.rest_limits["public_orderbook"]
        assert config.max_requests == 10
        assert config.window_seconds == 1.0
    
    def test_binance_profile(self):
        """Binance 프로파일"""
        assert BINANCE_PROFILE.exchange_name == "BINANCE"
        assert "public_orderbook" in BINANCE_PROFILE.rest_limits
        assert "order_rate" in BINANCE_PROFILE.rest_limits
        
        # Orderbook limit: 1200 req/min, weight=5
        config = BINANCE_PROFILE.rest_limits["public_orderbook"]
        assert config.max_requests == 1200
        assert config.window_seconds == 60.0
        assert config.weight_per_request == 5
    
    def test_get_rest_limiter(self):
        """Lazy init rate limiter"""
        limiter = UPBIT_PROFILE.get_rest_limiter("public_orderbook")
        assert limiter is not None
        assert isinstance(limiter, TokenBucketRateLimiter)
        
        # 두 번째 호출은 캐싱된 인스턴스 반환
        limiter2 = UPBIT_PROFILE.get_rest_limiter("public_orderbook")
        assert limiter is limiter2
