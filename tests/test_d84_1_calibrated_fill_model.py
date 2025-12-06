# -*- coding: utf-8 -*-
"""
D84-1: CalibratedFillModel 유닛 테스트

테스트 목표:
    1. Zone matching 정확도
    2. Calibration Ratio 적용 정확도
    3. Zone 미매칭 시 fallback 동작
    4. 기존 SimpleFillModel 로직 유지

Author: arbitrage-lite project
Date: 2025-12-06
"""

import pytest
from arbitrage.execution.fill_model import (
    SimpleFillModel,
    CalibratedFillModel,
    CalibrationTable,
    CalibrationZone,
    FillContext,
    FillResult,
)
from arbitrage.types import OrderSide


# Test Data: Calibration Table
@pytest.fixture
def sample_calibration():
    """샘플 Calibration Table"""
    return CalibrationTable(
        version="test_v1",
        zones=[
            {
                "zone_id": "Z1",
                "entry_min": 5.0,
                "entry_max": 7.0,
                "tp_min": 7.0,
                "tp_max": 12.0,
                "buy_fill_ratio": 0.35,
                "sell_fill_ratio": 1.0,
                "samples": 10,
            },
            {
                "zone_id": "Z2",
                "entry_min": 10.0,
                "entry_max": 14.0,
                "tp_min": 12.0,
                "tp_max": 16.0,
                "buy_fill_ratio": 0.25,
                "sell_fill_ratio": 1.0,
                "samples": 15,
            },
        ],
        default_buy_fill_ratio=0.2615,
        default_sell_fill_ratio=1.0,
        created_at="2025-12-06T10:00:00",
        source="test",
    )


# Test 1: Zone Matching - 정확한 매칭
def test_calibrated_fill_model_zone_matching_exact(sample_calibration):
    """Zone Matching: Entry/TP가 정확히 Zone 범위 내"""
    base_model = SimpleFillModel()
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=6.0,  # Z1 범위 내
        tp_bps=10.0,  # Z1 범위 내
    )
    
    assert calibrated_model.zone is not None
    assert calibrated_model.zone.zone_id == "Z1"


# Test 2: Zone Matching - 경계값
def test_calibrated_fill_model_zone_matching_boundary(sample_calibration):
    """Zone Matching: Entry/TP가 경계값"""
    base_model = SimpleFillModel()
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=10.0,  # Z2 하한
        tp_bps=12.0,  # Z2 하한
    )
    
    assert calibrated_model.zone is not None
    assert calibrated_model.zone.zone_id == "Z2"


# Test 3: Zone Matching - 미매칭 (기본값 사용)
def test_calibrated_fill_model_zone_matching_unmatched(sample_calibration):
    """Zone Matching: Entry/TP가 어떤 Zone에도 속하지 않음"""
    base_model = SimpleFillModel()
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=20.0,  # 범위 밖
        tp_bps=25.0,  # 범위 밖
    )
    
    assert calibrated_model.zone is None


# Test 4: Calibration Ratio 적용 - BUY
def test_calibrated_fill_model_buy_ratio_applied(sample_calibration):
    """Calibration Ratio: BUY Fill Ratio가 Zone별로 적용됨"""
    base_model = SimpleFillModel()
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=6.0,  # Z1
        tp_bps=10.0,
    )
    
    context = FillContext(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_quantity=1000.0,
        target_price=50000.0,
        available_volume=5000.0,  # 충분한 잔량
    )
    
    result = calibrated_model.execute(context)
    
    # Z1의 buy_fill_ratio=0.35 적용되어야 함
    assert result.fill_ratio == pytest.approx(0.35, abs=0.01)


# Test 5: Calibration Ratio 적용 - SELL
def test_calibrated_fill_model_sell_ratio_applied(sample_calibration):
    """Calibration Ratio: SELL Fill Ratio가 Zone별로 적용됨"""
    base_model = SimpleFillModel()
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=12.0,  # Z2
        tp_bps=14.0,
    )
    
    context = FillContext(
        symbol="BTC/USDT",
        side=OrderSide.SELL,
        order_quantity=500.0,
        target_price=51000.0,
        available_volume=3000.0,
    )
    
    result = calibrated_model.execute(context)
    
    # Z2의 sell_fill_ratio=1.0 적용되어야 함
    assert result.fill_ratio == pytest.approx(1.0, abs=0.01)


