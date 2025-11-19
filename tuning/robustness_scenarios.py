"""
D69 – ROBUSTNESS_TEST: 비정상 시장 상황 시뮬레이션

이 모듈은 다양한 스트레스 시나리오를 정의하고,
엔진/전략이 비정상 상황에서도 안정적으로 동작하는지 검증합니다.

시나리오:
1. SLIPPAGE_STRESS: 슬리피지 급증 (0~80bps)
2. FEE_SURGE: 수수료 급등 (0.04% → 0.15%)
3. FLASH_CRASH: 급락 시뮬레이션 (-2% in 5s)
4. FLASH_SPIKE: 급등 시뮬레이션 (+3% in 5s)
5. NOISE_SATURATION: 랜덤 노이즈 주입 (±0.5%)
6. MULTISYMBOL_STAGGER: 심볼별 다른 volatility
"""

import random
import time
from dataclasses import dataclass
from typing import Dict, Optional, Callable
from enum import Enum


class RobustnessScenario(Enum):
    """Robustness 테스트 시나리오"""
    SLIPPAGE_STRESS = "slippage_stress"
    FEE_SURGE = "fee_surge"
    FLASH_CRASH = "flash_crash"
    FLASH_SPIKE = "flash_spike"
    NOISE_SATURATION = "noise_saturation"
    MULTISYMBOL_STAGGER = "multisymbol_stagger"


@dataclass
class ScenarioConfig:
    """시나리오 설정"""
    scenario: RobustnessScenario
    duration_seconds: int = 120
    symbol: str = "BTCUSDT"
    
    # Slippage Stress
    slippage_min_bps: float = 0.0
    slippage_max_bps: float = 80.0
    
    # Fee Surge
    normal_fee_pct: float = 0.04
    surge_fee_pct: float = 0.15
    
    # Flash Crash/Spike
    flash_magnitude_pct: float = 2.0  # crash: -2%, spike: +3%
    flash_duration_seconds: float = 5.0
    flash_trigger_time: Optional[float] = None  # None이면 중간에 자동 트리거
    
    # Noise Saturation
    noise_magnitude_pct: float = 0.5
    
    # Multisymbol Stagger
    btc_volatility_multiplier: float = 2.0
    eth_volatility_multiplier: float = 1.0


class RobustnessInjector:
    """
    비정상 시장 상황 주입 클래스
    
    Paper Exchange가 가격을 생성할 때 이 클래스를 통해
    슬리피지, 수수료, 노이즈, 급등락 등을 주입합니다.
    """
    
    def __init__(self, config: ScenarioConfig):
        self.config = config
        self.start_time = time.time()
        self.flash_triggered = False
        
    def get_elapsed_time(self) -> float:
        """경과 시간 (초)"""
        return time.time() - self.start_time
    
    def should_trigger_flash(self) -> bool:
        """Flash Crash/Spike 트리거 시점 확인"""
        if self.flash_triggered:
            return False
        
        elapsed = self.get_elapsed_time()
        
        # 자동 트리거: 세션 중간 지점
        if self.config.flash_trigger_time is None:
            trigger_time = self.config.duration_seconds / 2.0
        else:
            trigger_time = self.config.flash_trigger_time
        
        if elapsed >= trigger_time:
            self.flash_triggered = True
            return True
        
        return False
    
    def inject_slippage(self, base_slippage_bps: float = 4.0) -> float:
        """
        슬리피지 주입
        
        SLIPPAGE_STRESS 시나리오: 0~80bps 랜덤
        기타: base_slippage_bps 사용
        """
        if self.config.scenario == RobustnessScenario.SLIPPAGE_STRESS:
            return random.uniform(
                self.config.slippage_min_bps,
                self.config.slippage_max_bps
            )
        return base_slippage_bps
    
    def inject_fee(self, base_fee_pct: float = 0.04) -> float:
        """
        수수료 주입
        
        FEE_SURGE 시나리오: surge_fee_pct 적용
        기타: base_fee_pct 사용
        """
        if self.config.scenario == RobustnessScenario.FEE_SURGE:
            return self.config.surge_fee_pct
        return base_fee_pct
    
    def inject_price_shock(self, base_price: float) -> float:
        """
        가격 급등락 주입
        
        FLASH_CRASH: -2% 급락
        FLASH_SPIKE: +3% 급등
        """
        if self.config.scenario == RobustnessScenario.FLASH_CRASH:
            if self.should_trigger_flash():
                magnitude = -abs(self.config.flash_magnitude_pct) / 100.0
                return base_price * (1.0 + magnitude)
        
        elif self.config.scenario == RobustnessScenario.FLASH_SPIKE:
            if self.should_trigger_flash():
                magnitude = abs(self.config.flash_magnitude_pct) / 100.0
                return base_price * (1.0 + magnitude)
        
        return base_price
    
    def inject_noise(self, base_price: float) -> float:
        """
        랜덤 노이즈 주입
        
        NOISE_SATURATION: ±0.5% 랜덤 노이즈
        """
        if self.config.scenario == RobustnessScenario.NOISE_SATURATION:
            noise_pct = random.uniform(
                -self.config.noise_magnitude_pct,
                self.config.noise_magnitude_pct
            ) / 100.0
            return base_price * (1.0 + noise_pct)
        
        return base_price
    
    def inject_multisymbol_volatility(
        self,
        symbol: str,
        base_price: float
    ) -> float:
        """
        멀티심볼 각각 다른 volatility 주입
        
        MULTISYMBOL_STAGGER:
        - BTC: 2x volatility
        - ETH: 1x volatility
        """
        if self.config.scenario == RobustnessScenario.MULTISYMBOL_STAGGER:
            if "BTC" in symbol:
                multiplier = self.config.btc_volatility_multiplier
            elif "ETH" in symbol:
                multiplier = self.config.eth_volatility_multiplier
            else:
                multiplier = 1.0
            
            # volatility = 기본 변동폭 * multiplier
            base_volatility_pct = 0.1  # 0.1%
            noise_pct = random.uniform(
                -base_volatility_pct * multiplier,
                base_volatility_pct * multiplier
            ) / 100.0
            
            return base_price * (1.0 + noise_pct)
        
        return base_price
    
    def apply_all_injections(
        self,
        symbol: str,
        base_price: float,
        base_slippage_bps: float = 4.0,
        base_fee_pct: float = 0.04
    ) -> Dict[str, float]:
        """
        모든 주입 로직 적용
        
        Returns:
            {
                'price': 최종 가격,
                'slippage_bps': 슬리피지,
                'fee_pct': 수수료
            }
        """
        # 1. 가격 shock 주입
        price = self.inject_price_shock(base_price)
        
        # 2. 노이즈 주입
        price = self.inject_noise(price)
        
        # 3. 멀티심볼 volatility 주입
        price = self.inject_multisymbol_volatility(symbol, price)
        
        # 4. 슬리피지 주입
        slippage_bps = self.inject_slippage(base_slippage_bps)
        
        # 5. 수수료 주입
        fee_pct = self.inject_fee(base_fee_pct)
        
        return {
            'price': price,
            'slippage_bps': slippage_bps,
            'fee_pct': fee_pct
        }


