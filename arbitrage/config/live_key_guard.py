# -*- coding: utf-8 -*-
"""
D98-4: Live Key Guard
=====================

테스트/개발/페이퍼 환경에서 실수로 REAL(LIVE) API Key를 로드하거나
주문이 나가는 사고를 구조적으로 차단하는 모듈.

Defense-in-Depth Architecture:
- Layer 0 (D98-4): Live Key Guard - 키 로딩 시점 차단
- Layer 1 (D98-3): Executor Guard - 주문 실행 시점 차단
- Layer 2 (D98-2): Adapter Guard - API 호출 시점 차단

Usage:
------
```python
from arbitrage.config.live_key_guard import validate_live_keys

# Settings.from_env()에서 호출
validate_live_keys(
    env=RuntimeEnv.PAPER,
    live_enabled=False,
    upbit_access_key="some_key",
    binance_api_key="some_key"
)
```

Environment Rules:
------------------
1. ARBITRAGE_ENV=live + LIVE_ENABLED=true → LIVE 키 허용
2. ARBITRAGE_ENV=paper → PAPER 키만 허용 (LIVE 키 차단)
3. ARBITRAGE_ENV=local_dev → Mock 키 허용 (실제 키 불필요)

Key Safety:
-----------
- Fail-Closed: 의심스러운 키는 즉시 차단
- Explicit Allow: LIVE_ENABLED=true가 명시되어야만 LIVE 키 허용
- Logging: 모든 키 로딩 시도를 로깅 (키 값은 로깅 안 함)
"""

import os
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class RuntimeEnv(str, Enum):
    """Runtime environment"""
    LOCAL_DEV = "local_dev"
    PAPER = "paper"
    LIVE = "live"


class LiveKeyError(Exception):
    """
    LIVE API Key 관련 오류.
    
    테스트/개발/페이퍼 환경에서 LIVE 키가 감지되었을 때 발생.
    """
    pass


def is_live_mode_allowed() -> bool:
    """
    LIVE 모드 허용 여부 확인.
    
    Returns:
        bool: LIVE_ENABLED=true이고 ARBITRAGE_ENV=live일 때만 True
    
    Notes:
        - Fail-Closed 원칙: 명시적으로 허용되지 않으면 차단
        - LIVE_ENABLED 기본값: false
    """
    live_enabled_str = os.getenv("LIVE_ENABLED", "false").lower()
    live_enabled = live_enabled_str in ("true", "1", "yes")
    
    env_str = os.getenv("ARBITRAGE_ENV", "local_dev").lower()
    
    # LIVE_ENABLED=true이고 ARBITRAGE_ENV=live일 때만 허용
    return live_enabled and env_str == "live"


def detect_live_key(
    key_name: str,
    key_value: Optional[str],
    env: RuntimeEnv
) -> bool:
    """
    LIVE 키 감지 (휴리스틱 기반).
    
    Args:
        key_name: 키 이름 (예: "UPBIT_ACCESS_KEY")
        key_value: 키 값
        env: 현재 환경
    
    Returns:
        bool: LIVE 키로 의심되면 True
    
    Detection Rules:
        1. 키가 비어있거나 None → False (Mock 모드)
        2. 테스트/예제 키 패턴 → False (안전)
        3. Paper 환경 + 실제 키 → True (LIVE 키 의심)
        4. Local_dev 환경 + 실제 키 → True (LIVE 키 의심)
    
    Notes:
        - False Positive 허용 (의심스러우면 차단)
        - False Negative 방지 (LIVE 키는 놓치지 않음)
    """
    if not key_value:
        # 키가 없으면 Mock 모드
        return False
    
    key_value_lower = key_value.lower()
    
    # 테스트/예제 키 패턴 (안전)
    safe_patterns = [
        "your_",           # your_upbit_access_key_here
        "test",            # test_key_123
        "mock",            # mock_api_key
        "example",         # example_key
        "dummy",           # dummy_secret
        "fake",            # fake_api_key
        "sample",          # sample_key
        "placeholder",     # placeholder_key
    ]
    
    for pattern in safe_patterns:
        if pattern in key_value_lower:
            logger.debug(f"[D98-4_LIVE_KEY_GUARD] {key_name}: 안전한 테스트 키 패턴 감지 ('{pattern}')")
            return False
    
    # Paper/Local_dev 환경에서 실제 키처럼 보이는 값 → LIVE 키 의심
    if env in (RuntimeEnv.PAPER, RuntimeEnv.LOCAL_DEV):
        # 실제 키는 보통 영숫자 혼합, 일정 길이 이상
        if len(key_value) >= 20 and any(c.isdigit() for c in key_value) and any(c.isalpha() for c in key_value):
            logger.warning(
                f"[D98-4_LIVE_KEY_GUARD] {key_name}: LIVE 키 의심 "
                f"(env={env.value}, 키 길이={len(key_value)})"
            )
            return True
    
    return False


