#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-4: Zone-aware Route Selection 테스트

Multiplicative Zone Preference 기반 Route Score 조정 검증
"""

import pytest
from arbitrage.execution.fill_model_integration import (
    FillModelConfig,
    FillModelIntegration,
    FillModelAdvice,
)


class TestZonePreferenceWeights:
    """Zone Preference Weights 기본 구조 테스트"""
    
    def test_zone_preference_weights_none(self):
        """mode=none일 때 모든 Zone weight=1.0"""
        config = FillModelConfig(mode="none")
        assert config.zone_preference["none"]["Z1"] == 1.0
        assert config.zone_preference["none"]["Z2"] == 1.0
        assert config.zone_preference["none"]["Z3"] == 1.0
        assert config.zone_preference["none"]["Z4"] == 1.0
        assert config.zone_preference["none"]["DEFAULT"] == 1.0
    
    def test_zone_preference_weights_advisory(self):
        """mode=advisory일 때 Z2 > Z3 > Z1/Z4"""
        config = FillModelConfig(mode="advisory")
        
        # Z2가 가장 높아야 함
        assert config.zone_preference["advisory"]["Z2"] > 1.0
        
        # Z1, Z4는 1.0보다 낮아야 함
        assert config.zone_preference["advisory"]["Z1"] < 1.0
        assert config.zone_preference["advisory"]["Z4"] < 1.0
        
        # Z2 > Z3 > Z1/Z4 ordering
        assert config.zone_preference["advisory"]["Z2"] > config.zone_preference["advisory"]["Z3"]
        assert config.zone_preference["advisory"]["Z3"] > config.zone_preference["advisory"]["Z1"]
    
    def test_zone_preference_weights_strict(self):
        """mode=strict일 때 Z2 >> Z3 > Z1/Z4"""
        config = FillModelConfig(mode="strict")
        
        # Z2가 1.1 이상이어야 함 (강한 우대)
        assert config.zone_preference["strict"]["Z2"] > 1.1
        
        # Z1, Z4는 0.9 미만이어야 함 (강한 패널티)
        assert config.zone_preference["strict"]["Z1"] < 0.9
        assert config.zone_preference["strict"]["Z4"] < 0.9
        
        # Z2 vs Z1 차이가 advisory보다 커야 함
        strict_diff = config.zone_preference["strict"]["Z2"] - config.zone_preference["strict"]["Z1"]
        advisory_diff = config.zone_preference["advisory"]["Z2"] - config.zone_preference["advisory"]["Z1"]
        assert strict_diff > advisory_diff


class TestMultiplicativeScoreAdjustment:
    """Multiplicative Score Adjustment 검증"""
    
    def test_adjust_route_score_none_mode(self):
        """mode=none일 때 score 변화 없음"""
        config = FillModelConfig(mode="none")
        integration = FillModelIntegration(config)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0, tp_bps=12.0, zone_id="Z2",
            expected_fill_probability=0.63, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        adjusted = integration.adjust_route_score(60.0, advice_z2)
        assert abs(adjusted - 60.0) < 0.01  # 변화 없음
    
    def test_adjust_route_score_advisory_z2(self):
        """mode=advisory, Z2일 때 +5% 증가"""
        config = FillModelConfig(mode="advisory")
        integration = FillModelIntegration(config)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0, tp_bps=12.0, zone_id="Z2",
            expected_fill_probability=0.63, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        # base_score=60.0 * 1.05 = 63.0
        adjusted = integration.adjust_route_score(60.0, advice_z2)
        assert abs(adjusted - 63.0) < 0.1
    
    def test_adjust_route_score_advisory_z1(self):
        """mode=advisory, Z1일 때 -10% 감소"""
        config = FillModelConfig(mode="advisory")
        integration = FillModelIntegration(config)
        
        advice_z1 = FillModelAdvice(
            entry_bps=6.0, tp_bps=8.0, zone_id="Z1",
            expected_fill_probability=0.26, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        # base_score=60.0 * 0.90 = 54.0
        adjusted = integration.adjust_route_score(60.0, advice_z1)
        assert abs(adjusted - 54.0) < 0.1
    
    def test_adjust_route_score_strict_z2(self):
        """mode=strict, Z2일 때 +15% 증가"""
        config = FillModelConfig(mode="strict")
        integration = FillModelIntegration(config)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0, tp_bps=12.0, zone_id="Z2",
            expected_fill_probability=0.63, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        # base_score=60.0 * 1.15 = 69.0
        adjusted = integration.adjust_route_score(60.0, advice_z2)
        assert abs(adjusted - 69.0) < 0.1
    
    def test_adjust_route_score_strict_z1(self):
        """mode=strict, Z1일 때 -20% 감소"""
        config = FillModelConfig(mode="strict")
        integration = FillModelIntegration(config)
        
        advice_z1 = FillModelAdvice(
            entry_bps=6.0, tp_bps=8.0, zone_id="Z1",
            expected_fill_probability=0.26, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        # base_score=60.0 * 0.80 = 48.0
        adjusted = integration.adjust_route_score(60.0, advice_z1)
        assert abs(adjusted - 48.0) < 0.1
    
    def test_adjust_route_score_clipping(self):
        """Score가 0~100 범위로 clipping되는지 확인"""
        config = FillModelConfig(mode="strict")
        integration = FillModelIntegration(config)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0, tp_bps=12.0, zone_id="Z2",
            expected_fill_probability=0.63, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        # base_score=95.0 * 1.15 = 109.25 → 100.0 (clipped)
        adjusted = integration.adjust_route_score(95.0, advice_z2)
        assert adjusted == 100.0
        
        advice_z1 = FillModelAdvice(
            entry_bps=6.0, tp_bps=8.0, zone_id="Z1",
            expected_fill_probability=0.26, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        # base_score=5.0 * 0.80 = 4.0 (정상)
        adjusted = integration.adjust_route_score(5.0, advice_z1)
        assert abs(adjusted - 4.0) < 0.1


class TestZoneDifferenceAmplification:
    """Zone 간 차이 증폭 효과 검증"""
    
    def test_strict_amplifies_zone_difference(self):
        """strict 모드가 advisory보다 zone 차이를 더 크게 만드는지 확인"""
        config_advisory = FillModelConfig(mode="advisory")
        config_strict = FillModelConfig(mode="strict")
        
        integration_advisory = FillModelIntegration(config_advisory)
        integration_strict = FillModelIntegration(config_strict)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0, tp_bps=12.0, zone_id="Z2",
            expected_fill_probability=0.63, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        advice_z1 = FillModelAdvice(
            entry_bps=6.0, tp_bps=8.0, zone_id="Z1",
            expected_fill_probability=0.26, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        base_score = 60.0
        
        # Advisory 모드
        advisory_z2 = integration_advisory.adjust_route_score(base_score, advice_z2)
        advisory_z1 = integration_advisory.adjust_route_score(base_score, advice_z1)
        advisory_diff = advisory_z2 - advisory_z1
        
        # Strict 모드
        strict_z2 = integration_strict.adjust_route_score(base_score, advice_z2)
        strict_z1 = integration_strict.adjust_route_score(base_score, advice_z1)
        strict_diff = strict_z2 - strict_z1
        
        # Strict 차이가 Advisory 차이보다 커야 함
        assert strict_diff > advisory_diff
        
        # 예상 값 검증
        # Advisory: Z2=63.0, Z1=54.0 → diff=9.0
        # Strict: Z2=69.0, Z1=48.0 → diff=21.0
        assert abs(advisory_diff - 9.0) < 0.5
        assert abs(strict_diff - 21.0) < 0.5


class TestDefaultZoneHandling:
    """DEFAULT Zone 처리 검증"""
    
    def test_default_zone_preference(self):
        """DEFAULT zone_id에 대한 처리 확인"""
        config = FillModelConfig(mode="advisory")
        integration = FillModelIntegration(config)
        
        advice_default = FillModelAdvice(
            entry_bps=50.0, tp_bps=60.0, zone_id="DEFAULT",
            expected_fill_probability=0.26, expected_slippage_bps=0.0,
            confidence_level=0.0
        )
        
        # DEFAULT zone은 advisory mode에서 0.95
        adjusted = integration.adjust_route_score(60.0, advice_default)
        assert abs(adjusted - 57.0) < 0.1  # 60.0 * 0.95 = 57.0


class TestBackwardCompatibility:
    """Backward Compatibility 검증"""
    
    def test_zone_preference_initialization(self):
        """zone_preference가 자동으로 초기화되는지 확인"""
        config = FillModelConfig(mode="advisory")
        
        # __post_init__에서 자동 초기화
        assert config.zone_preference is not None
        assert "none" in config.zone_preference
        assert "advisory" in config.zone_preference
        assert "strict" in config.zone_preference
    
    def test_custom_zone_preference(self):
        """Custom zone_preference를 제공할 수 있는지 확인"""
        custom_pref = {
            "none": {"Z1": 1.0, "Z2": 1.0, "Z3": 1.0, "Z4": 1.0, "DEFAULT": 1.0},
            "advisory": {"Z1": 0.95, "Z2": 1.10, "Z3": 1.00, "Z4": 0.95, "DEFAULT": 1.00},
            "strict": {"Z1": 0.85, "Z2": 1.20, "Z3": 0.90, "Z4": 0.85, "DEFAULT": 0.90},
        }
        
        config = FillModelConfig(mode="advisory", zone_preference=custom_pref)
        assert config.zone_preference["advisory"]["Z2"] == 1.10
        
        integration = FillModelIntegration(config)
        advice_z2 = FillModelAdvice(
            entry_bps=10.0, tp_bps=12.0, zone_id="Z2",
            expected_fill_probability=0.63, expected_slippage_bps=0.0,
            confidence_level=1.0
        )
        
        # base_score=60.0 * 1.10 = 66.0
        adjusted = integration.adjust_route_score(60.0, advice_z2)
        assert abs(adjusted - 66.0) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
