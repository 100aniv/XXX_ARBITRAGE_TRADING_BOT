"""
D75-4: Fee Model

거래소별 수수료 구조:
- Maker/Taker fee
- VIP tier
- 수수료 영향도 계산
"""

from dataclasses import dataclass
from typing import Literal
from decimal import Decimal, ROUND_HALF_UP

FeeType = Literal["maker", "taker"]
OrderType = Literal["maker", "taker"]


@dataclass
class FeeStructure:
    """거래소 수수료 구조"""
    exchange_name: str
    maker_fee_bps: float  # Maker 수수료 (basis points)
    taker_fee_bps: float  # Taker 수수료 (basis points)
    vip_tier: int = 0  # VIP 등급 (0 = 일반)
    
    def get_fee_bps(self, fee_type: FeeType) -> float:
        """수수료 조회 (float, backward compat)"""
        if fee_type == "maker":
            return self.maker_fee_bps
        else:
            return self.taker_fee_bps
    
    def get_fee_bps_decimal(self, fee_type: FeeType) -> Decimal:
        """수수료 조회 (Decimal, 18자리 정밀도)"""
        if fee_type == "maker":
            return Decimal(str(self.maker_fee_bps))
        else:
            return Decimal(str(self.taker_fee_bps))
    
    def total_round_trip_bps(self) -> float:
        """왕복 거래 총 수수료 (진입 + 청산)"""
        return self.taker_fee_bps * 2


@dataclass
class FeeModel:
    """
    두 거래소 간 수수료 모델.
    
    Arbitrage는 항상 양쪽 거래소에서 동시에 taker로 진입하므로
    taker fee만 고려.
    """
    fee_a: FeeStructure
    fee_b: FeeStructure
    
    def total_entry_fee_bps(self, entry_type_a: OrderType = "taker", entry_type_b: OrderType = "taker") -> float:
        """진입 시 총 수수료 (A + B)"""
        fee_a = self.fee_a.maker_fee_bps if entry_type_a == "maker" else self.fee_a.taker_fee_bps
        fee_b = self.fee_b.maker_fee_bps if entry_type_b == "maker" else self.fee_b.taker_fee_bps
        return fee_a + fee_b
    
    def total_exit_fee_bps(self, exit_type_a: OrderType = "taker", exit_type_b: OrderType = "taker") -> float:
        """청산 시 총 수수료 (A + B)"""
        fee_a = self.fee_a.maker_fee_bps if exit_type_a == "maker" else self.fee_a.taker_fee_bps
        fee_b = self.fee_b.maker_fee_bps if exit_type_b == "maker" else self.fee_b.taker_fee_bps
        return fee_a + fee_b
    
    def total_round_trip_bps(
        self,
        entry_type_a: OrderType = "taker",
        entry_type_b: OrderType = "taker",
        exit_type_a: OrderType = "taker",
        exit_type_b: OrderType = "taker"
    ) -> float:
        """왕복 거래 총 수수료"""
        return self.total_entry_fee_bps(entry_type_a, entry_type_b) + self.total_exit_fee_bps(exit_type_a, exit_type_b)
    
    def calculate_maker_taker_fee_bps(
        self,
        entry_type_a: OrderType = "maker",
        entry_type_b: OrderType = "taker",
        exit_type_a: OrderType = "taker",
        exit_type_b: OrderType = "taker"
    ) -> Decimal:
        """
        D_ALPHA-1: Maker-Taker 하이브리드 수수료 계산 (Decimal 정밀도)
        
        Args:
            entry_type_a: Exchange A 진입 주문 타입 (maker or taker)
            entry_type_b: Exchange B 진입 주문 타입 (maker or taker)
            exit_type_a: Exchange A 청산 주문 타입 (maker or taker)
            exit_type_b: Exchange B 청산 주문 타입 (maker or taker)
        
        Returns:
            총 수수료 (bps, Decimal 18자리)
        
        Note:
            Maker fee가 음수(rebate)일 경우 총 비용 감소
            예: Upbit maker=-5.0 (0.05% rebate) → 총 비용 감소
        """
        entry_fee_a = self.fee_a.get_fee_bps_decimal(entry_type_a)
        entry_fee_b = self.fee_b.get_fee_bps_decimal(entry_type_b)
        exit_fee_a = self.fee_a.get_fee_bps_decimal(exit_type_a)
        exit_fee_b = self.fee_b.get_fee_bps_decimal(exit_type_b)
        
        total_fee = entry_fee_a + entry_fee_b + exit_fee_a + exit_fee_b
        return total_fee.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
    
    def fee_impact_on_spread(self, spread_bps: float) -> float:
        """
        Spread에서 수수료가 차지하는 비율.
        
        Returns:
            0.0 ~ 1.0 (0% ~ 100%)
        """
        if spread_bps <= 0:
            return 1.0  # Spread가 음수면 수수료 영향 100%
        
        total_fee = self.total_entry_fee_bps()
        return min(1.0, total_fee / spread_bps)
    
    def net_spread_after_fee(self, gross_spread_bps: float) -> float:
        """수수료 차감 후 순 spread"""
        return gross_spread_bps - self.total_entry_fee_bps()


# ================================================
# Preset Fee Structures
# ================================================

# D_ALPHA-1: Maker rebate 반영 (negative fee)
UPBIT_FEE = FeeStructure(
    exchange_name="UPBIT",
    maker_fee_bps=-5.0,  # -0.05% (rebate)
    taker_fee_bps=5.0,   # 0.05%
)

BINANCE_FEE = FeeStructure(
    exchange_name="BINANCE",
    maker_fee_bps=2.0,   # 0.02% (reduced from 10.0)
    taker_fee_bps=10.0,  # 0.10%
)

BINANCE_VIP1_FEE = FeeStructure(
    exchange_name="BINANCE",
    maker_fee_bps=0.0,   # 0.00% (VIP1 maker fee waived)
    taker_fee_bps=9.0,   # 0.09%
    vip_tier=1,
)


def create_fee_model_upbit_binance(vip_tier: int = 0) -> FeeModel:
    """Upbit-Binance 수수료 모델 생성"""
    binance_fee = BINANCE_VIP1_FEE if vip_tier >= 1 else BINANCE_FEE
    return FeeModel(fee_a=UPBIT_FEE, fee_b=binance_fee)
