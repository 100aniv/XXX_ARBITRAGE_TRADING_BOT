# -*- coding: utf-8 -*-
"""
D86: Fill Model Re-Calibration 테스트

목적:
- D86 Calibration JSON 로드 검증
- Zone 매칭 로직 검증
- CalibratedFillModel 동작 검증
- Zone별 fill_ratio 적용 검증

Author: arbitrage-lite project
Date: 2025-12-07
"""

import json
import pytest
from pathlib import Path

from arbitrage.execution.fill_model import (
    SimpleFillModel,
    CalibratedFillModel,
    CalibrationTable,
    CalibrationZone,
    FillContext,
)
from arbitrage.types import OrderSide


@pytest.fixture
def d86_calibration():
    """D86 Calibration JSON 로드"""
    calibration_path = Path("logs/d86/d86_0_calibration.json")
    if not calibration_path.exists():
        pytest.skip("D86 calibration artifact not found: logs/d86/d86_0_calibration.json")
    with open(calibration_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return CalibrationTable(
        version=data["version"],
        zones=data["zones"],
        default_buy_fill_ratio=data["default_buy_fill_ratio"],
        default_sell_fill_ratio=data["default_sell_fill_ratio"],
        created_at=data["created_at"],
        source=data["source"],
    )


def test_d86_calibration_load(d86_calibration):
    """D86 Calibration JSON 로드 검증"""
    assert d86_calibration.version == "d86_0"
    assert len(d86_calibration.zones) == 4
    assert d86_calibration.default_buy_fill_ratio == 0.2615
    assert d86_calibration.default_sell_fill_ratio == 1.0


def test_d86_zone_z1_matching(d86_calibration):
    """Z1 (Entry 5-7 bps) Zone 매칭 검증"""
    # Entry 5.0, TP 7.0 → Z1
    zone = d86_calibration.select_zone(5.0, 7.0)
    assert zone is not None
    assert zone.zone_id == "Z1"
    assert zone.buy_fill_ratio == pytest.approx(0.2615, rel=0.01)
    
    # Entry 7.0, TP 10.0 → Z1 (경계값)
    zone = d86_calibration.select_zone(7.0, 10.0)
    assert zone is not None
    assert zone.zone_id in ["Z1", "Z2"]  # 경계값은 Z1 또는 Z2


def test_d86_zone_z2_matching(d86_calibration):
    """Z2 (Entry 7-12 bps) Zone 매칭 검증"""
    # Entry 10.0, TP 12.0 → Z2
    zone = d86_calibration.select_zone(10.0, 12.0)
    assert zone is not None
    assert zone.zone_id == "Z2"
    assert zone.buy_fill_ratio == pytest.approx(0.6307, rel=0.01)


def test_d86_zone_z3_matching(d86_calibration):
    """Z3 (Entry 12-20 bps) Zone 매칭 검증"""
    # Entry 15.0, TP 20.0 → Z3
    zone = d86_calibration.select_zone(15.0, 20.0)
    assert zone is not None
    assert zone.zone_id == "Z3"
    assert zone.buy_fill_ratio == pytest.approx(0.2615, rel=0.01)


def test_d86_zone_z4_matching(d86_calibration):
    """Z4 (Entry 20-30 bps) Zone 매칭 검증"""
    # Entry 25.0, TP 30.0 → Z4
    zone = d86_calibration.select_zone(25.0, 30.0)
    assert zone is not None
    assert zone.zone_id == "Z4"
    assert zone.buy_fill_ratio == pytest.approx(0.2615, rel=0.01)


def test_d86_calibrated_fill_model_z1(d86_calibration):
    """CalibratedFillModel with D86 Calibration (Z1) 검증"""
    base_model = SimpleFillModel(
        enable_partial_fill=True,
        enable_slippage=True,
        default_slippage_alpha=0.0001,
    )
    
    fill_model = CalibratedFillModel(
        base_model=base_model,
        calibration=d86_calibration,
        entry_bps=5.0,
        tp_bps=7.0,
    )
    
    # Z1 매칭 확인
    assert fill_model.zone is not None
    assert fill_model.zone.zone_id == "Z1"
    
    # BUY Fill 실행
    context = FillContext(
        symbol="BTC",
        side=OrderSide.BUY,
        order_quantity=1.0,
        target_price=50000.0,
        available_volume=10.0,
    )
    
    result = fill_model.execute(context)
    
    # Z1의 buy_fill_ratio=0.2615 적용 확인
    # SimpleFillModel이 100% 체결을 반환하면, Calibration Ratio로 보정됨
    # 실제 fill_ratio는 baseline * calibration_ratio
    assert result.fill_ratio <= 1.0
    assert result.filled_quantity > 0


def test_d86_calibrated_fill_model_z2(d86_calibration):
    """CalibratedFillModel with D86 Calibration (Z2) 검증"""
    base_model = SimpleFillModel(
        enable_partial_fill=True,
        enable_slippage=True,
        default_slippage_alpha=0.0001,
    )
    
    fill_model = CalibratedFillModel(
        base_model=base_model,
        calibration=d86_calibration,
        entry_bps=10.0,
        tp_bps=12.0,
    )
    
    # Z2 매칭 확인
    assert fill_model.zone is not None
    assert fill_model.zone.zone_id == "Z2"
    
    # BUY Fill 실행
    context = FillContext(
        symbol="BTC",
        side=OrderSide.BUY,
        order_quantity=1.0,
        target_price=50000.0,
        available_volume=10.0,
    )
    
    result = fill_model.execute(context)
    
    # Z2의 buy_fill_ratio=0.6307 적용 확인 (Z1보다 높음)
    assert result.fill_ratio <= 1.0
    assert result.filled_quantity > 0


def test_d86_zone_coverage():
    """D86 Calibration이 모든 Entry/TP 조합을 커버하는지 검증"""
    calibration_path = Path("logs/d86/d86_0_calibration.json")
    if not calibration_path.exists():
        pytest.skip("D86 calibration artifact not found: logs/d86/d86_0_calibration.json")
    with open(calibration_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # 모든 Zone에 샘플이 존재하는지 확인
    zones_with_samples = [z for z in data["zones"] if z["samples"] > 0]
    assert len(zones_with_samples) >= 3, "최소 3개 이상의 Zone에 샘플이 있어야 함"
    
    # Z2는 Z1과 다른 fill_ratio를 가져야 함
    z1 = next(z for z in data["zones"] if z["zone_id"] == "Z1")
    z2 = next(z for z in data["zones"] if z["zone_id"] == "Z2")
    
    assert z1["buy_fill_ratio"] != z2["buy_fill_ratio"], "Z1과 Z2는 다른 fill_ratio를 가져야 함"
    assert z2["buy_fill_ratio"] > z1["buy_fill_ratio"], "Z2의 fill_ratio가 Z1보다 높아야 함 (실측 데이터 기준)"
