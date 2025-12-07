# -*- coding: utf-8 -*-
"""
D87-2: Fill Model Integration Strict Mode Tests

Strict Mode 기능 검증:
- Strict Mode 파라미터 (±20% 범위)
- Advisory Mode 대비 더 강한 조정
- Mode 전환 정확성
- Backward Compatibility

Author: arbitrage-lite project
Date: 2025-12-07
"""

import json
import pytest
import tempfile
from pathlib import Path

from arbitrage.execution.fill_model_integration import (
    FillModelAdvice,
    FillModelConfig,
    FillModelIntegration,
)


# =============================================================================
# Fixture: Mock Calibration Data
# =============================================================================

@pytest.fixture
def mock_calibration_data():
    """Mock D86 calibration data"""
    return {
        "version": "d86_0",
        "created_at": "2025-12-07T12:00:00",
        "source": "Test Mock",
        "total_events": 60,
        "zones": [
            {
                "zone_id": "Z1",
                "entry_min": 5.0,
                "entry_max": 7.0,
                "tp_min": 7.0,
                "tp_max": 12.0,
                "buy_fill_ratio": 0.2615,
                "sell_fill_ratio": 1.0,
                "samples": 24,
            },
            {
                "zone_id": "Z2",
                "entry_min": 7.0,
                "entry_max": 12.0,
                "tp_min": 10.0,
                "tp_max": 20.0,
                "buy_fill_ratio": 0.6307,
                "sell_fill_ratio": 1.0,
                "samples": 20,
            },
            {
                "zone_id": "Z3",
                "entry_min": 12.0,
                "entry_max": 20.0,
                "tp_min": 15.0,
                "tp_max": 30.0,
                "buy_fill_ratio": 0.2615,
                "sell_fill_ratio": 1.0,
                "samples": 12,
            },
        ],
        "default_buy_fill_ratio": 0.2615,
        "default_sell_fill_ratio": 1.0,
    }


@pytest.fixture
def mock_calibration_file(tmp_path, mock_calibration_data):
    """Temporary calibration JSON file"""
    cal_file = tmp_path / "test_calibration.json"
    with open(cal_file, "w", encoding="utf-8") as f:
        json.dump(mock_calibration_data, f)
    return cal_file


# =============================================================================
# Test: Config Validation
# =============================================================================

def test_strict_mode_config_defaults():
    """Strict Mode 기본값 검증"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
    )
    
    # Strict Mode 기본값 확인
    assert config.strict_score_bias_z2 == 10.0
    assert config.strict_score_bias_other == -5.0
    assert config.strict_size_multiplier_z2 == 1.2
    assert config.strict_size_multiplier_other == 1.0
    assert config.strict_risk_multiplier_z2 == 1.2
    assert config.strict_risk_multiplier_other == 1.0


def test_strict_mode_config_custom_values():
    """Strict Mode 커스텀 값 설정"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        strict_score_bias_z2=15.0,
        strict_score_bias_other=-8.0,
        strict_size_multiplier_z2=1.15,
        strict_size_multiplier_other=0.95,
        strict_risk_multiplier_z2=1.15,
        strict_risk_multiplier_other=0.95,
    )
    
    assert config.strict_score_bias_z2 == 15.0
    assert config.strict_score_bias_other == -8.0
    assert config.strict_size_multiplier_z2 == 1.15
    assert config.strict_size_multiplier_other == 0.95


# =============================================================================
# Test: Strict Mode Score Adjustment
# =============================================================================

def test_strict_mode_adjust_route_score_z2(mock_calibration_file):
    """Strict Mode Z2 Score 보정 (+10.0 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    adjusted = integration.adjust_route_score(base_score=60.0, advice=advice)
    
    assert adjusted == 70.0  # 60 + 10


def test_strict_mode_adjust_route_score_z1(mock_calibration_file):
    """Strict Mode Z1 Score 보정 (-5.0 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=6.0,
        tp_bps=10.0,
        zone_id="Z1",
        expected_fill_probability=0.2615,
        expected_slippage_bps=0.0,
        confidence_level=0.7,
    )
    
    adjusted = integration.adjust_route_score(base_score=60.0, advice=advice)
    
    assert adjusted == 55.0  # 60 - 5


def test_strict_mode_score_stronger_than_advisory(mock_calibration_file):
    """Strict Mode가 Advisory보다 강하게 조정"""
    # Advisory Mode
    config_advisory = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration_advisory = FillModelIntegration.from_config(config_advisory)
    
    # Strict Mode
    config_strict = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration_strict = FillModelIntegration.from_config(config_strict)
    
    advice_z2 = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    base_score = 60.0
    advisory_score = integration_advisory.adjust_route_score(base_score, advice_z2)
    strict_score = integration_strict.adjust_route_score(base_score, advice_z2)
    
    # Strict가 더 크게 증가
    assert strict_score > advisory_score
    assert advisory_score == 65.0  # 60 + 5
    assert strict_score == 70.0  # 60 + 10


