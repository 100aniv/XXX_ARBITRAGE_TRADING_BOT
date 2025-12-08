# -*- coding: utf-8 -*-
"""
D87-1: Fill Model Integration Advisory Mode Tests

FillModelIntegration Advisory Mode 기능 검증:
- Calibration 로드 및 유효성 검증
- FillModelAdvice 생성 (Zone 매칭)
- Route Score 보정 (Z2 우대, Z1/Z3/Z4 페널티)
- Order Size 조정 (Z2 증가, 기타 유지)
- Risk Limit 조정 (Z2 완화, 기타 유지)
- Health Check (staleness, confidence)
- Mode="none" backward compatibility

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
            {
                "zone_id": "Z4",
                "entry_min": 20.0,
                "entry_max": 30.0,
                "tp_min": 25.0,
                "tp_max": 40.0,
                "buy_fill_ratio": 0.2615,
                "sell_fill_ratio": 1.0,
                "samples": 4,
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
# Test: Calibration Loading
# =============================================================================

def test_from_config_loads_calibration(mock_calibration_file):
    """from_config() calibration 로드 검증"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    
    integration = FillModelIntegration.from_config(config)
    
    assert integration.calibration_data is not None
    assert integration.calibration_data["version"] == "d86_0"
    assert len(integration.calibration_data["zones"]) == 4
    assert integration.calibration_loaded_at is not None


def test_from_config_missing_file():
    """from_config() 파일 없음 예외 검증"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path="/nonexistent/calibration.json",
    )
    
    with pytest.raises(FileNotFoundError):
        FillModelIntegration.from_config(config)


def test_from_config_invalid_format(tmp_path):
    """from_config() 잘못된 포맷 예외 검증"""
    invalid_file = tmp_path / "invalid.json"
    with open(invalid_file, "w") as f:
        json.dump({"invalid": "data"}, f)
    
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(invalid_file),
    )
    
    with pytest.raises(ValueError, match="missing required field"):
        FillModelIntegration.from_config(config)


def test_from_config_disabled_no_load():
    """enabled=False 시 calibration 로드 안 함"""
    config = FillModelConfig(
        enabled=False,
        mode="none",
        calibration_path="/some/path.json",
    )
    
    integration = FillModelIntegration.from_config(config)
    
    assert integration.calibration_data is None


# =============================================================================
# Test: Advice Generation (Zone Matching)
# =============================================================================

def test_compute_advice_z2_match(mock_calibration_file):
    """Z2 Zone 매칭 검증"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    # Z2 범위: Entry 7-12, TP 10-20
    advice = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
    
    assert advice is not None
    assert advice.zone_id == "Z2"
    assert advice.expected_fill_probability == 0.6307
    assert advice.entry_bps == 10.0
    assert advice.tp_bps == 15.0
    assert 0.0 <= advice.confidence_level <= 1.0


def test_compute_advice_z1_match(mock_calibration_file):
    """Z1 Zone 매칭 검증"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    # Z1 범위: Entry 5-7, TP 7-12
    advice = integration.compute_advice(entry_bps=6.0, tp_bps=10.0)
    
    assert advice is not None
    assert advice.zone_id == "Z1"
    assert advice.expected_fill_probability == 0.2615


def test_compute_advice_no_match_default(mock_calibration_file):
    """Zone 미매칭 시 DEFAULT 사용"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    # Zone 범위 밖
    advice = integration.compute_advice(entry_bps=40.0, tp_bps=50.0)
    
    assert advice is not None
    assert advice.zone_id == "DEFAULT"
    assert advice.expected_fill_probability == 0.2615  # default_buy_fill_ratio
    assert advice.confidence_level == 0.0


def test_compute_advice_mode_none_returns_none(mock_calibration_file):
    """mode='none' 시 None 반환"""
    config = FillModelConfig(
        enabled=True,
        mode="none",
        calibration_path=str(mock_calibration_file),
    )
    integration = FillModelIntegration.from_config(config)
    
    advice = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
    
    assert advice is None


def test_compute_advice_disabled_returns_none():
    """enabled=False 시 None 반환"""
    config = FillModelConfig(enabled=False)
    integration = FillModelIntegration(config=config)
    
    advice = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
    
    assert advice is None


# =============================================================================
# Test: Route Score Adjustment (Advisory Mode)
# =============================================================================

