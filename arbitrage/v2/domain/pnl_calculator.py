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

from typing import Literal, Tuple, Union
from decimal import Decimal, ROUND_HALF_UP


DECIMAL_QUANTIZE = Decimal("0.00000001")


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _ensure_decimal(value: Union[float, Decimal]) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return _to_decimal(value)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(DECIMAL_QUANTIZE, rounding=ROUND_HALF_UP)


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
    d_entry_price = _to_decimal(entry_price)
    d_exit_price = _to_decimal(exit_price)
    d_quantity = _to_decimal(quantity)

    if entry_side == "BUY" and exit_side == "SELL":
        # Normal arbitrage: BUY at entry_price, SELL at exit_price
        # profit = (SELL price - BUY price) * qty
        gross = (d_exit_price - d_entry_price) * d_quantity
        return float(_quantize(gross))
    
    elif entry_side == "SELL" and exit_side == "BUY":
        # Reverse arbitrage: SELL at entry_price, BUY at exit_price
        # profit = (SELL price - BUY price) * qty
        gross = (d_entry_price - d_exit_price) * d_quantity
        return float(_quantize(gross))
    
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
    realized = _to_decimal(gross_pnl) - _to_decimal(total_fee)
    return float(_quantize(realized))


def calculate_net_pnl_full(
    gross_pnl: Union[float, Decimal],
    total_fee: Union[float, Decimal],
    slippage_cost: Union[float, Decimal],
    latency_cost: Union[float, Decimal],
    partial_penalty: Union[float, Decimal],
    return_decimal: bool = False
) -> Tuple[Union[float, Decimal], Union[float, Decimal]]:
    """
    net_pnl_full 계산 (SSOT)

    Formula:
        net_pnl_full = gross_pnl - (fees + slippage + latency + partial_fill_penalty)

    Returns:
        (net_pnl_full, exec_cost_total)
    """
    d_gross = _ensure_decimal(gross_pnl)
    d_fee = _ensure_decimal(total_fee)
    d_slippage = _ensure_decimal(slippage_cost)
    d_latency = _ensure_decimal(latency_cost)
    d_partial = _ensure_decimal(partial_penalty)

    exec_cost_total = d_fee + d_slippage + d_latency + d_partial
    net_pnl_full = d_gross - exec_cost_total

    net_pnl_full_q = _quantize(net_pnl_full)
    exec_cost_total_q = _quantize(exec_cost_total)

    if return_decimal:
        return net_pnl_full_q, exec_cost_total_q

    return float(net_pnl_full_q), float(exec_cost_total_q)


def is_win(realized_pnl: Union[float, Decimal]) -> bool:
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
    if isinstance(realized_pnl, Decimal):
        return realized_pnl > Decimal("0")
    return realized_pnl > 0


def calculate_pnl_summary(
    entry_side: Literal["BUY", "SELL"],
    exit_side: Literal["BUY", "SELL"],
    entry_price: float,
    exit_price: float,
    quantity: float,
    total_fee: float,
    return_decimal: bool = False
) -> Tuple[Union[float, Decimal], Union[float, Decimal], bool]:
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
    d_entry_price = _to_decimal(entry_price)
    d_exit_price = _to_decimal(exit_price)
    d_quantity = _to_decimal(quantity)

    if entry_side == "BUY" and exit_side == "SELL":
        d_gross = (d_exit_price - d_entry_price) * d_quantity
    elif entry_side == "SELL" and exit_side == "BUY":
        d_gross = (d_entry_price - d_exit_price) * d_quantity
    else:
        raise ValueError(
            f"Invalid arbitrage side combination: entry={entry_side}, exit={exit_side}. "
            "Expected (BUY, SELL) or (SELL, BUY)."
        )

    d_realized = d_gross - _to_decimal(total_fee)
    win = is_win(d_realized)

    if return_decimal:
        return _quantize(d_gross), _quantize(d_realized), win

    return float(_quantize(d_gross)), float(_quantize(d_realized)), win
