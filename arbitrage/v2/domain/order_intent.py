"""
D205-18-4: OrderIntent (복원)

Purpose: 주문 의도 표현
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    """주문 방향"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class OrderIntent:
    """주문 의도"""
    symbol: str
    side: OrderSide
    quantity: float
    price: Optional[float] = None
    order_type: str = "MARKET"
    
    def __post_init__(self):
        if isinstance(self.side, str):
            self.side = OrderSide(self.side)
