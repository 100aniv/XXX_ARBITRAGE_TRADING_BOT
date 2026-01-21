"""
Metrics Collector for D72-4 Logging & Monitoring MVP

Real-time metrics collection with rolling window aggregation.
Stores metrics in Redis for fast access.
"""

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Deque
from dataclasses import dataclass, field

import redis


@dataclass
class MetricsSample:
    """Single metrics sample"""
    timestamp: float
    trades_count: int = 0
    errors_count: int = 0
    ws_latency_ms: float = 0.0
    loop_latency_ms: float = 0.0
    guard_triggers: int = 0
    pnl_change: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "trades_count": self.trades_count,
            "errors_count": self.errors_count,
            "ws_latency_ms": self.ws_latency_ms,
            "loop_latency_ms": self.loop_latency_ms,
            "guard_triggers": self.guard_triggers,
            "pnl_change": self.pnl_change
        }


class MetricsCollector:
    """
    Real-time metrics collector with rolling window
    
    Collects and aggregates metrics over a 60-second window.
    Updates are pushed to Redis for real-time monitoring.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        env: str = "development",
        session_id: Optional[str] = None,
        window_seconds: int = 60
    ):
        self.redis = redis_client
        self.env = env
        self.session_id = session_id
        self.window_seconds = window_seconds
        
        # Rolling window buffer
        self.samples: Deque[MetricsSample] = deque(maxlen=window_seconds)
        
        # Current sample (accumulates until flush)
        self.current_sample = MetricsSample(timestamp=time.time())
        
        # Last flush time
        self.last_flush = time.time()
        
        # Redis keys
        self.metrics_key = self._build_key()
        self.timeseries_key = f"{self.metrics_key}:timeseries"
    
    def _build_key(self) -> str:
        """Build Redis key for metrics"""
        base = f"arbitrage:metrics:{self.env}"
        if self.session_id:
            return f"{base}:{self.session_id}"
        return base
    
    def record_trade(self):
        """Record a trade execution"""
        self.current_sample.trades_count += 1
    
    def record_error(self):
        """Record an error"""
        self.current_sample.errors_count += 1
    
    def record_ws_latency(self, latency_ms: float):
        """Record WebSocket latency"""
        self.current_sample.ws_latency_ms = latency_ms
    
    def record_loop_latency(self, latency_ms: float):
        """Record main loop latency"""
        self.current_sample.loop_latency_ms = latency_ms
    
    def record_guard_trigger(self):
        """Record a guard trigger event"""
        self.current_sample.guard_triggers += 1
    
    def record_pnl_change(self, pnl_change: float):
        """Record PnL change"""
        self.current_sample.pnl_change = pnl_change
    
    def flush(self):
        """Flush current sample to Redis and rolling window"""
        now = time.time()
        
        # Update timestamp
        self.current_sample.timestamp = now
        
        # Add to rolling window
        self.samples.append(self.current_sample)
        
        # Push to Redis
        self._push_to_redis()
        
        # Reset current sample
        self.current_sample = MetricsSample(timestamp=now)
        self.last_flush = now
    
    def _push_to_redis(self):
        """Push aggregated metrics to Redis"""
        try:
            # Calculate aggregated metrics
            aggregated = self._aggregate_window()
            
            # Store as hash
            self.redis.hset(self.metrics_key, mapping=aggregated)
            self.redis.expire(self.metrics_key, 300)  # 5 minutes TTL
            
            # Add to timeseries (for historical view)
            self.redis.zadd(
                self.timeseries_key,
                {f"{time.time()}:{self.current_sample.trades_count}": time.time()}
            )
            self.redis.expire(self.timeseries_key, 3600)  # 1 hour TTL
            
        except Exception as e:
            print(f"[MetricsCollector] Failed to push to Redis: {e}")
    
    def _aggregate_window(self) -> Dict[str, str]:
        """Aggregate metrics over rolling window"""
        if not self.samples:
            return {
                "trades_per_minute": "0",
                "errors_per_minute": "0",
                "avg_ws_latency_ms": "0.0",
                "avg_loop_latency_ms": "0.0",
                "guard_triggers_per_minute": "0",
                "pnl_change_1min": "0.0",
                "sample_count": "0"
            }
        
        total_trades = sum(s.trades_count for s in self.samples)
        total_errors = sum(s.errors_count for s in self.samples)
        total_guard = sum(s.guard_triggers for s in self.samples)
        total_pnl = sum(s.pnl_change for s in self.samples)
        
        # Average latencies (only count non-zero values)
        ws_latencies = [s.ws_latency_ms for s in self.samples if s.ws_latency_ms > 0]
        loop_latencies = [s.loop_latency_ms for s in self.samples if s.loop_latency_ms > 0]
        
        avg_ws = sum(ws_latencies) / len(ws_latencies) if ws_latencies else 0.0
        avg_loop = sum(loop_latencies) / len(loop_latencies) if loop_latencies else 0.0
        
        return {
            "trades_per_minute": str(total_trades),
            "errors_per_minute": str(total_errors),
            "avg_ws_latency_ms": f"{avg_ws:.2f}",
            "avg_loop_latency_ms": f"{avg_loop:.2f}",
            "guard_triggers_per_minute": str(total_guard),
            "pnl_change_1min": f"{total_pnl:.2f}",
            "sample_count": str(len(self.samples)),
            "last_update": datetime.now(timezone.utc).isoformat()
        }
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current aggregated metrics"""
        return {
            k: v for k, v in self._aggregate_window().items()
        }
    
    def should_flush(self) -> bool:
        """Check if it's time to flush"""
        return (time.time() - self.last_flush) >= 1.0  # Flush every second


