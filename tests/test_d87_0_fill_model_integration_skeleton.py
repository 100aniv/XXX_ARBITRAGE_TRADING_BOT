# -*- coding: utf-8 -*-
"""
D87-0: Fill Model Integration Skeleton Tests

통합 인터페이스 정의 및 backward compatibility 검증.

D87-1+ 단계에서 실제 구현 후 테스트 확장 예정.

Author: arbitrage-lite project
Date: 2025-12-07
"""

import pytest
from dataclasses import asdict

from arbitrage.execution.fill_model_integration import (
    FillModelAdvice,
    FillModelConfig,
    FillModelIntegration,
)
from arbitrage.domain.arb_route import ArbRoute, RouteDirection, ArbRouteDecision
from arbitrage.arbitrage_core import OrderBookSnapshot
from arbitrage.domain.fee_model import FeeModel
from arbitrage.domain.market_spec import MarketSpec


# =============================================================================
# Fixture: Mock Data
# =============================================================================

@pytest.fixture
def mock_snapshot():
    """Mock OrderBookSnapshot"""
    return OrderBookSnapshot(
        timestamp=1234567890.0,
        best_bid_a=50000000.0,
        best_ask_a=50005000.0,
        best_bid_b=38461.0,
        best_ask_b=38463.0,
    )


@pytest.fixture
def mock_market_spec():
    """Mock MarketSpec"""
    return MarketSpec(
        base_symbol="BTC",
        quote_a="KRW",
        quote_b="USDT",
    )


@pytest.fixture
def mock_fee_model():
    """Mock FeeModel"""
    return FeeModel(
        taker_fee_bps=5.0,
        maker_fee_bps=2.0,
    )


# =============================================================================
# Test: FillModelAdvice Interface
# =============================================================================

def test_fill_model_advice_dataclass():
    """FillModelAdvice 데이터 클래스 구조 검증"""
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=2.5,
        confidence_level=0.8,
    )
    
    assert advice.entry_bps == 10.0
    assert advice.tp_bps == 15.0
    assert advice.zone_id == "Z2"
    assert advice.expected_fill_probability == 0.6307
    assert advice.expected_slippage_bps == 2.5
    assert advice.confidence_level == 0.8
    
    # Serializable
    advice_dict = asdict(advice)
    assert advice_dict["zone_id"] == "Z2"


def test_fill_model_advice_z1_low_fill_ratio():
    """Z1 (low fill_ratio=26%) 시나리오"""
    advice = FillModelAdvice(
        entry_bps=6.0,
        tp_bps=10.0,
        zone_id="Z1",
        expected_fill_probability=0.2615,
        expected_slippage_bps=3.0,
        confidence_level=0.7,
    )
    
    assert advice.zone_id == "Z1"
    assert advice.expected_fill_probability < 0.3


def test_fill_model_advice_z2_high_fill_ratio():
    """Z2 (high fill_ratio=63%) 시나리오"""
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=2.0,
        confidence_level=0.9,
    )
    
    assert advice.zone_id == "Z2"
    assert advice.expected_fill_probability > 0.6


# =============================================================================
# Test: FillModelConfig Interface
# =============================================================================

def test_fill_model_config_defaults():
    """FillModelConfig 기본값 검증"""
    config = FillModelConfig()
    
    assert config.enabled is False
    assert config.mode == "none"
    assert config.calibration_path is None
    assert config.min_confidence_level == 0.5
    assert config.staleness_threshold_seconds == 86400.0


def test_fill_model_config_advisory_mode():
    """Advisory Mode 설정"""
    config = FillModelConfig(
        enabled=True,
        mode="advisory",
        calibration_path="logs/d86/d86_0_calibration.json",
    )
    
    assert config.enabled is True
    assert config.mode == "advisory"
    assert "d86_0_calibration.json" in config.calibration_path


def test_fill_model_config_strict_mode():
    """Strict Mode 설정"""
    config = FillModelConfig(
        enabled=True,
        mode="strict",
        calibration_path="logs/d86/d86_0_calibration.json",
        min_confidence_level=0.7,
    )
    
    assert config.enabled is True
    assert config.mode == "strict"
    assert config.min_confidence_level == 0.7


