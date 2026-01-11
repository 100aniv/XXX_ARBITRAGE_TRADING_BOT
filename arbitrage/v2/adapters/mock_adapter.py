"""
MockAdapter - Test Adapter

Mock implementation for testing without real API calls.
"""

from typing import Dict, Any
import uuid

from arbitrage.v2.core import ExchangeAdapter, OrderIntent, OrderResult, OrderSide, OrderType


class MockAdapter(ExchangeAdapter):
    """
    Mock adapter for testing.
    
    Always succeeds with fake order IDs and fill data.
    Useful for:
    - Unit testing
    - Integration testing without real APIs
    - Smoke testing the Engine flow
    """
    
    def __init__(self, exchange_name: str = "mock"):
        """
        Initialize mock adapter.
        
        Args:
            exchange_name: Exchange identifier (default: "mock")
        """
        self.exchange_name = exchange_name
    
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
        filled_price = payload.get("ref_price") or payload.get("limit_price")
        if filled_price is None:
            # Fallback for testing without ref_price (경고 로그)
            filled_price = 100.0
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"[D205-15-6a] MockAdapter: filled_price fallback to 100.0. "
                f"Consider providing 'ref_price' or 'limit_price'. "
                f"payload keys: {list(payload.keys())}"
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
        
        Args:
            response: Mock response
            
        Returns:
            OrderResult
        """
        return OrderResult(
            success=True,
            order_id=response["order_id"],
            filled_qty=response.get("filled_qty"),
            filled_price=response.get("filled_price"),
            raw_response=response
        )
