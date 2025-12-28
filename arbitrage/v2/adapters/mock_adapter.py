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
        
        Args:
            payload: Mock payload
            
        Returns:
            Mock response
        """
        order_id = f"mock-{uuid.uuid4().hex[:8]}"
        
        response = {
            "order_id": order_id,
            "status": "filled",
            "filled_qty": payload.get("base_qty", 1.0),
            "filled_price": payload.get("limit_price", 100.0),
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
