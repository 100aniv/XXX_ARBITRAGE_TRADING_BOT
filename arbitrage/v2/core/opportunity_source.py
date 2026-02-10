from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from arbitrage.v2.opportunity import OpportunityCandidate, build_candidate
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.domain.fill_probability import FillProbabilityParams
from arbitrage.v2.core.config import ObiFilterConfig, ObiDynamicThresholdConfig
from arbitrage.v2.core.quote_normalizer import normalize_price_to_krw, is_units_mismatch
from arbitrage.v2.observability.latency_profiler import LatencyProfiler, LatencyStage

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

    def get_dynamic_threshold_state(self) -> Optional[Dict[str, Any]]:
        """OBI 동적 임계치 상태 반환"""
        return getattr(self, "_dynamic_threshold_state", None)

    def get_last_tick_timing(self) -> Optional[Dict[str, float]]:
        """최근 tick timing 샘플 반환"""
        return getattr(self, "_last_tick_timing", None)


def _candidate_to_edge_dict(candidate: OpportunityCandidate) -> Dict[str, Any]:
    obi_score = getattr(candidate, "obi_score", None)
    depth_imbalance = getattr(candidate, "depth_imbalance", None)
    obi_filter_pass = getattr(candidate, "obi_filter_pass", None)
    obi_filter_reason = getattr(candidate, "obi_filter_reason", None)
    obi_rank_score = getattr(candidate, "obi_rank_score", None)
    dynamic_threshold_pass = getattr(candidate, "dynamic_threshold_pass", None)
    dynamic_threshold_reason = getattr(candidate, "dynamic_threshold_reason", None)
    dynamic_threshold_value = getattr(candidate, "dynamic_threshold_value", None)
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
        "obi_score": round(float(obi_score), 6) if obi_score is not None else None,
        "depth_imbalance": round(float(depth_imbalance), 6) if depth_imbalance is not None else None,
        "obi_rank_score": round(float(obi_rank_score), 6) if obi_rank_score is not None else None,
        "obi_filter_pass": obi_filter_pass,
        "obi_filter_reason": obi_filter_reason,
        "dynamic_threshold_pass": dynamic_threshold_pass,
        "dynamic_threshold_reason": dynamic_threshold_reason,
        "dynamic_threshold_value": round(float(dynamic_threshold_value), 6) if dynamic_threshold_value is not None else None,
        "allow_unprofitable": getattr(candidate, "allow_unprofitable", False),
    }


def _compute_orderbook_obi(orderbook: Optional[Any], depth: int = 5) -> tuple[Optional[float], Optional[float]]:
    if not orderbook:
        return None, None

    bids = getattr(orderbook, "bids", None)
    asks = getattr(orderbook, "asks", None)
    if not isinstance(bids, (list, tuple)) or not isinstance(asks, (list, tuple)):
        return None, None

    bids = bids[:depth]
    asks = asks[:depth]
    bid_depth = sum(
        float(level.quantity)
        for level in bids
        if level is not None and getattr(level, "quantity", None) is not None
    )
    ask_depth = sum(
        float(level.quantity)
        for level in asks
        if level is not None and getattr(level, "quantity", None) is not None
    )
    if bid_depth <= 0 or ask_depth <= 0:
        return None, None

    depth_imbalance = bid_depth / ask_depth
    obi_score = (bid_depth - ask_depth) / (bid_depth + ask_depth)
    return obi_score, depth_imbalance


def _merge_metric(first: Optional[float], second: Optional[float]) -> Optional[float]:
    values = [value for value in (first, second) if value is not None]
    if not values:
        return None
    return sum(values) / len(values)


def _quantile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * q)
    idx = min(max(idx, 0), len(sorted_vals) - 1)
    return float(sorted_vals[idx])


def _estimate_pass_rate(values: List[float], threshold: float) -> float:
    if not values:
        return 0.0
    return sum(1 for v in values if v >= threshold) / len(values)


