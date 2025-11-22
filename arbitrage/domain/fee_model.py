"""
D75-4: Fee Model

거래소별 수수료 구조:
- Maker/Taker fee
- VIP tier
- 수수료 영향도 계산
"""

from dataclasses import dataclass
from typing import Literal

FeeType = Literal["maker", "taker"]


@dataclass
class FeeStructure:
    """거래소 수수료 구조"""
    exchange_name: str
    maker_fee_bps: float  # Maker 수수료 (basis points)
    taker_fee_bps: float  # Taker 수수료 (basis points)
    vip_tier: int = 0  # VIP 등급 (0 = 일반)
    
    def get_fee_bps(self, fee_type: FeeType) -> float:
        """수수료 조회"""
        if fee_type == "maker":
            return self.maker_fee_bps
        else:
            return self.taker_fee_bps
    
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
    
    def total_entry_fee_bps(self) -> float:
        """진입 시 총 수수료 (A + B)"""
        return self.fee_a.taker_fee_bps + self.fee_b.taker_fee_bps
    
    def total_exit_fee_bps(self) -> float:
        """청산 시 총 수수료 (A + B)"""
        return self.fee_a.taker_fee_bps + self.fee_b.taker_fee_bps
    
    def total_round_trip_bps(self) -> float:
        """왕복 거래 총 수수료"""
        return self.total_entry_fee_bps() + self.total_exit_fee_bps()
    
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

UPBIT_FEE = FeeStructure(
    exchange_name="UPBIT",
    maker_fee_bps=5.0,  # 0.05%
    taker_fee_bps=5.0,  # 0.05%
)

BINANCE_FEE = FeeStructure(
    exchange_name="BINANCE",
    maker_fee_bps=10.0,  # 0.10%
    taker_fee_bps=10.0,  # 0.10%
)

BINANCE_VIP1_FEE = FeeStructure(
    exchange_name="BINANCE",
    maker_fee_bps=9.0,   # 0.09%
    taker_fee_bps=9.0,   # 0.09%
    vip_tier=1,
)


def create_fee_model_upbit_binance(vip_tier: int = 0) -> FeeModel:
    """Upbit-Binance 수수료 모델 생성"""
    binance_fee = BINANCE_VIP1_FEE if vip_tier >= 1 else BINANCE_FEE
    return FeeModel(fee_a=UPBIT_FEE, fee_b=binance_fee)
