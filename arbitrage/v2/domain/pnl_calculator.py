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

from typing import Any, Literal, Tuple, Union, Optional, Dict
from decimal import Decimal, ROUND_HALF_UP


DECIMAL_QUANTIZE = Decimal("0.00000001")


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(value))


def _ensure_decimal(value: Union[float, Decimal]) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return _to_decimal(value)


def _ensure_decimal_or_zero(value: Optional[Union[float, Decimal]]) -> Decimal:
    if value is None:
        return Decimal("0")
    return _ensure_decimal(value)


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


def _normalize_side(side: str) -> str:
    return side.upper().strip()


def _calculate_gross_decimal(
    entry_side: str,
    exit_side: str,
    entry_price: Union[float, Decimal],
    exit_price: Union[float, Decimal],
    quantity: Union[float, Decimal],
) -> Decimal:
    d_entry_price = _ensure_decimal(entry_price)
    d_exit_price = _ensure_decimal(exit_price)
    d_quantity = _ensure_decimal(quantity)
    entry_side = _normalize_side(entry_side)
    exit_side = _normalize_side(exit_side)

    if entry_side == "BUY" and exit_side == "SELL":
        gross = (d_exit_price - d_entry_price) * d_quantity
    elif entry_side == "SELL" and exit_side == "BUY":
        gross = (d_entry_price - d_exit_price) * d_quantity
    else:
        raise ValueError(
            f"Invalid arbitrage side combination: entry={entry_side}, exit={exit_side}. "
            "Expected (BUY, SELL) or (SELL, BUY)."
        )
    return _quantize(gross)


def _calculate_spread_cost(
    side: str,
    bid: Optional[Union[float, Decimal]],
    ask: Optional[Union[float, Decimal]],
    quantity: Optional[Union[float, Decimal]],
) -> Decimal:
    if bid is None or ask is None or quantity is None:
        return Decimal("0")
    d_bid = _ensure_decimal(bid)
    d_ask = _ensure_decimal(ask)
    d_qty = _ensure_decimal(quantity)
    if d_bid <= 0 or d_ask <= 0 or d_qty <= 0:
        return Decimal("0")

    half_spread = abs(d_ask - d_bid) / Decimal("2")
    if half_spread <= 0:
        return Decimal("0")
    return _quantize(half_spread * d_qty)


def calculate_friction_breakdown(
    total_fee: Union[float, Decimal],
    slippage_cost: Union[float, Decimal],
    latency_cost: Union[float, Decimal],
    partial_penalty: Union[float, Decimal],
    entry_side: str,
    exit_side: str,
    entry_bid: Optional[Union[float, Decimal]] = None,
    entry_ask: Optional[Union[float, Decimal]] = None,
    exit_bid: Optional[Union[float, Decimal]] = None,
    exit_ask: Optional[Union[float, Decimal]] = None,
    entry_qty: Optional[Union[float, Decimal]] = None,
    exit_qty: Optional[Union[float, Decimal]] = None,
    return_decimal: bool = False,
) -> Dict[str, Union[float, Decimal]]:
    d_fee = _ensure_decimal_or_zero(total_fee)
    d_slippage = _ensure_decimal_or_zero(slippage_cost)
    d_latency = _ensure_decimal_or_zero(latency_cost)
    d_partial = _ensure_decimal_or_zero(partial_penalty)

    spread_entry = _calculate_spread_cost(entry_side, entry_bid, entry_ask, entry_qty)
    spread_exit = _calculate_spread_cost(exit_side, exit_bid, exit_ask, exit_qty)
    spread_total = _quantize(spread_entry + spread_exit)

    exec_cost_total = _quantize(d_fee + d_slippage + d_latency + d_partial + spread_total)

    breakdown: Dict[str, Union[float, Decimal]] = {
        "fee_total": _quantize(d_fee),
        "slippage_cost": _quantize(d_slippage),
        "latency_cost": _quantize(d_latency),
        "partial_fill_penalty": _quantize(d_partial),
        "spread_cost": spread_total,
        "exec_cost_total": exec_cost_total,
    }

    if return_decimal:
        return breakdown

    return {key: float(value) for key, value in breakdown.items()}


