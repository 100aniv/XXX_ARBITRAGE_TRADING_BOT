"""
D206-1: Profit Core Modularization + Tuner Interface

Purpose:
- 수익 로직 중앙화 (하드코딩 제거)
- 튜너 인터페이스 (엔진에 파라미터 주입 가능)

Constitutional Basis:
- Engine-Centric (엔진이 유일한 로직 소유자)
- Config SSOT (모든 파라미터는 config.yml 기반)
- No Magic Numbers (하드코딩 0개)

Author: arbitrage-lite V2
Date: 2026-01-15
"""

from typing import Protocol, Dict, Any, Optional, TYPE_CHECKING

# D206-1 HARDENED: config.py에서 import (circular import 해결)
from arbitrage.v2.core.config import ProfitCoreConfig, TunerConfig

# TYPE_CHECKING: BreakEvenParams (circular import 방지)
if TYPE_CHECKING:
    from arbitrage.v2.opportunity import BreakEvenParams


class BaseTuner(Protocol):
    """
    Tuner 인터페이스 (D206-1 AC-4)
    
    엔진은 이 인터페이스를 통해 튜너로부터 파라미터를 받음.
    
    Usage:
        engine.tuner = StaticTuner(config)
        params = engine.tuner.suggest_params()
        # ... run with params ...
        engine.tuner.report_result(kpi)
    """
    
    def suggest_params(self) -> Dict[str, Any]:
        """파라미터 제안 (튜너 → 엔진)"""
        ...
    
    def report_result(self, kpi: Dict[str, Any]) -> None:
        """결과 보고 (엔진 → 튜너)"""
        ...
    
    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """최적 파라미터 조회"""
        ...


class StaticTuner:
    """
    Static Tuner (D206-1 기본 구현)
    
    config.yml 기반으로 고정 파라미터 제공.
    Bayesian/Grid Tuner는 D206-2에서 구현.
    
    Args:
        config: TunerConfig (tuner.param_overrides 사용)
    
    Example:
        >>> config = TunerConfig(
        ...     enabled=True,
        ...     param_overrides={"buffer_bps": 15.0}
        ... )
        >>> tuner = StaticTuner(config)
        >>> params = tuner.suggest_params()
        >>> assert params["buffer_bps"] == 15.0
    """
    
    def __init__(self, config: TunerConfig):
        self.config = config
        self.results = []
    
    def suggest_params(self) -> Dict[str, Any]:
        """Config 기반 파라미터 반환"""
        if self.config.param_overrides:
            return self.config.param_overrides.copy()
        return {}
    
    def report_result(self, kpi: Dict[str, Any]) -> None:
        """결과 기록 (로그만, 튜닝 없음)"""
        self.results.append(kpi)
    
    def get_best_params(self) -> Optional[Dict[str, Any]]:
        """Static 모드는 최적화 없음"""
        return self.config.param_overrides


class ProfitCore:
    """
    Profit Core (수익 계산 중앙화)
    
    D206-1 AC-1: 하드코딩 제거 + Config SSOT 기반
    
    Purpose:
    - Opportunity 생성/평가 시 사용하는 기준 가격 제공
    - 가격 sanity check (이상치 탐지)
    - 튜너 인터페이스 통합 지점
    
    Args:
        config: ProfitCoreConfig
        tuner: Optional[BaseTuner] (튜너 훅)
    
    Usage:
        >>> # config.yml 기반 로딩 (REQUIRED)
        >>> from arbitrage.v2.core.config import load_config
        >>> v2_config = load_config("config/v2/config.yml")
        >>> core = ProfitCore(v2_config.profit_core)
        >>> price_krw = core.get_default_price("upbit", "BTC/KRW")
        >>> assert price_krw > 0  # config.yml 값 사용
    """
    
    def __init__(
        self,
        config: ProfitCoreConfig,
        tuner: Optional[BaseTuner] = None
    ):
        self.config = config
        self.tuner = tuner
    
    def get_default_price(self, exchange: str, symbol: str) -> float:
        """
        기본 가격 조회 (Mock/Fallback 용도)
        
        Args:
            exchange: "upbit", "binance"
            symbol: "BTC/KRW", "BTC/USDT"
        
        Returns:
            기준 가격 (config 기반, 하드코딩 없음)
        
        Raises:
            ValueError: 지원하지 않는 exchange/symbol
        """
        if exchange == "upbit" and "KRW" in symbol:
            return self.config.default_price_krw
        elif exchange == "binance" and "USDT" in symbol:
            return self.config.default_price_usdt
        else:
            raise ValueError(
                f"ProfitCore: Unsupported exchange/symbol: {exchange}/{symbol}"
            )
    
    def check_price_sanity(self, exchange: str, price: float) -> bool:
        """
        가격 이상치 탐지
        
        Args:
            exchange: "upbit", "binance"
            price: 실제 가격
        
        Returns:
            True: 정상, False: 이상치
        """
        if not self.config.enable_sanity_check:
            return True
        
        if exchange == "upbit":
            return (
                self.config.price_sanity_min_krw <= price <= self.config.price_sanity_max_krw
            )
        
        # binance는 sanity check 미적용 (향후 확장)
        return True
    
    def apply_tuner_overrides(self, params: "BreakEvenParams") -> "BreakEvenParams":
        """
        튜너 파라미터 오버라이드 적용
        
        Args:
            params: 기본 BreakEvenParams
        
        Returns:
            튜너가 제안한 값으로 오버라이드된 BreakEvenParams
        
        Example:
            >>> from arbitrage.domain.fee_model import FeeModel, FeeStructure
            >>> fee_model = FeeModel(FeeStructure.UPBIT_SPOT, FeeStructure.BINANCE_FUTURES)
            >>> tuner = StaticTuner(TunerConfig(param_overrides={"buffer_bps": 20.0}))
            >>> core = ProfitCore(ProfitCoreConfig(), tuner)
            >>> params = BreakEvenParams(fee_model=fee_model, buffer_bps=10.0, slippage_bps=15.0)
            >>> new_params = core.apply_tuner_overrides(params)
            >>> assert new_params.buffer_bps == 20.0
        """
        if not self.tuner:
            return params
        
        overrides = self.tuner.suggest_params()
        if not overrides:
            return params
        
        # BreakEvenParams 필드 오버라이드 (fee_model은 변경 없음)
        new_buffer = overrides.get("buffer_bps", params.buffer_bps)
        new_slippage = overrides.get("slippage_bps", params.slippage_bps)
        new_latency = overrides.get("latency_bps", params.latency_bps)
        
        # 새 인스턴스 생성 (fee_model은 그대로 유지)
        from arbitrage.v2.domain.break_even import BreakEvenParams as BP
        return BP(
            fee_model=params.fee_model,
            buffer_bps=new_buffer,
            slippage_bps=new_slippage,
            latency_bps=new_latency,
        )
