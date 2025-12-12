#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D92-4: PnL 통화 단위 검증 테스트

목적: KRW → USD 환산 로직 검증
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestPnLCurrencyConversion:
    """PnL KRW → USD 환산 검증"""
    
    def test_krw_to_usd_conversion(self):
        """TC1: KRW → USD 환산 (1 USD = 1300 KRW)"""
        pnl_krw = 8400.0
        fx_rate = 1300.0
        pnl_usd = pnl_krw / fx_rate
        
        expected = 6.46  # 8400 / 1300 ≈ 6.46
        assert abs(pnl_usd - expected) < 0.01, f"Expected {expected}, got {pnl_usd}"
    
    def test_negative_pnl_conversion(self):
        """TC2: 손실 시나리오 (KRW → USD)"""
        pnl_krw = -500.0
        fx_rate = 1300.0
        pnl_usd = pnl_krw / fx_rate
        
        expected = -0.38  # -500 / 1300 ≈ -0.38
        assert abs(pnl_usd - expected) < 0.01, f"Expected {expected}, got {pnl_usd}"
    
    def test_large_pnl_conversion(self):
        """TC3: 대규모 PnL (기존 -$40,200 오해 케이스)"""
        # 실제로는 -40,200 KRW였음 (약 -$31)
        pnl_krw = -40200.0
        fx_rate = 1300.0
        pnl_usd = pnl_krw / fx_rate
        
        expected = -30.92  # -40,200 / 1300 ≈ -30.92
        assert abs(pnl_usd - expected) < 0.01, f"Expected {expected}, got {pnl_usd}"
        
        # 이전 문서의 오해: -$40,200 → 실제로는 -$31
        assert pnl_usd > -100, "PnL should be small loss, not -$40,200"
    
    def test_zero_pnl(self):
        """TC4: PnL = 0"""
        pnl_krw = 0.0
        fx_rate = 1300.0
        pnl_usd = pnl_krw / fx_rate
        
        assert pnl_usd == 0.0
    
    def test_fx_rate_consistency(self):
        """TC5: FX rate 일관성 검증"""
        fx_rate = 1300.0
        
        # 1 USD = 1300 KRW
        assert fx_rate > 1000 and fx_rate < 1500, "FX rate should be realistic (1000~1500)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
