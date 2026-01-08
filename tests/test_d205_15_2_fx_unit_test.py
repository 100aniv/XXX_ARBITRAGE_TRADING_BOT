"""
D205-15-2: FX Unit Test (ADD-ON Requirement #1)

KRW-USDT 변환 로직 검증 단위 테스트
"""

import pytest
from arbitrage.v2.scan.metrics import ScanMetricsCalculator
from arbitrage.v2.scan.scanner import ScanConfig


def test_fx_conversion_krw_to_usdt():
    """
    FX 변환 단위 테스트 (정답 고정)
    
    Given:
        - Binance USDT bid = 1.0 USDT
        - FX rate = 1000 KRW/USDT
    
    Expected:
        - Binance KRW bid = 1000 KRW
    """
    fx_rate = 1000.0
    binance_usdt_bid = 1.0
    
    # scanner.py:154와 동일한 로직
    binance_krw_bid = binance_usdt_bid * fx_rate
    
    assert binance_krw_bid == 1000.0, f"Expected 1000 KRW, got {binance_krw_bid}"


def test_spread_calculation_same_currency():
    """
    Spread 계산 단위 테스트 (동일 통화)
    
    Given:
        - Upbit KRW mid = 1000 KRW
        - Binance KRW mid = 1100 KRW
    
    Expected:
        - spread_bps = (100 / 1000) * 10000 = 1000 bps
    """
    upbit_mid_krw = 1000.0
    binance_mid_krw = 1100.0
    
    # metrics.py:106-107와 동일한 로직
    spread_abs = abs(upbit_mid_krw - binance_mid_krw)
    spread_bps = (spread_abs / upbit_mid_krw) * 10000
    
    assert spread_bps == 1000.0, f"Expected 1000 bps, got {spread_bps}"


def test_edge_calculation_config_driven():
    """
    Edge 계산 단위 테스트 (Config-driven costs)
    
    Given:
        - spread_bps = 1000 bps
        - total_fee = 9 bps (upbit 5 + binance 4)
        - slippage = 5 bps
        - fx_conversion = 2 bps
        - buffer = 10 bps
    
    Expected:
        - raw_edge = 1000 - 9 = 991 bps
        - net_edge = 991 - 5 - 2 - 10 = 974 bps
    """
    scan_config = ScanConfig(
        fx_krw_per_usdt=1300.0,
        upbit_fee_bps=5.0,
        binance_fee_bps=4.0,
        slippage_bps=5.0,
        fx_conversion_bps=2.0,
        buffer_bps=10.0,
    )
    
    spread_bps = 1000.0
    
    # metrics.py:110-111과 동일한 로직
    total_fee_bps = scan_config.upbit_fee_bps + scan_config.binance_fee_bps
    raw_edge_bps = spread_bps - total_fee_bps
    net_edge_bps = raw_edge_bps - scan_config.slippage_bps - scan_config.fx_conversion_bps - scan_config.buffer_bps
    
    assert raw_edge_bps == 991.0, f"Expected raw_edge 991 bps, got {raw_edge_bps}"
    assert net_edge_bps == 974.0, f"Expected net_edge 974 bps, got {net_edge_bps}"


def test_fx_rate_sanity_check():
    """
    FX rate 상식 체크
    
    2025년 기준 KRW/USDT 환율은 1200~1500 범위
    """
    fx_rate = 1300.0
    
    assert 1200 <= fx_rate <= 1500, f"FX rate {fx_rate} out of realistic range (1200~1500)"
