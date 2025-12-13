# -*- coding: utf-8 -*-
"""
D92-6: Per-Leg PnL SSOT (Single Source of Truth)

체결 단가 기반(per-leg) realized PnL 정산.

핵심 원칙:
- Long leg: (sell_exit - buy_entry) * qty - fees - slippage
- Short leg: (sell_entry - buy_exit) * qty - fees - slippage
- Total = long + short
- Spread-diff는 표시용으로만 격하 (SSOT 아님)

Author: arbitrage-lite project
Date: 2025-12-14
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@dataclass
class LegFill:
    """
    한쪽 거래소 체결 정보
    
    Attributes:
        exchange: 거래소 이름 ("upbit", "binance")
        side: 주문 방향 ("buy", "sell")
        price: 체결 가격
        quantity: 체결 수량
        fee_bps: 수수료 (basis points, 예: 5 = 0.05%)
        slippage_bps: 슬리피지 (basis points, 예: 2 = 0.02%)
    """
    exchange: str
    side: str  # "buy" or "sell"
    price: float
    quantity: float
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    
    def get_fee_amount(self) -> float:
        """수수료 절대값 계산"""
        notional = self.price * self.quantity
        return notional * (self.fee_bps / 10000.0)
    
    def get_slippage_amount(self) -> float:
        """슬리피지 절대값 계산"""
        notional = self.price * self.quantity
        return notional * (self.slippage_bps / 10000.0)


@dataclass
class RoundTripPnL:
    """
    Round Trip PnL 결과
    
    Attributes:
        long_leg_pnl: Long leg PnL (USD)
        short_leg_pnl: Short leg PnL (USD)
        total_realized_pnl: 총 realized PnL (USD)
        fees_total: 총 수수료 (USD)
        slippage_total: 총 슬리피지 (USD)
        entry_prices: Entry 가격 요약 {"upbit": price, "binance": price}
        exit_prices: Exit 가격 요약 {"upbit": price, "binance": price}
        spread_diff_bps: Spread 변화 (표시용, SSOT 아님)
    """
    long_leg_pnl: float
    short_leg_pnl: float
    total_realized_pnl: float
    fees_total: float
    slippage_total: float
    entry_prices: Dict[str, float]
    exit_prices: Dict[str, float]
    spread_diff_bps: float = 0.0  # 표시용만


class PerLegPnLCalculator:
    """
    Per-Leg Realized PnL 계산기
    
    체결 단가 기반으로 realized PnL을 정산.
    """
    
    def __init__(self):
        """초기화"""
        pass
    
    def calculate_round_trip_pnl(
        self,
        entry_long: LegFill,
        entry_short: LegFill,
        exit_long: LegFill,
        exit_short: LegFill,
    ) -> RoundTripPnL:
        """
        Round Trip PnL 계산
        
        Arbitrage 구조:
        - Long leg: buy at entry_long.price, sell at exit_long.price
        - Short leg: sell at entry_short.price, buy at exit_short.price
        
        Args:
            entry_long: Entry Long leg (buy)
            entry_short: Entry Short leg (sell)
            exit_long: Exit Long leg (sell)
            exit_short: Exit Short leg (buy)
        
        Returns:
            RoundTripPnL
        """
        # Long leg PnL: (sell_exit - buy_entry) * qty - fees - slippage
        long_gross = (exit_long.price - entry_long.price) * entry_long.quantity
        long_fees = entry_long.get_fee_amount() + exit_long.get_fee_amount()
        long_slippage = entry_long.get_slippage_amount() + exit_long.get_slippage_amount()
        long_pnl = long_gross - long_fees - long_slippage
        
        # Short leg PnL: (sell_entry - buy_exit) * qty - fees - slippage
        short_gross = (entry_short.price - exit_short.price) * entry_short.quantity
        short_fees = entry_short.get_fee_amount() + exit_short.get_fee_amount()
        short_slippage = entry_short.get_slippage_amount() + exit_short.get_slippage_amount()
        short_pnl = short_gross - short_fees - short_slippage
        
        # Total
        total_pnl = long_pnl + short_pnl
        total_fees = long_fees + short_fees
        total_slippage = long_slippage + short_slippage
        
        # Entry/Exit 가격 요약
        entry_prices = {
            entry_long.exchange: entry_long.price,
            entry_short.exchange: entry_short.price,
        }
        exit_prices = {
            exit_long.exchange: exit_long.price,
            exit_short.exchange: exit_short.price,
        }
        
        # Spread diff (표시용)
        entry_spread = (entry_long.price - entry_short.price) / entry_long.price * 10000
        exit_spread = (exit_long.price - exit_short.price) / exit_long.price * 10000
        spread_diff = exit_spread - entry_spread
        
        logger.info(
            f"[D92-6_PNL] Round Trip: "
            f"long={long_pnl:.2f} USD, short={short_pnl:.2f} USD, "
            f"total={total_pnl:.2f} USD, fees={total_fees:.2f} USD, "
            f"slippage={total_slippage:.2f} USD"
        )
        
        return RoundTripPnL(
            long_leg_pnl=long_pnl,
            short_leg_pnl=short_pnl,
            total_realized_pnl=total_pnl,
            fees_total=total_fees,
            slippage_total=total_slippage,
            entry_prices=entry_prices,
            exit_prices=exit_prices,
            spread_diff_bps=spread_diff,
        )
    
    def calculate_synthetic_convergence(
        self,
        entry_spread_bps: float,
        exit_spread_bps: float,
        entry_price: float,
        quantity: float,
        fees_bps: float = 9.0,  # Upbit 5 + Binance 4
    ) -> RoundTripPnL:
        """
        Synthetic 수렴 시나리오 (테스트용)
        
        Spread 수렴 시 PnL 계산:
        - Entry spread: Upbit이 Binance보다 높음 (arbitrage 기회)
        - Exit spread: 더 낮아짐 (수렴)
        - Long leg (Upbit): buy entry → sell exit (spread 감소 = 손실)
        - Short leg (Binance): sell entry → buy exit (spread 감소 = 이득)
        
        Args:
            entry_spread_bps: Entry spread (bps)
            exit_spread_bps: Exit spread (bps)
            entry_price: Entry 기준 가격
            quantity: 수량
            fees_bps: 총 수수료 (bps)
        
        Returns:
            RoundTripPnL
        """
        # Spread 변화 (bps → 비율)
        spread_change_bps = exit_spread_bps - entry_spread_bps
        spread_change_ratio = spread_change_bps / 10000.0
        
        # Long leg (Upbit): buy at entry_price, sell at entry_price * (1 + spread_change_ratio)
        # PnL = (exit_price - entry_price) * qty = entry_price * spread_change_ratio * qty
        long_gross = entry_price * spread_change_ratio * quantity
        
        # Short leg (Binance): sell at entry_price, buy at entry_price * (1 - spread_change_ratio)
        # PnL = (entry_price - exit_price) * qty = entry_price * spread_change_ratio * qty
        # (spread 감소 시 short leg이 이득)
        short_gross = entry_price * spread_change_ratio * quantity
        
        # 총 gross PnL (spread 수렴 이득)
        total_gross = long_gross + short_gross
        
        # Fees
        notional = entry_price * quantity
        total_fees = notional * (fees_bps / 10000.0)
        
        # Total realized PnL
        total_pnl = total_gross - total_fees
        
        # Exit prices (spread 변화 반영)
        exit_price_upbit = entry_price * (1 + spread_change_ratio)
        exit_price_binance = entry_price * (1 - spread_change_ratio)
        
        return RoundTripPnL(
            long_leg_pnl=long_gross - (notional * 0.05 / 10000.0),  # Long leg fees (Upbit 5bps)
            short_leg_pnl=short_gross - (notional * 0.04 / 10000.0),  # Short leg fees (Binance 4bps)
            total_realized_pnl=total_pnl,
            fees_total=total_fees,
            slippage_total=0.0,
            entry_prices={"upbit": entry_price, "binance": entry_price},
            exit_prices={"upbit": exit_price_upbit, "binance": exit_price_binance},
            spread_diff_bps=spread_change_bps,
        )
