"""
MockAdapter - Test Adapter

Mock implementation for testing without real API calls.

D205-17: Realism Injection
- Slippage model: 20-50bps (config.yml SSOT, D205-18-1)
- 목적: 100% 승률 가짜 낙관 제거, 현실적 50-80% 승률 목표
"""

from typing import Dict, Any, Optional
import uuid
import random

from arbitrage.v2.core import ExchangeAdapter, OrderIntent, OrderResult, OrderSide, OrderType


class MockAdapter(ExchangeAdapter):
    """
    Mock adapter for testing.
    
    D205-18-1: SSOT 통합
    - 슬리피지 설정: config.yml에서 로드 (하드코딩 제거)
    - BUY: filled_price = ref_price * (1 + slippage)
    - SELL: filled_price = ref_price * (1 - slippage)
    
    D207-1-3 Add-on BF: Non-Zero Friction Value
    - 수수료 모델: Upbit 5bps (0.05%), Binance 4bps (0.04%)
    - fees_total > 0 강제 (현실 마찰 반영)
    
    Useful for:
    - Unit testing
    - Integration testing without real APIs
    - Smoke testing with realistic friction
    """
    
    # D207-1-3 Add-on BF: 실전 수수료 (bps)
    FEE_RATES = {
        "upbit": 5.0,    # 0.05% (5 bps)
        "binance": 4.0,  # 0.04% (4 bps)
        "mock": 5.0,     # fallback
    }
    
    def __init__(
        self, 
        exchange_name: str = "mock", 
        enable_slippage: Optional[bool] = None,
        slippage_bps_min: Optional[float] = None,
        slippage_bps_max: Optional[float] = None,
        config: Optional[Dict[str, Any]] = None
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
        
        # D205-18-1: Config SSOT 우선
        if config and "mock_adapter" in config:
            mock_cfg = config["mock_adapter"]
            self.enable_slippage = mock_cfg.get("enable_slippage", True)
            self.slippage_bps_min = mock_cfg.get("slippage_bps_min", 20.0)
            self.slippage_bps_max = mock_cfg.get("slippage_bps_max", 50.0)
        else:
            # 명시적 파라미터 또는 기본값
            self.enable_slippage = enable_slippage if enable_slippage is not None else True
            self.slippage_bps_min = slippage_bps_min if slippage_bps_min is not None else 20.0
            self.slippage_bps_max = slippage_bps_max if slippage_bps_max is not None else 50.0
    
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
        
        # D205-17: Realism Injection - Slippage 적용
        filled_price = base_price
        if self.enable_slippage:
            slippage_bps = random.uniform(self.slippage_bps_min, self.slippage_bps_max)
            slippage_ratio = slippage_bps / 10000.0
            
            side = payload.get("side", "").upper()
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
        
        response = {
            "order_id": order_id,
            "status": "filled",
            "filled_qty": filled_qty,
            "filled_price": filled_price,
            "exchange": payload.get("exchange"),
            "symbol": payload.get("symbol"),
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
        success = (status == "filled")
        
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
        
        return OrderResult(
            success=success,
            order_id=response["order_id"],
            filled_qty=response.get("filled_qty") if success else 0.0,
            filled_price=response.get("filled_price") if success else 0.0,
            fee=fee,
            raw_response=response
        )