def validate_live_keys(
    env: RuntimeEnv,
    live_enabled: bool,
    upbit_access_key: Optional[str] = None,
    upbit_secret_key: Optional[str] = None,
    binance_api_key: Optional[str] = None,
    binance_api_secret: Optional[str] = None,
) -> None:
    """
    LIVE 키 검증 (키 로딩 직전 호출).
    
    Args:
        env: 현재 환경 (RuntimeEnv)
        live_enabled: LIVE_ENABLED 플래그
        upbit_access_key: Upbit Access Key (선택)
        upbit_secret_key: Upbit Secret Key (선택)
        binance_api_key: Binance API Key (선택)
        binance_api_secret: Binance API Secret (선택)
    
    Raises:
        LiveKeyError: LIVE 키가 허용되지 않는 환경에서 감지된 경우
    
    Validation Rules:
        1. LIVE 모드 (env=live + live_enabled=true) → 모든 키 허용
        2. PAPER 모드 (env=paper) → LIVE 키 감지 시 차단
        3. LOCAL_DEV 모드 (env=local_dev) → LIVE 키 감지 시 차단
        4. LIVE_ENABLED=true 이지만 env != live → 차단 (안전 규칙)
    
    Examples:
        >>> # 안전: Paper 모드 + 테스트 키
        >>> validate_live_keys(
        ...     env=RuntimeEnv.PAPER,
        ...     live_enabled=False,
        ...     upbit_access_key="test_key_123"
        ... )
        
        >>> # 차단: Paper 모드 + LIVE 키 의심
        >>> validate_live_keys(
        ...     env=RuntimeEnv.PAPER,
        ...     live_enabled=False,
        ...     upbit_access_key="abc123def456ghi789jkl"  # 실제 키 패턴
        ... )
        LiveKeyError: [D98-4_LIVE_KEY_GUARD] 허용되지 않는 환경에서 LIVE Upbit 키 감지...
    """
    # D99-13 P12: validate_env.py 등 검증 스크립트에서 우회 가능
    if os.getenv("SKIP_LIVE_KEY_GUARD") == "1":
        logger.debug("[D98-4_LIVE_KEY_GUARD] Validation skipped (SKIP_LIVE_KEY_GUARD=1)")
        return
    
    # Rule 1: LIVE_ENABLED=true이지만 env != live → 차단
    if live_enabled and env != RuntimeEnv.LIVE:
        error_msg = (
            f"[D98-4_LIVE_KEY_GUARD] 환경 불일치: LIVE_ENABLED=true이지만 "
            f"ARBITRAGE_ENV={env.value} (live 아님). "
            f"LIVE 모드를 사용하려면 ARBITRAGE_ENV=live로 설정하세요."
        )
        logger.error(error_msg)
        raise LiveKeyError(error_msg)
    
    # Rule 2: LIVE 모드 → 모든 키 허용 (검증 통과)
    if env == RuntimeEnv.LIVE and live_enabled:
        logger.info(
            "[D98-4_LIVE_KEY_GUARD] LIVE 모드 활성화 "
            "(ARBITRAGE_ENV=live + LIVE_ENABLED=true). "
            "실제 거래 키 로딩 허용."
        )
        return
    
    # Rule 3: Paper/Local_dev 모드 → LIVE 키 감지
    keys_to_check = [
        ("UPBIT_ACCESS_KEY", upbit_access_key),
        ("UPBIT_SECRET_KEY", upbit_secret_key),
        ("BINANCE_API_KEY", binance_api_key),
        ("BINANCE_API_SECRET", binance_api_secret),
    ]
    
    for key_name, key_value in keys_to_check:
        if detect_live_key(key_name, key_value, env):
            error_msg = (
                f"[D98-4_LIVE_KEY_GUARD] 허용되지 않는 환경에서 LIVE {key_name} 감지. "
                f"현재 환경: {env.value}, LIVE_ENABLED: {live_enabled}. "
                f"LIVE 키를 사용하려면 ARBITRAGE_ENV=live + LIVE_ENABLED=true로 설정하세요. "
                f"Paper/테스트 환경에서는 테스트 키 또는 Mock 키를 사용하세요."
            )
            logger.error(error_msg)
            raise LiveKeyError(error_msg)
    
    # 모든 검증 통과
    logger.info(
        f"[D98-4_LIVE_KEY_GUARD] 키 검증 통과 "
        f"(env={env.value}, live_enabled={live_enabled})"
    )


def get_live_key_guard_status() -> dict:
    """
    현재 Live Key Guard 상태 반환 (디버깅/모니터링용).
    
    Returns:
        dict: Guard 상태 정보
    """
    return {
        "arbitrage_env": os.getenv("ARBITRAGE_ENV", "local_dev"),
        "live_enabled": os.getenv("LIVE_ENABLED", "false"),
        "live_mode_allowed": is_live_mode_allowed(),
        "guard_version": "D98-4",
    }
