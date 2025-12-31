"""
D205-8-2: FX Provider Interface — Live Mode Safeguard

목표: Fixed FX와 Live FX를 분리하여 Live mode 사고 방지 (1300원 참사 방지)

SSOT: docs/v2/SSOT_RULES.md
"""

from abc import ABC, abstractmethod
from typing import Dict


class FxProvider(ABC):
    """FX rate provider 인터페이스"""
    
    @abstractmethod
    def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """
        환율 조회
        
        Args:
            from_currency: 출발 통화 (e.g., "USDT")
            to_currency: 도착 통화 (e.g., "KRW")
        
        Returns:
            환율 (e.g., 1450.0)
        
        Raises:
            ValueError: 지원하지 않는 통화 쌍
        """
        pass
    
    @abstractmethod
    def is_live(self) -> bool:
        """Live mode provider 여부"""
        pass


class FixedFxProvider(FxProvider):
    """
    Fixed FX provider (Test/Paper/Replay 전용)
    
    주의: Live mode에서 사용 금지 (validate_fx_provider_for_mode로 차단됨)
    """
    
    def __init__(self, fx_krw_per_usdt: float = 1450.0):
        """
        Args:
            fx_krw_per_usdt: USDT → KRW 환율 (기본값: 1450.0)
        """
        self.fx_krw_per_usdt = fx_krw_per_usdt
    
    def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """고정 환율 반환"""
        if from_currency == "USDT" and to_currency == "KRW":
            return self.fx_krw_per_usdt
        elif from_currency == "KRW" and to_currency == "KRW":
            return 1.0
        else:
            raise ValueError(f"Unsupported FX pair: {from_currency}/{to_currency}")
    
    def is_live(self) -> bool:
        """Fixed FX는 Live 아님"""
        return False


class LiveFxProvider(FxProvider):
    """
    Live FX provider (Yahoo/Upbit/외부 API)
    
    현재: 미구현 (D206에서 구현 예정)
    """
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: 외부 API 키 (필요 시)
        """
        self.api_key = api_key
        # TODO(D206): API 연결 초기화
    
    def get_fx_rate(self, from_currency: str, to_currency: str) -> float:
        """실시간 환율 조회 (미구현)"""
        # TODO(D206): 실시간 API 호출 구현
        raise NotImplementedError(
            "LiveFxProvider not yet implemented. "
            "This will be implemented in D206 when LIVE mode is activated."
        )
    
    def is_live(self) -> bool:
        """Live FX는 Live"""
        return True


def validate_fx_provider_for_mode(provider: FxProvider, mode: str):
    """
    Live mode safeguard: Fixed FX 사용 금지
    
    목적: Live mode에서 고정 환율 (1450.0) 사용 시 발생할 수 있는
          "1300원 참사" (잘못된 환율로 주문) 사고를 원천 차단
    
    Args:
        provider: FX provider
        mode: "paper" / "live"
    
    Raises:
        ValueError: Live mode에서 Fixed FX 사용 시 (Fail Fast)
    
    Example:
        >>> # Paper mode (OK)
        >>> fx = FixedFxProvider(1450.0)
        >>> validate_fx_provider_for_mode(fx, "paper")  # ✅ PASS
        
        >>> # Live mode (CRASH with 🚨 FATAL)
        >>> fx = FixedFxProvider(1450.0)
        >>> validate_fx_provider_for_mode(fx, "live")  # ❌ Raises ValueError
    """
    if mode == "live" and not provider.is_live():
        raise ValueError(
            "🚨 FATAL: Live trading requires a real-time FX provider!\n"
            "Fixed FX (1450.0) cannot be used in LIVE mode.\n"
            "This is a safeguard to prevent '1300원 참사' (wrong FX rate orders).\n"
            "Please configure LiveFxProvider with a valid API key.\n"
            "\n"
            "SSOT Reference: D_ROADMAP.md → D206 Prerequisite #1"
        )
