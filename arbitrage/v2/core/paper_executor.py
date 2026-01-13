from typing import Dict, Optional
import logging

from arbitrage.v2.core import OrderIntent, OrderSide
from arbitrage.v2.adapters import MockAdapter

logger = logging.getLogger(__name__)


class PaperExecutor:
    """Paper 주문 실행 + Balance 관리"""
    
    def __init__(self, initial_balance: Optional[Dict[str, float]] = None):
        self.adapter = MockAdapter(enable_slippage=False)
        self.balance = initial_balance or {
            "KRW": 10_000_000.0,
            "USDT": 10_000.0,
            "BTC": 0.1,
            "ETH": 1.0,
        }
    
    def execute(self, intent: OrderIntent, ref_price: Optional[float] = None):
        """주문 실행 (MockAdapter)"""
        payload = self.adapter.translate_intent(intent)
        if ref_price:
            payload["ref_price"] = ref_price
        response = self.adapter.submit_order(payload)
        order_result = self.adapter.parse_response(response)
        self._update_balance(intent, order_result)
        return order_result
    
    def _update_balance(self, intent: OrderIntent, order_result):
        """Balance 업데이트"""
        if intent.side == OrderSide.BUY:
            if intent.exchange == "upbit":
                self.balance["KRW"] -= (order_result.filled_qty or 0.01) * (order_result.filled_price or 50_000_000.0)
                self.balance["BTC"] += (order_result.filled_qty or 0.01)
            else:
                self.balance["USDT"] -= (order_result.filled_qty or 0.01) * (order_result.filled_price or 40_000.0)
                self.balance["BTC"] += (order_result.filled_qty or 0.01)
        else:
            if intent.exchange == "upbit":
                self.balance["BTC"] -= (intent.base_qty or 0.01)
                self.balance["KRW"] += (order_result.filled_qty or 0.01) * (order_result.filled_price or 50_000_000.0)
            else:
                self.balance["BTC"] -= (intent.base_qty or 0.01)
                self.balance["USDT"] += (order_result.filled_qty or 0.01) * (order_result.filled_price or 40_000.0)
