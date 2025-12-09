# -*- coding: utf-8 -*-
"""
D89-0: Zone Preference Weight Tuning - Unit Tests

Advisory mode의 Z2 가중치 강화 (1.05 → 3.00) 검증.

Test Scenarios:
1. T1: Advisory vs Strict Score 비교
2. T2: 설정값 반영 검증
3. T3: Score Clipping 검증

Author: arbitrage-lite project
Date: 2025-12-09
"""

import pytest
from arbitrage.execution.fill_model_integration import (
    FillModelConfig,
    FillModelIntegration,
    FillModelAdvice,
)


class TestD89ZonePreferenceWeightTuning:
    """
    D89-0: Zone Preference Weight Tuning 테스트
    """
    
    def test_t1_advisory_vs_strict_score_comparison(self):
        """
        T1: Advisory vs Strict Score 비교
        
        동일한 base_score에 대해:
        - Advisory Z2 Score >> Strict Z2 Score (3.00 vs 1.15)
        - Advisory Z1 Score ≈ Strict Z1 Score (둘 다 0.80)
        """
        # Arrange
        base_score = 70.0
        
        # Advisory Config
        advisory_config = FillModelConfig(
            enabled=True,
            mode="advisory",
            calibration_path=None,
        )
        advisory_integration = FillModelIntegration(advisory_config)
        
        # Strict Config
        strict_config = FillModelConfig(
            enabled=True,
            mode="strict",
            calibration_path=None,
        )
        strict_integration = FillModelIntegration(strict_config)
        
        # Mock Advice (Z2)
        advice_z2 = FillModelAdvice(
            entry_bps=10.0,
            tp_bps=20.0,
            zone_id="Z2",
            expected_fill_probability=0.9,
            expected_slippage_bps=2.0,
            confidence_level=0.8,
        )
        
        # Mock Advice (Z1)
        advice_z1 = FillModelAdvice(
            entry_bps=10.0,
            tp_bps=20.0,
            zone_id="Z1",
            expected_fill_probability=0.5,
            expected_slippage_bps=5.0,
            confidence_level=0.8,
        )
        
        # Act
        advisory_score_z2 = advisory_integration.adjust_route_score(base_score, advice_z2)
        strict_score_z2 = strict_integration.adjust_route_score(base_score, advice_z2)
        
        advisory_score_z1 = advisory_integration.adjust_route_score(base_score, advice_z1)
        strict_score_z1 = strict_integration.adjust_route_score(base_score, advice_z1)
        
        # Assert
        # Advisory Z2 = 70 * 3.00 = 210 (clipped to 100)
        assert advisory_score_z2 == 100.0, \
            f"Advisory Z2 should be clipped to 100, got {advisory_score_z2}"
        
        # Strict Z2 = 70 * 1.15 = 80.5
        assert 80.0 <= strict_score_z2 <= 81.0, \
            f"Strict Z2 should be ~80.5, got {strict_score_z2}"
        
        # Advisory Z2 >> Strict Z2
        assert advisory_score_z2 > strict_score_z2, \
            f"Advisory Z2 ({advisory_score_z2}) should be > Strict Z2 ({strict_score_z2})"
        
        # Advisory Z1 = 70 * 0.80 = 56.0
        assert 55.5 <= advisory_score_z1 <= 56.5, \
            f"Advisory Z1 should be ~56.0, got {advisory_score_z1}"
        
        # Strict Z1 = 70 * 0.80 = 56.0
        assert 55.5 <= strict_score_z1 <= 56.5, \
            f"Strict Z1 should be ~56.0, got {strict_score_z1}"
        
        # Advisory Z1 ≈ Strict Z1 (둘 다 0.80)
        assert abs(advisory_score_z1 - strict_score_z1) < 0.1, \
            f"Advisory Z1 ({advisory_score_z1}) ≈ Strict Z1 ({strict_score_z1})"
    
    def test_t2_config_zone_preference_values(self):
        """
        T2: 설정값 반영 검증
        
        FillModelConfig 생성 시 zone_preference 값 확인:
        - Advisory Z2 = 3.00 (D89-0 강화)
        - Strict Z2 = 1.15 (기준선 유지)
        """
        # Arrange & Act
        advisory_config = FillModelConfig(
            enabled=True,
            mode="advisory",
            calibration_path=None,
        )
        
        strict_config = FillModelConfig(
            enabled=True,
            mode="strict",
            calibration_path=None,
        )
        
        # Assert
        assert advisory_config.zone_preference is not None, \
            "Advisory config should have zone_preference"
        assert strict_config.zone_preference is not None, \
            "Strict config should have zone_preference"
        
        # Advisory Z2 = 3.00
        advisory_z2 = advisory_config.zone_preference.get("advisory", {}).get("Z2")
        assert advisory_z2 == 3.00, \
            f"Advisory Z2 should be 3.00, got {advisory_z2}"
        
        # Advisory Z1 = 0.80
        advisory_z1 = advisory_config.zone_preference.get("advisory", {}).get("Z1")
        assert advisory_z1 == 0.80, \
            f"Advisory Z1 should be 0.80, got {advisory_z1}"
        
        # Strict Z2 = 1.15 (unchanged)
        strict_z2 = strict_config.zone_preference.get("strict", {}).get("Z2")
        assert strict_z2 == 1.15, \
            f"Strict Z2 should be 1.15, got {strict_z2}"
        
        # Strict Z1 = 0.80
        strict_z1 = strict_config.zone_preference.get("strict", {}).get("Z1")
        assert strict_z1 == 0.80, \
            f"Strict Z1 should be 0.80, got {strict_z1}"
    
    def test_t3_score_clipping_to_100(self):
        """
        T3: Score Clipping 검증
        
        base_score=70, Z2=3.00 → adjusted_score=210 → clipped to 100
        0~100 범위 내 clipping 정상 작동
        """
        # Arrange
        base_score = 70.0
        config = FillModelConfig(
            enabled=True,
            mode="advisory",
            calibration_path=None,
        )
        integration = FillModelIntegration(config)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0,
            tp_bps=20.0,
            zone_id="Z2",
            expected_fill_probability=0.9,
            expected_slippage_bps=2.0,
            confidence_level=0.8,
        )
        
        # Act
        adjusted_score = integration.adjust_route_score(base_score, advice_z2)
        
        # Assert
        # 70 * 3.00 = 210, but clipped to 100
        assert adjusted_score == 100.0, \
            f"Score should be clipped to 100, got {adjusted_score}"
        
        # 0~100 범위 내
        assert 0.0 <= adjusted_score <= 100.0, \
            f"Score should be in [0, 100], got {adjusted_score}"
    
    def test_t4_backward_compatibility_none_mode(self):
        """
        T4: Backward Compatibility - None Mode
        
        mode="none"일 때는 가중치가 모두 1.0이어야 함.
        """
        # Arrange
        base_score = 70.0
        config = FillModelConfig(
            enabled=False,
            mode="none",
            calibration_path=None,
        )
        integration = FillModelIntegration(config)
        
        advice_z2 = FillModelAdvice(
            entry_bps=10.0,
            tp_bps=20.0,
            zone_id="Z2",
            expected_fill_probability=0.9,
            expected_slippage_bps=2.0,
            confidence_level=0.8,
        )
        
        # Act
        adjusted_score = integration.adjust_route_score(base_score, advice_z2)
        
        # Assert
        # None mode: no adjustment
        assert adjusted_score == base_score, \
            f"None mode should not adjust score, got {adjusted_score} (expected {base_score})"
    
    def test_t5_z3_z4_weights(self):
        """
        T5: Z3, Z4 가중치 검증
        
        Advisory Z3 = 0.85, Z4 = 0.80 확인
        """
        # Arrange
        base_score = 80.0
        config = FillModelConfig(
            enabled=True,
            mode="advisory",
            calibration_path=None,
        )
        integration = FillModelIntegration(config)
        
        advice_z3 = FillModelAdvice(
            entry_bps=10.0,
            tp_bps=20.0,
            zone_id="Z3",
            expected_fill_probability=0.7,
            expected_slippage_bps=3.0,
            confidence_level=0.8,
        )
        
        advice_z4 = FillModelAdvice(
            entry_bps=10.0,
            tp_bps=20.0,
            zone_id="Z4",
            expected_fill_probability=0.6,
            expected_slippage_bps=4.0,
            confidence_level=0.8,
        )
        
        # Act
        adjusted_score_z3 = integration.adjust_route_score(base_score, advice_z3)
        adjusted_score_z4 = integration.adjust_route_score(base_score, advice_z4)
        
        # Assert
        # Z3: 80 * 0.85 = 68.0
        assert 67.5 <= adjusted_score_z3 <= 68.5, \
            f"Z3 score should be ~68.0, got {adjusted_score_z3}"
        
        # Z4: 80 * 0.80 = 64.0
        assert 63.5 <= adjusted_score_z4 <= 64.5, \
            f"Z4 score should be ~64.0, got {adjusted_score_z4}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
