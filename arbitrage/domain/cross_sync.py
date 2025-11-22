"""
D75-4: Cross-Exchange Sync

Cross-exchange position/inventory 동기화:
- Inventory tracking (A/B 잔고 추적)
- Exposure 계산 (절대량 & 비율)
- Rebalance 필요성 판단 (execution 아님)
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class Inventory:
    """거래소별 inventory"""
    exchange_name: str
    base_balance: float  # Base asset (e.g., BTC)
    quote_balance: float  # Quote asset (e.g., KRW, USDT)
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def total_value_in_quote(self, base_price: float) -> float:
        """
        총 자산 가치 (quote 기준).
        
        Args:
            base_price: Base asset 가격 (quote 단위)
        
        Returns:
            Total value in quote currency
        """
        return self.base_balance * base_price + self.quote_balance
    
    def base_ratio(self, base_price: float) -> float:
        """
        Base asset 비율.
        
        Returns:
            0.0 ~ 1.0 (0% ~ 100%)
        """
        total_value = self.total_value_in_quote(base_price)
        if total_value == 0.0:
            return 0.0
        return (self.base_balance * base_price) / total_value


@dataclass
class RebalanceSignal:
    """Rebalance 신호"""
    needed: bool
    reason: str
    imbalance_ratio: float  # -1.0 ~ 1.0
    exposure_risk: float  # 0.0 ~ 1.0
    recommended_action: str  # "BUY_A_SELL_B", "BUY_B_SELL_A", "NONE"
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class InventoryTracker:
    """
    Cross-exchange inventory tracker.
    
    두 거래소 간 잔고/포지션 차이를 추적하고
    rebalance 필요성을 판단.
    """
    
    def __init__(
        self,
        imbalance_threshold: float = 0.3,  # ±30% 이상 불균형 시 rebalance
        exposure_threshold: float = 0.8,   # 80% 이상 한쪽 집중 시 위험
    ):
        """
        Args:
            imbalance_threshold: Imbalance ratio threshold for rebalance
            exposure_threshold: Exposure ratio threshold for risk warning
        """
        self.imbalance_threshold = imbalance_threshold
        self.exposure_threshold = exposure_threshold
        
        # Inventory state
        self._inventory_a: Optional[Inventory] = None
        self._inventory_b: Optional[Inventory] = None
    
    def update_inventory(
        self,
        inventory_a: Inventory,
        inventory_b: Inventory,
    ) -> None:
        """Inventory 업데이트"""
        self._inventory_a = inventory_a
        self._inventory_b = inventory_b
    
    def calculate_imbalance(
        self,
        base_price_a: float,
        base_price_b: float,
    ) -> float:
        """
        Inventory imbalance ratio 계산.
        
        Formula:
        imbalance = (value_a - value_b) / (value_a + value_b)
        
        Args:
            base_price_a: Base asset price in exchange A (quote A)
            base_price_b: Base asset price in exchange B (quote B)
        
        Returns:
            -1.0 ~ 1.0
            양수: A가 많음, 음수: B가 많음
        """
        if self._inventory_a is None or self._inventory_b is None:
            return 0.0
        
        value_a = self._inventory_a.total_value_in_quote(base_price_a)
        value_b = self._inventory_b.total_value_in_quote(base_price_b)
        
        total_value = value_a + value_b
        if total_value == 0.0:
            return 0.0
        
        return (value_a - value_b) / total_value
    
    def calculate_exposure_risk(
        self,
        base_price_a: float,
        base_price_b: float,
    ) -> float:
        """
        Exposure risk 계산.
        
        한쪽 거래소에 자산이 집중되면 위험도 증가.
        
        Returns:
            0.0 ~ 1.0 (낮을수록 안전)
        """
        imbalance = abs(self.calculate_imbalance(base_price_a, base_price_b))
        
        # Imbalance가 클수록 exposure risk 증가
        if imbalance > self.exposure_threshold:
            return 1.0
        return imbalance / self.exposure_threshold
    
    def check_rebalance_needed(
        self,
        base_price_a: float,
        base_price_b: float,
    ) -> RebalanceSignal:
        """
        Rebalance 필요성 판단.
        
        Args:
            base_price_a: Base asset price in exchange A
            base_price_b: Base asset price in exchange B
        
        Returns:
            RebalanceSignal
        """
        imbalance = self.calculate_imbalance(base_price_a, base_price_b)
        exposure_risk = self.calculate_exposure_risk(base_price_a, base_price_b)
        
        # Rebalance 필요성 판단
        if abs(imbalance) > self.imbalance_threshold:
            if imbalance > 0:
                # A가 많음 → A 줄이고 B 늘리기
                return RebalanceSignal(
                    needed=True,
                    reason=f"Imbalance too high: {imbalance:.2%} (A > B)",
                    imbalance_ratio=imbalance,
                    exposure_risk=exposure_risk,
                    recommended_action="BUY_B_SELL_A",
                )
            else:
                # B가 많음 → B 줄이고 A 늘리기
                return RebalanceSignal(
                    needed=True,
                    reason=f"Imbalance too high: {imbalance:.2%} (B > A)",
                    imbalance_ratio=imbalance,
                    exposure_risk=exposure_risk,
                    recommended_action="BUY_A_SELL_B",
                )
        
        # Rebalance 불필요
        return RebalanceSignal(
            needed=False,
            reason=f"Balanced: {imbalance:.2%}",
            imbalance_ratio=imbalance,
            exposure_risk=exposure_risk,
            recommended_action="NONE",
        )
    
    def get_inventory_state(self) -> Tuple[Optional[Inventory], Optional[Inventory]]:
        """현재 inventory 상태 반환"""
        return self._inventory_a, self._inventory_b
    
    def get_imbalance_for_symbol(
        self,
        symbol_a: str,
        symbol_b: str,
        base_price_a: float,
        base_price_b: float,
    ) -> float:
        """
        특정 symbol에 대한 imbalance ratio 반환.
        
        Universe provider에서 사용.
        """
        return self.calculate_imbalance(base_price_a, base_price_b)
