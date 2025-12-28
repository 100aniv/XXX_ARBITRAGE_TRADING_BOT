"""
UpbitAdapter - Upbit Exchange Adapter

V2 implementation referencing V1 upbit_spot.py.
"""

from typing import Dict, Any
import logging

from arbitrage.v2.core import ExchangeAdapter, OrderIntent, OrderResult, OrderSide, OrderType


logger = logging.getLogger(__name__)


class UpbitAdapter(ExchangeAdapter):
    """
    Upbit exchange adapter (V2).
    
    Upbit API Rules (referenced from V1 upbit_spot.py):
    - MARKET BUY: 'price' (KRW amount) required, 'volume' forbidden
    - MARKET SELL: 'volume' (coin quantity) required, 'price' forbidden
    - Symbol format: BTC/KRW → BTC-KRW
    
    Safety:
    - Default implementation returns mock response
    - Real API calls require explicit READ_ONLY flag
    """
    
    def __init__(self, read_only: bool = True):
        """
        Initialize Upbit adapter.
        
        Args:
            read_only: If True, only payload validation (no real API calls)
        """
        self.read_only = read_only
        if not read_only:
            logger.warning("[V2 Upbit] READ_ONLY=False - Real API calls ENABLED")
        else:
            logger.info("[V2 Upbit] READ_ONLY=True - Mock mode")
    
    def translate_intent(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        Translate OrderIntent to Upbit API payload.
        
        Implements Upbit-specific rules:
        - Symbol transformation: BTC/KRW → KRW-BTC
        - MARKET BUY: 'price' field (KRW amount)
        - MARKET SELL: 'volume' field (coin quantity)
        
        Args:
            intent: Order intent
            
        Returns:
            Upbit API payload
            
        Raises:
            ValueError: If intent violates Upbit rules
        """
        intent.validate()
        
        base, quote = intent.symbol.split("/")
        upbit_market = f"{quote}-{base}"
        
        payload = {
            "market": upbit_market,
            "side": intent.side.value.lower(),
            "ord_type": intent.order_type.value.lower()
        }
        
        if intent.order_type == OrderType.MARKET:
            if intent.side == OrderSide.BUY:
                if not intent.quote_amount or intent.quote_amount <= 0:
                    raise ValueError(
                        f"[V2 Upbit] MARKET BUY requires positive quote_amount, "
                        f"got: {intent.quote_amount}"
                    )
                payload["price"] = str(int(intent.quote_amount))
                
            elif intent.side == OrderSide.SELL:
                if not intent.base_qty or intent.base_qty <= 0:
                    raise ValueError(
                        f"[V2 Upbit] MARKET SELL requires positive base_qty, "
                        f"got: {intent.base_qty}"
                    )
                payload["volume"] = str(intent.base_qty)
        
        elif intent.order_type == OrderType.LIMIT:
            if not intent.limit_price or intent.limit_price <= 0:
                raise ValueError(
                    f"[V2 Upbit] LIMIT order requires positive limit_price, "
                    f"got: {intent.limit_price}"
                )
            
            payload["price"] = str(int(intent.limit_price))
            
            if intent.side == OrderSide.BUY:
                if not intent.quote_amount or intent.quote_amount <= 0:
                    raise ValueError(
                        f"[V2 Upbit] LIMIT BUY requires positive quote_amount, "
                        f"got: {intent.quote_amount}"
                    )
                volume = intent.quote_amount / intent.limit_price
                payload["volume"] = str(volume)
            
            elif intent.side == OrderSide.SELL:
                if not intent.base_qty or intent.base_qty <= 0:
                    raise ValueError(
                        f"[V2 Upbit] LIMIT SELL requires positive base_qty, "
                        f"got: {intent.base_qty}"
                    )
                payload["volume"] = str(intent.base_qty)
        
        logger.debug(f"[V2 Upbit] Translated intent to payload: {payload}")
        return payload
    
    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit order to Upbit (mock in V2).
        
        V2 Safety Policy:
        - Default: Return mock response
        - Real API: Requires explicit READ_ONLY=False flag
        
        Args:
            payload: Upbit API payload
            
        Returns:
            Upbit API response (mock)
        """
        if self.read_only:
            logger.info(f"[V2 Upbit] Mock order submission: {payload}")
            return {
                "uuid": "mock-upbit-" + payload["market"],
                "side": payload["side"],
                "ord_type": payload["ord_type"],
                "price": payload.get("price"),
                "volume": payload.get("volume"),
                "state": "done",
                "market": payload["market"],
                "created_at": "2025-12-29T00:00:00+09:00",
                "trades": []
            }
        else:
            raise NotImplementedError(
                "[V2 Upbit] Real API calls not implemented in V2 kickoff. "
                "Use V1 upbit_spot.py for production."
            )
    
    def parse_response(self, response: Dict[str, Any]) -> OrderResult:
        """
        Parse Upbit response to OrderResult.
        
        Args:
            response: Upbit API response
            
        Returns:
            Standardized OrderResult
        """
        success = response.get("state") in ["done", "wait"]
        order_id = response.get("uuid")
        
        filled_qty = None
        filled_price = None
        if "trades" in response and response["trades"]:
            filled_qty = sum(float(t.get("volume", 0)) for t in response["trades"])
            total_value = sum(
                float(t.get("price", 0)) * float(t.get("volume", 0))
                for t in response["trades"]
            )
            if filled_qty > 0:
                filled_price = total_value / filled_qty
        
        result = OrderResult(
            success=success,
            order_id=order_id,
            filled_qty=filled_qty,
            filled_price=filled_price,
            raw_response=response
        )
        
        logger.debug(f"[V2 Upbit] Parsed result: {result}")
        return result
