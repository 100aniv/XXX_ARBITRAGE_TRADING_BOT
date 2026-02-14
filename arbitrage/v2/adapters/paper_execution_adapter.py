"""
PaperExecutionAdapter - Paper Trading Adapter

D207-1-5 Add-on Alpha: Naming to Reality
- 이전 이름: MockAdapter (오해의 소지 - "Mock 데이터"로 혼동)
- 새 이름: PaperExecutionAdapter (Paper Trading = 실제 시장가 + 모의 체결)
- MockAdapter는 backward compatibility를 위한 deprecated alias로 유지

Paper execution without real API calls (but with REAL market data).

D205-17: Realism Injection
- Slippage model: 20-50bps (config.yml SSOT, D205-18-1)
- 목적: 100% 승률 가짜 낙관 제거, 현실적 50-80% 승률 목표

D207-1-3 Add-on BF: Non-Zero Friction Value
- 수수료 모델: Upbit 5bps (0.05%), Binance 4bps (0.04%)
- fees_total > 0 강제 (현실 마찰 반영)
"""

from typing import Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
import random
import time

from arbitrage.v2.core import ExchangeAdapter, OrderIntent, OrderResult, OrderSide, OrderType


DECIMAL_QUANTIZE = Decimal("0.00000001")


def _to_decimal(value: Optional[float]) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(DECIMAL_QUANTIZE, rounding=ROUND_HALF_UP)


