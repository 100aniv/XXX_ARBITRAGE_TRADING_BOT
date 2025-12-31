"""
D205-8: Quote Normalizer v1 테스트

테스트 범위:
- USDT → KRW 변환 정확성
- fx 주입/기록 강제
- 비정상 spread/edge에서 units_mismatch_warning true
- 정상 범위에서 false
"""

import pytest
from arbitrage.v2.core.quote_normalizer import (
    normalize_price_to_krw,
    normalize_notional_to_krw,
    is_units_mismatch,
    get_quote_mode,
    DEFAULT_FX_KRW_PER_USDT,
)


class TestQuoteNormalizer:
    """Quote Normalizer 테스트"""
    
    def test_normalize_price_krw_passthrough(self):
        """KRW → KRW 변환 (passthrough)"""
        price = 100000.0
        result = normalize_price_to_krw(price, "KRW")
        assert result == 100000.0
    
    def test_normalize_price_usdt_to_krw(self):
        """USDT → KRW 변환"""
        price_usdt = 100.0
        fx_rate = 1300.0
        result = normalize_price_to_krw(price_usdt, "USDT", fx_rate)
        assert result == 130000.0
    
    def test_normalize_price_usdt_default_fx(self):
        """USDT → KRW 변환 (기본 FX rate)"""
        price_usdt = 100.0
        result = normalize_price_to_krw(price_usdt, "USDT")
        assert result == 100.0 * DEFAULT_FX_KRW_PER_USDT
    
    def test_normalize_price_unsupported_quote(self):
        """지원하지 않는 quote currency"""
        with pytest.raises(ValueError, match="Unsupported quote currency"):
            normalize_price_to_krw(100.0, "JPY")
    
    def test_normalize_notional_krw(self):
        """Notional KRW 변환"""
        notional = 100000.0
        result = normalize_notional_to_krw(notional, "KRW")
        assert result == 100000.0
    
    def test_normalize_notional_usdt(self):
        """Notional USDT → KRW 변환"""
        notional_usdt = 100.0
        fx_rate = 1300.0
        result = normalize_notional_to_krw(notional_usdt, "USDT", fx_rate)
        assert result == 130000.0


class TestSanityGuard:
    """SanityGuard 테스트"""
    
    def test_units_mismatch_normal_spread(self):
        """정상 범위 spread (수백~수천 bps)"""
        spread_bps = 1000.0
        edge_bps = 500.0
        result = is_units_mismatch(spread_bps, edge_bps)
        assert result is False
    
    def test_units_mismatch_large_spread(self):
        """비정상 spread (수십만 bps) → units_mismatch"""
        spread_bps = 150000.0
        edge_bps = 145000.0
        result = is_units_mismatch(spread_bps, edge_bps)
        assert result is True
    
    def test_units_mismatch_negative_spread(self):
        """음수 spread (절댓값 체크)"""
        spread_bps = -150000.0
        edge_bps = 500.0
        result = is_units_mismatch(spread_bps, edge_bps)
        assert result is True
    
    def test_units_mismatch_edge_only(self):
        """Edge만 비정상"""
        spread_bps = 1000.0
        edge_bps = 200000.0
        result = is_units_mismatch(spread_bps, edge_bps)
        assert result is True
    
    def test_units_mismatch_threshold(self):
        """임계값 경계 테스트"""
        # 경계값 (정확히 100000)
        result_boundary = is_units_mismatch(100000.0, 0.0)
        assert result_boundary is False  # abs(100000) > 100000 → False
        
        # 경계값 초과
        result_over = is_units_mismatch(100001.0, 0.0)
        assert result_over is True


class TestQuoteMode:
    """Quote mode 문자열 생성 테스트"""
    
    def test_quote_mode_binance(self):
        """Binance 포함 → USDT->KRW"""
        result = get_quote_mode("upbit", "binance", 1300.0)
        assert result == "USDT->KRW@1300.0"
    
    def test_quote_mode_binance_default_fx(self):
        """Binance 포함 → USDT->KRW (기본 FX)"""
        result = get_quote_mode("upbit", "binance", None)
        assert result == f"USDT->KRW@{DEFAULT_FX_KRW_PER_USDT}"
    
    def test_quote_mode_krw_only(self):
        """KRW 전용 (Binance 없음)"""
        result = get_quote_mode("upbit", "upbit")
        assert result == "KRW"


class TestIntegration:
    """통합 시나리오 테스트"""
    
    def test_upbit_binance_normalization(self):
        """Upbit(KRW) vs Binance(USDT) 정규화 시나리오"""
        # 입력: Upbit BTC/KRW = 140,000,000 KRW
        #       Binance BTC/USDT = 100,000 USDT
        # FX: 1300 KRW/USDT
        # 정규화 후: 140,000,000 KRW vs 130,000,000 KRW
        
        upbit_price_krw = 140000000.0
        binance_price_usdt = 100000.0
        fx_rate = 1300.0
        
        upbit_normalized = normalize_price_to_krw(upbit_price_krw, "KRW", fx_rate)
        binance_normalized = normalize_price_to_krw(binance_price_usdt, "USDT", fx_rate)
        
        assert upbit_normalized == 140000000.0
        assert binance_normalized == 130000000.0
        
        # Spread 계산 (정규화 후)
        spread_percent = (upbit_normalized - binance_normalized) / binance_normalized * 100.0
        spread_bps = abs(spread_percent * 100.0)
        
        # 예상: (140M - 130M) / 130M * 100 = 7.69%
        # 769 bps (정상 범위)
        assert 700 < spread_bps < 800
        
        # SanityGuard 체크 (정상이어야 함)
        assert is_units_mismatch(spread_bps, spread_bps) is False
    
    def test_non_normalized_detection(self):
        """정규화 안 된 상태 감지 (비정상 spread)"""
        # 정규화 없이 직접 비교 (잘못된 방법)
        upbit_price_krw = 140000000.0
        binance_price_usdt = 100000.0  # 정규화 안 함
        
        # 잘못된 spread 계산
        spread_percent = (upbit_price_krw - binance_price_usdt) / binance_price_usdt * 100.0
        spread_bps = abs(spread_percent * 100.0)
        
        # 예상: (140M - 100K) / 100K * 100 = 139900%
        # 13,990,000 bps (비정상)
        assert spread_bps > 1000000
        
        # SanityGuard 감지 (units_mismatch should be True)
        assert is_units_mismatch(spread_bps, 0.0) is True
