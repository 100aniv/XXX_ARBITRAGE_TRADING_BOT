"""
OrderIntent - Semantic Layer

Exchange-independent order intent representation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    """Order side: BUY or SELL"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type: MARKET or LIMIT"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class OrderIntent:
    """
    Exchange-independent order intent.
    
    MARKET Order Convention:
    - BUY MARKET: quote_amount required (KRW/USDT amount to spend)
    - SELL MARKET: base_qty required (BTC/ETH quantity to sell)
    
    LIMIT Order Convention:
    - BUY LIMIT: quote_amount + limit_price required
    - SELL LIMIT: base_qty + limit_price required
    
    Attributes:
        exchange: Exchange identifier (e.g., "upbit", "binance")
        symbol: Trading pair (e.g., "BTC/KRW", "BTC/USDT")
        side: BUY or SELL
        order_type: MARKET or LIMIT
        base_qty: Base asset quantity (for SELL orders)
        quote_amount: Quote asset amount (for BUY orders)
        limit_price: Limit price (for LIMIT orders)
        route_id: Optional route identifier for tracking
        strategy_id: Optional strategy identifier
    """
    exchange: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    
    base_qty: Optional[float] = None
    quote_amount: Optional[float] = None
    limit_price: Optional[float] = None
    
    route_id: Optional[str] = None
    strategy_id: Optional[str] = None
    
    def validate(self):
        """
        Validate the order intent.
        
        Raises:
            ValueError: If the intent is invalid
        """
        if self.order_type == OrderType.MARKET:
            if self.side == OrderSide.BUY:
                if not self.quote_amount or self.quote_amount <= 0:
                    raise ValueError(
                        f"MARKET BUY requires positive quote_amount, "
                        f"got: {self.quote_amount}"
                    )
            elif self.side == OrderSide.SELL:
                if not self.base_qty or self.base_qty <= 0:
                    raise ValueError(
                        f"MARKET SELL requires positive base_qty, "
                        f"got: {self.base_qty}"
                    )
        
        elif self.order_type == OrderType.LIMIT:
            if not self.limit_price or self.limit_price <= 0:
                raise ValueError(
                    f"LIMIT order requires positive limit_price, "
                    f"got: {self.limit_price}"
                )
            
            if self.side == OrderSide.BUY:
                if not self.quote_amount or self.quote_amount <= 0:
                    raise ValueError(
                        f"LIMIT BUY requires positive quote_amount, "
                        f"got: {self.quote_amount}"
                    )
            elif self.side == OrderSide.SELL:
                if not self.base_qty or self.base_qty <= 0:
                    raise ValueError(
                        f"LIMIT SELL requires positive base_qty, "
                        f"got: {self.base_qty}"
                    )
    
    def __repr__(self) -> str:
        """Human-readable representation"""
        if self.order_type == OrderType.MARKET:
            if self.side == OrderSide.BUY:
                detail = f"quote_amount={self.quote_amount}"
            else:
                detail = f"base_qty={self.base_qty}"
        else:
            if self.side == OrderSide.BUY:
                detail = f"quote_amount={self.quote_amount} @ {self.limit_price}"
            else:
                detail = f"base_qty={self.base_qty} @ {self.limit_price}"
        
        return (
            f"OrderIntent({self.exchange}:{self.symbol} "
            f"{self.side.value} {self.order_type.value} {detail})"
        )
