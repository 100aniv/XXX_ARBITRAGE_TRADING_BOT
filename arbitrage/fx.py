#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FX Normalization Module
=======================
환율 관리 및 정규화 (TTL 캐싱 포함)

책임:
- USD/KRW 환율 조회 (정적값 기반)
- TTL 기반 캐싱으로 API 호출 과도 방지
- Failsafe: 환율이 0이거나 급등락 시 최근 값 유지
- 향후 외부 API/DB 연동을 위한 인터페이스 제공

PHASE C: 정적 환율 + TTL 캐싱
PHASE D: API/DB 연동 구현 예정
"""

import logging
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger("arbitrage.fx")

# 글로벌 FX 캐시 (모듈 레벨)
_fx_cache: Dict[str, Tuple[float, float]] = {}  # key -> (value, timestamp)

# Redis 클라이언트 (선택적, PHASE D2)
_redis_client: Optional[object] = None


def get_usdkrw(config: Dict) -> float:
    """USD/KRW 환율 조회 (TTL 캐싱 포함)
    
    Args:
        config: 글로벌 설정 딕셔너리
    
    Returns:
        float: USD/KRW 환율
    
    동작:
    - TTL 내 캐시 존재: 캐시값 반환
    - TTL 만료 또는 캐시 없음: 새로 조회
    - mode == "static": config.fx.usdkrw 반환
    - 오류 시: 기본값 1350.0 반환
    """
    try:
        fx_config = config.get("fx", {})
        ttl_seconds = float(fx_config.get("ttl_seconds", 3.0))
        
        # 캐시 확인
        cache_key = "usdkrw"
        now = time.time()
        
        if cache_key in _fx_cache:
            cached_value, cached_time = _fx_cache[cache_key]
            if now - cached_time < ttl_seconds:
                logger.debug("fx_cache_hit usdkrw=%.2f age=%.2fs", cached_value, now - cached_time)
                return cached_value
        
        # 캐시 미스 또는 TTL 만료: 새로 조회
        mode = fx_config.get("mode", "static")
        
        if mode == "static":
            usdkrw = float(fx_config.get("usdkrw", 1350.0))
            
            # Failsafe: 환율이 0이거나 비정상적으로 크면 최근 값 유지
            if usdkrw <= 0:
                logger.warning("fx_invalid_rate usdkrw=%.2f, using cached value", usdkrw)
                if cache_key in _fx_cache:
                    return _fx_cache[cache_key][0]
                usdkrw = 1350.0
            
            # 캐시 저장
            _fx_cache[cache_key] = (usdkrw, now)
            
            # Redis에 발행 (PHASE D2 – 선택적)
            _publish_fx_to_redis(config, "usdkrw", usdkrw)
            
            logger.debug("fx_mode=static usdkrw=%.2f ttl=%.1fs", usdkrw, ttl_seconds)
            return usdkrw
        
        # 다른 모드는 아직 미구현 (PHASE D 이후)
        logger.warning(
            "fx_mode=%s not implemented in PHASE C, fallback to static mode",
            mode
        )
        usdkrw = float(fx_config.get("usdkrw", 1350.0))
        _fx_cache[cache_key] = (usdkrw, now)
        return usdkrw
    
    except (KeyError, TypeError, ValueError) as e:
        logger.error("fx_config_error: %s, using default 1350.0", str(e))
        return 1350.0


def _publish_fx_to_redis(config: Dict, symbol: str, value: float) -> None:
    """FX 환율을 Redis에 발행 (PHASE D2 – 선택적)
    
    Args:
        config: 글로벌 설정 딕셔너리
        symbol: 환율 쌍 (예: "usdkrw")
        value: 환율 값
    """
    global _redis_client
    
    redis_cfg = config.get("redis", {})
    if not redis_cfg.get("enabled", False):
        return
    
    try:
        # Redis 클라이언트 초기화 (첫 호출 시)
        if _redis_client is None:
            from arbitrage.redis_client import get_redis_client
            _redis_client = get_redis_client(config)
        
        # Redis에 발행
        if _redis_client and _redis_client.available:
            ttl = redis_cfg.get("health_ttl_seconds", 60)
            _redis_client.set_fx_rate(symbol, value, ttl=ttl)
    except Exception as e:
        logger.debug(f"Failed to publish FX to Redis: {e}")


def clear_fx_cache() -> None:
    """FX 캐시 초기화 (테스트용)"""
    global _fx_cache
    _fx_cache.clear()
    logger.debug("fx_cache cleared")


def get_cache_info() -> Dict:
    """캐시 상태 조회 (디버깅용)
    
    Returns:
        dict: 캐시 정보 {key: (value, age_seconds), ...}
    """
    now = time.time()
    info = {}
    for key, (value, timestamp) in _fx_cache.items():
        age = now - timestamp
        info[key] = {"value": value, "age_seconds": age}
    return info


# ============================================================================
# 향후 확장 함수 (PHASE D 이후)
# ============================================================================

def fetch_usdkrw_from_upbit(symbol: str = "USDT-KRW") -> Optional[float]:
    """업비트에서 USDT/KRW 환율 조회 (PHASE D)
    
    Args:
        symbol: 업비트 심볼 (기본값: USDT-KRW)
    
    Returns:
        float or None: 환율 또는 None (실패 시)
    
    TODO: PHASE D에서 구현
    - 업비트 REST API 호출
    - USDT-KRW 현물 시세 조회
    - 에러 처리 및 재시도 로직
    """
    raise NotImplementedError("Upbit 기반 환율 조회는 PHASE D에서 구현 예정")


def fetch_usdkrw_from_api(api_url: str, timeout: int = 5) -> Optional[float]:
    """외부 API에서 환율 조회 (PHASE D)
    
    Args:
        api_url: 환율 API URL
        timeout: 타임아웃 (초)
    
    Returns:
        float or None: 환율 또는 None (실패 시)
    
    TODO: PHASE D에서 구현
    - requests 라이브러리 사용
    - 에러 처리 및 재시도 로직
    - 응답 파싱 및 검증
    """
    raise NotImplementedError("API 기반 환율 조회는 PHASE D에서 구현 예정")


def fetch_usdkrw_from_db(db_connection) -> Optional[float]:
    """데이터베이스에서 환율 조회 (PHASE D)
    
    Args:
        db_connection: DB 연결 객체
    
    Returns:
        float or None: 환율 또는 None (실패 시)
    
    TODO: PHASE D에서 구현
    - DB 쿼리 실행
    - 최신 환율 레코드 조회
    - 타임스탬프 검증
    """
    raise NotImplementedError("DB 기반 환율 조회는 PHASE D에서 구현 예정")
