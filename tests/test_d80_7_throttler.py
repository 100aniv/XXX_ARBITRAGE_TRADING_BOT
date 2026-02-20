"""
D80-7: Alert Throttler Tests
"""

import pytest
import time
from arbitrage.alerting import AlertThrottler


class TestAlertThrottlerMemory:
    """Test AlertThrottler with in-memory backend"""
    
    def test_init_memory_mode(self):
        """Test initialization in memory mode"""
        throttler = AlertThrottler(redis_client=None, window_seconds=10)
        
        assert throttler._use_redis is False
        assert throttler.window_seconds == 10
        
        stats = throttler.get_stats()
        assert stats["backend"] == "memory"
    
    def test_should_send_first_time(self):
        """Test alert allowed on first send"""
        throttler = AlertThrottler(redis_client=None, window_seconds=5)
        
        assert throttler.should_send("test-key") is True
    
    def test_throttling_within_window(self):
        """Test alert throttled within window"""
        throttler = AlertThrottler(redis_client=None, window_seconds=2)
        
        # First send
        assert throttler.should_send("test-key") is True
        throttler.mark_sent("test-key")
        
        # Second send within window
        assert throttler.should_send("test-key") is False
        
        stats = throttler.get_stats()
        assert stats["throttled_count"] == 1
        assert stats["allowed_count"] == 1
    
    def test_throttling_after_window(self):
        """Test alert allowed after window expires"""
        throttler = AlertThrottler(redis_client=None, window_seconds=1)
        
        # First send
        assert throttler.should_send("test-key") is True
        throttler.mark_sent("test-key")
        
        # Wait for window to expire (timing jitter tolerant)
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if throttler.should_send("test-key") is True:
                break
            time.sleep(0.05)
        else:
            pytest.fail("Throttle window did not expire within expected time")
    
    def test_multiple_keys(self):
        """Test throttling with multiple keys"""
        throttler = AlertThrottler(redis_client=None, window_seconds=10)
        
        # Different keys should be independent
        assert throttler.should_send("key-1") is True
        throttler.mark_sent("key-1")
        
        assert throttler.should_send("key-2") is True
        throttler.mark_sent("key-2")
        
        # Same keys should be throttled
        assert throttler.should_send("key-1") is False
        assert throttler.should_send("key-2") is False
        
        stats = throttler.get_stats()
        assert stats["throttled_count"] == 2
        assert stats["allowed_count"] == 2
    
    def test_clear_specific_key(self):
        """Test clearing specific throttle key"""
        throttler = AlertThrottler(redis_client=None, window_seconds=10)
        
        throttler.mark_sent("key-1")
        throttler.mark_sent("key-2")
        
        # Clear key-1
        throttler.clear("key-1")
        
        # key-1 should be allowed, key-2 still throttled
        assert throttler.should_send("key-1") is True
        assert throttler.should_send("key-2") is False
    
    def test_clear_all(self):
        """Test clearing all throttle keys"""
        throttler = AlertThrottler(redis_client=None, window_seconds=10)
        
        throttler.mark_sent("key-1")
        throttler.mark_sent("key-2")
        throttler.mark_sent("key-3")
        
        # Clear all
        throttler.clear()
        
        # All keys should be allowed
        assert throttler.should_send("key-1") is True
        assert throttler.should_send("key-2") is True
        assert throttler.should_send("key-3") is True
    
    def test_get_remaining_window(self):
        """Test getting remaining throttle window"""
        throttler = AlertThrottler(redis_client=None, window_seconds=5)
        
        # Before first send
        assert throttler.get_remaining_window("test-key") is None
        
        # After first send
        throttler.mark_sent("test-key")
        remaining = throttler.get_remaining_window("test-key")
        
        assert remaining is not None
        assert 0 <= remaining <= 5
        
        # Wait and check again
        time.sleep(1)
        remaining2 = throttler.get_remaining_window("test-key")
        
        if remaining2 is not None:
            assert remaining2 <= remaining


class TestAlertThrottlerStats:
    """Test throttler statistics"""
    
    def test_initial_stats(self):
        """Test initial statistics"""
        throttler = AlertThrottler(redis_client=None)
        
        stats = throttler.get_stats()
        
        assert stats["backend"] == "memory"
        assert stats["window_seconds"] == 300
        assert stats["throttled_count"] == 0
        assert stats["allowed_count"] == 0
        assert stats["redis_errors"] == 0
        assert stats["active_keys"] == 0
    
    def test_stats_updates(self):
        """Test statistics updates"""
        throttler = AlertThrottler(redis_client=None, window_seconds=10)
        
        # Allowed
        throttler.should_send("key-1")
        throttler.mark_sent("key-1")
        
        # Throttled
        throttler.should_send("key-1")
        throttler.should_send("key-1")
        
        # Another key
        throttler.should_send("key-2")
        throttler.mark_sent("key-2")
        
        stats = throttler.get_stats()
        
        assert stats["throttled_count"] == 2
        assert stats["allowed_count"] == 2
        assert stats["active_keys"] == 2


class TestThrottlingScenarios:
    """Test real-world throttling scenarios"""
    
    def test_fx_source_down_alert(self):
        """Test FX source down alert throttling"""
        throttler = AlertThrottler(redis_client=None, window_seconds=300)  # 5 minutes
        
        alert_key = "FX-001:binance"
        
        # First alert
        assert throttler.should_send(alert_key) is True
        throttler.mark_sent(alert_key)
        
        # Repeated alerts within 5 minutes should be throttled
        for _ in range(10):
            assert throttler.should_send(alert_key) is False
        
        stats = throttler.get_stats()
        assert stats["throttled_count"] == 10
        assert stats["allowed_count"] == 1
    
    def test_different_sources_independent(self):
        """Test different FX sources are independent"""
        throttler = AlertThrottler(redis_client=None, window_seconds=300)
        
        # Different sources should each get one alert
        assert throttler.should_send("FX-001:binance") is True
        throttler.mark_sent("FX-001:binance")
        
        assert throttler.should_send("FX-001:okx") is True
        throttler.mark_sent("FX-001:okx")
        
        assert throttler.should_send("FX-001:bybit") is True
        throttler.mark_sent("FX-001:bybit")
        
        stats = throttler.get_stats()
        assert stats["allowed_count"] == 3
        assert stats["throttled_count"] == 0
    
    def test_critical_vs_warning_alerts(self):
        """Test critical and warning alerts are independent"""
        throttler = AlertThrottler(redis_client=None, window_seconds=300)
        
        # FX-002 (P0 Critical)
        assert throttler.should_send("FX-002:all") is True
        throttler.mark_sent("FX-002:all")
        
        # FX-001 (P2 Warning) - should still be allowed
        assert throttler.should_send("FX-001:binance") is True
        throttler.mark_sent("FX-001:binance")
        
        stats = throttler.get_stats()
        assert stats["allowed_count"] == 2
