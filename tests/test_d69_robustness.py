"""
D69 – ROBUSTNESS_TEST Unit Tests

Robustness 시나리오 주입 로직 검증
"""

import sys
import os

# 프로젝트 루트 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from tuning.robustness_scenarios import (
    RobustnessScenario,
    ScenarioConfig,
    RobustnessInjector,
    create_scenario_config
)


class TestRobustnessInjector(unittest.TestCase):
    """RobustnessInjector 클래스 테스트"""
    
    def test_slippage_stress_injection(self):
        """슬리피지 스트레스 주입 테스트"""
        config = create_scenario_config('slippage_stress', duration_seconds=10)
        injector = RobustnessInjector(config)
        
        # 슬리피지가 0~80bps 범위 내에 있어야 함
        for _ in range(10):
            slippage = injector.inject_slippage()
            self.assertGreaterEqual(slippage, 0.0)
            self.assertLessEqual(slippage, 80.0)
    
    def test_fee_surge_injection(self):
        """수수료 급등 주입 테스트"""
        config = create_scenario_config('fee_surge', duration_seconds=10)
        injector = RobustnessInjector(config)
        
        # 수수료가 0.15%여야 함
        fee = injector.inject_fee()
        self.assertEqual(fee, 0.15)
    
    def test_flash_crash_injection(self):
        """Flash Crash 주입 테스트"""
        config = create_scenario_config('flash_crash', duration_seconds=10)
        config.flash_trigger_time = 0.0  # 즉시 트리거
        injector = RobustnessInjector(config)
        
        base_price = 100000.0
        shocked_price = injector.inject_price_shock(base_price)
        
        # -2% 급락해야 함
        expected_price = base_price * 0.98
        self.assertAlmostEqual(shocked_price, expected_price, places=2)
    
    def test_flash_spike_injection(self):
        """Flash Spike 주입 테스트"""
        config = ScenarioConfig(
            scenario=RobustnessScenario.FLASH_SPIKE,
            duration_seconds=10,
            flash_magnitude_pct=3.0,
            flash_trigger_time=0.0  # 즉시 트리거
        )
        injector = RobustnessInjector(config)
        
        base_price = 100000.0
        shocked_price = injector.inject_price_shock(base_price)
        
        # +3% 급등해야 함
        expected_price = base_price * 1.03
        self.assertAlmostEqual(shocked_price, expected_price, places=2)
    
    def test_noise_injection(self):
        """노이즈 주입 테스트"""
        config = create_scenario_config('noise_saturation', duration_seconds=10)
        injector = RobustnessInjector(config)
        
        base_price = 100000.0
        
        # 노이즈가 ±0.5% 범위 내에 있어야 함
        for _ in range(10):
            noisy_price = injector.inject_noise(base_price)
            deviation_pct = abs((noisy_price - base_price) / base_price) * 100.0
            self.assertLessEqual(deviation_pct, 0.5)
    
    def test_multisymbol_volatility_injection(self):
        """멀티심볼 volatility 주입 테스트"""
        config = create_scenario_config('multisymbol_stagger', duration_seconds=10)
        injector = RobustnessInjector(config)
        
        base_price = 100000.0
        
        # BTC는 2x volatility
        btc_price = injector.inject_multisymbol_volatility("BTCUSDT", base_price)
        self.assertIsNotNone(btc_price)
        
        # ETH는 1x volatility
        eth_price = injector.inject_multisymbol_volatility("ETHUSDT", base_price)
        self.assertIsNotNone(eth_price)
    
    def test_apply_all_injections(self):
        """전체 주입 로직 통합 테스트"""
        config = create_scenario_config('slippage_stress', duration_seconds=10)
        injector = RobustnessInjector(config)
        
        result = injector.apply_all_injections(
            symbol="BTCUSDT",
            base_price=100000.0
        )
        
        # 결과 딕셔너리에 필수 키가 있어야 함
        self.assertIn('price', result)
        self.assertIn('slippage_bps', result)
        self.assertIn('fee_pct', result)
        
        # 가격이 양수여야 함
        self.assertGreater(result['price'], 0)


class TestScenarioConfig(unittest.TestCase):
    """ScenarioConfig 생성 테스트"""
    
    def test_create_slippage_stress_config(self):
        """Slippage Stress 설정 생성 테스트"""
        config = create_scenario_config('slippage_stress', duration_seconds=120)
        self.assertEqual(config.scenario, RobustnessScenario.SLIPPAGE_STRESS)
        self.assertEqual(config.duration_seconds, 120)
    
    def test_create_fee_surge_config(self):
        """Fee Surge 설정 생성 테스트"""
        config = create_scenario_config('fee_surge', duration_seconds=60)
        self.assertEqual(config.scenario, RobustnessScenario.FEE_SURGE)
        self.assertEqual(config.duration_seconds, 60)
    
    def test_flash_trigger_time_auto_set(self):
        """Flash 시나리오 자동 트리거 시간 설정 테스트"""
        config = create_scenario_config('flash_crash', duration_seconds=100)
        self.assertEqual(config.flash_trigger_time, 50.0)  # 중간 지점


if __name__ == '__main__':
    unittest.main()
