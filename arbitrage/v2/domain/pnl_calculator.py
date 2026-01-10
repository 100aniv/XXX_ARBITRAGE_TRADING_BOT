"""
D205-15-6: PnL Calculator (Profit/Loss Calculation)

Engine-Centric 원칙에 따라 PaperRunner에서 추출.
실거래(Live) 수익 계산에도 재사용 가능.

Purpose:
- Arbitrage 방향별 Gross PnL 계산
- Realized PnL 계산 (수수료 차감)
- Win/Loss 판정

Author: arbitrage-lite V2
Date: 2026-01-10
"""

from typing import Literal, Tuple


def calculate_gross_pnl(
    entry_side: Literal["BUY", "SELL"],
    exit_side: Literal["BUY", "SELL"],
    entry_price: float,
    exit_price: float,
    quantity: float
) -> float:
    """
    Arbitrage 방향별 Gross PnL 계산
    
    Args:
        entry_side: Entry 주문 방향
        exit_side: Exit 주문 방향
        entry_price: Entry 체결 가격
        exit_price: Exit 체결 가격
        quantity: 거래 수량
    
    Returns:
        gross_pnl (수수료 차감 전 수익)
    
    Logic:
        - Normal Arbitrage (BUY → SELL): profit = (sell - buy) * qty
        - Reverse Arbitrage (SELL → BUY): profit = (sell - buy) * qty
          (entry=SELL, exit=BUY이므로 entry - exit)
    
    Example:
        >>> calculate_gross_pnl("BUY", "SELL", 100.0, 102.0, 0.1)
        0.2  # (102 - 100) * 0.1
        >>> calculate_gross_pnl("SELL", "BUY", 102.0, 100.0, 0.1)
        0.2  # (102 - 100) * 0.1
    """
    if entry_side == "BUY" and exit_side == "SELL":
        # Normal arbitrage: BUY at entry_price, SELL at exit_price
        # profit = (SELL price - BUY price) * qty
        return (exit_price - entry_price) * quantity
    
    elif entry_side == "SELL" and exit_side == "BUY":
        # Reverse arbitrage: SELL at entry_price, BUY at exit_price
        # profit = (SELL price - BUY price) * qty
        return (entry_price - exit_price) * quantity
    
    else:
        # Unexpected: both BUY or both SELL
        raise ValueError(
            f"Invalid arbitrage side combination: entry={entry_side}, exit={exit_side}. "
            "Expected (BUY, SELL) or (SELL, BUY)."
        )


def calculate_realized_pnl(
    gross_pnl: float,
    total_fee: float
) -> float:
    """
    Realized PnL 계산 (수수료 차감)
    
    Args:
        gross_pnl: Gross PnL (수수료 전)
        total_fee: 총 수수료 (entry + exit)
    
    Returns:
        realized_pnl (순수익)
    
    Example:
        >>> calculate_realized_pnl(0.2, 0.05)
        0.15  # 0.2 - 0.05
    """
    return gross_pnl - total_fee


def is_win(realized_pnl: float) -> bool:
    """
    Win/Loss 판정
    
    Args:
        realized_pnl: 순수익
    
    Returns:
        True if win, False if loss
    
    Example:
        >>> is_win(0.15)
        True
        >>> is_win(-0.05)
        False
    """
    return realized_pnl > 0


def calculate_pnl_summary(
    entry_side: Literal["BUY", "SELL"],
    exit_side: Literal["BUY", "SELL"],
    entry_price: float,
    exit_price: float,
    quantity: float,
    total_fee: float
) -> Tuple[float, float, bool]:
    """
    PnL 계산 전체 (Gross, Realized, Win 판정)
    
    Args:
        entry_side: Entry 주문 방향
        exit_side: Exit 주문 방향
        entry_price: Entry 체결 가격
        exit_price: Exit 체결 가격
        quantity: 거래 수량
        total_fee: 총 수수료
    
    Returns:
        (gross_pnl, realized_pnl, is_win)
    
    Example:
        >>> calculate_pnl_summary("BUY", "SELL", 100.0, 102.0, 0.1, 0.05)
        (0.2, 0.15, True)
    """
    gross_pnl = calculate_gross_pnl(entry_side, exit_side, entry_price, exit_price, quantity)
    realized_pnl = calculate_realized_pnl(gross_pnl, total_fee)
    win = is_win(realized_pnl)
    
    return gross_pnl, realized_pnl, win