def _slippage_cost_from_result(result: Any) -> Decimal:
    if not result:
        return Decimal("0")
    ref_price = getattr(result, "ref_price", None)
    filled_qty = getattr(result, "filled_qty", None)
    if ref_price is None or filled_qty is None:
        return Decimal("0")

    d_ref = _ensure_decimal_or_zero(ref_price)
    d_qty = _ensure_decimal_or_zero(filled_qty)
    if d_ref <= 0 or d_qty <= 0:
        return Decimal("0")

    slippage_bps = getattr(result, "slippage_bps", None)
    if slippage_bps is None:
        filled_price = getattr(result, "filled_price", None)
        if filled_price is None:
            return Decimal("0")
        diff = abs(_ensure_decimal(filled_price) - d_ref)
        return _quantize(diff * d_qty)

    slippage_ratio = abs(_ensure_decimal(slippage_bps)) / Decimal("10000")
    return _quantize(abs(d_ref) * slippage_ratio * d_qty)


def _latency_cost_from_result(result: Any) -> Decimal:
    if not result:
        return Decimal("0")
    ref_price = getattr(result, "ref_price", None)
    filled_qty = getattr(result, "filled_qty", None)
    if ref_price is None or filled_qty is None:
        return Decimal("0")

    drift_bps = getattr(result, "pessimistic_drift_bps", None)
    if drift_bps is None:
        return Decimal("0")

    d_ref = _ensure_decimal_or_zero(ref_price)
    d_qty = _ensure_decimal_or_zero(filled_qty)
    if d_ref <= 0 or d_qty <= 0:
        return Decimal("0")

    slippage_bps = getattr(result, "slippage_bps", 0.0) or 0.0
    slippage_ratio = abs(_ensure_decimal(slippage_bps)) / Decimal("10000")
    drift_ratio = abs(_ensure_decimal(drift_bps)) / Decimal("10000")
    return _quantize(abs(d_ref * (Decimal("1") + slippage_ratio) * drift_ratio * d_qty))


def _latency_ms_from_result(result: Any) -> float:
    if not result:
        return 0.0
    latency_ms = getattr(result, "latency_ms", None)
    if latency_ms is None:
        return 0.0
    try:
        return float(latency_ms)
    except (TypeError, ValueError):
        return 0.0


def _partial_penalty_from_results(entry_result: Any, exit_result: Any) -> Decimal:
    if not entry_result or not exit_result:
        return Decimal("0")

    entry_qty = getattr(entry_result, "filled_qty", None)
    exit_qty = getattr(exit_result, "filled_qty", None)
    if entry_qty is None or exit_qty is None:
        return Decimal("0")

    qty_diff = abs(_ensure_decimal_or_zero(entry_qty) - _ensure_decimal_or_zero(exit_qty))
    if qty_diff <= 0:
        return Decimal("0")

    base_price = getattr(exit_result, "ref_price", None)
    if base_price is None:
        base_price = getattr(exit_result, "filled_price", None)
    if base_price is None:
        base_price = getattr(entry_result, "ref_price", None)
    if base_price is None:
        base_price = getattr(entry_result, "filled_price", None)
    if base_price is None:
        return Decimal("0")

    return _quantize(abs(_ensure_decimal(base_price)) * qty_diff)


def _reject_count_from_result(result: Any) -> float:
    if not result:
        return 0.0
    return 1.0 if getattr(result, "reject_flag", False) else 0.0


