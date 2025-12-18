# -*- coding: utf-8 -*-
"""
D98-1: Read-only Guard (실주문 0건 강제 보장)

실계좌 주문 생성/취소/출금을 하드 블락하는 안전장치.
Fail-Closed 원칙: 기본값으로 모든 거래 함수를 차단.
"""

import os
import logging
from typing import Optional
from functools import wraps

logger = logging.getLogger(__name__)


class ReadOnlyError(Exception):
    """
    Read-only 모드에서 거래 함수 호출 시 발생하는 예외.
    
    실주문/취소/출금 함수가 호출되면 즉시 이 예외를 발생시켜 차단.
    """
    pass


class ReadOnlyGuard:
    """
    Read-only Guard (거래 함수 하드 블락)
    
    환경변수 READ_ONLY_ENFORCED를 통해 제어:
    - true (기본값): 모든 거래 함수 차단 (Fail-Closed)
    - false: 정상 동작 (PAPER 모드에서만 허용)
    
    차단 대상:
    - create_order (주문 생성)
    - cancel_order (주문 취소)
    - withdraw (출금, 구현 시)
    
    허용 대상:
    - get_orderbook (조회)
    - get_balance (조회)
    - get_open_positions (조회)
    - get_order_status (조회)
    
    Usage:
        from arbitrage.config.readonly_guard import enforce_readonly
        
        @enforce_readonly
        def create_order(self, ...):
            # 이 함수는 READ_ONLY_ENFORCED=true일 때 실행 불가
            pass
    """
    
    ENV_READ_ONLY = "READ_ONLY_ENFORCED"
    
    def __init__(self):
        """
        ReadOnlyGuard 초기화.
        
        환경변수 READ_ONLY_ENFORCED를 읽어 read-only 모드 여부 결정.
        기본값: true (Fail-Closed)
        """
        self._is_read_only = self._load_read_only_setting()
        
        if self._is_read_only:
            logger.warning(
                f"[D98-1_READONLY_GUARD] Read-only mode ENABLED. "
                f"All trading functions (create_order, cancel_order, withdraw) are BLOCKED."
            )
        else:
            logger.info(
                f"[D98-1_READONLY_GUARD] Read-only mode DISABLED. "
                f"Trading functions are allowed (use with caution)."
            )
    
    def _load_read_only_setting(self) -> bool:
        """
        환경변수에서 READ_ONLY_ENFORCED 설정 로드.
        
        Returns:
            bool: True면 read-only 모드 (거래 차단), False면 정상 모드
        
        Note:
            기본값은 true (Fail-Closed 원칙)
            false로 설정하려면 명시적으로 환경변수 설정 필요
        """
        env_value = os.getenv(self.ENV_READ_ONLY, "true").lower().strip()
        
        # "false", "no", "0" 이외는 모두 true로 처리 (Fail-Closed)
        is_read_only = env_value not in ["false", "no", "0"]
        
        return is_read_only
    
    def check_readonly(self, operation: str) -> None:
        """
        Read-only 모드 체크.
        
        Args:
            operation: 작업 이름 (예: "create_order", "cancel_order")
        
        Raises:
            ReadOnlyError: read-only 모드일 때 거래 함수 호출 시
        """
        if self._is_read_only:
            error_msg = (
                f"[D98-1_READONLY_GUARD] BLOCKED: {operation} is not allowed in READ_ONLY mode. "
                f"Set {self.ENV_READ_ONLY}=false to enable trading (PAPER mode only)."
            )
            logger.error(error_msg)
            raise ReadOnlyError(error_msg)
    
    @property
    def is_read_only(self) -> bool:
        """Read-only 모드 여부 반환"""
        return self._is_read_only


# Global instance (singleton)
_guard_instance: Optional[ReadOnlyGuard] = None


def get_readonly_guard() -> ReadOnlyGuard:
    """
    ReadOnlyGuard 싱글톤 인스턴스 반환.
    
    Returns:
        ReadOnlyGuard 인스턴스
    """
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = ReadOnlyGuard()
    return _guard_instance


def enforce_readonly(func):
    """
    Read-only Guard 데코레이터.
    
    거래 함수에 이 데코레이터를 적용하면,
    READ_ONLY_ENFORCED=true일 때 함수 실행이 차단됨.
    
    Usage:
        @enforce_readonly
        def create_order(self, ...):
            pass
    
    Args:
        func: 차단할 거래 함수
    
    Returns:
        Wrapped function
    
    Raises:
        ReadOnlyError: read-only 모드일 때 호출 시
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        guard = get_readonly_guard()
        operation = func.__name__
        guard.check_readonly(operation)
        
        # Read-only 체크 통과 시 원본 함수 실행
        return func(*args, **kwargs)
    
    return wrapper


def is_readonly_mode() -> bool:
    """
    현재 read-only 모드 여부 반환.
    
    Returns:
        bool: True면 read-only 모드 (거래 차단)
    """
    guard = get_readonly_guard()
    return guard.is_read_only


def set_readonly_mode(enabled: bool) -> None:
    """
    Read-only 모드 강제 설정 (테스트용).
    
    Args:
        enabled: True면 read-only 모드 활성화, False면 비활성화
    
    Warning:
        이 함수는 테스트 목적으로만 사용해야 함.
        프로덕션에서는 환경변수로 제어할 것.
    """
    global _guard_instance
    _guard_instance = None  # Reset singleton
    os.environ[ReadOnlyGuard.ENV_READ_ONLY] = "true" if enabled else "false"
    _guard_instance = ReadOnlyGuard()
    
    logger.warning(
        f"[D98-1_READONLY_GUARD] Read-only mode forcibly set to: {enabled} "
        f"(for testing only)"
    )
