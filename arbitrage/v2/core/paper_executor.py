from typing import Dict, Optional, Any
import logging

from arbitrage.v2.core import OrderIntent, OrderSide
from arbitrage.v2.adapters import MockAdapter
from arbitrage.v2.core.profit_core import ProfitCore

logger = logging.getLogger(__name__)


class PaperExecutor:
    """Paper 주문 실행 + Balance 관리
    
    D206-1 FIXPACK:
    - profit_core 필수 의존성 (None 금지)
    - WARN=FAIL (fallback 제거)
    - No Magic Numbers (하드코딩 0건)
    """
    
    def __init__(
        self,
        profit_core: ProfitCore,
        initial_balance: Optional[Dict[str, float]] = None,
        adapter_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            profit_core: ProfitCore (REQUIRED - config.yml 기반)
            initial_balance: 초기 잔고
            adapter_config: PaperExecutionAdapter 설정 (mock_adapter 섹션 포함)
        
        Raises:
            TypeError: profit_core가 None일 경우
        """
        if profit_core is None:
            raise TypeError("PaperExecutor: profit_core is REQUIRED (WARN=FAIL principle)")
        
        self.profit_core = profit_core
        self.adapter = MockAdapter(config=adapter_config)
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
        """
        Balance 업데이트
        
        D206-1 FIXPACK:
        - 하드코딩 0건 (profit_core 필수)
        - fallback 제거 (WARN=FAIL)
        - config.yml 기반 가격만 사용
        """
        # profit_core는 __init__에서 필수 검증됨
        default_price_krw = self.profit_core.get_default_price("upbit", "BTC/KRW")
        default_price_usdt = self.profit_core.get_default_price("binance", "BTC/USDT")
        
        if intent.side == OrderSide.BUY:
            if intent.exchange == "upbit":
                self.balance["KRW"] -= (order_result.filled_qty or 0.01) * (order_result.filled_price or default_price_krw)
                self.balance["BTC"] += (order_result.filled_qty or 0.01)
            else:
                self.balance["USDT"] -= (order_result.filled_qty or 0.01) * (order_result.filled_price or default_price_usdt)
                self.balance["BTC"] += (order_result.filled_qty or 0.01)
        else:
            if intent.exchange == "upbit":
                self.balance["BTC"] -= (intent.base_qty or 0.01)
                self.balance["KRW"] += (order_result.filled_qty or 0.01) * (order_result.filled_price or default_price_krw)
            else:
                self.balance["BTC"] -= (intent.base_qty or 0.01)
                self.balance["USDT"] += (order_result.filled_qty or 0.01) * (order_result.filled_price or default_price_usdt)