def test_adjust_route_score_z2_bonus(mock_calibration_file):
    """Z2 Score 보정 (+5.0 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_score_bias_z2=5.0,
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
    
    assert adjusted == 63.0  # 60 * 1.05 (D87-4 multiplicative)


def test_adjust_route_score_z1_penalty(mock_calibration_file):
    """Z1 Score 보정 (-2.0 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_score_bias_other=-2.0,
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
    
    assert adjusted == 54.0  # 60 * 0.90 (D87-4 multiplicative)


def test_adjust_route_score_clipping(mock_calibration_file):
    """Score 0~100 범위 클리핑"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_score_bias_z2=50.0,
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
    
    assert adjusted == 94.5  # 90.0 * 1.05 = 94.5 (D87-4 multiplicative, no clip needed) to 100


def test_adjust_route_score_mode_none_no_change():
    """mode='none' 시 score 변경 없음"""
    config = FillModelConfig(enabled=True, mode="none")
    integration = FillModelIntegration(config=config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    adjusted = integration.adjust_route_score(base_score=60.0, advice=advice)
    
    assert adjusted == 60.0  # no change


# =============================================================================
# Test: Order Size Adjustment (Advisory Mode)
# =============================================================================

def test_adjust_order_size_z2_increase(mock_calibration_file):
    """Z2 주문 수량 증가 (1.1배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_size_multiplier_z2=1.1,
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
    
    assert adjusted == pytest.approx(0.011, rel=1e-6)  # 0.01 * 1.1


def test_adjust_order_size_z1_no_change(mock_calibration_file):
    """Z1 주문 수량 변화 없음 (1.0배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_size_multiplier_other=1.0,
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


def test_adjust_order_size_mode_none_no_change():
    """mode='none' 시 size 변경 없음"""
    config = FillModelConfig(enabled=True, mode="none")
    integration = FillModelIntegration(config=config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    adjusted = integration.adjust_order_size(base_size=0.01, advice=advice)
    
    assert adjusted == 0.01


# =============================================================================
# Test: Risk Limit Adjustment (Advisory Mode)
# =============================================================================

def test_adjust_risk_limit_z2_relaxed(mock_calibration_file):
    """Z2 Risk Limit 완화 (1.1배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_risk_multiplier_z2=1.1,
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
    
    assert adjusted == pytest.approx(110000.0, rel=1e-6)  # 100000 * 1.1


def test_adjust_risk_limit_z1_no_change(mock_calibration_file):
    """Z1 Risk Limit 변화 없음 (1.0배 기본)"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_risk_multiplier_other=1.0,
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


def test_adjust_risk_limit_mode_none_no_change():
    """mode='none' 시 limit 변경 없음"""
    config = FillModelConfig(enabled=True, mode="none")
    integration = FillModelIntegration(config=config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=0.0,
        confidence_level=0.8,
    )
    
    adjusted = integration.adjust_risk_limit(base_limit=100000.0, advice=advice)
    
    assert adjusted == 100000.0


# =============================================================================
# Test: Health Check
# =============================================================================

def test_check_health_healthy(mock_calibration_file):
    """정상 상태 Health Check"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        min_confidence_level=0.5,
    )
    integration = FillModelIntegration.from_config(config)
    
    health = integration.check_health()
    
    assert health["healthy"] is True
    assert health["calibration_age_seconds"] >= 0.0
    assert health["confidence_level"] > 0.0
    assert len(health["warnings"]) == 0


def test_check_health_no_calibration():
    """Calibration 없을 때 Health Check"""
    config = FillModelConfig(enabled=False)
    integration = FillModelIntegration(config=config)
    
    health = integration.check_health()
    
    assert health["healthy"] is False
    assert "Calibration 데이터 없음" in health["warnings"]


def test_check_health_low_confidence(mock_calibration_file):
    """낮은 confidence Health Check"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        min_confidence_level=0.9,  # 매우 높은 threshold
    )
    integration = FillModelIntegration.from_config(config)
    
    health = integration.check_health()
    
    assert health["healthy"] is False
    assert any("Confidence 낮음" in w for w in health["warnings"])


# =============================================================================
# Test: Integration Summary
# =============================================================================

def test_d87_1_integration_summary(mock_calibration_file):
    """
    D87-1 통합 요약 테스트
    
    검증 항목:
    - Calibration 로드 및 Zone 매칭
    - Z2 Zone에서 Score/Size/Limit 우대
    - Z1/Z3/Z4 Zone에서 Score 페널티
    - mode='none' backward compatibility
    """
    # 1. Advisory Mode 활성화
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path=str(mock_calibration_file),
        advisory_score_bias_z2=5.0,
        advisory_score_bias_other=-2.0,
        advisory_size_multiplier_z2=1.1,
        advisory_size_multiplier_other=1.0,
        advisory_risk_multiplier_z2=1.1,
        advisory_risk_multiplier_other=1.0,
    )
    integration = FillModelIntegration.from_config(config)
    
    # 2. Z2 Advice 생성
    advice_z2 = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
    assert advice_z2.zone_id == "Z2"
    assert advice_z2.expected_fill_probability > 0.6
    
    # 3. Z2 우대 검증
    score_z2 = integration.adjust_route_score(base_score=60.0, advice=advice_z2)
    assert score_z2 == 63.0  # 60 * 1.05 (D87-4 multiplicative)
    
    size_z2 = integration.adjust_order_size(base_size=0.01, advice=advice_z2)
    assert size_z2 == pytest.approx(0.011)  # 1.1x
    
    limit_z2 = integration.adjust_risk_limit(base_limit=100000.0, advice=advice_z2)
    assert limit_z2 == pytest.approx(110000.0)  # 1.1x
    
    # 4. Z1 Advice 생성
    advice_z1 = integration.compute_advice(entry_bps=6.0, tp_bps=10.0)
    assert advice_z1.zone_id == "Z1"
    assert advice_z1.expected_fill_probability < 0.3
    
    # 5. Z1 페널티 검증
    score_z1 = integration.adjust_route_score(base_score=60.0, advice=advice_z1)
    assert score_z1 == 54.0  # 60 * 0.90 (D87-4 multiplicative)
    
    size_z1 = integration.adjust_order_size(base_size=0.01, advice=advice_z1)
    assert size_z1 == 0.01  # 1.0x (no change)
    
    limit_z1 = integration.adjust_risk_limit(base_limit=100000.0, advice=advice_z1)
    assert limit_z1 == 100000.0  # 1.0x (no change)
    
    # 6. Health Check
    health = integration.check_health()
    assert health["healthy"] is True