# =============================================================================
# Test: Strict Mode Size Adjustment
# =============================================================================

def test_strict_mode_adjust_order_size_z2(mock_calibration_file):
    """Strict Mode Z2 주문 수량 증가 (1.2배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    adjusted = integration.adjust_order_size(base_size=0.01, advice=advice)
    
    assert adjusted == pytest.approx(0.012, rel=1e-6)  # 0.01 * 1.2


def test_strict_mode_adjust_order_size_z1(mock_calibration_file):
    """Strict Mode Z1 주문 수량 변화 없음 (1.0배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=6.0,
        tp_bps=10.0,
        zone_id="Z1",
        expected_fill_probability=0.2615,
        expected_slippage_bps=0.0,
        confidence_level=0.7,
    )
    
    adjusted = integration.adjust_order_size(base_size=0.01, advice=advice)
    
    assert adjusted == 0.01


def test_strict_mode_size_stronger_than_advisory(mock_calibration_file):
    """Strict Mode가 Advisory보다 더 크게 수량 증가"""
    # Advisory Mode
    config_advisory = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration_advisory = FillModelIntegration.from_config(config_advisory)
    
    # Strict Mode
    config_strict = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration_strict = FillModelIntegration.from_config(config_strict)
    
    advice_z2 = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    base_size = 0.01
    advisory_size = integration_advisory.adjust_order_size(base_size, advice_z2)
    strict_size = integration_strict.adjust_order_size(base_size, advice_z2)
    
    # Strict가 더 크게 증가
    assert strict_size > advisory_size
    assert advisory_size == pytest.approx(0.011)  # 0.01 * 1.1
    assert strict_size == pytest.approx(0.012)  # 0.01 * 1.2


# =============================================================================
# Test: Strict Mode Risk Limit Adjustment
# =============================================================================

def test_strict_mode_adjust_risk_limit_z2(mock_calibration_file):
    """Strict Mode Z2 Risk Limit 완화 (1.2배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    adjusted = integration.adjust_risk_limit(base_limit=100000.0, advice=advice)
    
    assert adjusted == pytest.approx(120000.0, rel=1e-6)  # 100000 * 1.2


def test_strict_mode_adjust_risk_limit_z1(mock_calibration_file):
    """Strict Mode Z1 Risk Limit 변화 없음 (1.0배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=6.0,
        tp_bps=10.0,
        zone_id="Z1",
        expected_fill_probability=0.2615,
        expected_slippage_bps=0.0,
        confidence_level=0.7,
    )
    
    adjusted = integration.adjust_risk_limit(base_limit=100000.0, advice=advice)
    
    assert adjusted == 100000.0


def test_strict_mode_limit_stronger_than_advisory(mock_calibration_file):
    """Strict Mode가 Advisory보다 더 크게 Limit 완화"""
    # Advisory Mode
    config_advisory = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration_advisory = FillModelIntegration.from_config(config_advisory)
    
    # Strict Mode
    config_strict = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration_strict = FillModelIntegration.from_config(config_strict)
    
    advice_z2 = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    base_limit = 100000.0
    advisory_limit = integration_advisory.adjust_risk_limit(base_limit, advice_z2)
    strict_limit = integration_strict.adjust_risk_limit(base_limit, advice_z2)
    
    # Strict가 더 크게 완화
    assert strict_limit > advisory_limit
    assert advisory_limit == pytest.approx(110000.0)  # 100000 * 1.1
    assert strict_limit == pytest.approx(120000.0)  # 100000 * 1.2


# =============================================================================
# Test: Mode Switching
# =============================================================================

