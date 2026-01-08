"""
D205-15-4: Real-time FX Integration Tests

테스트 범위:
- LiveFxProvider: crypto-implied 계산, 캐시, fallback
- FxRateInfo: Evidence 직렬화
- validate_fx_provider_for_mode: LIVE 차단
- Config fx 섹션 로딩

SSOT: D_ROADMAP.md → D205-15-4
"""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from arbitrage.v2.core.fx_provider import (
    FxProvider,
    FixedFxProvider,
    LiveFxProvider,
    FxRateInfo,
    validate_fx_provider_for_mode,
)


class TestFxRateInfo:
    """FxRateInfo 데이터클래스 테스트"""
    
    def test_to_dict_basic(self):
        """기본 직렬화"""
        info = FxRateInfo(
            rate=1450.0,
            source="crypto_implied",
            timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            degraded=False,
        )
        result = info.to_dict()
        
        assert result["fx_rate"] == 1450.0
        assert result["fx_source"] == "crypto_implied"
        assert "2026-01-08" in result["fx_timestamp"]
        assert result["fx_degraded"] is False
        assert result["fx_degraded_reason"] is None
    
    def test_to_dict_degraded(self):
        """degraded 상태 직렬화"""
        info = FxRateInfo(
            rate=1400.0,
            source="crypto_implied_fallback",
            timestamp=datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc),
            degraded=True,
            degraded_reason="Network timeout",
        )
        result = info.to_dict()
        
        assert result["fx_degraded"] is True
        assert result["fx_degraded_reason"] == "Network timeout"


class TestFixedFxProvider:
    """FixedFxProvider 테스트"""
    
    def test_get_fx_rate_usdt_krw(self):
        """USDT → KRW 고정 환율"""
        provider = FixedFxProvider(fx_krw_per_usdt=1450.0)
        rate = provider.get_fx_rate("USDT", "KRW")
        assert rate == 1450.0
    
    def test_get_fx_rate_krw_krw(self):
        """KRW → KRW = 1.0"""
        provider = FixedFxProvider()
        rate = provider.get_fx_rate("KRW", "KRW")
        assert rate == 1.0
    
    def test_get_fx_rate_unsupported(self):
        """지원하지 않는 통화 쌍"""
        provider = FixedFxProvider()
        with pytest.raises(ValueError, match="Unsupported FX pair"):
            provider.get_fx_rate("USD", "KRW")
    
    def test_is_live_false(self):
        """Fixed provider는 Live 아님"""
        provider = FixedFxProvider()
        assert provider.is_live() is False


