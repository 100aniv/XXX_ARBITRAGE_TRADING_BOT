"""
D80-7: Alert Throttler (Redis-based)

Prevents duplicate alerts within a configurable time window.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AlertThrottler:
    """
    Alert throttler with Redis backend
    
    Prevents sending duplicate alerts within a time window (default: 5 minutes).
    
    Features:
    - Redis-backed key-value store for distributed throttling
    - In-memory fallback for testing/paper mode
    - Per-alert-key throttling
    - Statistics tracking
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        window_seconds: int = 300,  # 5 minutes default
        use_memory_fallback: bool = True,
    ):
        """
        Initialize throttler
        
        Args:
            redis_client: Redis client (None for in-memory mode)
            window_seconds: Throttle window duration in seconds
            use_memory_fallback: Use in-memory fallback if Redis unavailable
        """
        self.redis_client = redis_client
        self.window_seconds = window_seconds
        self.use_memory_fallback = use_memory_fallback
        
        # In-memory fallback (for testing or when Redis unavailable)
        self._memory_store: Dict[str, float] = {}
        
        # Statistics
        self._stats = {
            "throttled_count": 0,
            "allowed_count": 0,
            "redis_errors": 0,
        }
        
        # Determine mode
        self._use_redis = redis_client is not None
        if self._use_redis:
            try:
                # Test Redis connection
                redis_client.ping()
                logger.info("[AlertThrottler] Using Redis backend")
            except Exception as e:
                logger.warning(f"[AlertThrottler] Redis unavailable: {e}")
                if use_memory_fallback:
                    self._use_redis = False
                    logger.info("[AlertThrottler] Falling back to in-memory mode")
                else:
                    raise
        else:
            logger.info("[AlertThrottler] Using in-memory backend")
    
    def should_send(self, alert_key: str) -> bool:
        """
        Check if alert should be sent (not throttled)
        
        Args:
            alert_key: Unique alert key (e.g., "FX-001:binance")
        
        Returns:
            True if alert should be sent, False if throttled
        """
        if self._use_redis:
            return self._should_send_redis(alert_key)
        else:
            return self._should_send_memory(alert_key)
    
    def mark_sent(self, alert_key: str) -> None:
        """
        Mark alert as sent (update throttle timestamp)
        
        Args:
            alert_key: Unique alert key
        """
        if self._use_redis:
            self._mark_sent_redis(alert_key)
        else:
            self._mark_sent_memory(alert_key)
        
        self._stats["allowed_count"] += 1
    
    def _should_send_redis(self, alert_key: str) -> bool:
        """Check throttle status using Redis"""
        try:
            redis_key = f"alert_throttle:{alert_key}"
            
            # Get last sent timestamp
            last_sent_ts = self.redis_client.get(redis_key)
            
            if last_sent_ts is None:
                # Never sent before
                return True
            
            # Check if window expired
            last_sent_time = float(last_sent_ts)
            elapsed = time.time() - last_sent_time
            
            if elapsed >= self.window_seconds:
                return True
            else:
                self._stats["throttled_count"] += 1
                logger.debug(
                    f"[AlertThrottler] Throttled: {alert_key} "
                    f"(elapsed={elapsed:.1f}s, window={self.window_seconds}s)"
                )
                return False
        
        except Exception as e:
            logger.error(f"[AlertThrottler] Redis error: {e}")
            self._stats["redis_errors"] += 1
            
            # Fallback to allowing alert on error (fail-open policy)
            return True
    
    def _mark_sent_redis(self, alert_key: str) -> None:
        """Mark alert as sent in Redis"""
        try:
            redis_key = f"alert_throttle:{alert_key}"
            current_ts = time.time()
            
            # Set with expiration (window + buffer)
            self.redis_client.setex(
                redis_key,
                self.window_seconds + 60,  # Add 60s buffer
                str(current_ts)
            )
        
        except Exception as e:
            logger.error(f"[AlertThrottler] Redis mark_sent error: {e}")
            self._stats["redis_errors"] += 1
    
    def _should_send_memory(self, alert_key: str) -> bool:
        """Check throttle status using in-memory store"""
        current_time = time.time()
        
        if alert_key not in self._memory_store:
            return True
        
        last_sent_time = self._memory_store[alert_key]
        elapsed = current_time - last_sent_time
        
        if elapsed >= self.window_seconds:
            return True
        else:
            self._stats["throttled_count"] += 1
            logger.debug(
                f"[AlertThrottler] Throttled: {alert_key} "
                f"(elapsed={elapsed:.1f}s, window={self.window_seconds}s)"
            )
            return False
    
    def _mark_sent_memory(self, alert_key: str) -> None:
        """Mark alert as sent in memory"""
        self._memory_store[alert_key] = time.time()
    
    def clear(self, alert_key: Optional[str] = None) -> None:
        """
        Clear throttle state
        
        Args:
            alert_key: Specific key to clear, or None to clear all
        """
        if self._use_redis:
            try:
                if alert_key:
                    redis_key = f"alert_throttle:{alert_key}"
                    self.redis_client.delete(redis_key)
                else:
                    # Clear all throttle keys (use with caution)
                    pattern = "alert_throttle:*"
                    for key in self.redis_client.scan_iter(pattern):
                        self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"[AlertThrottler] Redis clear error: {e}")
        else:
            if alert_key:
                self._memory_store.pop(alert_key, None)
            else:
                self._memory_store.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get throttler statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "backend": "redis" if self._use_redis else "memory",
            "window_seconds": self.window_seconds,
            "throttled_count": self._stats["throttled_count"],
            "allowed_count": self._stats["allowed_count"],
            "redis_errors": self._stats["redis_errors"],
            "active_keys": len(self._memory_store) if not self._use_redis else None,
        }
    
    def get_remaining_window(self, alert_key: str) -> Optional[int]:
        """
        Get remaining throttle window for an alert key
        
        Args:
            alert_key: Alert key
        
        Returns:
            Remaining seconds, or None if not throttled
        """
        current_time = time.time()
        
        if self._use_redis:
            try:
                redis_key = f"alert_throttle:{alert_key}"
                last_sent_ts = self.redis_client.get(redis_key)
                
                if last_sent_ts is None:
                    return None
                
                last_sent_time = float(last_sent_ts)
            except Exception as e:
                logger.error(f"[AlertThrottler] Redis get_remaining_window error: {e}")
                return None
        else:
            if alert_key not in self._memory_store:
                return None
            last_sent_time = self._memory_store[alert_key]
        
        elapsed = current_time - last_sent_time
        remaining = self.window_seconds - elapsed
        
        return max(0, int(remaining)) if remaining > 0 else None
