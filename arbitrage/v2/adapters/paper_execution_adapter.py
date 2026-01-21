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
import uuid
import random
import time

from arbitrage.v2.core import ExchangeAdapter, OrderIntent, OrderResult, OrderSide, OrderType


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
        pessimistic_drift_bps_max: Optional[float] = None
    ):
        """
        Initialize mock adapter.
        
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
        
        # D205-18-1: Config SSOT 우선
        if config and "mock_adapter" in config:
            mock_cfg = config["mock_adapter"]
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
    
    def translate_intent(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        Translate intent to mock payload.
        
        Just returns a simple representation for logging.
        
        Args:
            intent: Order intent
            
        Returns:
            Mock payload
        """
        intent.validate()
        
        payload = {
            "exchange": self.exchange_name,
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
        Submit mock order (returns fake success response).
        
        D205-15-6a: ref_price 기반 filled_price (Fail-fast)
        D205-15-6b: MARKET BUY filled_qty 계약 고정
        - MARKET BUY: filled_qty = quote_amount / filled_price (계산 필수)
        - MARKET SELL: filled_qty = base_qty (직접 사용)
        - 계산 불가 시 RuntimeError (Fail-fast)
        
        Args:
            payload: Mock payload
            
        Returns:
            Mock response
        """
        # D207-1-6: Realism Pack v1 - latency with exponential tail
        latency_ms = float(self.latency_base_ms)
        if self.latency_jitter_ms > 0:
            latency_ms += random.expovariate(1.0 / float(self.latency_jitter_ms))
        time.sleep(latency_ms / 1000.0)

        order_id = f"mock-{uuid.uuid4().hex[:8]}"
        
        # D205-15-6a: ref_price 우선, 없으면 limit_price, 둘 다 없으면 fallback (경고)
        base_price = payload.get("ref_price") or payload.get("limit_price")
        if base_price is None:
            # Fallback for testing without ref_price (경고 로그)
            base_price = 100.0
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"[D205-15-6a] MockAdapter: base_price fallback to 100.0. "
                f"Consider providing 'ref_price' or 'limit_price'. "
                f"payload keys: {list(payload.keys())}"
            )
        
        side = payload.get("side", "").upper()

        # D205-17: Realism Injection - Slippage 적용
        # D207-1-6: Realism Pack v1 - randomized bps within config range
        filled_price = base_price
        slippage_bps = 0.0
        if self.enable_slippage:
            min_bps = min(self.slippage_bps_min, self.slippage_bps_max)
            max_bps = max(self.slippage_bps_min, self.slippage_bps_max)
            slippage_bps = min_bps if min_bps == max_bps else random.uniform(min_bps, max_bps)
            slippage_ratio = slippage_bps / 10000.0
            
            if side == "BUY":
                # BUY: 불리하게 (더 높은 가격에 체결)
                filled_price = base_price * (1 + slippage_ratio)
            elif side == "SELL":
                # SELL: 불리하게 (더 낮은 가격에 체결)
                filled_price = base_price * (1 - slippage_ratio)
            
            # 슬리피지 적용 로그 (검증용)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[D205-17 Slippage] {side} base={base_price:.2f}, "
                f"slippage={slippage_bps:.2f}bps, filled={filled_price:.2f}"
            )

        # D207-3: Pessimistic Drift (physical price contamination)
        drift_bps_min = min(self.pessimistic_drift_bps_min, self.pessimistic_drift_bps_max)
        drift_bps_max = max(self.pessimistic_drift_bps_min, self.pessimistic_drift_bps_max)
        drift_bps = drift_bps_min if drift_bps_min == drift_bps_max else random.uniform(drift_bps_min, drift_bps_max)
        drift_ratio = drift_bps / 10000.0
        if drift_ratio > 0:
            if side == "BUY":
                filled_price = filled_price * (1 + drift_ratio)
            elif side == "SELL":
                filled_price = filled_price * (1 - drift_ratio)

        if drift_bps > 0:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[D207-3 Drift] {side} drift={drift_bps:.2f}bps, filled={filled_price:.2f}"
            )
        
        # D205-15-6b: MARKET BUY filled_qty 계약 고정 (V2_ARCHITECTURE invariant)
        order_type = payload.get("order_type", "").upper()
        side = payload.get("side", "").upper()
        
        if order_type == "MARKET" and side == "BUY":
            # MARKET BUY: filled_qty = quote_amount / filled_price
            quote_amount = payload.get("quote_amount")
            if not quote_amount or quote_amount <= 0:
                raise RuntimeError(
                    f"[D205-15-6b] MockAdapter: MARKET BUY requires positive quote_amount. "
                    f"Got: {quote_amount}, payload: {payload}"
                )
            if not filled_price or filled_price <= 0:
                raise RuntimeError(
                    f"[D205-15-6b] MockAdapter: MARKET BUY requires positive filled_price. "
                    f"Got: {filled_price}, payload: {payload}"
                )
            filled_qty = quote_amount / filled_price
        else:
            # MARKET SELL or LIMIT: base_qty 직접 사용
            filled_qty = payload.get("base_qty")
            if not filled_qty or filled_qty <= 0:
                raise RuntimeError(
                    f"[D205-15-6b] MockAdapter: filled_qty missing or invalid. "
                    f"order_type={order_type}, side={side}, base_qty={filled_qty}, payload: {payload}"
                )
        
        partial_fill_ratio = 1.0
        status = "filled"
        partial_fill_probability = self.partial_fill_probability
        if not self.enable_slippage and not self._partial_fill_configured:
            partial_fill_probability = 0.0
        if partial_fill_probability > 0 and random.random() < partial_fill_probability:
            ratio_min = min(self.partial_fill_ratio_min, self.partial_fill_ratio_max)
            ratio_max = max(self.partial_fill_ratio_min, self.partial_fill_ratio_max)
            partial_fill_ratio = max(0.01, min(1.0, random.uniform(ratio_min, ratio_max)))
            status = "partial"
            filled_qty *= partial_fill_ratio

        response = {
            "order_id": order_id,
            "status": status,
            "filled_qty": filled_qty,
            "filled_price": filled_price,
            "ref_price": base_price,
            "slippage_bps": slippage_bps,
            "pessimistic_drift_bps": drift_bps,
            "latency_ms": latency_ms,
            "exchange": payload.get("exchange"),
            "symbol": payload.get("symbol"),
            "partial_fill_ratio": partial_fill_ratio,
        }
        
        return response
    
    def parse_response(self, response: Dict[str, Any]) -> OrderResult:
        """
        Parse mock response to OrderResult.
        
        D207-1-3 Add-on BF: Non-Zero Friction Value
        - 수수료 계산: filled_qty * filled_price * fee_rate
        - Upbit 5bps, Binance 4bps 강제 적용
        
        Args:
            response: Mock response
            
        Returns:
            OrderResult
        """
        status = response.get("status", "filled")
        success = status in ["filled", "partial"]
        
        # D207-1-3 Add-on BF: 수수료 계산 (현실 마찰)
        fee = 0.0
        if success:
            filled_qty = response.get("filled_qty", 0.0)
            filled_price = response.get("filled_price", 0.0)
            exchange = response.get("exchange", "mock").lower()
            
            # 거래소별 수수료율 (bps)
            fee_rate_bps = self.FEE_RATES.get(exchange, self.FEE_RATES["mock"])
            fee_rate = fee_rate_bps / 10000.0  # bps -> ratio
            
            # 수수료 = 거래 금액 * 수수료율
            trade_value = filled_qty * filled_price
            fee = trade_value * fee_rate
            
            # 검증 로그
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"[D207-1-3 Add-on BF] Fee calculated: exchange={exchange}, "
                f"qty={filled_qty:.6f}, price={filled_price:.2f}, "
                f"fee_rate={fee_rate_bps}bps, fee={fee:.4f}"
            )
        
        partial_fill_ratio = response.get("partial_fill_ratio")
        if partial_fill_ratio is None:
            partial_fill_ratio = 1.0 if success else 0.0

        return OrderResult(
            success=success,
            order_id=response["order_id"],
            filled_qty=response.get("filled_qty") if success else 0.0,
            filled_price=response.get("filled_price") if success else 0.0,
            fee=fee,
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