def _compute_dynamic_threshold(
    values: List[float],
    percentile: float,
    min_pass_rate: float,
    min_samples: int,
    min_net_edge_bps: float,
) -> tuple[float, float, bool, str]:
    if not values:
        return float(min_net_edge_bps), 0.0, True, "no_samples"

    sample_n = len(values)
    percentile = max(0.0, min(1.0, float(percentile)))
    min_pass_rate = max(0.0, min(1.0, float(min_pass_rate)))

    base_threshold = _quantile(values, percentile)
    threshold = float(base_threshold if base_threshold is not None else min(values))
    threshold = max(threshold, float(min_net_edge_bps))
    expected_pass_rate = _estimate_pass_rate(values, threshold)
    fallback_used = False
    reason = "percentile"

    if sample_n < min_samples:
        fallback_used = True
        reason = "min_samples"

    if expected_pass_rate < min_pass_rate:
        fallback_used = True
        fallback_quantile = 1.0 - min_pass_rate
        fallback_threshold = _quantile(values, fallback_quantile)
        if fallback_threshold is not None:
            threshold = max(float(fallback_threshold), float(min_net_edge_bps))
        expected_pass_rate = _estimate_pass_rate(values, threshold)
        reason = "min_pass_rate"

    if expected_pass_rate <= 0.0:
        fallback_used = True
        threshold = float(min(values))
        expected_pass_rate = _estimate_pass_rate(values, threshold)
        reason = "zero_pass_guard"

    return float(threshold), float(expected_pass_rate), fallback_used, reason


def _obi_rank_score(direction: Any, obi_score: Optional[float]) -> Optional[float]:
    if obi_score is None:
        return None
    direction_value = getattr(direction, "value", direction)
    if direction_value == "buy_a_sell_b":
        return float(obi_score)
    if direction_value == "buy_b_sell_a":
        return float(-obi_score)
    return None


