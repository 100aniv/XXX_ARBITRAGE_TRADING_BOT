"""
BinanceAdapter - Binance Exchange Adapter (V2)

D201-1: MARKET semantics implementation for Binance Spot.
"""

from typing import Dict, Any
import logging

from arbitrage.v2.core import ExchangeAdapter, OrderIntent, OrderResult, OrderSide, OrderType


logger = logging.getLogger(__name__)


class BinanceAdapter(ExchangeAdapter):
    """
    Binance Spot exchange adapter (V2).
    
    Binance Spot API Rules:
    - MARKET BUY: 'quoteOrderQty' (USDT amount) required, 'quantity' forbidden
    - MARKET SELL: 'quantity' (BTC quantity) required, 'quoteOrderQty' forbidden
    - Symbol format: BTC/USDT → BTCUSDT (no separator)
    
    Reference: https://binance-docs.github.io/apidocs/spot/en/#new-order-trade
    
    Safety:
    - Default implementation returns mock response
    - Real API calls require explicit READ_ONLY flag
    """
    
    def __init__(self, read_only: bool = True):
        """
        Initialize Binance adapter.
        
        Args:
            read_only: If True, only payload validation (no real API calls)
        """
        self.read_only = read_only
        if not read_only:
            logger.warning("[V2 Binance] READ_ONLY=False - Real API calls ENABLED")
        else:
            logger.info("[V2 Binance] READ_ONLY=True - Mock mode")
    
    def translate_intent(self, intent: OrderIntent) -> Dict[str, Any]:
        """
        Translate OrderIntent to Binance Spot API payload.
        
        Implements Binance-specific rules:
        - Symbol transformation: BTC/USDT → BTCUSDT
        - MARKET BUY: 'quoteOrderQty' field (USDT amount)
        - MARKET SELL: 'quantity' field (BTC quantity)
        
        Args:
            intent: Order intent
            
        Returns:
            Binance API payload
            
        Raises:
            ValueError: If intent violates Binance rules
        """
        intent.validate()
        
        binance_symbol = intent.symbol.replace("/", "")
        
        payload = {
            "symbol": binance_symbol,
            "side": intent.side.value,
            "type": intent.order_type.value
        }
        
        if intent.order_type == OrderType.MARKET:
            if intent.side == OrderSide.BUY:
                if not intent.quote_amount or intent.quote_amount <= 0:
                    raise ValueError(
                        f"[V2 Binance] MARKET BUY requires positive quote_amount, "
                        f"got: {intent.quote_amount}"
                    )
                payload["quoteOrderQty"] = f"{intent.quote_amount:.8f}"
                
            elif intent.side == OrderSide.SELL:
                if not intent.base_qty or intent.base_qty <= 0:
                    raise ValueError(
                        f"[V2 Binance] MARKET SELL requires positive base_qty, "
                        f"got: {intent.base_qty}"
                    )
                payload["quantity"] = f"{intent.base_qty:.8f}"
        
        elif intent.order_type == OrderType.LIMIT:
            if not intent.limit_price or intent.limit_price <= 0:
                raise ValueError(
                    f"[V2 Binance] LIMIT order requires positive limit_price, "
                    f"got: {intent.limit_price}"
                )
            
            payload["price"] = f"{intent.limit_price:.8f}"
            payload["timeInForce"] = "GTC"
            
            if intent.side == OrderSide.BUY:
                if not intent.quote_amount or intent.quote_amount <= 0:
                    raise ValueError(
                        f"[V2 Binance] LIMIT BUY requires positive quote_amount, "
                        f"got: {intent.quote_amount}"
                    )
                quantity = intent.quote_amount / intent.limit_price
                payload["quantity"] = f"{quantity:.8f}"
            
            elif intent.side == OrderSide.SELL:
                if not intent.base_qty or intent.base_qty <= 0:
                    raise ValueError(
                        f"[V2 Binance] LIMIT SELL requires positive base_qty, "
                        f"got: {intent.base_qty}"
                    )
                payload["quantity"] = f"{intent.base_qty:.8f}"
        
        logger.debug(f"[V2 Binance] Translated intent to payload: {payload}")
        return payload
    
    def submit_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit order to Binance (mock in V2).
        
        V2 Safety Policy:
        - Default: Return mock response
        - Real API: Requires explicit READ_ONLY=False flag
        
        Args:
            payload: Binance API payload
            
        Returns:
            Binance API response (mock)
        """
        if self.read_only:
            logger.info(f"[V2 Binance] Mock order submission: {payload}")
            return {
                "symbol": payload["symbol"],
                "orderId": 12345678,
                "orderListId": -1,
                "clientOrderId": "mock-binance-" + payload["symbol"],
                "transactTime": 1640000000000,
                "price": payload.get("price", "0.00000000"),
                "origQty": payload.get("quantity", payload.get("quoteOrderQty", "0.00000000")),
                "executedQty": payload.get("quantity", payload.get("quoteOrderQty", "0.00000000")),
                "cummulativeQuoteQty": payload.get("quoteOrderQty", "0.00000000"),
                "status": "FILLED",
                "timeInForce": payload.get("timeInForce", "GTC"),
                "type": payload["type"],
                "side": payload["side"],
                "fills": []
            }
        else:
            raise NotImplementedError(
                "[V2 Binance] Real API calls not implemented in V2 kickoff. "
                "Use V1 binance_futures.py for production."
            )
    
    def parse_response(self, response: Dict[str, Any]) -> OrderResult:
        """
        Parse Binance response to OrderResult.
        
        Args:
            response: Binance API response
            
        Returns:
            Standardized OrderResult
        """
        success = response.get("status") in ["FILLED", "NEW", "PARTIALLY_FILLED"]
        order_id = str(response.get("orderId", ""))
        
        filled_qty = float(response.get("executedQty", 0))
        
        filled_price = None
        if "fills" in response and response["fills"]:
            total_qty = sum(float(f.get("qty", 0)) for f in response["fills"])
            total_value = sum(
                float(f.get("price", 0)) * float(f.get("qty", 0))
                for f in response["fills"]
            )
            if total_qty > 0:
                filled_price = total_value / total_qty
        elif filled_qty > 0:
            cummulative_quote_qty = float(response.get("cummulativeQuoteQty", 0))
            if cummulative_quote_qty > 0:
                filled_price = cummulative_quote_qty / filled_qty
        
        result = OrderResult(
            success=success,
            order_id=order_id,
            filled_qty=filled_qty,
            filled_price=filled_price,
            raw_response=response
        )
        
        logger.debug(f"[V2 Binance] Parsed result: {result}")
        return result
