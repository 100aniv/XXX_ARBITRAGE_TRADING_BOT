from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple
import asyncio
import functools
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from arbitrage.v2.opportunity import OpportunityCandidate, build_candidate, detect_candidates
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.domain.fill_probability import FillProbabilityParams
from arbitrage.v2.core.config import ObiFilterConfig, ObiDynamicThresholdConfig
from arbitrage.v2.core.quote_normalizer import normalize_price_to_krw, is_units_mismatch
from arbitrage.v2.observability.latency_profiler import LatencyProfiler, LatencyStage
from arbitrage.v2.core.tick_context import RestCallInTickError

logger = logging.getLogger(__name__)


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        qty
        for level in bids
        for qty in [_safe_float(getattr(level, "quantity", None))]
        if level is not None and qty is not None
    )
    ask_depth = sum(
        qty
        for level in asks
        for qty in [_safe_float(getattr(level, "quantity", None))]
        if level is not None and qty is not None
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

    _UPBIT_ORDERBOOK_WEIGHT = 1
    _UPBIT_TICKER_WEIGHT = 1
    _BINANCE_ORDERBOOK_WEIGHT = 5
    _BINANCE_TICKER_WEIGHT = 1
    
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
        upbit_ws_provider=None,
        binance_ws_provider=None,
        clean_room: bool = False,
        ws_only_mode: bool = False,
        order_size_policy_mode: Optional[str] = None,
        fixed_quote: Optional[Dict[str, Any]] = None,
        default_quote_amount: float = 100000.0,
        rng: Optional[random.Random] = None,
    ):
        self.upbit_provider = upbit_provider
        self.binance_provider = binance_provider
        self.rate_limiter_upbit = rate_limiter_upbit
        self.rate_limiter_binance = rate_limiter_binance
        self.upbit_ws_provider = upbit_ws_provider
        self.binance_ws_provider = binance_ws_provider
        self.fx_provider = fx_provider
        self.break_even_params = break_even_params
        self.kpi = kpi
        self.profit_core = profit_core
        self.clean_room = bool(clean_room)
        self.ws_only_mode = bool(ws_only_mode or clean_room)
        self.order_size_policy_mode = order_size_policy_mode
        self.fixed_quote = dict(fixed_quote or {})
        self.default_quote_amount = float(default_quote_amount)
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
        self._last_tick_start_perf: Optional[float] = None
        self._marketdata_executor = ThreadPoolExecutor(
            max_workers=self._resolve_marketdata_workers()
        )

    def _resolve_marketdata_workers(self, pair_count: Optional[int] = None) -> int:
        if pair_count is None:
            pair_count = len(self._get_symbol_pairs())
        pair_count = max(1, int(pair_count))
        if isinstance(self.max_symbols_per_tick, int) and self.max_symbols_per_tick > 0:
            pair_count = min(pair_count, self.max_symbols_per_tick)
        target = pair_count * 2
        return max(4, min(32, target))

    def _ensure_marketdata_executor(self, pair_count: int) -> None:
        target = self._resolve_marketdata_workers(pair_count)
        current = getattr(self._marketdata_executor, "_max_workers", None)
        if current == target:
            return
        if self._marketdata_executor:
            self._marketdata_executor.shutdown(wait=False)
        self._marketdata_executor = ThreadPoolExecutor(max_workers=target)

    def _consume_rate_limit(self, limiter, weight: int, label: str, iteration: int) -> bool:
        if limiter is None:
            return True
        allowed = True
        try:
            allowed = limiter.consume(weight=weight)
        except TypeError:
            try:
                allowed = limiter.consume(tokens=weight)
            except TypeError:
                allowed = limiter.consume(weight)
        except Exception as exc:
            logger.warning(f"[EXEC] RateLimiter error ({label}): {exc}")
            return True

        if not allowed:
            self.kpi.ratelimit_hits += 1
            if iteration % 10 == 1:
                logger.warning(f"[EXEC] {label} RateLimit exceeded")
        return allowed

    def _get_cached_orderbook(self, ws_provider, symbol: str, exchange: str):
        if ws_provider is None:
            return None
        try:
            return ws_provider.get_latest_orderbook(symbol)
        except Exception as exc:
            logger.warning(f"[EXEC] {exchange} WS cache error: {exc}")
            return None

    def _guard_rate_limit_ban(self, provider, exchange: str) -> None:
        status = getattr(provider, "last_error_status", None)
        if status == 429:
            logger.critical(f"[CRITICAL FAIL] {exchange} HTTP 429 (IP ban detected)")
            raise RuntimeError(f"{exchange} HTTP 429 (IP ban detected)")

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
        if not isinstance(bids, (list, tuple)) or not isinstance(asks, (list, tuple)):
            return None, None
        if not bids or not asks:
            return None, None
        try:
            bid_val = _safe_float(getattr(bids[0], "price", None))
            ask_val = _safe_float(getattr(asks[0], "price", None))
        except (TypeError, ValueError, AttributeError, IndexError):
            return None, None
        if bid_val is None or ask_val is None or bid_val <= 0 or ask_val <= 0:
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
        """Real MarketData 기반 Opportunity 생성"""
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
        tick_interval_ms = None
        if self._last_tick_start_perf is not None:
            tick_interval_ms = (tick_start - self._last_tick_start_perf) * 1000.0
        self._last_tick_start_perf = tick_start
        ticker_fetch_ms = 0.0
        orderbook_fetch_ms = 0.0
        decision_ms = 0.0
        io_ms = 0.0
        md_upbit_ms = 0.0
        md_binance_ms = 0.0
        rate_limiter_wait_ms = 0.0
        self._latency_profiler.start_span(LatencyStage.RECEIVE_TICK)
        decide_span_started = False

        try:
            if not self.clean_room:
                if self.upbit_provider is None or self.binance_provider is None:
                    logger.error("[EXEC] Provider is None")
                    self.kpi.real_ticks_fail_count += 1
                    _set_edge_distribution([], reason="provider_none")
                    return None
            else:
                if self.upbit_ws_provider is None or self.binance_ws_provider is None:
                    raise RuntimeError("[CLEAN_ROOM] WS providers are required")
            
            # EXEC: FX rate 조회 (Dynamic FX Intelligence)
            fx_fetch_start = time.perf_counter()
            fx_rate = self.fx_provider.get_fx_rate("USDT", "KRW")
            io_ms += (time.perf_counter() - fx_fetch_start) * 1000.0
            
            # EXEC: FX rate info 기록 (LiveFxProvider인 경우)
            if hasattr(self.fx_provider, 'get_rate_info'):
                fx_info = self.fx_provider.get_rate_info()
                if fx_info:
                    self.kpi.fx_rate = fx_info.rate
                    self.kpi.fx_rate_source = fx_info.source
                    self.kpi.fx_rate_timestamp = fx_info.timestamp.isoformat()
                    self.kpi.fx_rate_degraded = fx_info.degraded
                    
                    # EXEC: FX age 계산 (TTL guard)
                    fx_age_sec = (datetime.now(timezone.utc) - fx_info.timestamp).total_seconds()
                    self.kpi.fx_rate_age_sec = fx_age_sec
                    
                    # EXEC: FX staleness guard (TTL > 60s이면 FAIL)
                    fx_ttl_threshold = 60.0
                    if fx_age_sec > fx_ttl_threshold:
                        logger.warning(
                            f"[EXEC FX_STALE] FX rate too old: {fx_age_sec:.1f}s > {fx_ttl_threshold}s, "
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
                logger.error(f"[EXEC] FX rate suspicious: {fx_rate} KRW/USDT")
                self.kpi.bump_reject("sanity_guard")
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason="fx_rate_suspicious")
                return None

            symbol_pairs = self._get_symbol_pairs()
            if not symbol_pairs:
                logger.error("[EXEC INVALID_UNIVERSE] symbols empty")
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason="invalid_universe")
                return None

            invalid_pairs = [
                idx for idx, pair in enumerate(symbol_pairs)
                if not isinstance(pair, (list, tuple)) or len(pair) != 2
                or not all(isinstance(item, str) and item for item in pair)
            ]
            if invalid_pairs:
                logger.error(f"[EXEC INVALID_UNIVERSE] invalid pairs={invalid_pairs[:5]}")
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution([], reason="invalid_universe")
                return None

            symbol_pairs, sampling_policy = self._select_symbol_pairs(symbol_pairs)

            if symbol_pairs:
                self._latency_profiler.start_span(LatencyStage.DECIDE)
                decide_span_started = True

            candidates_all: List[OpportunityCandidate] = []
            tick_processed = False

            if symbol_pairs:
                self._ensure_marketdata_executor(len(symbol_pairs))

            obi_depth = int(self.obi_filter_cfg.levels) if self.obi_filter_cfg else 5
            if obi_depth <= 0:
                obi_depth = 5

            upbit_external_limit = (
                self.rate_limiter_upbit is not None
                and getattr(self.upbit_provider, "rate_limiter", None) is None
            )
            binance_external_limit = (
                self.rate_limiter_binance is not None
                and getattr(self.binance_provider, "rate_limiter", None) is None
            )

            async def _fetch_marketdata_for_pairs() -> List[Dict[str, Any]]:
                loop = asyncio.get_running_loop()
                max_workers = max(1, self._resolve_marketdata_workers(len(symbol_pairs)))
                semaphore = asyncio.Semaphore(max_workers)

                async def _run_in_executor(func, *args, **kwargs) -> tuple[Optional[Any], float]:
                    async with semaphore:
                        fetch_start = time.perf_counter()
                        call = functools.partial(func, *args, **kwargs)
                        try:
                            result = await loop.run_in_executor(self._marketdata_executor, call)
                        except RestCallInTickError:
                            raise
                        except Exception:
                            result = None
                        fetch_elapsed_ms = (time.perf_counter() - fetch_start) * 1000.0
                        return result, fetch_elapsed_ms

                async def _fetch_for_pair(symbol_a: str, symbol_b: str) -> Dict[str, Any]:
                    metrics = {
                        "orderbook_fetch_ms": 0.0,
                        "ticker_fetch_ms": 0.0,
                        "io_ms": 0.0,
                        "md_upbit_ms": 0.0,
                        "md_binance_ms": 0.0,
                        "rate_limiter_wait_ms": 0.0,
                    }
                    failures: List[str] = []

                    orderbook_upbit = self._get_cached_orderbook(
                        self.upbit_ws_provider, symbol_a, "upbit"
                    )
                    orderbook_binance = self._get_cached_orderbook(
                        self.binance_ws_provider, symbol_b, "binance"
                    )

                    if self.ws_only_mode:
                        if orderbook_upbit is None:
                            raise RuntimeError(
                                f"[WS_ONLY] Orderbook WS cache miss (upbit): symbol={symbol_a}. "
                                f"REST fallback is forbidden in WS-only mode."
                            )
                        if orderbook_binance is None:
                            raise RuntimeError(
                                f"[WS_ONLY] Orderbook WS cache miss (binance): symbol={symbol_b}. "
                                f"REST fallback is forbidden in WS-only mode."
                            )

                    orderbook_requests = []
                    if orderbook_upbit is None:
                        if upbit_external_limit:
                            rate_limit_start = time.perf_counter()
                            allowed = self._consume_rate_limit(
                                self.rate_limiter_upbit,
                                weight=self._UPBIT_ORDERBOOK_WEIGHT,
                                label="Upbit",
                                iteration=iteration,
                            )
                            metrics["rate_limiter_wait_ms"] += (
                                time.perf_counter() - rate_limit_start
                            ) * 1000.0
                            if not allowed:
                                failures.append("ratelimit_upbit")
                                return {
                                    "symbol_a": symbol_a,
                                    "symbol_b": symbol_b,
                                    "skip": True,
                                    "failures": failures,
                                    "metrics": metrics,
                                }
                        orderbook_requests.append(
                            (
                                "upbit",
                                self.upbit_provider.get_orderbook,
                                (symbol_a,),
                                {"depth": obi_depth},
                            )
                        )

                    if orderbook_binance is None:
                        if binance_external_limit:
                            rate_limit_start = time.perf_counter()
                            allowed = self._consume_rate_limit(
                                self.rate_limiter_binance,
                                weight=self._BINANCE_ORDERBOOK_WEIGHT,
                                label="Binance",
                                iteration=iteration,
                            )
                            metrics["rate_limiter_wait_ms"] += (
                                time.perf_counter() - rate_limit_start
                            ) * 1000.0
                            if not allowed:
                                failures.append("ratelimit_binance")
                                return {
                                    "symbol_a": symbol_a,
                                    "symbol_b": symbol_b,
                                    "skip": True,
                                    "failures": failures,
                                    "metrics": metrics,
                                }
                        orderbook_requests.append(
                            (
                                "binance",
                                self.binance_provider.get_orderbook,
                                (symbol_b,),
                                {"depth": obi_depth},
                            )
                        )

                    if orderbook_requests:
                        orderbook_results = await asyncio.gather(
                            *[
                                _run_in_executor(func, *args, **kwargs)
                                for _, func, args, kwargs in orderbook_requests
                            ]
                        )
                        for (label, _, _, _), (result, fetch_elapsed_ms) in zip(
                            orderbook_requests, orderbook_results
                        ):
                            metrics["orderbook_fetch_ms"] += fetch_elapsed_ms
                            metrics["io_ms"] += fetch_elapsed_ms
                            if label == "upbit":
                                metrics["md_upbit_ms"] += fetch_elapsed_ms
                                orderbook_upbit = result
                                if orderbook_upbit is None:
                                    self._guard_rate_limit_ban(self.upbit_provider, "Upbit")
                            else:
                                metrics["md_binance_ms"] += fetch_elapsed_ms
                                orderbook_binance = result
                                if orderbook_binance is None:
                                    self._guard_rate_limit_ban(self.binance_provider, "Binance")

                    upbit_bid, upbit_ask = (None, None)
                    if orderbook_upbit:
                        upbit_bid, upbit_ask = self._extract_orderbook_bid_ask(orderbook_upbit)

                    binance_bid_usdt, binance_ask_usdt = (None, None)
                    if orderbook_binance:
                        binance_bid_usdt, binance_ask_usdt = self._extract_orderbook_bid_ask(
                            orderbook_binance
                        )

                    need_upbit_ticker = not upbit_bid or not upbit_ask
                    need_binance_ticker = not binance_bid_usdt or not binance_ask_usdt

                    if self.ws_only_mode and (need_upbit_ticker or need_binance_ticker):
                        raise RuntimeError(
                            f"[WS_ONLY] Ticker WS cache miss (need_upbit_ticker={need_upbit_ticker}, "
                            f"need_binance_ticker={need_binance_ticker}). REST fallback is forbidden in WS-only mode."
                        )

                    ticker_requests = []
                    if need_upbit_ticker:
                        if upbit_external_limit:
                            rate_limit_start = time.perf_counter()
                            allowed = self._consume_rate_limit(
                                self.rate_limiter_upbit,
                                weight=self._UPBIT_TICKER_WEIGHT,
                                label="Upbit",
                                iteration=iteration,
                            )
                            metrics["rate_limiter_wait_ms"] += (
                                time.perf_counter() - rate_limit_start
                            ) * 1000.0
                            if not allowed:
                                failures.append("ratelimit_upbit")
                                return {
                                    "symbol_a": symbol_a,
                                    "symbol_b": symbol_b,
                                    "skip": True,
                                    "failures": failures,
                                    "metrics": metrics,
                                }
                        ticker_requests.append(
                            (
                                "upbit",
                                self.upbit_provider.get_ticker,
                                (symbol_a,),
                                {},
                            )
                        )

                    if need_binance_ticker:
                        if binance_external_limit:
                            rate_limit_start = time.perf_counter()
                            allowed = self._consume_rate_limit(
                                self.rate_limiter_binance,
                                weight=self._BINANCE_TICKER_WEIGHT,
                                label="Binance",
                                iteration=iteration,
                            )
                            metrics["rate_limiter_wait_ms"] += (
                                time.perf_counter() - rate_limit_start
                            ) * 1000.0
                            if not allowed:
                                failures.append("ratelimit_binance")
                                return {
                                    "symbol_a": symbol_a,
                                    "symbol_b": symbol_b,
                                    "skip": True,
                                    "failures": failures,
                                    "metrics": metrics,
                                }
                        ticker_requests.append(
                            (
                                "binance",
                                self.binance_provider.get_ticker,
                                (symbol_b,),
                                {},
                            )
                        )

                    ticker_upbit = None
                    ticker_binance = None
                    if ticker_requests:
                        ticker_results = await asyncio.gather(
                            *[
                                _run_in_executor(func, *args, **kwargs)
                                for _, func, args, kwargs in ticker_requests
                            ]
                        )
                        for (label, _, _, _), (result, fetch_elapsed_ms) in zip(
                            ticker_requests, ticker_results
                        ):
                            metrics["ticker_fetch_ms"] += fetch_elapsed_ms
                            metrics["io_ms"] += fetch_elapsed_ms
                            if label == "upbit":
                                metrics["md_upbit_ms"] += fetch_elapsed_ms
                                ticker_upbit = result
                                if ticker_upbit is None:
                                    self._guard_rate_limit_ban(self.upbit_provider, "Upbit")
                            else:
                                metrics["md_binance_ms"] += fetch_elapsed_ms
                                ticker_binance = result
                                if ticker_binance is None:
                                    self._guard_rate_limit_ban(self.binance_provider, "Binance")

                    if (upbit_bid is None or upbit_ask is None) and ticker_upbit is not None:
                        upbit_bid, upbit_ask = self._extract_bid_ask(ticker_upbit)

                    if (binance_bid_usdt is None or binance_ask_usdt is None) and ticker_binance is not None:
                        binance_bid_usdt, binance_ask_usdt = self._extract_bid_ask(ticker_binance)

                    upbit_bid_qty = None
                    upbit_ask_qty = None
                    if orderbook_upbit is not None:
                        bids = getattr(orderbook_upbit, "bids", None)
                        asks = getattr(orderbook_upbit, "asks", None)
                        if isinstance(bids, (list, tuple)) and isinstance(asks, (list, tuple)) and bids and asks:
                            upbit_bid_qty = _safe_float(getattr(bids[0], "quantity", None))
                            upbit_ask_qty = _safe_float(getattr(asks[0], "quantity", None))
                    if (upbit_bid_qty is None or upbit_ask_qty is None) and ticker_upbit is not None:
                        if upbit_bid_qty is None:
                            upbit_bid_qty = _safe_float(getattr(ticker_upbit, "bid_size", None))
                        if upbit_ask_qty is None:
                            upbit_ask_qty = _safe_float(getattr(ticker_upbit, "ask_size", None))

                    binance_bid_qty = None
                    binance_ask_qty = None
                    if orderbook_binance is not None:
                        bids = getattr(orderbook_binance, "bids", None)
                        asks = getattr(orderbook_binance, "asks", None)
                        if isinstance(bids, (list, tuple)) and isinstance(asks, (list, tuple)) and bids and asks:
                            binance_bid_qty = _safe_float(getattr(bids[0], "quantity", None))
                            binance_ask_qty = _safe_float(getattr(asks[0], "quantity", None))
                    if (binance_bid_qty is None or binance_ask_qty is None) and ticker_binance is not None:
                        if binance_bid_qty is None:
                            binance_bid_qty = _safe_float(getattr(ticker_binance, "bid_size", None))
                        if binance_ask_qty is None:
                            binance_ask_qty = _safe_float(getattr(ticker_binance, "ask_size", None))

                    return {
                        "symbol_a": symbol_a,
                        "symbol_b": symbol_b,
                        "orderbook_upbit": orderbook_upbit,
                        "orderbook_binance": orderbook_binance,
                        "upbit_bid": upbit_bid,
                        "upbit_ask": upbit_ask,
                        "binance_bid_usdt": binance_bid_usdt,
                        "binance_ask_usdt": binance_ask_usdt,
                        "upbit_bid_qty": upbit_bid_qty,
                        "upbit_ask_qty": upbit_ask_qty,
                        "binance_bid_qty": binance_bid_qty,
                        "binance_ask_qty": binance_ask_qty,
                        "failures": failures,
                        "metrics": metrics,
                    }

                tasks = [
                    _fetch_for_pair(symbol_a, symbol_b)
                    for symbol_a, symbol_b in symbol_pairs
                ]
                if not tasks:
                    return []
                return await asyncio.gather(*tasks)

            try:
                # D_ALPHA-FAST: per-tick marketdata 수집이 장시간 블로킹되면
                # duration 종료가 지연될 수 있으므로 tick 단위 timeout을 둔다.
                marketdata_results = asyncio.run(
                    asyncio.wait_for(_fetch_marketdata_for_pairs(), timeout=15.0)
                )
            except asyncio.TimeoutError:
                self.kpi.real_ticks_fail_count += 1
                _set_edge_distribution(
                    [],
                    reason="marketdata_fetch_timeout",
                    sampling_policy=sampling_policy,
                )
                return None

            for task in marketdata_results:
                for reason in task.get("failures", []):
                    _record_failure(reason)

                if task.get("skip"):
                    continue

                metrics = task.get("metrics", {})
                orderbook_fetch_ms += float(metrics.get("orderbook_fetch_ms", 0.0))
                ticker_fetch_ms += float(metrics.get("ticker_fetch_ms", 0.0))
                io_ms += float(metrics.get("io_ms", 0.0))
                md_upbit_ms += float(metrics.get("md_upbit_ms", 0.0))
                md_binance_ms += float(metrics.get("md_binance_ms", 0.0))
                rate_limiter_wait_ms += float(metrics.get("rate_limiter_wait_ms", 0.0))

                symbol_a = task["symbol_a"]
                symbol_b = task["symbol_b"]
                orderbook_upbit = task.get("orderbook_upbit")
                orderbook_binance = task.get("orderbook_binance")
                upbit_bid = task.get("upbit_bid")
                upbit_ask = task.get("upbit_ask")
                binance_bid_usdt = task.get("binance_bid_usdt")
                binance_ask_usdt = task.get("binance_ask_usdt")
                upbit_bid_qty = task.get("upbit_bid_qty")
                upbit_ask_qty = task.get("upbit_ask_qty")
                binance_bid_qty = task.get("binance_bid_qty")
                binance_ask_qty = task.get("binance_ask_qty")

                if not upbit_bid or not upbit_ask or upbit_bid <= 0 or upbit_ask <= 0:
                    if iteration % 10 == 1:
                        logger.warning("[EXEC] Upbit price missing (orderbook/ticker)")
                    _record_failure("upbit_price_missing")
                    continue

                if (
                    not binance_bid_usdt
                    or not binance_ask_usdt
                    or binance_bid_usdt <= 0
                    or binance_ask_usdt <= 0
                ):
                    if iteration % 10 == 1:
                        logger.warning("[EXEC] Binance price missing (orderbook/ticker)")
                    _record_failure("binance_price_missing")
                    continue

                # EXEC: profit_core 필수 (검증됨)
                upbit_mid = (upbit_bid + upbit_ask) / 2.0
                binance_mid_usdt = (binance_bid_usdt + binance_ask_usdt) / 2.0

                is_btc_krw = symbol_a.startswith("BTC/")
                is_btc_usdt = symbol_b.startswith("BTC/")
                if is_btc_krw and not self.profit_core.check_price_sanity("upbit", upbit_mid):
                    logger.error(f"[EXEC] Upbit price suspicious: {upbit_mid:.0f} KRW")
                    _record_failure("upbit_price_suspicious")
                    continue

                if is_btc_usdt and (binance_mid_usdt < 20_000 or binance_mid_usdt > 150_000):
                    logger.error(f"[EXEC] Binance price suspicious: {binance_mid_usdt:.2f} USDT")
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
                        f"[EXEC] Real Upbit bid/ask ({symbol_a}): {upbit_bid:,.0f}/{upbit_ask:,.0f} KRW"
                    )
                    logger.info(
                        f"[EXEC] Real Binance bid/ask ({symbol_b}): {binance_bid_usdt:.2f}/{binance_ask_usdt:.2f} USDT"
                    )

                binance_bid_krw = normalize_price_to_krw(binance_bid_usdt, "USDT", fx_rate)
                binance_ask_krw = normalize_price_to_krw(binance_ask_usdt, "USDT", fx_rate)

                upbit_bid_size = None
                upbit_ask_size = None
                if upbit_bid_qty is not None and upbit_bid is not None and upbit_bid > 0:
                    upbit_bid_size = float(upbit_bid) * float(upbit_bid_qty)
                if upbit_ask_qty is not None and upbit_ask is not None and upbit_ask > 0:
                    upbit_ask_size = float(upbit_ask) * float(upbit_ask_qty)

                binance_bid_size = None
                binance_ask_size = None
                if binance_bid_qty is not None and binance_bid_krw is not None and binance_bid_krw > 0:
                    binance_bid_size = float(binance_bid_krw) * float(binance_bid_qty)
                if binance_ask_qty is not None and binance_ask_krw is not None and binance_ask_krw > 0:
                    binance_ask_size = float(binance_ask_krw) * float(binance_ask_qty)

                def _resolve_notional_krw(price_a_val: float, price_b_val: float) -> Optional[float]:
                    if self.maker_mode:
                        return None
                    order_size_mode = (self.order_size_policy_mode or "").strip().lower()
                    if order_size_mode in ("", "none", "disabled"):
                        return None
                    quote_amount = self.default_quote_amount
                    buy_exchange = None
                    if price_a_val < price_b_val:
                        buy_exchange = "upbit"
                    elif price_a_val > price_b_val:
                        buy_exchange = "binance"

                    if order_size_mode == "fixed_quote":
                        if buy_exchange == "upbit":
                            quote_amount = self.fixed_quote.get("upbit_krw", quote_amount)
                            return float(quote_amount)
                        if buy_exchange == "binance":
                            quote_amount = self.fixed_quote.get("binance_usdt", quote_amount)
                            return float(quote_amount) * float(fx_rate)

                    return None

                candidate_a = detect_candidates(
                    symbol=symbol_a,
                    exchange_a="upbit",
                    exchange_b="binance",
                    price_a=upbit_ask,
                    price_b=binance_bid_krw,
                    params=self.break_even_params,
                    deterministic_drift_bps=self.deterministic_drift_bps,
                    maker_mode=self.maker_mode,
                    fill_probability_params=self.fill_probability_params,
                    notional=_resolve_notional_krw(upbit_ask, binance_bid_krw),
                    upbit_bid_size=upbit_bid_size,
                    upbit_ask_size=upbit_ask_size,
                    binance_bid_size=binance_bid_size,
                    binance_ask_size=binance_ask_size,
                )

                candidate_b = detect_candidates(
                    symbol=symbol_a,
                    exchange_a="upbit",
                    exchange_b="binance",
                    price_a=upbit_bid,
                    price_b=binance_ask_krw,
                    params=self.break_even_params,
                    deterministic_drift_bps=self.deterministic_drift_bps,
                    maker_mode=self.maker_mode,
                    fill_probability_params=self.fill_probability_params,
                    notional=_resolve_notional_krw(upbit_bid, binance_ask_krw),
                    upbit_bid_size=upbit_bid_size,
                    upbit_ask_size=upbit_ask_size,
                    binance_bid_size=binance_bid_size,
                    binance_ask_size=binance_ask_size,
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
                logger.info(f"[EXEC] FX rate: {fx_rate} KRW/USDT")

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

            # EXEC: Real tick successfully processed (candidate profitability와 무관)
            if tick_processed:
                self.kpi.real_ticks_ok_count += 1

            # EXEC: Survey Mode - profitable=False인 candidate에 대한 reject reason 기록
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
            
        except RestCallInTickError:
            raise
        except Exception as e:
            logger.warning(f"[EXEC] Real opportunity failed: {e}")
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
            tick_sleep_ms = None
            if tick_interval_ms is not None:
                tick_sleep_ms = max(0.0, tick_interval_ms - tick_elapsed_ms)
            md_total_ms = md_upbit_ms + md_binance_ms
            timing = {
                "tick_elapsed_ms": round(tick_elapsed_ms, 3),
                "tick_compute_ms": round(tick_elapsed_ms, 3),
                "tick_interval_ms": round(tick_interval_ms, 3) if tick_interval_ms is not None else None,
                "tick_sleep_ms": round(tick_sleep_ms, 3) if tick_sleep_ms is not None else None,
                "ticker_fetch_ms": round(ticker_fetch_ms, 3),
                "orderbook_fetch_ms": round(orderbook_fetch_ms, 3),
                "decision_ms": round(decision_ms, 3),
                "io_ms": round(io_ms, 3),
                "md_upbit_ms": round(md_upbit_ms, 3),
                "md_binance_ms": round(md_binance_ms, 3),
                "md_total_ms": round(md_total_ms, 3),
                "compute_decision_ms": round(decision_ms, 3),
                "rate_limiter_wait_ms": round(rate_limiter_wait_ms, 3),
            }
            self._last_tick_timing = timing
            if self.kpi is not None:
                self.kpi.record_tick_timing(
                    tick_elapsed_ms=tick_elapsed_ms,
                    ticker_fetch_ms=ticker_fetch_ms,
                    orderbook_fetch_ms=orderbook_fetch_ms,
                    decision_ms=decision_ms,
                    io_ms=io_ms,
                    tick_compute_ms=tick_elapsed_ms,
                    tick_interval_ms=tick_interval_ms,
                    tick_sleep_ms=tick_sleep_ms,
                    md_upbit_ms=md_upbit_ms,
                    md_binance_ms=md_binance_ms,
                    md_total_ms=md_total_ms,
                    compute_decision_ms=decision_ms,
                    rate_limiter_wait_ms=rate_limiter_wait_ms,
                )


class MockOpportunitySource(OpportunitySource):
    """Mock Opportunity 생성 (가상 가격)
    
    EXEC: profit_core 필수 의존성
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
        
        EXEC: profit_core 필수
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
            logger.warning(f"[EXEC] Mock build_candidate failed: {e}")
            self.kpi.errors.append(f"build_candidate: {e}")
            self._edge_distribution_sample = {
                "iteration": iteration,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "reason": "exception",
                "candidates": [],
            }
            return None