def create_scenario_config(
    scenario_name: str,
    duration_seconds: int = 120,
    symbol: str = "BTCUSDT"
) -> ScenarioConfig:
    """
    시나리오 이름으로 설정 생성
    
    Args:
        scenario_name: 'slippage_stress', 'fee_surge', etc.
        duration_seconds: 테스트 실행 시간
        symbol: 심볼 (MULTISYMBOL_STAGGER는 무시)
    
    Returns:
        ScenarioConfig
    """
    scenario = RobustnessScenario(scenario_name)
    
    config = ScenarioConfig(
        scenario=scenario,
        duration_seconds=duration_seconds,
        symbol=symbol
    )
    
    # Flash 시나리오는 중간에 트리거
    if scenario in [RobustnessScenario.FLASH_CRASH, RobustnessScenario.FLASH_SPIKE]:
        config.flash_trigger_time = duration_seconds / 2.0
    
    return config


# 시나리오별 기대 동작 정의
SCENARIO_EXPECTATIONS = {
    RobustnessScenario.SLIPPAGE_STRESS: {
        "description": "슬리피지 0~80bps 랜덤 주입",
        "expected_pnl_impact": "negative",
        "expected_winrate_impact": "decrease",
        "crash_allowed": False,
        "entry_exit_required": True
    },
    RobustnessScenario.FEE_SURGE: {
        "description": "수수료 0.04% → 0.15% 급등",
        "expected_pnl_impact": "negative",
        "expected_winrate_impact": "stable",
        "crash_allowed": False,
        "entry_exit_required": True
    },
    RobustnessScenario.FLASH_CRASH: {
        "description": "-2% 급락 in 5s",
        "expected_pnl_impact": "negative_or_neutral",
        "expected_winrate_impact": "stable",
        "crash_allowed": False,
        "entry_exit_required": True,
        "sl_trigger_expected": True
    },
    RobustnessScenario.FLASH_SPIKE: {
        "description": "+3% 급등 in 5s",
        "expected_pnl_impact": "neutral",
        "expected_winrate_impact": "stable",
        "crash_allowed": False,
        "entry_exit_required": True,
        "entry_flood_not_allowed": True  # Entry 폭주 금지
    },
    RobustnessScenario.NOISE_SATURATION: {
        "description": "±0.5% 랜덤 노이즈",
        "expected_pnl_impact": "neutral",
        "expected_winrate_impact": "stable",
        "crash_allowed": False,
        "entry_exit_required": True
    },
    RobustnessScenario.MULTISYMBOL_STAGGER: {
        "description": "BTC 2x volatility, ETH 1x",
        "expected_pnl_impact": "neutral",
        "expected_winrate_impact": "stable",
        "crash_allowed": False,
        "entry_exit_required": True,
        "portfolio_dd_constraint": True  # Portfolio DD <= max(symbol DD)
    }
}
