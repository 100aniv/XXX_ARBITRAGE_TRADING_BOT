#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis Client Module (PHASE D – MODULE D2)
==========================================

Redis 기반 캐시 및 헬스 모니터링을 위한 클라이언트.

특징:
- redis-py 지연 import (선택적 의존성)
- 연결 실패 시 graceful fallback
- 키 네이밍 컨벤션 중앙화
- FX 환율 캐시, 헬스 heartbeat 저장
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis 클라이언트 래퍼 (선택적 의존성)
    
    Redis가 설치되지 않았거나 연결 실패 시 graceful fallback.
    """

    def __init__(self, config: Dict):
        """
        Args:
            config: redis 설정 딕셔너리 (config.redis)
        """
        self.enabled = config.get("enabled", False)
        self.url = config.get("url", "redis://localhost:6379/0")
        self.prefix = config.get("prefix", "arb")
        self.health_ttl_seconds = config.get("health_ttl_seconds", 60)
        
        self.client = None
        self.available = False
        
        if self.enabled:
            self._init_connection()
        else:
            logger.info("[RedisClient] Redis disabled in config")

    def _init_connection(self) -> None:
        """Redis 연결 초기화"""
        try:
            import redis
            self.client = redis.from_url(self.url, decode_responses=True)
            # 연결 테스트
            self.client.ping()
            self.available = True
            logger.info(f"[RedisClient] Connected to {self.url} (prefix={self.prefix})")
        except ImportError:
            logger.warning(
                "[RedisClient] redis-py is not installed. "
                "Install it with: pip install redis"
            )
            self.available = False
        except Exception as e:
            logger.warning(f"[RedisClient] Failed to connect to Redis: {e}")
            self.available = False

    def _make_key(self, *parts: str) -> str:
        """키 생성 (프리픽스 포함)
        
        예:
            _make_key("fx", "usdkrw") → "arb:fx:usdkrw"
            _make_key("heartbeat", "paper_runner") → "arb:heartbeat:paper_runner"
        """
        return f"{self.prefix}:{':'.join(parts)}"

    def set_fx_rate(self, symbol: str, value: float, ttl: Optional[int] = None) -> bool:
        """환율 캐시 저장
        
        Args:
            symbol: 환율 쌍 (예: "usdkrw")
            value: 환율 값
            ttl: TTL (초, None이면 무제한)
        
        Returns:
            성공 여부
        """
        if not self.available:
            return False
        
        try:
            key = self._make_key("fx", symbol)
            if ttl:
                self.client.setex(key, ttl, str(value))
            else:
                self.client.set(key, str(value))
            logger.debug(f"[RedisClient] Set FX rate: {key}={value}")
            return True
        except Exception as e:
            logger.warning(f"[RedisClient] Failed to set FX rate: {e}")
            return False

    def get_fx_rate(self, symbol: str) -> Optional[float]:
        """환율 캐시 조회
        
        Args:
            symbol: 환율 쌍 (예: "usdkrw")
        
        Returns:
            환율 값 또는 None
        """
        if not self.available:
            return None
        
        try:
            key = self._make_key("fx", symbol)
            value = self.client.get(key)
            if value:
                logger.debug(f"[RedisClient] Got FX rate from cache: {key}={value}")
                return float(value)
            return None
        except Exception as e:
            logger.warning(f"[RedisClient] Failed to get FX rate: {e}")
            return None

    def set_heartbeat(self, component: str, ttl: Optional[int] = None) -> bool:
        """헬스 체크 heartbeat 저장
        
        Args:
            component: 컴포넌트 이름 (예: "paper_runner", "collector")
            ttl: TTL (초, None이면 config의 health_ttl_seconds 사용)
        
        Returns:
            성공 여부
        """
        if not self.available:
            return False
        
        try:
            key = self._make_key("heartbeat", component)
            timestamp = datetime.now(timezone.utc).isoformat()
            ttl = ttl or self.health_ttl_seconds
            self.client.setex(key, ttl, timestamp)
            logger.debug(f"[RedisClient] Set heartbeat: {key}={timestamp}")
            return True
        except Exception as e:
            logger.warning(f"[RedisClient] Failed to set heartbeat: {e}")
            return False

    def get_heartbeat(self, component: str) -> Optional[datetime]:
        """헬스 체크 heartbeat 조회
        
        Args:
            component: 컴포넌트 이름
        
        Returns:
            마지막 heartbeat 시간 또는 None
        """
        if not self.available:
            return None
        
        try:
            key = self._make_key("heartbeat", component)
            value = self.client.get(key)
            if value:
                logger.debug(f"[RedisClient] Got heartbeat: {key}={value}")
                return datetime.fromisoformat(value)
            return None
        except Exception as e:
            logger.warning(f"[RedisClient] Failed to get heartbeat: {e}")
            return None

    def set_spread_snapshot(self, symbol: str, snapshot: Dict, ttl: int = 60) -> bool:
        """스프레드 스냅샷 저장
        
        Args:
            symbol: 심볼 (예: "BTC")
            snapshot: 스냅샷 데이터 (dict)
            ttl: TTL (초)
        
        Returns:
            성공 여부
        """
        if not self.available:
            return False
        
        try:
            import json
            key = self._make_key("spread", symbol)
            value = json.dumps(snapshot)
            self.client.setex(key, ttl, value)
            logger.debug(f"[RedisClient] Set spread snapshot: {key}")
            return True
        except Exception as e:
            logger.warning(f"[RedisClient] Failed to set spread snapshot: {e}")
            return False

    def get_spread_snapshot(self, symbol: str) -> Optional[Dict]:
        """스프레드 스냅샷 조회
        
        Args:
            symbol: 심볼
        
        Returns:
            스냅샷 데이터 또는 None
        """
        if not self.available:
            return None
        
        try:
            import json
            key = self._make_key("spread", symbol)
            value = self.client.get(key)
            if value:
                logger.debug(f"[RedisClient] Got spread snapshot: {key}")
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"[RedisClient] Failed to get spread snapshot: {e}")
            return None

    def ping(self) -> bool:
        """Redis 연결 테스트
        
        Returns:
            연결 가능 여부
        """
        if not self.available:
            return False
        
        try:
            self.client.ping()
            return True
        except Exception as e:
            logger.warning(f"[RedisClient] Ping failed: {e}")
            return False

    def close(self) -> None:
        """Redis 연결 종료"""
        if self.client:
            try:
                self.client.close()
                logger.info("[RedisClient] Connection closed")
            except Exception as e:
                logger.warning(f"[RedisClient] Failed to close connection: {e}")


# 글로벌 Redis 클라이언트 인스턴스 (선택적)
_redis_client: Optional[RedisClient] = None


def get_redis_client(config: Dict) -> RedisClient:
    """Redis 클라이언트 싱글톤 반환
    
    Args:
        config: 전체 설정 딕셔너리
    
    Returns:
        RedisClient 인스턴스
    """
    global _redis_client
    if _redis_client is None:
        redis_cfg = config.get("redis", {})
        _redis_client = RedisClient(redis_cfg)
    return _redis_client


def reset_redis_client() -> None:
    """Redis 클라이언트 리셋 (테스트용)"""
    global _redis_client
    if _redis_client:
        _redis_client.close()
    _redis_client = None