def test_mode_none_no_adjustment(mock_calibration_file):
    """mode='none' 시 조정 없음"""
    config = FillModelConfig(
        enabled=True,
        mode="none",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    # Score, Size, Limit 모두 변화 없음
    assert integration.adjust_route_score(60.0, advice) == 60.0
    assert integration.adjust_order_size(0.01, advice) == 0.01
    assert integration.adjust_risk_limit(100000.0, advice) == 100000.0


def test_mode_advisory_vs_strict_all_metrics(mock_calibration_file):
    """Advisory vs Strict 전체 비교"""
    # Advisory
    config_advisory = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration_advisory = FillModelIntegration.from_config(config_advisory)
    
    # Strict
    config_strict = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration_strict = FillModelIntegration.from_config(config_strict)
    
    advice_z2 = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    # Score
    advisory_score = integration_advisory.adjust_route_score(60.0, advice_z2)
    strict_score = integration_strict.adjust_route_score(60.0, advice_z2)
    assert strict_score > advisory_score
    
    # Size
    advisory_size = integration_advisory.adjust_order_size(0.01, advice_z2)
    strict_size = integration_strict.adjust_order_size(0.01, advice_z2)
    assert strict_size > advisory_size
    
    # Limit
    advisory_limit = integration_advisory.adjust_risk_limit(100000.0, advice_z2)
    strict_limit = integration_strict.adjust_risk_limit(100000.0, advice_z2)
    assert strict_limit > advisory_limit


# =============================================================================
# Test: Backward Compatibility
# =============================================================================

def test_backward_compatibility_with_d87_1():
    """D87-1 Advisory Mode와의 호환성"""
    # D87-1 Advisory Mode 설정 (Strict 파라미터 없음)
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        advisory_score_bias_z2=5.0,
        advisory_size_multiplier_z2=1.1,
    )
    
    # Strict 파라미터 기본값 확인
    assert config.strict_score_bias_z2 == 10.0
    assert config.strict_size_multiplier_z2 == 1.2
    
    # Advisory Mode에서는 Strict 파라미터 무시
    integration = FillModelIntegration(config=config)
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    # Advisory 파라미터만 적용
    score = integration.adjust_route_score(60.0, advice)
    assert score == 65.0  # 60 + 5 (advisory_score_bias_z2)


# =============================================================================
# Test: Boundary & Edge Cases
# =============================================================================

def test_strict_mode_score_clipping_upper(mock_calibration_file):
    """Strict Mode Score 상한 클리핑 (100)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
        strict_score_bias_z2=50.0,  # 매우 큰 bias
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    adjusted = integration.adjust_route_score(base_score=90.0, advice=advice)
    
    assert adjusted == 100.0  # clipped to 100


def test_strict_mode_score_clipping_lower(mock_calibration_file):
    """Strict Mode Score 하한 클리핑 (0)"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
        strict_score_bias_other=-100.0,  # 매우 큰 penalty
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = FillModelAdvice(
        entry_bps=6.0,
        tp_bps=10.0,
        zone_id="Z1",
        expected_fill_probability=0.2615,
        expected_slippage_bps=0.0,
        confidence_level=0.7,
    )
    
    adjusted = integration.adjust_route_score(base_score=50.0, advice=advice)
    
    assert adjusted == 0.0  # clipped to 0


# =============================================================================
# Test: D87-2 Integration Summary
# =============================================================================

def test_d87_2_strict_mode_summary(mock_calibration_file):
    """
    D87-2 Strict Mode 통합 요약 테스트
    
    검증 항목:
    - Strict Mode 파라미터 (±20% 범위)
    - Advisory 대비 더 강한 조정
    - Z2 Zone 우대, Z1/Z3/Z4 페널티
    - Backward Compatibility
    """
    # 1. Strict Mode 활성화
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    # 2. Z2 Advice 생성
    advice_z2 = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
    assert advice_z2.zone_id == "Z2"
    
    # 3. Z2 Strict 조정 검증 (±20% 범위)
    score_z2 = integration.adjust_route_score(base_score=60.0, advice=advice_z2)
    assert score_z2 == 70.0  # +10.0 (strict_score_bias_z2)
    
    size_z2 = integration.adjust_order_size(base_size=0.01, advice=advice_z2)
    assert size_z2 == pytest.approx(0.012)  # 1.2x (strict_size_multiplier_z2)
    
    limit_z2 = integration.adjust_risk_limit(base_limit=100000.0, advice=advice_z2)
    assert limit_z2 == pytest.approx(120000.0)  # 1.2x (strict_risk_multiplier_z2)
    
    # 4. Z1 Advice 생성
    advice_z1 = integration.compute_advice(entry_bps=6.0, tp_bps=10.0)
    assert advice_z1.zone_id == "Z1"
    
    # 5. Z1 페널티 검증
    score_z1 = integration.adjust_route_score(base_score=60.0, advice=advice_z1)
    assert score_z1 == 55.0  # -5.0 (strict_score_bias_other)
    
    size_z1 = integration.adjust_order_size(base_size=0.01, advice=advice_z1)
    assert size_z1 == 0.01  # 1.0x (no change)
    
    limit_z1 = integration.adjust_risk_limit(base_limit=100000.0, advice=advice_z1)
    assert limit_z1 == 100000.0  # 1.0x (no change)
    
    # 6. Advisory vs Strict 비교
    config_advisory = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration_advisory = FillModelIntegration.from_config(config_advisory)
    
    advisory_score = integration_advisory.adjust_route_score(60.0, advice_z2)
    assert score_z2 > advisory_score  # 70 > 65