class MetricsAggregator:
    """
    Multi-session metrics aggregator
    
    Aggregates metrics across multiple sessions for system-wide view.
    """
    
    def __init__(self, redis_client: redis.Redis, env: str = "development"):
        self.redis = redis_client
        self.env = env
        self.base_key = f"arbitrage:metrics:{env}"
    
    def get_all_session_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all active sessions"""
        try:
            # Find all session metric keys (exclude timeseries keys)
            pattern = f"{self.base_key}:*"
            keys = self.redis.keys(pattern)
            
            metrics = {}
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode()
                
                # Skip timeseries keys
                if key.endswith(':timeseries'):
                    continue
                
                session_id = key.split(":")[-1]
                
                # Check if key is a hash (not a stream or other type)
                key_type = self.redis.type(key)
                if key_type != 'hash':
                    continue
                
                session_metrics = self.redis.hgetall(key)
                
                if session_metrics:
                    metrics[session_id] = {
                        k.decode() if isinstance(k, bytes) else k: 
                        v.decode() if isinstance(v, bytes) else v
                        for k, v in session_metrics.items()
                    }
            
            return metrics
        except Exception as e:
            print(f"[MetricsAggregator] Failed to get session metrics: {e}")
            return {}
    
    def get_system_summary(self) -> Dict[str, Any]:
        """Get system-wide metrics summary"""
        all_metrics = self.get_all_session_metrics()
        
        if not all_metrics:
            return {
                "total_sessions": 0,
                "total_trades_per_minute": 0,
                "total_errors_per_minute": 0,
                "avg_loop_latency_ms": 0.0
            }
        
        total_trades = sum(
            int(m.get("trades_per_minute", 0))
            for m in all_metrics.values()
        )
        total_errors = sum(
            int(m.get("errors_per_minute", 0))
            for m in all_metrics.values()
        )
        
        # Average loop latency across sessions
        latencies = [
            float(m.get("avg_loop_latency_ms", 0))
            for m in all_metrics.values()
            if float(m.get("avg_loop_latency_ms", 0)) > 0
        ]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        return {
            "total_sessions": len(all_metrics),
            "total_trades_per_minute": total_trades,
            "total_errors_per_minute": total_errors,
            "avg_loop_latency_ms": round(avg_latency, 2)
        }
