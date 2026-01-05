"""
D205-11-2: Redis Latency Wrapper Unit Tests

목적:
- RedisLatencyWrapper 기능 검증
- LatencyProfiler 연동 확인
- REDIS_READ/WRITE stage 계측 검증

Author: arbitrage-lite V2
Date: 2026-01-05
"""

import pytest
from unittest.mock import Mock, MagicMock
from arbitrage.v2.storage.redis_latency_wrapper import RedisLatencyWrapper, RedisPipelineWrapper
from arbitrage.v2.observability.latency_profiler import LatencyProfiler, LatencyStage


class TestRedisLatencyWrapper:
    """Redis Latency Wrapper 테스트"""
    
    def test_get_with_profiler(self):
        """GET with profiler enabled"""
        mock_redis = Mock()
        mock_redis.get.return_value = b"value"
        profiler = LatencyProfiler(enabled=True)
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler)
        result = wrapper.get("key")
        
        assert result == b"value"
        mock_redis.get.assert_called_once_with("key")
        
        stats = profiler.stats.get(LatencyStage.REDIS_READ)
        assert stats is not None
        assert stats.count == 1
    
    def test_get_without_profiler(self):
        """GET without profiler (no-op)"""
        mock_redis = Mock()
        mock_redis.get.return_value = b"value"
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler=None)
        result = wrapper.get("key")
        
        assert result == b"value"
        mock_redis.get.assert_called_once_with("key")
    
    def test_set_with_profiler(self):
        """SET with profiler enabled"""
        mock_redis = Mock()
        mock_redis.set.return_value = True
        profiler = LatencyProfiler(enabled=True)
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler)
        result = wrapper.set("key", "value")
        
        assert result is True
        mock_redis.set.assert_called_once_with("key", "value", ex=None)
        
        stats = profiler.stats.get(LatencyStage.REDIS_WRITE)
        assert stats is not None
        assert stats.count == 1
    
    def test_incr_with_profiler(self):
        """INCR with profiler enabled"""
        mock_redis = Mock()
        mock_redis.incr.return_value = 5
        profiler = LatencyProfiler(enabled=True)
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler)
        result = wrapper.incr("counter", 1)
        
        assert result == 5
        mock_redis.incr.assert_called_once_with("counter", 1)
        
        stats = profiler.stats.get(LatencyStage.REDIS_WRITE)
        assert stats is not None
        assert stats.count == 1
    
    def test_mget_with_profiler(self):
        """MGET with profiler enabled"""
        mock_redis = Mock()
        mock_redis.mget.return_value = [b"val1", b"val2"]
        profiler = LatencyProfiler(enabled=True)
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler)
        result = wrapper.mget(["key1", "key2"])
        
        assert result == [b"val1", b"val2"]
        mock_redis.mget.assert_called_once_with(["key1", "key2"])
        
        stats = profiler.stats.get(LatencyStage.REDIS_READ)
        assert stats is not None
        assert stats.count == 1
    
    def test_pipeline_execute(self):
        """Pipeline execute with profiler enabled"""
        mock_pipe = Mock()
        mock_pipe.execute.return_value = [True, True]
        mock_redis = Mock()
        mock_redis.pipeline.return_value = mock_pipe
        profiler = LatencyProfiler(enabled=True)
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler)
        pipe = wrapper.pipeline()
        pipe.set("key1", "val1")
        pipe.incr("key2")
        result = pipe.execute()
        
        assert result == [True, True]
        mock_pipe.set.assert_called_once()
        mock_pipe.incr.assert_called_once()
        mock_pipe.execute.assert_called_once()
        
        stats = profiler.stats.get(LatencyStage.REDIS_WRITE)
        assert stats is not None
        assert stats.count == 1
    
    def test_delete_with_profiler(self):
        """DELETE with profiler enabled"""
        mock_redis = Mock()
        mock_redis.delete.return_value = 2
        profiler = LatencyProfiler(enabled=True)
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler)
        result = wrapper.delete("key1", "key2")
        
        assert result == 2
        mock_redis.delete.assert_called_once_with("key1", "key2")
        
        stats = profiler.stats.get(LatencyStage.REDIS_WRITE)
        assert stats is not None
        assert stats.count == 1
    
    def test_profiler_disabled(self):
        """Profiler disabled (no overhead)"""
        mock_redis = Mock()
        mock_redis.get.return_value = b"value"
        profiler = LatencyProfiler(enabled=False)
        
        wrapper = RedisLatencyWrapper(mock_redis, profiler)
        result = wrapper.get("key")
        
        assert result == b"value"
        
        stats = profiler.stats.get(LatencyStage.REDIS_READ)
        assert stats is None or stats.count == 0
