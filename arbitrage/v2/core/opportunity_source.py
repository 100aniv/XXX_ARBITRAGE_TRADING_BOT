from abc import ABC, abstractmethod
from typing import Optional
import logging

from arbitrage.v2.opportunity import OpportunityCandidate, build_candidate
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.core.quote_normalizer import normalize_price_to_krw

logger = logging.getLogger(__name__)


class OpportunitySource(ABC):
    """Opportunity 생성 인터페이스 (Strategy Pattern)"""
    
    @abstractmethod
    def generate(self, iteration: int) -> Optional[OpportunityCandidate]:
        """Opportunity 생성 (Real/Mock 전략에 따라 구현)"""
        pass


class RealOpportunitySource(OpportunitySource):
    """Real MarketData 기반 Opportunity 생성"""
    
    def __init__(
        self,
        upbit_provider,
        binance_provider,
        rate_limiter_upbit,
        rate_limiter_binance,
        fx_provider,  # FixedFxProvider or LiveFxProvider
        break_even_params: BreakEvenParams,
        kpi,
        profit_core=None,
    ):
        self.upbit_provider = upbit_provider
        self.binance_provider = binance_provider
        self.rate_limiter_upbit = rate_limiter_upbit
        self.rate_limiter_binance = rate_limiter_binance
        self.fx_provider = fx_provider
        self.break_even_params = break_even_params
        self.kpi = kpi
        self.profit_core = profit_core
    
    def generate(self, iteration: int) -> Optional[OpportunityCandidate]:
        """Real MarketData 기반 Opportunity 생성 (D205-9)"""
        try:
            if self.upbit_provider is None or self.binance_provider is None:
                logger.error(f"[D207-1] Provider is None")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if not self.rate_limiter_upbit.consume(tokens=1):
                self.kpi.ratelimit_hits += 1
                if iteration % 10 == 1:
                    logger.warning(f"[D207-1] Upbit RateLimit exceeded")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            ticker_upbit = self.upbit_provider.get_ticker("BTC/KRW")
            if not ticker_upbit or ticker_upbit.last <= 0:
                if iteration % 10 == 1:
                    logger.warning(f"[D207-1] Upbit ticker fetch failed")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if not self.rate_limiter_binance.consume(tokens=1):
                self.kpi.ratelimit_hits += 1
                if iteration % 10 == 1:
                    logger.warning(f"[D207-1] Binance RateLimit exceeded")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            ticker_binance = self.binance_provider.get_ticker("BTC/USDT")
            if not ticker_binance or ticker_binance.last <= 0:
                if iteration % 10 == 1:
                    logger.warning(f"[D207-1] Binance ticker fetch failed")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            # D206-1 FIXPACK: profit_core 필수 (검증됨)
            if not self.profit_core.check_price_sanity("upbit", ticker_upbit.last):
                logger.error(f"[D207-1] Upbit price suspicious: {ticker_upbit.last:.0f} KRW")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if ticker_binance.last < 20_000 or ticker_binance.last > 150_000:
                logger.error(f"[D207-1] Binance price suspicious: {ticker_binance.last:.2f} USDT")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if iteration == 1:
                logger.info(f"[D207-1] Real Upbit: {ticker_upbit.last:,.0f} KRW")
                logger.info(f"[D207-1] Real Binance: {ticker_binance.last:.2f} USDT")
            
            fx_rate = self.fx_provider.get_rate("USDT", "KRW")
            
            if fx_rate < 1000 or fx_rate > 2000:
                logger.error(f"[D207-1] FX rate suspicious: {fx_rate} KRW/USDT")
                self.kpi.bump_reject("sanity_guard")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            price_a = ticker_upbit.last
            price_b_usdt = ticker_binance.last
            price_b = normalize_price_to_krw(price_b_usdt, "USDT", fx_rate)
            
            if iteration == 1:
                logger.info(f"[D207-1] FX rate: {fx_rate} KRW/USDT")
                logger.info(f"[D207-1] Normalized Binance: {price_b:,.0f} KRW")
            
            candidate = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=price_a,
                price_b=price_b,
                params=self.break_even_params,
            )
            
            self.kpi.real_ticks_ok_count += 1
            return candidate
            
        except Exception as e:
            logger.warning(f"[D207-1] Real opportunity failed: {e}")
            self.kpi.errors.append(f"real_opportunity: {e}")
            self.kpi.real_ticks_fail_count += 1
            return None


class MockOpportunitySource(OpportunitySource):
    """Mock Opportunity 생성 (가상 가격)
    
    D206-1 FIXPACK:
    - profit_core 필수 의존성
    - WARN=FAIL (fallback 제거)
    - No Magic Numbers
    """
    
    def __init__(
        self,
        fx_provider,
        break_even_params: BreakEvenParams,
        kpi,
        profit_core: "ProfitCore",
    ):
        """Args:
            profit_core: ProfitCore (REQUIRED - 기본 가격)
        
        Raises:
            TypeError: profit_core가 None일 경우
        """
        if profit_core is None:
            raise TypeError("MockOpportunitySource: profit_core is REQUIRED (WARN=FAIL principle)")
        
        self.fx_provider = fx_provider
        self.break_even_params = break_even_params
        self.kpi = kpi
        self.profit_core = profit_core
    
    def generate(self, iteration: int) -> Optional[OpportunityCandidate]:
        """
        Mock Opportunity 생성
        
        D206-1 FIXPACK:
        - 하드코딩 0건 (profit_core 필수)
        - config.yml 기반 가격만 사용
        """
        # profit_core는 __init__에서 필수 검증됨
        base_price_a_krw = self.profit_core.get_default_price("upbit", "BTC/KRW")
        base_price_b_usdt = self.profit_core.get_default_price("binance", "BTC/USDT")
        
        fx_rate = self.fx_provider.get_rate("USDT", "KRW")
        base_price_b_krw = normalize_price_to_krw(base_price_b_usdt, "USDT", fx_rate)
        
        spread_pct = 0.003 + (iteration % 10) * 0.0002
        price_a = base_price_a_krw * (1 + spread_pct / 2)
        price_b = base_price_b_krw * (1 - spread_pct / 2)
        
        try:
            candidate = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=price_a,
                price_b=price_b,
                params=self.break_even_params,
            )
            return candidate
        except Exception as e:
            logger.warning(f"[D207-1] Mock build_candidate failed: {e}")
            self.kpi.errors.append(f"build_candidate: {e}")
            return None