def _obi_direction_allowed(
    direction: Any,
    obi_score: Optional[float],
    threshold: float,
) -> tuple[bool, Optional[str]]:
    if obi_score is None:
        return False, "obi_missing"
    direction_value = getattr(direction, "value", direction)
    threshold = abs(float(threshold))
    if direction_value == "buy_a_sell_b":
        if obi_score < threshold:
            return False, "obi_threshold"
        return True, None
    if direction_value == "buy_b_sell_a":
        if obi_score > -threshold:
            return False, "obi_threshold"
        return True, None
    return False, "direction_none"


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
        negative_edge_execution_probability: float = 0.0,
        negative_edge_floor_bps: float = 0.0,
        obi_filter: Optional[ObiFilterConfig] = None,
        obi_dynamic_threshold: Optional[ObiDynamicThresholdConfig] = None,
        min_net_edge_bps: float = 0.0,
        rng: Optional[random.Random] = None,
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
        self.negative_edge_execution_probability = float(negative_edge_execution_probability or 0.0)
        self.negative_edge_floor_bps = float(negative_edge_floor_bps or 0.0)
        self.obi_filter_cfg = obi_filter or ObiFilterConfig()
        self.obi_dynamic_cfg = obi_dynamic_threshold or ObiDynamicThresholdConfig()
        self.min_net_edge_bps = float(min_net_edge_bps or 0.0)
        self._dynamic_threshold_samples: List[float] = []
        self._dynamic_threshold_started_at: Optional[float] = None
        self._dynamic_threshold_value: Optional[float] = None
        self._dynamic_threshold_expected_pass_rate: Optional[float] = None
        self._dynamic_threshold_reason: str = "disabled"
        self._dynamic_threshold_fallback: bool = False
        self._dynamic_threshold_ready: bool = False
        self._dynamic_threshold_state: Dict[str, Any] = {
            "enabled": bool(self.obi_dynamic_cfg.enabled),
            "status": "disabled" if not self.obi_dynamic_cfg.enabled else "warming_up",
            "warmup_sec": int(self.obi_dynamic_cfg.warmup_sec),
        }
        self._rng = rng or random
        self._edge_distribution_sample: Optional[Dict[str, Any]] = None
        self._symbol_pair_idx = 0
        self._latency_profiler = LatencyProfiler(enabled=True)
        self._last_tick_timing: Optional[Dict[str, float]] = None
        self._marketdata_executor = ThreadPoolExecutor(max_workers=2)

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

    @staticmethod
    def _extract_orderbook_bid_ask(orderbook) -> tuple[Optional[float], Optional[float]]:
        bids = getattr(orderbook, "bids", None)
        asks = getattr(orderbook, "asks", None)
        if not bids or not asks:
            return None, None
        try:
            bid_val = float(bids[0].price)
            ask_val = float(asks[0].price)
        except (TypeError, ValueError, AttributeError, IndexError):
            return None, None
        if bid_val <= 0 or ask_val <= 0:
            return None, None
        return bid_val, ask_val

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

    def _update_dynamic_threshold_state(
        self,
        candidates: List[OpportunityCandidate],
        now_ts: float,
    ) -> Dict[str, Any]:
        cfg = self.obi_dynamic_cfg
        if not cfg.enabled:
            state = {
                "enabled": False,
                "status": "disabled",
                "warmup_sec": int(cfg.warmup_sec),
                "warmup_elapsed_sec": 0.0,
                "warmup_remaining_sec": float(cfg.warmup_sec),
                "sample_count": 0,
                "percentile": float(cfg.percentile),
                "min_pass_rate": float(cfg.min_pass_rate),
                "min_samples": int(cfg.min_samples),
                "min_net_edge_bps": float(self.min_net_edge_bps),
                "threshold": None,
                "expected_pass_rate": None,
                "fallback_used": None,
                "reason": "disabled",
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                "ready": False,
            }
            self._dynamic_threshold_state = state
            return state

        if self._dynamic_threshold_started_at is None:
            self._dynamic_threshold_started_at = now_ts

        elapsed = max(0.0, now_ts - self._dynamic_threshold_started_at)
        if not self._dynamic_threshold_ready:
            for candidate in candidates:
                if candidate is None:
                    continue
                self._dynamic_threshold_samples.append(float(candidate.net_edge_bps))
            if elapsed >= float(cfg.warmup_sec):
                threshold, pass_rate, fallback_used, reason = _compute_dynamic_threshold(
                    self._dynamic_threshold_samples,
                    percentile=cfg.percentile,
                    min_pass_rate=cfg.min_pass_rate,
                    min_samples=cfg.min_samples,
                    min_net_edge_bps=self.min_net_edge_bps,
                )
                self._dynamic_threshold_value = threshold
                self._dynamic_threshold_expected_pass_rate = pass_rate
                self._dynamic_threshold_reason = reason
                self._dynamic_threshold_fallback = fallback_used
                self._dynamic_threshold_ready = True

        status = "ready" if self._dynamic_threshold_ready else "warming_up"
        remaining = max(0.0, float(cfg.warmup_sec) - elapsed)
        state = {
            "enabled": True,
            "status": status,
            "warmup_sec": int(cfg.warmup_sec),
            "warmup_elapsed_sec": round(elapsed, 2),
            "warmup_remaining_sec": round(remaining, 2),
            "sample_count": len(self._dynamic_threshold_samples),
            "percentile": float(cfg.percentile),
            "min_pass_rate": float(cfg.min_pass_rate),
            "min_samples": int(cfg.min_samples),
            "min_net_edge_bps": float(self.min_net_edge_bps),
            "threshold": self._dynamic_threshold_value if self._dynamic_threshold_ready else None,
            "expected_pass_rate": (
                self._dynamic_threshold_expected_pass_rate if self._dynamic_threshold_ready else None
            ),
            "fallback_used": self._dynamic_threshold_fallback if self._dynamic_threshold_ready else None,
            "reason": self._dynamic_threshold_reason if self._dynamic_threshold_ready else "warming_up",
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "ready": self._dynamic_threshold_ready,
        }
        self._dynamic_threshold_state = state
        return state
    
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

        tick_start = time.perf_counter()
        ticker_fetch_ms = 0.0
        orderbook_fetch_ms = 0.0
        decision_ms = 0.0
        io_ms = 0.0
        self._latency_profiler.start_span(LatencyStage.RECEIVE_TICK)
        decide_span_started = False

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
            fx_fetch_start = time.perf_counter()
            fx_rate = self.fx_provider.get_fx_rate("USDT", "KRW")
            io_ms += (time.perf_counter() - fx_fetch_start) * 1000.0
            
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

            if symbol_pairs:
                self._latency_profiler.start_span(LatencyStage.DECIDE)
                decide_span_started = True

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

                if self.rate_limiter_binance and not self.rate_limiter_binance.consume(tokens=1):
                    self.kpi.ratelimit_hits += 1
                    if iteration % 10 == 1:
                        logger.warning(f"[D207-1] Binance RateLimit exceeded")
                    _record_failure("ratelimit_binance")
                    continue

                obi_depth = int(self.obi_filter_cfg.levels) if self.obi_filter_cfg else 5
                if obi_depth <= 0:
                    obi_depth = 5

                orderbook_fetch_start = time.perf_counter()
                future_upbit = self._marketdata_executor.submit(
                    self.upbit_provider.get_orderbook, symbol_a, depth=obi_depth
                )
                future_binance = self._marketdata_executor.submit(
                    self.binance_provider.get_orderbook, symbol_b, depth=obi_depth
                )
                try:
                    orderbook_upbit = future_upbit.result()
                except Exception:
                    orderbook_upbit = None
                try:
                    orderbook_binance = future_binance.result()
                except Exception:
                    orderbook_binance = None
                fetch_elapsed_ms = (time.perf_counter() - orderbook_fetch_start) * 1000.0
                orderbook_fetch_ms += fetch_elapsed_ms
                io_ms += fetch_elapsed_ms

                ticker_upbit = None
                ticker_binance = None

                if not orderbook_upbit:
                    upbit_status = getattr(self.upbit_provider, "last_error_status", None)
                    if iteration % 10 == 1:
                        if upbit_status == 429:
                            self.kpi.ratelimit_hits += 1
                            logger.info("[D207-1] Upbit orderbook rate limited (429)")
                        else:
                            logger.warning("[D207-1] Upbit orderbook fetch failed")
                    ticker_start = time.perf_counter()
                    ticker_upbit = self.upbit_provider.get_ticker(symbol_a)
                    ticker_elapsed_ms = (time.perf_counter() - ticker_start) * 1000.0
                    ticker_fetch_ms += ticker_elapsed_ms
                    io_ms += ticker_elapsed_ms

                if not orderbook_binance:
                    if iteration % 10 == 1:
                        logger.warning("[D207-1] Binance orderbook fetch failed")
                    ticker_start = time.perf_counter()
                    ticker_binance = self.binance_provider.get_ticker(symbol_b)
                    ticker_elapsed_ms = (time.perf_counter() - ticker_start) * 1000.0
                    ticker_fetch_ms += ticker_elapsed_ms
                    io_ms += ticker_elapsed_ms

                upbit_bid, upbit_ask = (None, None)
                if orderbook_upbit:
                    upbit_bid, upbit_ask = self._extract_orderbook_bid_ask(orderbook_upbit)
                if (not upbit_bid or not upbit_ask) and ticker_upbit is None:
                    ticker_start = time.perf_counter()
                    ticker_upbit = self.upbit_provider.get_ticker(symbol_a)
                    ticker_elapsed_ms = (time.perf_counter() - ticker_start) * 1000.0
                    ticker_fetch_ms += ticker_elapsed_ms
                    io_ms += ticker_elapsed_ms
                if (not upbit_bid or not upbit_ask) and ticker_upbit:
                    upbit_bid, upbit_ask = self._extract_bid_ask(ticker_upbit)
                if not upbit_bid or not upbit_ask or upbit_bid <= 0 or upbit_ask <= 0:
                    if iteration % 10 == 1:
                        logger.warning("[D207-1] Upbit price missing (orderbook/ticker)")
                    _record_failure("upbit_price_missing")
                    continue

                binance_bid_usdt, binance_ask_usdt = (None, None)
                if orderbook_binance:
                    binance_bid_usdt, binance_ask_usdt = self._extract_orderbook_bid_ask(orderbook_binance)
                if (not binance_bid_usdt or not binance_ask_usdt) and ticker_binance is None:
                    ticker_start = time.perf_counter()
                    ticker_binance = self.binance_provider.get_ticker(symbol_b)
                    ticker_elapsed_ms = (time.perf_counter() - ticker_start) * 1000.0
                    ticker_fetch_ms += ticker_elapsed_ms
                    io_ms += ticker_elapsed_ms
                if (not binance_bid_usdt or not binance_ask_usdt) and ticker_binance:
                    binance_bid_usdt, binance_ask_usdt = self._extract_bid_ask(ticker_binance)
                if (
                    not binance_bid_usdt
                    or not binance_ask_usdt
                    or binance_bid_usdt <= 0
                    or binance_ask_usdt <= 0
                ):
                    if iteration % 10 == 1:
                        logger.warning("[D207-1] Binance price missing (orderbook/ticker)")
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

                decision_start = time.perf_counter()
                obi_upbit, depth_upbit = _compute_orderbook_obi(orderbook_upbit, depth=obi_depth)
                obi_binance, depth_binance = _compute_orderbook_obi(orderbook_binance, depth=obi_depth)
                obi_score = _merge_metric(obi_upbit, obi_binance)
                depth_imbalance = _merge_metric(depth_upbit, depth_binance)

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
                    decision_ms += (time.perf_counter() - decision_start) * 1000.0
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
                    candidate.obi_score = obi_score
                    candidate.depth_imbalance = depth_imbalance
                    candidates_all.append(candidate)

                decision_ms += (time.perf_counter() - decision_start) * 1000.0

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

            now_ts = time.time()
            dynamic_state = self._update_dynamic_threshold_state(candidates_all, now_ts)
            obi_filter_enabled = bool(self.obi_filter_cfg and self.obi_filter_cfg.enabled)
            dynamic_enabled = bool(dynamic_state.get("enabled"))
            dynamic_ready = bool(dynamic_state.get("ready"))

            for candidate in candidates_all:
                obi_score_value = getattr(candidate, "obi_score", None)
                candidate.obi_rank_score = _obi_rank_score(candidate.direction, obi_score_value)
                if obi_filter_enabled:
                    allowed, reason = _obi_direction_allowed(
                        candidate.direction,
                        obi_score_value,
                        self.obi_filter_cfg.threshold,
                    )
                    if allowed and candidate.obi_rank_score is None:
                        allowed = False
                        reason = "obi_rank_missing"
                    candidate.obi_filter_pass = allowed
                    candidate.obi_filter_reason = reason
                else:
                    candidate.obi_filter_pass = None
                    candidate.obi_filter_reason = "disabled"

                if not dynamic_enabled:
                    candidate.dynamic_threshold_pass = None
                    candidate.dynamic_threshold_reason = "disabled"
                    candidate.dynamic_threshold_value = None
                elif not dynamic_ready:
                    candidate.dynamic_threshold_pass = None
                    candidate.dynamic_threshold_reason = "warmup"
                    candidate.dynamic_threshold_value = None
                else:
                    threshold_value = dynamic_state.get("threshold")
                    candidate.dynamic_threshold_value = threshold_value
                    if threshold_value is None:
                        candidate.dynamic_threshold_pass = None
                        candidate.dynamic_threshold_reason = "threshold_missing"
                    elif candidate.net_edge_bps >= float(threshold_value):
                        candidate.dynamic_threshold_pass = True
                        candidate.dynamic_threshold_reason = None
                    else:
                        candidate.dynamic_threshold_pass = False
                        candidate.dynamic_threshold_reason = "below_threshold"

            if obi_filter_enabled and self.obi_filter_cfg.top_k > 0:
                ranked = [c for c in candidates_all if c.obi_filter_pass]
                ranked.sort(
                    key=lambda c: (
                        c.obi_rank_score if c.obi_rank_score is not None else float("-inf")
                    ),
                    reverse=True,
                )
                for idx, candidate in enumerate(ranked):
                    if idx >= self.obi_filter_cfg.top_k:
                        candidate.obi_filter_pass = False
                        candidate.obi_filter_reason = "obi_top_k"

            _set_edge_distribution(candidates_all, sampling_policy=sampling_policy)

            # D207-5: Real tick successfully processed (candidate profitability와 무관)
            if tick_processed:
                self.kpi.real_ticks_ok_count += 1

            # D207-7: Survey Mode - profitable=False인 candidate에 대한 reject reason 기록
            if self.survey_mode:
                for c in candidates_all:
                    if not c.profitable:
                        self.kpi.bump_reject("profitable_false")

            negative_prob = max(0.0, min(1.0, self.negative_edge_execution_probability))
            negative_floor = float(self.negative_edge_floor_bps)
            filtered_candidates = candidates_all
            if obi_filter_enabled:
                filtered_candidates = [c for c in filtered_candidates if c.obi_filter_pass]
            if dynamic_enabled and dynamic_ready:
                filtered_candidates = [c for c in filtered_candidates if c.dynamic_threshold_pass]

            if not filtered_candidates:
                if dynamic_enabled and dynamic_ready:
                    self.kpi.bump_reject("dynamic_threshold_drop")
                elif obi_filter_enabled:
                    self.kpi.bump_reject("obi_filter_drop")
                return None

            negative_candidates = [
                c for c in filtered_candidates
                if c.net_edge_bps < 0 and c.net_edge_bps >= negative_floor
            ]

            candidate = None
            if negative_prob > 0 and negative_candidates and self._rng.random() < negative_prob:
                candidate = max(negative_candidates, key=lambda c: c.net_edge_bps)
                candidate.allow_unprofitable = True
            else:
                profitable_candidates = [c for c in filtered_candidates if c.profitable]
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
        finally:
            if decide_span_started and LatencyStage.DECIDE in self._latency_profiler.active_spans:
                self._latency_profiler.end_span(LatencyStage.DECIDE)
            if LatencyStage.RECEIVE_TICK in self._latency_profiler.active_spans:
                self._latency_profiler.end_span(LatencyStage.RECEIVE_TICK)
            tick_elapsed_ms = (time.perf_counter() - tick_start) * 1000.0
            if ticker_fetch_ms <= 0.0 and orderbook_fetch_ms > 0.0:
                ticker_fetch_ms = orderbook_fetch_ms
            timing = {
                "tick_elapsed_ms": round(tick_elapsed_ms, 3),
                "ticker_fetch_ms": round(ticker_fetch_ms, 3),
                "orderbook_fetch_ms": round(orderbook_fetch_ms, 3),
                "decision_ms": round(decision_ms, 3),
                "io_ms": round(io_ms, 3),
            }
            self._last_tick_timing = timing
            if self.kpi is not None:
                self.kpi.record_tick_timing(
                    tick_elapsed_ms=tick_elapsed_ms,
                    ticker_fetch_ms=ticker_fetch_ms,
                    orderbook_fetch_ms=orderbook_fetch_ms,
                    decision_ms=decision_ms,
                    io_ms=io_ms,
                )


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
        negative_edge_execution_probability: float = 0.0,
        negative_edge_floor_bps: float = 0.0,
        rng: Optional[random.Random] = None,
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
        self.negative_edge_execution_probability = float(negative_edge_execution_probability or 0.0)
        self.negative_edge_floor_bps = float(negative_edge_floor_bps or 0.0)
        self._rng = rng or random
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
                if not candidate.profitable:
                    negative_prob = max(0.0, min(1.0, self.negative_edge_execution_probability))
                    negative_floor = float(self.negative_edge_floor_bps)
                    if (
                        negative_prob > 0
                        and candidate.net_edge_bps >= negative_floor
                        and self._rng.random() < negative_prob
                    ):
                        candidate.allow_unprofitable = True
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
