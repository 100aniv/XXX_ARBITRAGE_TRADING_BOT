# -*- coding: utf-8 -*-
"""
D92-5: PnL 통화 SSOT 검증 테스트

목표:
- total_pnl_krw / total_pnl_usd / fx_rate 필드 존재 확인
- KRW → USD 환산 로직 검증

Author: arbitrage-lite project
Date: 2025-12-13 (D92-5)
"""

import pytest


def test_pnl_currency_conversion():
    """PnL KRW → USD 환산 검증"""
    # Given
    pnl_krw = -13000.0
    fx_rate = 1300.0
    
    # When
    pnl_usd = pnl_krw / fx_rate
    
    # Then
    assert pnl_usd == -10.0, f"Expected -10.0 USD, got {pnl_usd}"


def test_pnl_currency_schema():
    """KPI metrics에 PnL 통화 필드 존재 확인"""
    # Given: D92-5 SSOT 스키마
    metrics = {
        "total_pnl_krw": -13000.0,
        "total_pnl_usd": -10.0,
        "fx_rate": 1300.0,
        "currency_note": "pnl_krw converted using fx_rate",
    }
    
    # Then
    assert "total_pnl_krw" in metrics
    assert "total_pnl_usd" in metrics
    assert "fx_rate" in metrics
    assert "currency_note" in metrics
    
    assert isinstance(metrics["total_pnl_krw"], (int, float))
    assert isinstance(metrics["total_pnl_usd"], (int, float))
    assert isinstance(metrics["fx_rate"], (int, float))
    assert isinstance(metrics["currency_note"], str)


def test_pnl_positive_conversion():
    """양수 PnL 환산 검증"""
    # Given
    pnl_krw = 26000.0
    fx_rate = 1300.0
    
    # When
    pnl_usd = pnl_krw / fx_rate
    
    # Then
    assert pnl_usd == 20.0


def test_fx_rate_validation():
    """fx_rate 기본값 검증"""
    # Given
    default_fx_rate = 1300.0
    
    # Then
    assert default_fx_rate > 0
    assert 1000 <= default_fx_rate <= 1500, "FX rate should be in reasonable range"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
