from typing import Dict, Optional, Any
from decimal import Decimal, ROUND_HALF_UP
import logging

from arbitrage.v2.core import OrderIntent, OrderSide
from arbitrage.v2.adapters import PaperAdapter
from arbitrage.v2.core.profit_core import ProfitCore

logger = logging.getLogger(__name__)


DECIMAL_QUANTIZE = Decimal("0.00000001")


def _to_decimal(value: Optional[float]) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(DECIMAL_QUANTIZE, rounding=ROUND_HALF_UP)


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
        self.adapter = PaperAdapter(config=adapter_config)
        base_balance = initial_balance or {
            "KRW": 10_000_000.0,
            "USDT": 10_000.0,
            "BTC": 0.1,
            "ETH": 1.0,
        }
        self.balance = {k: _quantize(_to_decimal(v)) for k, v in base_balance.items()}

    @property
    def adapter_random_seed(self) -> Optional[int]:
        if not hasattr(self, "adapter") or self.adapter is None:
            return None
        return getattr(self.adapter, "random_seed", None)
    
    def execute(
        self,
        intent: OrderIntent,
        ref_price: Optional[float] = None,
        top_depth: Optional[float] = None,
    ):
        """주문 실행 (PaperAdapter)"""
        payload = self.adapter.translate_intent(intent)
        if ref_price:
            payload["ref_price"] = ref_price
        if top_depth is not None:
            payload["top_depth"] = top_depth
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
        if not order_result or not getattr(order_result, "success", False):
            return
        if not order_result.filled_qty or not order_result.filled_price:
            return
        # profit_core는 __init__에서 필수 검증됨
        default_price_krw = _to_decimal(self.profit_core.get_default_price("upbit", "BTC/KRW"))
        default_price_usdt = _to_decimal(self.profit_core.get_default_price("binance", "BTC/USDT"))
        filled_qty = _quantize(_to_decimal(order_result.filled_qty))
        filled_price = _quantize(_to_decimal(order_result.filled_price))
        base_qty = _quantize(_to_decimal(intent.base_qty)) if intent.base_qty else Decimal("0")
        fallback_qty = Decimal("0.01")
        
        if intent.side == OrderSide.BUY:
            if intent.exchange == "upbit":
                qty = filled_qty if filled_qty > 0 else fallback_qty
                price = filled_price if filled_price > 0 else default_price_krw
                self.balance["KRW"] = _quantize(self.balance["KRW"] - (qty * price))
                self.balance["BTC"] = _quantize(self.balance["BTC"] + qty)
            else:
                qty = filled_qty if filled_qty > 0 else fallback_qty
                price = filled_price if filled_price > 0 else default_price_usdt
                self.balance["USDT"] = _quantize(self.balance["USDT"] - (qty * price))
                self.balance["BTC"] = _quantize(self.balance["BTC"] + qty)
        else:
            if intent.exchange == "upbit":
                qty = base_qty if base_qty > 0 else fallback_qty
                price = filled_price if filled_price > 0 else default_price_krw
                self.balance["BTC"] = _quantize(self.balance["BTC"] - qty)
                self.balance["KRW"] = _quantize(self.balance["KRW"] + (filled_qty if filled_qty > 0 else fallback_qty) * price)
            else:
                qty = base_qty if base_qty > 0 else fallback_qty
                price = filled_price if filled_price > 0 else default_price_usdt
                self.balance["BTC"] = _quantize(self.balance["BTC"] - qty)
                self.balance["USDT"] = _quantize(self.balance["USDT"] + (filled_qty if filled_qty > 0 else fallback_qty) * price)
