import logging
from typing import Optional, Any, List
from arbitrage.v2.observability.latency_profiler import LatencyProfiler, LatencyStage

logger = logging.getLogger(__name__)


class RedisLatencyWrapper:
    def __init__(self, redis_client: Any, profiler: Optional[LatencyProfiler] = None):
        self.redis = redis_client
        self.profiler = profiler
        self._enabled = profiler is not None and profiler.enabled
    
    def get(self, key: str):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_READ)
        try:
            return self.redis.get(key)
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_READ)
    
    def set(self, key: str, value: Any, ex: Optional[int] = None):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_WRITE)
        try:
            return self.redis.set(key, value, ex=ex)
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_WRITE)
    
    def incr(self, key: str, amount: int = 1):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_WRITE)
        try:
            return self.redis.incr(key, amount)
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_WRITE)
    
    def mget(self, keys: List[str]):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_READ)
        try:
            return self.redis.mget(keys)
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_READ)
    
    def delete(self, *keys: str):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_WRITE)
        try:
            return self.redis.delete(*keys)
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_WRITE)
    
    def decr(self, key: str, amount: int = 1):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_WRITE)
        try:
            return self.redis.decr(key, amount)
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_WRITE)
    
    def hget(self, name: str, key: str):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_READ)
        try:
            return self.redis.hget(name, key)
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_READ)
    
    def pipeline(self):
        return RedisPipelineWrapper(self.redis.pipeline(), self.profiler)


class RedisPipelineWrapper:
    def __init__(self, pipeline: Any, profiler: Optional[LatencyProfiler] = None):
        self.pipe = pipeline
        self.profiler = profiler
        self._enabled = profiler is not None and profiler.enabled
    
    def set(self, key: str, value: Any, ex: Optional[int] = None):
        self.pipe.set(key, value, ex=ex)
        return self
    
    def incr(self, key: str, amount: int = 1):
        self.pipe.incr(key, amount)
        return self
    
    def decr(self, key: str, amount: int = 1):
        self.pipe.decr(key, amount)
        return self
    
    def delete(self, *keys: str):
        self.pipe.delete(*keys)
        return self
    
    def execute(self):
        if self._enabled:
            self.profiler.start_span(LatencyStage.REDIS_WRITE)
        try:
            return self.pipe.execute()
        finally:
            if self._enabled:
                self.profiler.end_span(LatencyStage.REDIS_WRITE)
