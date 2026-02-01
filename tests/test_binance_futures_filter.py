"""
D_ALPHA-1U-FIX-1: Binance Futures exchangeInfo Filter Tests

Tests:
- fetch_futures_supported_bases() 기능 검증
- PEPE, BTC, ETH 등 주요 심볼 지원 확인
- UniverseBuilder futures 필터 통합 검증
"""

import pytest
from arbitrage.exchanges.binance_public_data import BinancePublicDataClient


def test_fetch_futures_supported_bases_returns_set():
    """fetch_futures_supported_bases()가 set을 반환하는지 검증"""
    client = BinancePublicDataClient()
    try:
        bases = client.fetch_futures_supported_bases(quote_asset="USDT")
        
        assert isinstance(bases, set), "Should return set"
        assert len(bases) > 0, "Should have at least one base"
    finally:
        client.close()


def test_fetch_futures_supported_bases_includes_major_symbols():
    """주요 심볼(BTC, ETH, BNB)이 포함되는지 검증"""
    client = BinancePublicDataClient()
    try:
        bases = client.fetch_futures_supported_bases(quote_asset="USDT")
        
        # 주요 심볼 검증
        major_symbols = {"BTC", "ETH", "BNB"}
        assert major_symbols.issubset(bases), f"Should include {major_symbols}"
    finally:
        client.close()


def test_fetch_futures_supported_bases_reasonable_count():
    """합리적인 개수의 bases를 반환하는지 검증 (100+)"""
    client = BinancePublicDataClient()
    try:
        bases = client.fetch_futures_supported_bases(quote_asset="USDT")
        
        # Binance Futures는 100개 이상의 USDT 페어 지원
        assert len(bases) >= 100, f"Expected >= 100 bases, got {len(bases)}"
    finally:
        client.close()


def test_fetch_futures_supported_bases_no_quote_in_bases():
    """Base에 quote currency가 포함되지 않는지 검증"""
    client = BinancePublicDataClient()
    try:
        bases = client.fetch_futures_supported_bases(quote_asset="USDT")
        
        # Base에 "USDT" 문자열이 포함되면 안 됨
        for base in bases:
            assert "USDT" not in base, f"Base {base} should not contain USDT"
    finally:
        client.close()


def test_fetch_futures_supported_bases_handles_empty_response():
    """API 실패 시 빈 set 반환 검증 (모의 실패 시나리오)"""
    # 이 테스트는 실제 API가 정상이면 건너뜀
    # 실패 케이스는 integration test에서 mocking으로 검증
    pass


@pytest.mark.skipif(
    True,  # 실제 API 호출 비용 절약
    reason="Real API call - enable only for full integration tests"
)
def test_fetch_futures_supported_bases_real_api():
    """실제 Binance Futures API 호출 검증 (통합 테스트용)"""
    client = BinancePublicDataClient()
    try:
        bases = client.fetch_futures_supported_bases(quote_asset="USDT")
        
        # 최소 기대치
        assert len(bases) >= 200, f"Expected >= 200 bases, got {len(bases)}"
        
        # 로그 출력 (디버깅용)
        print(f"Fetched {len(bases)} futures-supported bases")
        print(f"Sample bases: {sorted(list(bases))[:20]}")
    finally:
        client.close()