def calculate_execution_friction_from_results(
    entry_result: Any,
    exit_result: Any,
    return_decimal: bool = False,
) -> Dict[str, Union[float, Decimal]]:
    """
    Single welding-truth API for execution-result friction decomposition.

    This function is the only allowed place to derive friction totals from
    OrderResult-like objects (fee/slippage/latency/partial/reject).
    """
    fee_total = _quantize(
        _ensure_decimal_or_zero(getattr(entry_result, "fee", None))
        + _ensure_decimal_or_zero(getattr(exit_result, "fee", None))
    )
    slippage_cost = _quantize(
        _slippage_cost_from_result(entry_result) + _slippage_cost_from_result(exit_result)
    )
    latency_cost = _quantize(
        _latency_cost_from_result(entry_result) + _latency_cost_from_result(exit_result)
    )
    partial_penalty = _quantize(_partial_penalty_from_results(entry_result, exit_result))
    latency_total_ms = _latency_ms_from_result(entry_result) + _latency_ms_from_result(exit_result)
    reject_count = _reject_count_from_result(entry_result) + _reject_count_from_result(exit_result)

    payload: Dict[str, Union[float, Decimal]] = {
        "total_fee": fee_total,
        "slippage_cost": slippage_cost,
        "latency_cost": latency_cost,
        "partial_fill_penalty": partial_penalty,
        "latency_total_ms": float(latency_total_ms),
        "reject_count": float(reject_count),
    }

    if return_decimal:
        return payload

    return {
        "total_fee": float(fee_total),
        "slippage_cost": float(slippage_cost),
        "latency_cost": float(latency_cost),
        "partial_fill_penalty": float(partial_penalty),
        "latency_total_ms": float(latency_total_ms),
        "reject_count": float(reject_count),
    }


def calculate_net_pnl_full_welded(
    entry_side: Literal["BUY", "SELL"],
    exit_side: Literal["BUY", "SELL"],
    entry_price: Union[float, Decimal],
    exit_price: Union[float, Decimal],
    entry_qty: Optional[Union[float, Decimal]],
    exit_qty: Optional[Union[float, Decimal]],
    total_fee: Union[float, Decimal],
    slippage_cost: Union[float, Decimal],
    latency_cost: Union[float, Decimal],
    partial_penalty: Union[float, Decimal],
    entry_bid: Optional[Union[float, Decimal]] = None,
    entry_ask: Optional[Union[float, Decimal]] = None,
    exit_bid: Optional[Union[float, Decimal]] = None,
    exit_ask: Optional[Union[float, Decimal]] = None,
    return_decimal: bool = False,
) -> Dict[str, Union[float, Decimal]]:
    qty = entry_qty if entry_qty is not None and float(entry_qty) > 0 else exit_qty
    if qty is None:
        qty = 0.0

    gross = _calculate_gross_decimal(entry_side, exit_side, entry_price, exit_price, qty)
    realized = _quantize(gross - _ensure_decimal_or_zero(total_fee))

    friction = calculate_friction_breakdown(
        total_fee=total_fee,
        slippage_cost=slippage_cost,
        latency_cost=latency_cost,
        partial_penalty=partial_penalty,
        entry_side=entry_side,
        exit_side=exit_side,
        entry_bid=entry_bid,
        entry_ask=entry_ask,
        exit_bid=exit_bid,
        exit_ask=exit_ask,
        entry_qty=entry_qty,
        exit_qty=exit_qty,
        return_decimal=True,
    )
    exec_cost_total = friction["exec_cost_total"]
    net_pnl_full = _quantize(gross - exec_cost_total)

    payload: Dict[str, Union[float, Decimal]] = {
        "gross_pnl": gross,
        "realized_pnl": realized,
        "net_pnl_full": net_pnl_full,
        "exec_cost_total": exec_cost_total,
        "fee_total": friction["fee_total"],
        "slippage_cost": friction["slippage_cost"],
        "latency_cost": friction["latency_cost"],
        "partial_fill_penalty": friction["partial_fill_penalty"],
        "spread_cost": friction["spread_cost"],
    }

    if return_decimal:
        return payload

    return {key: float(value) for key, value in payload.items()}


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