# Test 6: Fallback to Default - Zone 미매칭 시
def test_calibrated_fill_model_fallback_default(sample_calibration):
    """Fallback: Zone 미매칭 시 기본값 사용"""
    base_model = SimpleFillModel()
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=20.0,  # 범위 밖
        tp_bps=25.0,
    )
    
    context = FillContext(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_quantity=1000.0,
        target_price=50000.0,
        available_volume=5000.0,
    )
    
    result = calibrated_model.execute(context)
    
    # default_buy_fill_ratio=0.2615 적용되어야 함
    assert result.fill_ratio == pytest.approx(0.2615, abs=0.01)


# Test 7: Slippage 로직 유지
def test_calibrated_fill_model_slippage_preserved(sample_calibration):
    """Slippage: 기존 SimpleFillModel의 Slippage 로직 유지"""
    base_model = SimpleFillModel(enable_slippage=True, default_slippage_alpha=0.0001)
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=6.0,
        tp_bps=10.0,
    )
    
    context = FillContext(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_quantity=1000.0,
        target_price=50000.0,
        available_volume=5000.0,
    )
    
    result = calibrated_model.execute(context)
    
    # Slippage가 적용되어 effective_price > target_price
    assert result.slippage_bps >= 0
    assert result.effective_price >= context.target_price


# Test 8: Fill Ratio Clamping
def test_calibrated_fill_model_ratio_clamping(sample_calibration):
    """Fill Ratio: 0.0 ~ 1.0 범위로 Clamp"""
    base_model = SimpleFillModel()
    
    # 비정상적으로 높은 Calibration Ratio
    bad_calibration = CalibrationTable(
        version="test_bad",
        zones=[
            {
                "zone_id": "Z_BAD",
                "entry_min": 5.0,
                "entry_max": 7.0,
                "tp_min": 7.0,
                "tp_max": 12.0,
                "buy_fill_ratio": 1.5,  # 1.0 초과
                "sell_fill_ratio": 1.0,
                "samples": 1,
            },
        ],
        default_buy_fill_ratio=0.2615,
        default_sell_fill_ratio=1.0,
        created_at="2025-12-06",
        source="test",
    )
    
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=bad_calibration,
        entry_bps=6.0,
        tp_bps=10.0,
    )
    
    context = FillContext(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_quantity=1000.0,
        target_price=50000.0,
        available_volume=5000.0,
    )
    
    result = calibrated_model.execute(context)
    
    # Fill Ratio는 1.0을 초과하지 않아야 함
    assert result.fill_ratio <= 1.0


# Test 9: Zero Available Volume
def test_calibrated_fill_model_zero_available_volume(sample_calibration):
    """Edge Case: available_volume=0일 때 미체결"""
    base_model = SimpleFillModel()
    calibrated_model = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=6.0,
        tp_bps=10.0,
    )
    
    context = FillContext(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_quantity=1000.0,
        target_price=50000.0,
        available_volume=0.0,  # 잔량 없음
    )
    
    result = calibrated_model.execute(context)
    
    assert result.filled_quantity == 0.0
    assert result.fill_ratio == 0.0
    assert result.status == "unfilled"


# Test 10: Multiple Zones Coverage
def test_calibrated_fill_model_multiple_zones(sample_calibration):
    """Zone Coverage: 여러 Zone에 대해 각각 다른 Fill Ratio 적용"""
    base_model = SimpleFillModel()
    
    # Z1
    model_z1 = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=6.0,
        tp_bps=10.0,
    )
    
    # Z2
    model_z2 = CalibratedFillModel(
        base_model=base_model,
        calibration=sample_calibration,
        entry_bps=12.0,
        tp_bps=14.0,
    )
    
    context = FillContext(
        symbol="BTC/USDT",
        side=OrderSide.BUY,
        order_quantity=1000.0,
        target_price=50000.0,
        available_volume=5000.0,
    )
    
    result_z1 = model_z1.execute(context)
    result_z2 = model_z2.execute(context)
    
    # Z1=0.35, Z2=0.25로 다른 Fill Ratio
    assert result_z1.fill_ratio == pytest.approx(0.35, abs=0.01)
    assert result_z2.fill_ratio == pytest.approx(0.25, abs=0.01)
    assert result_z1.fill_ratio != result_z2.fill_ratio