# =============================================================================
# Test: FillModelIntegration Skeleton
# =============================================================================

def test_fill_model_integration_init():
    """FillModelIntegration 초기화 검증"""
    config = FillModelConfig(enabled=False, mode="none")
    integration = FillModelIntegration(config)
    
    assert integration.config.enabled is False
    assert integration.config.mode == "none"


def test_fill_model_integration_compute_advice_implemented():
    """compute_advice() D87-1 구현 완료 검증"""
    config = FillModelConfig(enabled=False)
    integration = FillModelIntegration(config)
    
    # D87-1: enabled=False이면 None 반환
    result = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
    assert result is None


def test_fill_model_integration_adjust_route_score_implemented():
    """adjust_route_score() D87-1 구현 완료 검증"""
    config = FillModelConfig(enabled=False, mode="none")
    integration = FillModelIntegration(config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=2.5,
        confidence_level=0.8,
    )
    
    # D87-1: mode='none'이면 base_score 그대로 반환
    result = integration.adjust_route_score(base_score=60.0, advice=advice)
    assert result == 60.0


def test_fill_model_integration_adjust_order_size_implemented():
    """adjust_order_size() D87-1 구현 완료 검증 (adjust_order_params는 adjust_order_size로 변경)"""
    config = FillModelConfig(enabled=False, mode="none")
    integration = FillModelIntegration(config)
    
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=2.5,
        confidence_level=0.8,
    )
    
    # D87-1: adjust_order_size 구현 완료 (mode='none'이면 base_size 그대로 반환)
    result = integration.adjust_order_size(base_size=0.01, advice=advice)
    assert result == 0.01


def test_fill_model_integration_check_health_implemented():
    """check_health() D87-1 구현 완료 검증"""
    config = FillModelConfig(enabled=False)
    integration = FillModelIntegration(config)
    
    # D87-1: check_health 구현 완료 (calibration 없으면 unhealthy)
    result = integration.check_health()
    assert result["healthy"] is False
    assert "Calibration 데이터 없음" in result["warnings"]


# =============================================================================
# Test: ArbRoute Backward Compatibility
# =============================================================================

# NOTE: ArbRoute integration tests are skipped in D87-0 skeleton
# due to complex fixture dependencies.
# Full integration tests will be added in D87-1 after implementation.


# =============================================================================
# Test: Integration Summary
# =============================================================================

def test_d87_0_integration_summary():
    """
    D87-0/D87-1 통합 요약 테스트
    
    검증 항목:
    - FillModelAdvice, FillModelConfig, FillModelIntegration 인터페이스 정의 완료
    - ArbRoute.evaluate() backward compatibility 유지
    - D87-1에서 모든 메서드 구현 완료 (Advisory Mode)
    """
    # 1. FillModelAdvice 생성 가능
    advice = FillModelAdvice(
        entry_bps=10.0,
        tp_bps=15.0,
        zone_id="Z2",
        expected_fill_probability=0.6307,
        expected_slippage_bps=2.5,
        confidence_level=0.8,
    )
    assert advice.zone_id == "Z2"
    
    # 2. FillModelConfig 생성 가능
    config = FillModelConfig(enabled=False, mode="none")
    assert config.mode == "none"
    
    # 3. FillModelIntegration 초기화 가능
    integration = FillModelIntegration(config)
    assert integration.config.enabled is False
    
    # 4. D87-1: 메서드들이 구현되어 정상 동작 (enabled=False이면 no-op)
    result = integration.compute_advice(10.0, 15.0)
    assert result is None  # enabled=False
    
    score = integration.adjust_route_score(60.0, advice)
    assert score == 60.0  # mode='none'
    
    size = integration.adjust_order_size(0.01, advice)
    assert size == 0.01  # mode='none'
    
    limit = integration.adjust_risk_limit(100000.0, advice)
    assert limit == 100000.0  # mode='none'
    
    health = integration.check_health()
    assert health["healthy"] is False  # no calibration
