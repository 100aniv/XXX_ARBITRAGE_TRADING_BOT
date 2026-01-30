from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
import logging
from datetime import datetime, timezone

from arbitrage.v2.opportunity import OpportunityCandidate, build_candidate
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.domain.fill_probability import FillProbabilityParams
from arbitrage.v2.core.quote_normalizer import normalize_price_to_krw, is_units_mismatch

logger = logging.getLogger(__name__)


class OpportunitySource(ABC):
    """Opportunity 생성 인터페이스 (Strategy Pattern)"""
    
    @abstractmethod
    def generate(self, iteration: int) -> Optional[OpportunityCandidate]:
        """Opportunity 생성 (Real/Mock 전략에 따라 구현)"""
        pass

    def get_edge_distribution_sample(self) -> Optional[Dict[str, Any]]:
        """최근 Tick의 Edge Distribution 샘플 반환"""
        return getattr(self, "_edge_distribution_sample", None)


def _candidate_to_edge_dict(candidate: OpportunityCandidate) -> Dict[str, Any]:
    return {
        "symbol": candidate.symbol,
        "exchange_a": candidate.exchange_a,
        "exchange_b": candidate.exchange_b,
        "price_a": candidate.price_a,
        "price_b": candidate.price_b,
        "spread_bps": round(candidate.spread_bps, 4),
        "break_even_bps": round(candidate.break_even_bps, 4),
        "edge_bps": round(candidate.edge_bps, 4),
        "deterministic_drift_bps": round(candidate.deterministic_drift_bps, 4),
        "net_edge_bps": round(candidate.net_edge_bps, 4),
        "direction": candidate.direction.value,
        "profitable": candidate.profitable,
        "exchange_a_bid": candidate.exchange_a_bid,
        "exchange_a_ask": candidate.exchange_a_ask,
        "exchange_b_bid": candidate.exchange_b_bid,
        "exchange_b_ask": candidate.exchange_b_ask,
        "fx_rate": candidate.fx_rate,
        "fx_rate_source": candidate.fx_rate_source,
        "fx_rate_age_sec": candidate.fx_rate_age_sec,
        "fx_rate_timestamp": candidate.fx_rate_timestamp,
        "fx_rate_degraded": candidate.fx_rate_degraded,
    }


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
        deterministic_drift_bps: float = 0.0,
        symbols: Optional[List[Tuple[str, str]]] = None,
        max_symbols_per_tick: Optional[int] = None,
        survey_mode: bool = False,
        maker_mode: bool = False,
        fill_probability_params: Optional[FillProbabilityParams] = None,
    ):
        self.upbit_provider = upbit_provider
        self.binance_provider = binance_provider
        self.rate_limiter_upbit = rate_limiter_upbit
        self.rate_limiter_binance = rate_limiter_binance
        self.fx_provider = fx_provider
        self.break_even_params = break_even_params
        self.kpi = kpi
        self.profit_core = profit_core
        self.deterministic_drift_bps = deterministic_drift_bps
        self.symbols = list(symbols) if symbols else None
        self.max_symbols_per_tick = max_symbols_per_tick
        self.survey_mode = survey_mode
        self.maker_mode = maker_mode
        self.fill_probability_params = fill_probability_params
        self._edge_distribution_sample: Optional[Dict[str, Any]] = None
        self._symbol_pair_idx = 0

    @staticmethod
    def _extract_bid_ask(ticker) -> tuple[Optional[float], Optional[float]]:
        bid = getattr(ticker, "bid", None)
        ask = getattr(ticker, "ask", None)
        if bid is not None and ask is not None:
            try:
                bid_val = float(bid)
                ask_val = float(ask)
            except (TypeError, ValueError):
                bid_val = None
                ask_val = None
            if bid_val is not None and ask_val is not None and bid_val > 0 and ask_val > 0:
                return bid_val, ask_val

        last = getattr(ticker, "last", None)
        if last is not None:
            try:
                last_val = float(last)
            except (TypeError, ValueError):
                return None, None
            if last_val > 0:
                return last_val, last_val

        return None, None

    def _get_symbol_pairs(self) -> List[Tuple[str, str]]:
        if self.symbols:
            return list(self.symbols)
        return [("BTC/KRW", "BTC/USDT")]

    def _select_symbol_pairs(
        self,
        symbol_pairs: List[Tuple[str, str]]
    ) -> tuple[List[Tuple[str, str]], Dict[str, Any]]:
        if not symbol_pairs:
            return [], {}

        max_symbols = self.max_symbols_per_tick
        if not isinstance(max_symbols, int) or max_symbols <= 0:
            max_symbols = None

        universe_size = len(symbol_pairs)
        if max_symbols is None or max_symbols >= universe_size:
            return list(symbol_pairs), {
                "mode": "all",
                "max_symbols_per_tick": max_symbols,
                "universe_size": universe_size,
                "symbols_sampled": universe_size,
            }

        selected: List[Tuple[str, str]] = []
        for _ in range(max_symbols):
            selected.append(symbol_pairs[self._symbol_pair_idx])
            self._symbol_pair_idx = (self._symbol_pair_idx + 1) % universe_size

        return selected, {
            "mode": "round_robin",
            "max_symbols_per_tick": max_symbols,
            "universe_size": universe_size,
            "symbols_sampled": len(selected),
        }
    
    def generate(self, iteration: int) -> Optional[OpportunityCandidate]:
        """Real MarketData 기반 Opportunity 생성 (D205-9)"""
        def _set_edge_distribution(
            candidates: List[OpportunityCandidate],
            reason: str = "",
            sampling_policy: Optional[Dict[str, Any]] = None,
        ) -> None:
            sorted_candidates = sorted(
                [c for c in candidates if c],
                key=lambda c: c.net_edge_bps,
                reverse=True,
            )
            sample = {
                "iteration": iteration,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "reason": reason,
                "candidates": [_candidate_to_edge_dict(c) for c in sorted_candidates[:50]],
            }
            if sampling_policy:
                sample["sampling_policy"] = sampling_policy
            self._edge_distribution_sample = sample

        failure_reasons: Dict[str, int] = {}

        def _record_failure(reason: str) -> None:
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

        try:
            if self.upbit_provider is None or self.binance_provider is None:
                logger.error(f"[D207-1] Provider is None")
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason="provider_none")
                return None
            
            if self.rate_limiter_upbit and getattr(self.upbit_provider, "rate_limiter", None) is None:
                if not self.rate_limiter_upbit.consume(tokens=1):
                    self.kpi.ratelimit_hits += 1
                    if iteration % 10 == 1:
                        logger.warning(f"[D207-1] Upbit RateLimit exceeded")
                    self.kpi.real_ticks_fail_count += 1
                    _set_edge_distribution([], reason="ratelimit_upbit")
                    return None
            
            # D207-1-2: FX rate 조회 (AU: Dynamic FX Intelligence)
            fx_rate = self.fx_provider.get_fx_rate("USDT", "KRW")
            
            # D207-1-2: FX rate info 기록 (LiveFxProvider인 경우)
            if hasattr(self.fx_provider, 'get_rate_info'):
                fx_info = self.fx_provider.get_rate_info()
                if fx_info:
                    self.kpi.fx_rate = fx_info.rate
                    self.kpi.fx_rate_source = fx_info.source
                    self.kpi.fx_rate_timestamp = fx_info.timestamp.isoformat()
                    self.kpi.fx_rate_degraded = fx_info.degraded
                    
                    # D207-1-2: FX age 계산 (TTL guard)
                    fx_age_sec = (datetime.now(timezone.utc) - fx_info.timestamp).total_seconds()
                    self.kpi.fx_rate_age_sec = fx_age_sec
                    
                    # D207-1-2: FX staleness guard (TTL > 60s이면 FAIL)
                    fx_ttl_threshold = 60.0
                    if fx_age_sec > fx_ttl_threshold:
                        logger.warning(
                            f"[D207-1-2 FX_STALE] FX rate too old: {fx_age_sec:.1f}s > {fx_ttl_threshold}s, "
                            f"source={fx_info.source}, degraded={fx_info.degraded}"
                        )
                        self.kpi.bump_reject("fx_stale")
                        _set_edge_distribution([], reason="fx_stale")
                        return None  # Stop generation (FX too old)
            else:
                # FixedFxProvider인 경우 (Paper mode)
                self.kpi.fx_rate = fx_rate
                self.kpi.fx_rate_source = "fixed"
                self.kpi.fx_rate_age_sec = 0.0
                self.kpi.fx_rate_timestamp = ""
                self.kpi.fx_rate_degraded = False
            
            if fx_rate < 1000 or fx_rate > 2000:
                logger.error(f"[D207-1] FX rate suspicious: {fx_rate} KRW/USDT")
                self.kpi.bump_reject("sanity_guard")
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason="fx_rate_suspicious")
                return None

            symbol_pairs = self._get_symbol_pairs()
            if not symbol_pairs:
                logger.error("[D207-6] INVALID_UNIVERSE: symbols empty")
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason="invalid_universe")
                return None

            invalid_pairs = [
                idx for idx, pair in enumerate(symbol_pairs)
                if not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(isinstance(item, str) and item for item in pair)
            ]
            if invalid_pairs:
                logger.error(f"[D207-6] INVALID_UNIVERSE: invalid pairs={invalid_pairs[:5]}")
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason="invalid_universe")
                return None

            symbol_pairs, sampling_policy = self._select_symbol_pairs(symbol_pairs)

            candidates_all: List[OpportunityCandidate] = []
            tick_processed = False

            for symbol_a, symbol_b in symbol_pairs:
                if self.rate_limiter_upbit and getattr(self.upbit_provider, "rate_limiter", None) is None:
                    if not self.rate_limiter_upbit.consume(tokens=1):
                        self.kpi.ratelimit_hits += 1
                        if iteration % 10 == 1:
                            logger.warning(f"[D207-1] Upbit RateLimit exceeded")
                        _record_failure("ratelimit_upbit")
                        continue

                ticker_upbit = self.upbit_provider.get_ticker(symbol_a)
                if not ticker_upbit:
                    upbit_status = getattr(self.upbit_provider, "last_error_status", None)
                    if iteration % 10 == 1:
                        if upbit_status == 429:
                            self.kpi.ratelimit_hits += 1
                            logger.info("[D207-1] Upbit ticker rate limited (429)")
                        else:
                            logger.warning(f"[D207-1] Upbit ticker fetch failed")
                    _record_failure("ticker_upbit_missing")
                    continue

                if self.rate_limiter_binance and not self.rate_limiter_binance.consume(tokens=1):
                    self.kpi.ratelimit_hits += 1
                    if iteration % 10 == 1:
                        logger.warning(f"[D207-1] Binance RateLimit exceeded")
                    _record_failure("ratelimit_binance")
                    continue

                ticker_binance = self.binance_provider.get_ticker(symbol_b)
                if not ticker_binance:
                    if iteration % 10 == 1:
                        logger.warning(f"[D207-1] Binance ticker fetch failed")
                    _record_failure("ticker_binance_missing")
                    continue

                upbit_bid, upbit_ask = self._extract_bid_ask(ticker_upbit)
                if not upbit_bid or not upbit_ask or upbit_bid <= 0 or upbit_ask <= 0:
                    if iteration % 10 == 1:
                        logger.warning("[D207-1] Upbit price missing (bid/ask/last)")
                    _record_failure("upbit_price_missing")
                    continue

                binance_bid_usdt, binance_ask_usdt = self._extract_bid_ask(ticker_binance)
                if not binance_bid_usdt or not binance_ask_usdt or binance_bid_usdt <= 0 or binance_ask_usdt <= 0:
                    if iteration % 10 == 1:
                        logger.warning("[D207-1] Binance price missing (bid/ask/last)")
                    _record_failure("binance_price_missing")
                    continue

                # D206-1 FIXPACK: profit_core 필수 (검증됨)
                upbit_mid = (upbit_bid + upbit_ask) / 2.0
                binance_mid_usdt = (binance_bid_usdt + binance_ask_usdt) / 2.0

                is_btc_krw = symbol_a.startswith("BTC/")
                is_btc_usdt = symbol_b.startswith("BTC/")
                if is_btc_krw and not self.profit_core.check_price_sanity("upbit", upbit_mid):
                    logger.error(f"[D207-1] Upbit price suspicious: {upbit_mid:.0f} KRW")
                    _record_failure("upbit_price_suspicious")
                    continue

                if is_btc_usdt and (binance_mid_usdt < 20_000 or binance_mid_usdt > 150_000):
                    logger.error(f"[D207-1] Binance price suspicious: {binance_mid_usdt:.2f} USDT")
                    _record_failure("binance_price_suspicious")
                    continue

                tick_processed = True

                if iteration == 1:
                    logger.info(
                        f"[D207-1] Real Upbit bid/ask ({symbol_a}): {upbit_bid:,.0f}/{upbit_ask:,.0f} KRW"
                    )
                    logger.info(
                        f"[D207-1] Real Binance bid/ask ({symbol_b}): {binance_bid_usdt:.2f}/{binance_ask_usdt:.2f} USDT"
                    )

                binance_bid_krw = normalize_price_to_krw(binance_bid_usdt, "USDT", fx_rate)
                binance_ask_krw = normalize_price_to_krw(binance_ask_usdt, "USDT", fx_rate)

                candidate_a = build_candidate(
                    symbol=symbol_a,
                    exchange_a="upbit",
                    exchange_b="binance",
                    price_a=upbit_ask,
                    price_b=binance_bid_krw,
                    params=self.break_even_params,
                    deterministic_drift_bps=self.deterministic_drift_bps,
                    maker_mode=self.maker_mode,
                    fill_probability_params=self.fill_probability_params,
                )

                candidate_b = build_candidate(
                    symbol=symbol_a,
                    exchange_a="upbit",
                    exchange_b="binance",
                    price_a=upbit_bid,
                    price_b=binance_ask_krw,
                    params=self.break_even_params,
                    deterministic_drift_bps=self.deterministic_drift_bps,
                    maker_mode=self.maker_mode,
                    fill_probability_params=self.fill_probability_params,
                )

                candidates = [c for c in [candidate_a, candidate_b] if c]
                if not candidates:
                    _record_failure("candidate_none")
                    continue

                for candidate in candidates:
                    if is_units_mismatch(candidate.spread_bps, candidate.edge_bps):
                        self.kpi.bump_reject("units_mismatch")
                        _record_failure("units_mismatch")
                        continue

                    candidate.exchange_a_bid = upbit_bid
                    candidate.exchange_a_ask = upbit_ask
                    candidate.exchange_b_bid = binance_bid_krw
                    candidate.exchange_b_ask = binance_ask_krw
                    candidate.fx_rate = self.kpi.fx_rate
                    candidate.fx_rate_source = self.kpi.fx_rate_source
                    candidate.fx_rate_age_sec = self.kpi.fx_rate_age_sec
                    candidate.fx_rate_timestamp = self.kpi.fx_rate_timestamp
                    candidate.fx_rate_degraded = self.kpi.fx_rate_degraded
                    candidates_all.append(candidate)

            if iteration == 1:
                logger.info(f"[D207-1] FX rate: {fx_rate} KRW/USDT")

            if not candidates_all:
                reason = "no_candidates"
                if failure_reasons:
                    reason_detail = ",".join(
                        f"{key}={failure_reasons[key]}" for key in sorted(failure_reasons)
                    )
                    reason = f"all_failed:{reason_detail}"
                if not tick_processed:
                    self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason=reason, sampling_policy=sampling_policy)
                return None

            _set_edge_distribution(candidates_all, sampling_policy=sampling_policy)

            # D207-5: Real tick successfully processed (candidate profitability와 무관)
            if tick_processed:
                self.kpi.real_ticks_ok_count += 1

            # D207-7: Survey Mode - profitable=False인 candidate에 대한 reject reason 기록
            if self.survey_mode:
                for c in candidates_all:
                    if not c.profitable:
                        self.kpi.bump_reject("profitable_false")

            profitable_candidates = [c for c in candidates_all if c.profitable]
            candidate = max(profitable_candidates, key=lambda c: c.net_edge_bps) if profitable_candidates else None

            if not candidate:
                return None
            return candidate
            
        except Exception as e:
            logger.warning(f"[D207-1] Real opportunity failed: {e}")
            self.kpi.errors.append(f"real_opportunity: {e}")
            self.kpi.real_ticks_fail_count += 1
            self._edge_distribution_sample = {
                "iteration": iteration,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "reason": "exception",
                "candidates": [],
            }
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
        deterministic_drift_bps: float = 0.0,
        maker_mode: bool = False,
        fill_probability_params: Optional[FillProbabilityParams] = None,
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
        self.deterministic_drift_bps = deterministic_drift_bps
        self.maker_mode = maker_mode
        self.fill_probability_params = fill_probability_params
        self._edge_distribution_sample: Optional[Dict[str, Any]] = None
    
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
                deterministic_drift_bps=self.deterministic_drift_bps,
                maker_mode=self.maker_mode,
                fill_probability_params=self.fill_probability_params,
            )
            if candidate:
                candidate.exchange_a_bid = price_a
                candidate.exchange_a_ask = price_a
                candidate.exchange_b_bid = price_b
                candidate.exchange_b_ask = price_b
                candidate.fx_rate = fx_rate
                candidate.fx_rate_source = "fixed" if not self.fx_provider.is_live() else "live"
                candidate.fx_rate_age_sec = 0.0
                candidate.fx_rate_timestamp = ""
                candidate.fx_rate_degraded = False
                self._edge_distribution_sample = {
                    "iteration": iteration,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "reason": "",
                    "candidates": [_candidate_to_edge_dict(candidate)],
                }
            return candidate
        except Exception as e:
            logger.warning(f"[D207-1] Mock build_candidate failed: {e}")
            self.kpi.errors.append(f"build_candidate: {e}")
            self._edge_distribution_sample = {
                "iteration": iteration,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "reason": "exception",
                "candidates": [],
            }
            return None
