from abc import ABC, abstractmethod
from typing import Optional
import logging

from arbitrage.v2.opportunity.candidate import OpportunityCandidate, build_candidate
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.marketdata.fx_provider import FXProvider
from arbitrage.v2.opportunity.price_normalizer import normalize_price_to_krw

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
        fx_provider: FXProvider,
        break_even_params: BreakEvenParams,
        kpi,
    ):
        self.upbit_provider = upbit_provider
        self.binance_provider = binance_provider
        self.rate_limiter_upbit = rate_limiter_upbit
        self.rate_limiter_binance = rate_limiter_binance
        self.fx_provider = fx_provider
        self.break_even_params = break_even_params
        self.kpi = kpi
    
    def generate(self, iteration: int) -> Optional[OpportunityCandidate]:
        """Real MarketData 기반 Opportunity 생성 (D205-9)"""
        try:
            if self.upbit_provider is None or self.binance_provider is None:
                logger.error(f"[D205-18-2D] Provider is None")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if not self.rate_limiter_upbit.consume(weight=1):
                self.kpi.ratelimit_hits += 1
                if iteration % 10 == 1:
                    logger.warning(f"[D205-18-2D] Upbit RateLimit exceeded")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            ticker_upbit = self.upbit_provider.get_ticker("BTC/KRW")
            if not ticker_upbit or ticker_upbit.last <= 0:
                if iteration % 10 == 1:
                    logger.warning(f"[D205-18-2D] Upbit ticker fetch failed")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if not self.rate_limiter_binance.consume(weight=1):
                self.kpi.ratelimit_hits += 1
                if iteration % 10 == 1:
                    logger.warning(f"[D205-18-2D] Binance RateLimit exceeded")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            ticker_binance = self.binance_provider.get_ticker("BTC/USDT")
            if not ticker_binance or ticker_binance.last <= 0:
                if iteration % 10 == 1:
                    logger.warning(f"[D205-18-2D] Binance ticker fetch failed")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if ticker_upbit.last < 50_000_000 or ticker_upbit.last > 200_000_000:
                logger.error(f"[D205-18-2D] Upbit price suspicious: {ticker_upbit.last:.0f} KRW")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if ticker_binance.last < 20_000 or ticker_binance.last > 150_000:
                logger.error(f"[D205-18-2D] Binance price suspicious: {ticker_binance.last:.2f} USDT")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            if iteration == 1:
                logger.info(f"[D205-18-2D] Real Upbit: {ticker_upbit.last:,.0f} KRW")
                logger.info(f"[D205-18-2D] Real Binance: {ticker_binance.last:.2f} USDT")
            
            fx_rate = self.fx_provider.get_fx_rate("USDT", "KRW")
            
            if fx_rate < 1000 or fx_rate > 2000:
                logger.error(f"[D205-18-2D] FX rate suspicious: {fx_rate} KRW/USDT")
                self.kpi.bump_reject("sanity_guard")
                self.kpi.real_ticks_fail_count += 1
                return None
            
            price_a = ticker_upbit.last
            price_b_usdt = ticker_binance.last
            price_b = normalize_price_to_krw(price_b_usdt, "USDT", fx_rate)
            
            if iteration == 1:
                logger.info(f"[D205-18-2D] FX rate: {fx_rate} KRW/USDT")
                logger.info(f"[D205-18-2D] Normalized Binance: {price_b:,.0f} KRW")
            
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
            logger.warning(f"[D205-18-2D] Real opportunity failed: {e}")
            self.kpi.errors.append(f"real_opportunity: {e}")
            self.kpi.real_ticks_fail_count += 1
            return None


class MockOpportunitySource(OpportunitySource):
    """Mock Opportunity 생성 (가상 가격)"""
    
    def __init__(
        self,
        fx_provider: FXProvider,
        break_even_params: BreakEvenParams,
        kpi,
    ):
        self.fx_provider = fx_provider
        self.break_even_params = break_even_params
        self.kpi = kpi
    
    def generate(self, iteration: int) -> Optional[OpportunityCandidate]:
        """Mock Opportunity 생성"""
        base_price_a_krw = 50_000_000.0
        base_price_b_usdt = 40_000.0
        
        fx_rate = self.fx_provider.get_fx_rate("USDT", "KRW")
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
            logger.warning(f"[D205-18-2D] Mock build_candidate failed: {e}")
            self.kpi.errors.append(f"build_candidate: {e}")
            return None
