"""
D98-0: LIVE 모드 안전장치 (Fail-Closed)

실수로도 LIVE 모드가 실행되지 않도록 다층 안전장치 구현.
기본 동작: LIVE 모드 시도 시 즉시 종료.
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from arbitrage.config.settings import get_settings


class LiveSafetyError(Exception):
    """LIVE 모드 안전 검증 실패"""
    pass


class LiveSafetyValidator:
    """
    LIVE 모드 실행을 위한 안전 검증기.
    
    Fail-Closed 원칙:
    - 기본값은 항상 거부
    - 모든 조건을 명시적으로 만족해야만 허용
    """
    
    # 필수 환경변수
    ENV_ARM_ACK = "LIVE_ARM_ACK"
    ENV_ARM_AT = "LIVE_ARM_AT"
    ENV_MAX_NOTIONAL = "LIVE_MAX_NOTIONAL_USD"
    
    # 검증 상수
    REQUIRED_ACK = "I_UNDERSTAND_LIVE_RISK"
    MAX_ARM_AGE_SECONDS = 600  # 10분
    MIN_NOTIONAL_USD = 10.0
    MAX_NOTIONAL_USD = 1000.0  # 초기 상한
    
    def __init__(self):
        self.settings = get_settings()
        
    def validate_live_mode(self) -> Tuple[bool, str]:
        """
        LIVE 모드 실행 가능 여부 검증.
        
        Returns:
            (is_valid, error_message)
            - is_valid: True면 LIVE 실행 가능, False면 차단
            - error_message: 실패 시 사유, 성공 시 빈 문자열
        """
        # 1. 환경 확인
        if self.settings.env != "live":
            # PAPER 모드는 항상 허용
            return True, ""
        
        # 2. LIVE 모드 진입 시도 감지
        # 기본 동작: 거부
        
        # 3. ARM ACK 확인
        ack = os.getenv(self.ENV_ARM_ACK)
        if ack != self.REQUIRED_ACK:
            return False, (
                f"LIVE 모드 차단: {self.ENV_ARM_ACK} 환경변수가 올바르지 않습니다.\n"
                f"필수값: '{self.REQUIRED_ACK}'\n"
                f"현재값: '{ack}'\n"
                f"LIVE 모드는 명시적 확인 없이 실행할 수 없습니다."
            )
        
        # 4. ARM AT (타임스탬프) 확인
        arm_at = os.getenv(self.ENV_ARM_AT)
        if not arm_at:
            return False, (
                f"LIVE 모드 차단: {self.ENV_ARM_AT} 환경변수가 설정되지 않았습니다.\n"
                f"UTC 타임스탬프(초)를 설정해야 합니다.\n"
                f"예: export {self.ENV_ARM_AT}=$(date +%s)"
            )
        
        try:
            arm_timestamp = int(arm_at)
        except ValueError:
            return False, (
                f"LIVE 모드 차단: {self.ENV_ARM_AT} 값이 유효한 타임스탬프가 아닙니다.\n"
                f"현재값: '{arm_at}'"
            )
        
        # 5. ARM 타임스탬프 유효성 (10분 이내)
        now_timestamp = int(time.time())
        age_seconds = now_timestamp - arm_timestamp
        
        if age_seconds < 0:
            return False, (
                f"LIVE 모드 차단: {self.ENV_ARM_AT} 타임스탬프가 미래입니다.\n"
                f"현재: {now_timestamp}, ARM: {arm_timestamp}"
            )
        
        if age_seconds > self.MAX_ARM_AGE_SECONDS:
            return False, (
                f"LIVE 모드 차단: {self.ENV_ARM_AT} 타임스탬프가 너무 오래되었습니다.\n"
                f"경과 시간: {age_seconds}초 (최대: {self.MAX_ARM_AGE_SECONDS}초)\n"
                f"LIVE 모드는 10분 이내에 실행해야 합니다.\n"
                f"새로운 타임스탬프를 설정하세요."
            )
        
        # 6. MAX NOTIONAL 확인
        max_notional = os.getenv(self.ENV_MAX_NOTIONAL)
        if not max_notional:
            return False, (
                f"LIVE 모드 차단: {self.ENV_MAX_NOTIONAL} 환경변수가 설정되지 않았습니다.\n"
                f"최대 거래 금액(USD)을 명시해야 합니다.\n"
                f"허용 범위: {self.MIN_NOTIONAL_USD} ~ {self.MAX_NOTIONAL_USD}"
            )
        
        try:
            max_notional_value = float(max_notional)
        except ValueError:
            return False, (
                f"LIVE 모드 차단: {self.ENV_MAX_NOTIONAL} 값이 유효한 숫자가 아닙니다.\n"
                f"현재값: '{max_notional}'"
            )
        
        if max_notional_value < self.MIN_NOTIONAL_USD:
            return False, (
                f"LIVE 모드 차단: {self.ENV_MAX_NOTIONAL} 값이 너무 작습니다.\n"
                f"현재값: ${max_notional_value:.2f}\n"
                f"최소값: ${self.MIN_NOTIONAL_USD:.2f}"
            )
        
        if max_notional_value > self.MAX_NOTIONAL_USD:
            return False, (
                f"LIVE 모드 차단: {self.ENV_MAX_NOTIONAL} 값이 너무 큽니다.\n"
                f"현재값: ${max_notional_value:.2f}\n"
                f"최대값: ${self.MAX_NOTIONAL_USD:.2f}"
            )
        
        # 7. 모든 검증 통과
        return True, ""
    
    def enforce_live_mode_safety(self) -> None:
        """
        LIVE 모드 안전 검증 강제 실행.
        검증 실패 시 LiveSafetyError 예외 발생.
        """
        is_valid, error_message = self.validate_live_mode()
        
        if not is_valid:
            raise LiveSafetyError(error_message)


def check_live_mode_safety() -> None:
    """
    LIVE 모드 안전 검증 (프로그램 진입점에서 호출).
    
    검증 실패 시 LiveSafetyError 예외 발생.
    """
    validator = LiveSafetyValidator()
    validator.enforce_live_mode_safety()


def is_live_mode_armed() -> bool:
    """
    LIVE 모드 ARM 상태 확인.
    
    Returns:
        True: LIVE 모드 실행 가능
        False: LIVE 모드 차단됨
    """
    validator = LiveSafetyValidator()
    is_valid, _ = validator.validate_live_mode()
    return is_valid