class TestLiveFxProvider:
    """LiveFxProvider 테스트"""
    
    def test_init_default(self):
        """기본 초기화"""
        provider = LiveFxProvider()
        assert provider.source == "crypto_implied"
        assert provider.ttl_seconds == 10.0
        assert provider.is_live() is True
    
    def test_get_fx_rate_krw_krw(self):
        """KRW → KRW = 1.0"""
        provider = LiveFxProvider()
        rate = provider.get_fx_rate("KRW", "KRW")
        assert rate == 1.0
    
    def test_get_fx_rate_unsupported(self):
        """지원하지 않는 통화 쌍"""
        provider = LiveFxProvider()
        with pytest.raises(ValueError, match="Unsupported FX pair"):
            provider.get_fx_rate("USD", "EUR")
    
    def test_crypto_implied_no_fetcher_fallback(self):
        """market_data_fetcher 없으면 기본값 1400.0 반환"""
        provider = LiveFxProvider(source="crypto_implied")
        rate = provider.get_fx_rate("USDT", "KRW")
        assert rate == 1400.0  # 기본값 fallback
    
    def test_crypto_implied_with_mock_fetcher(self):
        """mock fetcher로 crypto-implied 계산"""
        mock_fetcher = MagicMock()
        mock_fetcher.get_mid_price.side_effect = lambda exch, sym: {
            ("upbit", "BTC/KRW"): 145_000_000,  # 1.45억 원
            ("binance", "BTC/USDT"): 100_000,    # 10만 USDT
        }.get((exch, sym), 0)
        
        provider = LiveFxProvider(
            source="crypto_implied",
            market_data_fetcher=mock_fetcher,
        )
        rate = provider.get_fx_rate("USDT", "KRW")
        
        # 145,000,000 / 100,000 = 1450.0
        assert rate == 1450.0
    
    def test_cache_ttl(self):
        """캐시 TTL 동작"""
        mock_fetcher = MagicMock()
        mock_fetcher.get_mid_price.side_effect = lambda exch, sym: {
            ("upbit", "BTC/KRW"): 145_000_000,
            ("binance", "BTC/USDT"): 100_000,
        }.get((exch, sym), 0)
        
        provider = LiveFxProvider(
            source="crypto_implied",
            ttl_seconds=0.1,  # 100ms TTL
            market_data_fetcher=mock_fetcher,
        )
        
        # 첫 호출
        rate1 = provider.get_fx_rate("USDT", "KRW")
        assert rate1 == 1450.0
        
        # 캐시에서 반환 (fetch 호출 없음)
        mock_fetcher.get_mid_price.reset_mock()
        rate2 = provider.get_fx_rate("USDT", "KRW")
        assert rate2 == 1450.0
        assert mock_fetcher.get_mid_price.call_count == 0  # 캐시 히트
        
        # TTL 만료 후 재조회
        time.sleep(0.15)
        rate3 = provider.get_fx_rate("USDT", "KRW")
        assert rate3 == 1450.0
        assert mock_fetcher.get_mid_price.call_count == 2  # 재조회
    
    def test_fallback_after_failure(self):
        """실패 후 last_good_rate fallback"""
        mock_fetcher = MagicMock()
        call_count = [0]
        
        def side_effect(exch, sym):
            call_count[0] += 1
            if call_count[0] <= 2:  # 첫 2회 성공
                return {
                    ("upbit", "BTC/KRW"): 145_000_000,
                    ("binance", "BTC/USDT"): 100_000,
                }.get((exch, sym), 0)
            else:  # 이후 실패
                raise RuntimeError("Network error")
        
        mock_fetcher.get_mid_price.side_effect = side_effect
        
        provider = LiveFxProvider(
            source="crypto_implied",
            ttl_seconds=0.05,  # 50ms TTL
            market_data_fetcher=mock_fetcher,
        )
        
        # 첫 호출 성공
        rate1 = provider.get_fx_rate("USDT", "KRW")
        assert rate1 == 1450.0
        
        # TTL 만료 후 실패 → fallback
        time.sleep(0.1)
        rate2 = provider.get_fx_rate("USDT", "KRW")
        assert rate2 == 1450.0  # last_good_rate
        
        # degraded 상태 확인
        info = provider.get_rate_info()
        assert info is not None
        assert info.degraded is True
        assert "Network error" in (info.degraded_reason or "")
    
    def test_first_failure_raises(self):
        """첫 조회 실패 시 예외 발생"""
        mock_fetcher = MagicMock()
        mock_fetcher.get_mid_price.side_effect = RuntimeError("API down")
        
        provider = LiveFxProvider(
            source="crypto_implied",
            market_data_fetcher=mock_fetcher,
        )
        
        with pytest.raises(RuntimeError, match="no fallback available"):
            provider.get_fx_rate("USDT", "KRW")
    
    def test_get_krw_per_usdt_convenience(self):
        """get_krw_per_usdt 편의 메서드"""
        provider = LiveFxProvider()
        rate = provider.get_krw_per_usdt()
        assert rate == 1400.0  # 기본값 fallback
    
    def test_get_rate_info(self):
        """get_rate_info Evidence 정보"""
        provider = LiveFxProvider()
        provider.get_fx_rate("USDT", "KRW")
        
        info = provider.get_rate_info()
        assert info is not None
        assert info.rate == 1400.0
        assert info.source == "crypto_implied"
        assert info.degraded is False


class TestValidateFxProviderForMode:
    """validate_fx_provider_for_mode 테스트"""
    
    def test_paper_mode_fixed_ok(self):
        """Paper mode에서 Fixed OK"""
        provider = FixedFxProvider(1450.0)
        validate_fx_provider_for_mode(provider, "paper")  # 예외 없음
    
    def test_paper_mode_live_ok(self):
        """Paper mode에서 Live OK"""
        provider = LiveFxProvider()
        validate_fx_provider_for_mode(provider, "paper")  # 예외 없음
    
    def test_live_mode_fixed_blocked(self):
        """Live mode에서 Fixed 차단"""
        provider = FixedFxProvider(1450.0)
        with pytest.raises(ValueError, match="FATAL"):
            validate_fx_provider_for_mode(provider, "live")
    
    def test_live_mode_live_ok(self):
        """Live mode에서 Live OK"""
        provider = LiveFxProvider()
        validate_fx_provider_for_mode(provider, "live")  # 예외 없음
    
    def test_replay_mode_fixed_ok(self):
        """Replay mode에서 Fixed OK"""
        provider = FixedFxProvider(1450.0)
        validate_fx_provider_for_mode(provider, "replay")  # 예외 없음


class TestHttpSource:
    """HTTP 소스 테스트"""
    
    def test_http_source_no_url_raises(self):
        """HTTP 소스인데 URL 없으면 예외"""
        provider = LiveFxProvider(source="http")
        with pytest.raises(RuntimeError, match="http_base_url"):
            provider.get_fx_rate("USDT", "KRW")