class PaperExecutionAdapter(ExchangeAdapter):
    """
    Paper trading adapter - executes orders in paper mode with realistic friction.
    
    NOTE: This is NOT about "mock data" - it uses REAL market data from exchanges.
    "Paper" means we don't send real orders, but we simulate fills with realistic fees/slippage.
    
    D205-18-1: SSOT 통합
    - 슬리피지 설정: config.yml에서 로드 (하드코딩 제거)
    - BUY: filled_price = ref_price * (1 + slippage)
    - SELL: filled_price = ref_price * (1 - slippage)
    
    D207-1-3 Add-on BF: Non-Zero Friction Value
    - 수수료 모델: Upbit 5bps (0.05%), Binance 4bps (0.04%)
    - fees_total > 0 강제 (현실 마찰 반영)
    
    Useful for:
    - Paper trading (real prices, simulated fills)
    - Integration testing without real money
    - Smoke testing with realistic friction
    """
    
    # D207-1-3 Add-on BF: 실전 수수료 (bps)
    FEE_RATES = {
        "upbit": 5.0,    # 0.05% (5 bps)
        "binance": 4.0,  # 0.04% (4 bps)
        "mock": 5.0,     # fallback
    }

    # D207-1-6 Realism Pack v1: Execution realism defaults
    LATENCY_BASE_MS = 300.0
    LATENCY_JITTER_MS = 80.0  # exp tail mean
    PARTIAL_FILL_PROBABILITY = 0.15
    PARTIAL_FILL_RATIO_MIN = 0.5
    PARTIAL_FILL_RATIO_MAX = 0.9
    PESSIMISTIC_DRIFT_BPS_MIN = 10.0
    PESSIMISTIC_DRIFT_BPS_MAX = 10.0
    ADVERSE_SLIPPAGE_PROBABILITY = 0.0
    ADVERSE_SLIPPAGE_BPS_MIN = 10.0
    ADVERSE_SLIPPAGE_BPS_MAX = 20.0
    FILL_REJECT_PROBABILITY = 0.0
    
    def __init__(
        self, 
        exchange_name: str = "mock", 
        enable_slippage: Optional[bool] = None,
        slippage_bps_min: Optional[float] = None,
        slippage_bps_max: Optional[float] = None,
        config: Optional[Dict[str, Any]] = None,
        latency_base_ms: Optional[float] = None,
        latency_jitter_ms: Optional[float] = None,
        partial_fill_probability: Optional[float] = None,
        partial_fill_ratio_min: Optional[float] = None,
        partial_fill_ratio_max: Optional[float] = None,
        pessimistic_drift_bps_min: Optional[float] = None,
        pessimistic_drift_bps_max: Optional[float] = None,
        adverse_slippage_probability: Optional[float] = None,
        adverse_slippage_bps_min: Optional[float] = None,
        adverse_slippage_bps_max: Optional[float] = None,
        fill_reject_probability: Optional[float] = None,
        max_safe_ratio: Optional[float] = None,
        rng: Optional[random.Random] = None
    ):
        """
        Initialize paper adapter.
        
        D205-18-1: Config SSOT 통합
        - 우선순위: config > 명시적 파라미터 > 기본값
        - 기본값은 백업용 (config 없을 때만)
        
        Args:
            exchange_name: Exchange identifier (default: "mock")
            enable_slippage: Enable realistic slippage (None = config에서 로드)
            slippage_bps_min: Min slippage bps (None = config에서 로드)
            slippage_bps_max: Max slippage bps (None = config에서 로드)
            config: Config dict (execution.mock_adapter 섹션)
        """
        self.exchange_name = exchange_name
        self._partial_fill_configured = False
        self._fee_rates = dict(self.FEE_RATES)
        self._rng = rng or random.Random(0)
        self._order_seq = 0
        self.random_seed = None
        
        # D205-18-1: Config SSOT 우선
        if config and "mock_adapter" in config:
            mock_cfg = config["mock_adapter"]
            if rng is None:
                seed = mock_cfg.get("random_seed")
                if seed is not None:
                    self.random_seed = int(seed)
                    self._rng = random.Random(self.random_seed)
            self._partial_fill_configured = "partial_fill_probability" in mock_cfg
            self.enable_slippage = mock_cfg.get("enable_slippage", True)
            self.slippage_bps_min = mock_cfg.get("slippage_bps_min", 20.0)
            self.slippage_bps_max = mock_cfg.get("slippage_bps_max", 50.0)
            self.latency_base_ms = mock_cfg.get("latency_base_ms", self.LATENCY_BASE_MS)
            self.latency_jitter_ms = mock_cfg.get("latency_jitter_ms", self.LATENCY_JITTER_MS)
            self.partial_fill_probability = mock_cfg.get(
                "partial_fill_probability", self.PARTIAL_FILL_PROBABILITY
            )
            self.partial_fill_ratio_min = mock_cfg.get(
                "partial_fill_ratio_min", self.PARTIAL_FILL_RATIO_MIN
            )
            self.partial_fill_ratio_max = mock_cfg.get(
                "partial_fill_ratio_max", self.PARTIAL_FILL_RATIO_MAX
            )
            self.pessimistic_drift_bps_min = mock_cfg.get(
                "pessimistic_drift_bps_min", self.PESSIMISTIC_DRIFT_BPS_MIN
            )
            self.pessimistic_drift_bps_max = mock_cfg.get(
                "pessimistic_drift_bps_max", self.PESSIMISTIC_DRIFT_BPS_MAX
            )
            self.adverse_slippage_probability = mock_cfg.get(
                "adverse_slippage_probability", self.ADVERSE_SLIPPAGE_PROBABILITY
            )
            self.adverse_slippage_bps_min = mock_cfg.get(
                "adverse_slippage_bps_min", self.ADVERSE_SLIPPAGE_BPS_MIN
            )
            self.adverse_slippage_bps_max = mock_cfg.get(
                "adverse_slippage_bps_max", self.ADVERSE_SLIPPAGE_BPS_MAX
            )
            self.fill_reject_probability = mock_cfg.get(
                "fill_reject_probability", self.FILL_REJECT_PROBABILITY
            )
            self.max_safe_ratio = float(mock_cfg.get("max_safe_ratio", 0.3))
            fee_rates = config.get("fee_rates") if isinstance(config, dict) else None
            if isinstance(fee_rates, dict):
                self._fee_rates.update({str(k).lower(): float(v) for k, v in fee_rates.items()})
        else:
            # 명시적 파라미터 또는 기본값
            self._partial_fill_configured = partial_fill_probability is not None
            self.enable_slippage = enable_slippage if enable_slippage is not None else True
            self.slippage_bps_min = slippage_bps_min if slippage_bps_min is not None else 20.0
            self.slippage_bps_max = slippage_bps_max if slippage_bps_max is not None else 50.0
            self.latency_base_ms = latency_base_ms if latency_base_ms is not None else self.LATENCY_BASE_MS
            self.latency_jitter_ms = latency_jitter_ms if latency_jitter_ms is not None else self.LATENCY_JITTER_MS
            self.partial_fill_probability = (
                partial_fill_probability
                if partial_fill_probability is not None
                else self.PARTIAL_FILL_PROBABILITY
            )
            self.partial_fill_ratio_min = (
                partial_fill_ratio_min
                if partial_fill_ratio_min is not None
                else self.PARTIAL_FILL_RATIO_MIN
            )
            self.partial_fill_ratio_max = (
                partial_fill_ratio_max
                if partial_fill_ratio_max is not None
                else self.PARTIAL_FILL_RATIO_MAX
            )
            self.pessimistic_drift_bps_min = (
                pessimistic_drift_bps_min
                if pessimistic_drift_bps_min is not None
                else self.PESSIMISTIC_DRIFT_BPS_MIN
            )
            self.pessimistic_drift_bps_max = (
                pessimistic_drift_bps_max
                if pessimistic_drift_bps_max is not None
                else self.PESSIMISTIC_DRIFT_BPS_MAX
            )
            self.adverse_slippage_probability = (
                adverse_slippage_probability
                if adverse_slippage_probability is not None
                else self.ADVERSE_SLIPPAGE_PROBABILITY
            )
            self.adverse_slippage_bps_min = (
                adverse_slippage_bps_min
                if adverse_slippage_bps_min is not None
                else self.ADVERSE_SLIPPAGE_BPS_MIN
            )
            self.adverse_slippage_bps_max = (
                adverse_slippage_bps_max
                if adverse_slippage_bps_max is not None
                else self.ADVERSE_SLIPPAGE_BPS_MAX
            )
            self.fill_reject_probability = (
                fill_reject_probability
                if fill_reject_probability is not None
                else self.FILL_REJECT_PROBABILITY
            )
            self.max_safe_ratio = float(max_safe_ratio if max_safe_ratio is not None else 0.3)
            if config and isinstance(config, dict):
                fee_rates = config.get("fee_rates")
                if isinstance(fee_rates, dict):
                    self._fee_rates.update({str(k).lower(): float(v) for k, v in fee_rates.items()})

    def _calculate_partial_fill_ratio(self, payload: Dict[str, Any]) -> float:
        """
        Deterministic partial fill ratio (Anti-Dice).

        Rule:
        - size_ratio <= max_safe_ratio -> fill_ratio = 1.0
        - otherwise -> fill_ratio = max_safe_ratio / size_ratio (clamp to [0.1, 1.0])
        """
        try:
            side = str(payload.get("side", "")).upper()
            order_size = 0.0
            if side == "BUY":
                quote_amount = float(payload.get("quote_amount") or 0.0)
                base_price = payload.get("ref_price") or payload.get("limit_price")
                base_price_f = float(base_price) if base_price is not None else 0.0
                if quote_amount > 0 and base_price_f > 0:
                    order_size = quote_amount / base_price_f
                else:
                    order_size = 0.0
            else:
                order_size = float(payload.get("base_qty") or 0.0)

            top_depth = payload.get("top_depth")
            if top_depth is None:
                return 1.0
            top_depth = float(top_depth)
            if order_size <= 0 or top_depth <= 0:
                return 1.0

            max_safe = float(self.max_safe_ratio or 0.3)
            size_ratio = order_size / top_depth
            if size_ratio <= max_safe:
                return 1.0
            fill_ratio = max_safe / size_ratio
            fill_ratio = max(0.1, min(1.0, fill_ratio))
            return round(fill_ratio, 2)
        except Exception:
            return 1.0
    
    def translate_intent(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        Translate intent to paper payload.
        
        Just returns a simple representation for logging.
        
        Args:
            intent: Order intent
            
        Returns:
            Paper payload
        """
        intent.validate()
        
        payload = {
            "exchange": intent.exchange,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "order_type": intent.order_type.value,
        }
        
        if intent.order_type == OrderType.MARKET:
            if intent.side == OrderSide.BUY:
                payload["quote_amount"] = intent.quote_amount
            else:
                payload["base_qty"] = intent.base_qty
        else:
            payload["limit_price"] = intent.limit_price
            if intent.side == OrderSide.BUY:
                payload["quote_amount"] = intent.quote_amount
            else:
                payload["base_qty"] = intent.base_qty
        
        return payload
    
    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit paper order (returns simulated success response).
        
        D205-15-6a: ref_price 기반 filled_price (Fail-fast)
        D205-15-6b: MARKET BUY filled_qty 계약 고정
        - MARKET BUY: filled_qty = quote_amount / filled_price (계산 필수)
        - MARKET SELL: filled_qty = base_qty (직접 사용)
        - 계산 불가 시 RuntimeError (Fail-fast)
        
        Args:
            payload: Paper payload
            
        Returns:
            Paper response
        """
        # D207-1-6: Realism Pack v1 - latency with exponential tail
        latency_ms = float(self.latency_base_ms)
        if self.latency_jitter_ms > 0:
            latency_ms += self._rng.expovariate(1.0 / float(self.latency_jitter_ms))
        time.sleep(latency_ms / 1000.0)

        self._order_seq += 1
        order_id = f"paper-{str(payload.get('exchange') or self.exchange_name)}-{self._order_seq:08d}"
        
        # D205-15-6a: ref_price 우선, 없으면 limit_price, 둘 다 없으면 fallback (경고)
        base_price = payload.get("ref_price") or payload.get("limit_price")
        if base_price is None:
            # Fallback for testing without ref_price (경고 로그)
            base_price = 100.0
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"[D205-15-6a] PaperAdapter: base_price fallback to 100.0. "
                f"Consider providing 'ref_price' or 'limit_price'. "
                f"payload keys: {list(payload.keys())}"
            )
        
        side = payload.get("side", "").upper()
        base_price_decimal = _to_decimal(base_price)

        size_ratio = None
        try:
            top_depth_val = payload.get("top_depth")
            if top_depth_val is not None:
                top_depth_f = float(top_depth_val)
                if top_depth_f > 0:
                    if side == "BUY":
                        quote_amount = float(payload.get("quote_amount") or 0.0)
                        base_price_f = float(base_price) if base_price is not None else 0.0
                        order_size = (quote_amount / base_price_f) if (quote_amount > 0 and base_price_f > 0) else 0.0
                    else:
                        order_size = float(payload.get("base_qty") or 0.0)
                    if order_size > 0:
                        size_ratio = float(order_size) / float(top_depth_f)
        except Exception:
            size_ratio = None

        reject_probability = float(self.fill_reject_probability or 0.0)
        should_reject = False
        if reject_probability >= 1.0:
            should_reject = True
        elif reject_probability > 0:
            if size_ratio is not None:
                if size_ratio > float(self.max_safe_ratio or 0.3) * 3.0:
                    should_reject = True
            else:
                should_reject = self._rng.random() < reject_probability

        if should_reject:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[D_ALPHA-1U-FIX-2-1 Reject] {side} reject_prob={reject_probability:.2f}"
            )
            return {
                "order_id": order_id,
                "status": "rejected",
                "filled_qty": 0.0,
                "filled_price": 0.0,
                "ref_price": base_price,
                "slippage_bps": 0.0,
                "pessimistic_drift_bps": 0.0,
                "latency_ms": latency_ms,
                "exchange": payload.get("exchange"),
                "symbol": payload.get("symbol"),
                "partial_fill_ratio": 0.0,
                "adverse_slippage_bps": 0.0,
                "top_depth": payload.get("top_depth"),
                "size_ratio": size_ratio,
                "error_message": "fill_rejected",
            }

        # D205-17: Realism Injection - Slippage 적용
        # D207-1-6: Realism Pack v1 - randomized bps within config range
        filled_price = base_price_decimal
        slippage_bps = 0.0
        adverse_slippage_bps = 0.0
        if self.enable_slippage:
            min_bps = min(self.slippage_bps_min, self.slippage_bps_max)
            max_bps = max(self.slippage_bps_min, self.slippage_bps_max)
            slippage_bps = min_bps if min_bps == max_bps else self._rng.uniform(min_bps, max_bps)
            adverse_prob = float(self.adverse_slippage_probability or 0.0)
            should_adverse = False
            if adverse_prob >= 1.0:
                should_adverse = True
            elif adverse_prob > 0:
                if size_ratio is not None:
                    should_adverse = self._rng.random() < adverse_prob
                else:
                    should_adverse = self._rng.random() < adverse_prob
            if should_adverse:
                adv_min = min(self.adverse_slippage_bps_min, self.adverse_slippage_bps_max)
                adv_max = max(self.adverse_slippage_bps_min, self.adverse_slippage_bps_max)
                adverse_slippage_bps = adv_min if adv_min == adv_max else self._rng.uniform(adv_min, adv_max)
                slippage_bps += adverse_slippage_bps
            slippage_ratio = _to_decimal(slippage_bps) / Decimal("10000")
            
            if side == "BUY":
                # BUY: 불리하게 (더 높은 가격에 체결)
                filled_price = base_price_decimal * (Decimal("1") + slippage_ratio)
            elif side == "SELL":
                # SELL: 불리하게 (더 낮은 가격에 체결)
                filled_price = base_price_decimal * (Decimal("1") - slippage_ratio)
            
            # 슬리피지 적용 로그 (검증용)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[D205-17 Slippage] {side} base={float(base_price_decimal):.2f}, "
                f"slippage={slippage_bps:.2f}bps, filled={float(filled_price):.2f}"
            )
            if adverse_slippage_bps > 0:
                logger.info(
                    f"[D_ALPHA-1U-FIX-2-1 Adverse] {side} adverse_slippage={adverse_slippage_bps:.2f}bps"
                )

        # D207-3: Pessimistic Drift (physical price contamination)
        drift_bps_min = min(self.pessimistic_drift_bps_min, self.pessimistic_drift_bps_max)
        drift_bps_max = max(self.pessimistic_drift_bps_min, self.pessimistic_drift_bps_max)
        drift_bps = drift_bps_min if drift_bps_min == drift_bps_max else self._rng.uniform(drift_bps_min, drift_bps_max)
        drift_ratio = _to_decimal(drift_bps) / Decimal("10000")
        if drift_ratio > 0:
            if side == "BUY":
                filled_price = filled_price * (Decimal("1") + drift_ratio)
            elif side == "SELL":
                filled_price = filled_price * (Decimal("1") - drift_ratio)

        if drift_bps > 0:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[D207-3 Drift] {side} drift={drift_bps:.2f}bps, filled={float(filled_price):.2f}"
            )
        
        # D205-15-6b: MARKET BUY filled_qty 계약 고정 (V2_ARCHITECTURE invariant)
        order_type = payload.get("order_type", "").upper()
        side = payload.get("side", "").upper()
        
        filled_price = _quantize(filled_price)

        if order_type == "MARKET" and side == "BUY":
            # MARKET BUY: filled_qty = quote_amount / filled_price
            quote_amount = payload.get("quote_amount")
            if not quote_amount or quote_amount <= 0:
                raise RuntimeError(
                    f"[D205-15-6b] PaperAdapter: MARKET BUY requires positive quote_amount. "
                    f"Got: {quote_amount}, payload: {payload}"
                )
            if filled_price <= 0:
                raise RuntimeError(
                    f"[D205-15-6b] PaperAdapter: MARKET BUY requires positive filled_price. "
                    f"Got: {filled_price}, payload: {payload}"
                )
            filled_qty = _quantize(_to_decimal(quote_amount) / filled_price)
        else:
            # MARKET SELL or LIMIT: base_qty 직접 사용
            filled_qty = _to_decimal(payload.get("base_qty"))
            if filled_qty <= 0:
                raise RuntimeError(
                    f"[D205-15-6b] PaperAdapter: filled_qty missing or invalid. "
                    f"order_type={order_type}, side={side}, base_qty={filled_qty}, payload: {payload}"
                )
            filled_qty = _quantize(filled_qty)
        
        partial_fill_ratio = 1.0
        status = "filled"
        partial_fill_probability = self.partial_fill_probability
        if not self.enable_slippage and not self._partial_fill_configured:
            partial_fill_probability = 0.0
        if partial_fill_probability > 0:
            partial_fill_ratio = self._calculate_partial_fill_ratio(payload)
            if partial_fill_ratio < 1.0:
                status = "partial"
                filled_qty = _quantize(filled_qty * _to_decimal(partial_fill_ratio))

        response = {
            "order_id": order_id,
            "status": status,
            "filled_qty": float(filled_qty),
            "filled_price": float(filled_price),
            "ref_price": float(base_price_decimal),
            "slippage_bps": slippage_bps,
            "pessimistic_drift_bps": drift_bps,
            "latency_ms": latency_ms,
            "exchange": payload.get("exchange"),
            "symbol": payload.get("symbol"),
            "partial_fill_ratio": partial_fill_ratio,
            "adverse_slippage_bps": adverse_slippage_bps,
            "top_depth": payload.get("top_depth"),
            "size_ratio": size_ratio,
        }
        
        return response
    
    def parse_response(self, response: Dict[str, Any]) -> OrderResult:
        """
        Parse paper response to OrderResult.
        
        D207-1-3 Add-on BF: Non-Zero Friction Value
        - 수수료 계산: filled_qty * filled_price * fee_rate
        - Upbit 5bps, Binance 4bps 강제 적용
        
        Args:
            response: Paper response
            
        Returns:
            OrderResult
        """
        status = response.get("status", "filled")
        success = status in ["filled", "partial"]
        
        filled_qty_decimal = _to_decimal(response.get("filled_qty", 0.0))
        filled_price_decimal = _to_decimal(response.get("filled_price", 0.0))
        filled_qty_decimal = _quantize(filled_qty_decimal)
        filled_price_decimal = _quantize(filled_price_decimal)
        
        # D207-1-3 Add-on BF: 수수료 계산 (현실 마찰)
        fee_decimal = Decimal("0")
        if success:
            exchange = response.get("exchange", "mock").lower()
            
            # 거래소별 수수료율 (bps)
            fee_rate_bps = _to_decimal(self._fee_rates.get(exchange, self._fee_rates["mock"]))
            fee_rate = fee_rate_bps / Decimal("10000")  # bps -> ratio
            
            # 수수료 = 거래 금액 * 수수료율
            trade_value = filled_qty_decimal * filled_price_decimal
            fee_decimal = _quantize(trade_value * fee_rate)
            
            # 검증 로그
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[D207-1-3 Add-on BF] Fee calculated: exchange={exchange}, "
                f"qty={float(filled_qty_decimal):.6f}, price={float(filled_price_decimal):.2f}, "
                f"fee_rate={float(fee_rate_bps):.2f}bps, fee={float(fee_decimal):.4f}"
            )
        
        partial_fill_ratio = response.get("partial_fill_ratio")
        if partial_fill_ratio is None:
            partial_fill_ratio = 1.0 if success else 0.0

        return OrderResult(
            success=success,
            order_id=response["order_id"],
            filled_qty=float(filled_qty_decimal) if success else 0.0,
            filled_price=float(filled_price_decimal) if success else 0.0,
            fee=float(fee_decimal),
            ref_price=response.get("ref_price"),
            slippage_bps=response.get("slippage_bps"),
            pessimistic_drift_bps=response.get("pessimistic_drift_bps"),
            latency_ms=response.get("latency_ms"),
            reject_flag=False if success else True,
            partial_fill_ratio=partial_fill_ratio,
            raw_response=response
        )


# D207-1-5 Add-on Alpha: Backward compatibility alias
# DEPRECATED: Use PaperExecutionAdapter instead
MockAdapter = PaperExecutionAdapter
