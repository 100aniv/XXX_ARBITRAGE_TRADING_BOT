"""
D205-15-6: Trade Processor (OrderIntent → Trade Result)

Engine-Centric 원칙에 따라 PaperRunner에서 추출.
실거래(Live) Trade 처리에도 재사용 가능.

Purpose:
- OrderIntent 2개 (entry + exit) → Trade 결과 계산
- Fill 시뮬레이션 (execution risk 적용)
- Fee 계산
- PnL 계산
- Trade 결과 반환 (DB 저장/KPI 업데이트는 Runner 담당)

Author: arbitrage-lite V2
Date: 2026-01-10
"""

from dataclasses import dataclass
from typing import Tuple
from arbitrage.v2.core import OrderIntent
from arbitrage.v2.opportunity import BreakEvenParams
from arbitrage.v2.domain.fill_model import apply_execution_risk, calculate_fee
from arbitrage.v2.domain.pnl_calculator import calculate_pnl_summary


@dataclass
class TradeResult:
    """
    Trade 처리 결과
    
    Runner는 이 결과를 받아서 DB 저장 + KPI 업데이트만 수행.
    """
    # Entry
    entry_qty: float
    entry_price: float
    entry_fee: float
    entry_fee_currency: str
    
    # Exit
    exit_qty: float
    exit_price: float
    exit_fee: float
    exit_fee_currency: str
    
    # PnL
    total_fee: float
    gross_pnl: float
    realized_pnl: float
    is_win: bool


class TradeProcessor:
    """
    Trade 처리기 (Engine-Centric)
    
    OrderIntent 2개 → TradeResult 계산
    """
    
    def __init__(self, break_even_params: BreakEvenParams):
        """
        Args:
            break_even_params: 수수료, 슬리피지, 레이턴시 등 파라미터
        """
        self.break_even_params = break_even_params
    
    def process_intents(
        self,
        entry_intent: OrderIntent,
        exit_intent: OrderIntent,
        entry_result,
        exit_result
    ) -> TradeResult:
        """
        OrderIntent 2개 → TradeResult 계산
        
        Args:
            entry_intent: Entry OrderIntent
            exit_intent: Exit OrderIntent
            entry_result: Entry 체결 결과 (MockOrderResult)
            exit_result: Exit 체결 결과 (MockOrderResult)
        
        Returns:
            TradeResult (가격, 수량, 수수료, PnL)
        
        Raises:
            ValueError: 유효하지 않은 arbitrage 방향 (BUY/BUY or SELL/SELL)
        """
        # D205-15-6a: Fail-fast - filled data 필수 (마법 상수 제거)
        entry_qty = entry_result.filled_qty or entry_intent.base_qty
        if not entry_qty or entry_qty <= 0:
            raise ValueError(
                f"TradeProcessor: entry_qty missing or invalid. "
                f"filled_qty={entry_result.filled_qty}, intent.base_qty={entry_intent.base_qty}"
            )
        
        entry_base_price = entry_result.filled_price or entry_intent.limit_price
        if not entry_base_price or entry_base_price <= 0:
            raise ValueError(
                f"TradeProcessor: entry_base_price missing or invalid. "
                f"filled_price={entry_result.filled_price}, intent.limit_price={entry_intent.limit_price}. "
                f"Ensure MockAdapter sets ref_price or intent has limit_price."
            )
        
        # Entry 체결 가격 (execution risk 적용)
        entry_price = apply_execution_risk(
            entry_base_price,
            entry_intent.side.value.upper(),
            self.break_even_params
        )
        
        # Entry 수수료
        entry_fee_bps = (
            self.break_even_params.fee_model.fee_a.taker_fee_bps
            if entry_intent.exchange == "upbit"
            else self.break_even_params.fee_model.fee_b.taker_fee_bps
        )
        entry_fee = calculate_fee(entry_price, entry_qty, entry_fee_bps)
        entry_fee_currency = "KRW" if "KRW" in entry_intent.symbol else "USDT"
        
        # D205-15-6a: Fail-fast - exit filled data 필수
        exit_qty = exit_result.filled_qty or exit_intent.base_qty
        if not exit_qty or exit_qty <= 0:
            raise ValueError(
                f"TradeProcessor: exit_qty missing or invalid. "
                f"filled_qty={exit_result.filled_qty}, intent.base_qty={exit_intent.base_qty}"
            )
        
        exit_base_price = exit_result.filled_price or exit_intent.limit_price
        if not exit_base_price or exit_base_price <= 0:
            raise ValueError(
                f"TradeProcessor: exit_base_price missing or invalid. "
                f"filled_price={exit_result.filled_price}, intent.limit_price={exit_intent.limit_price}. "
                f"Ensure MockAdapter sets ref_price or intent has limit_price."
            )
        
        # Exit 체결 가격 (execution risk 적용)
        exit_price = apply_execution_risk(
            exit_base_price,
            exit_intent.side.value.upper(),
            self.break_even_params
        )
        
        # Exit 수수료
        exit_fee_bps = (
            self.break_even_params.fee_model.fee_a.taker_fee_bps
            if exit_intent.exchange == "upbit"
            else self.break_even_params.fee_model.fee_b.taker_fee_bps
        )
        exit_fee = calculate_fee(exit_price, exit_qty, exit_fee_bps)
        exit_fee_currency = "KRW" if "KRW" in exit_intent.symbol else "USDT"
        
        # D205-15-6b: 수량 정합성 검증 (entry_qty ≠ exit_qty → PnL 왜곡 방지)
        qty_diff_pct = abs(entry_qty - exit_qty) / entry_qty * 100 if entry_qty > 0 else 0
        if qty_diff_pct > 1.0:
            # 1% 이상 차이 → FAIL-fast (계약 위반)
            raise ValueError(
                f"[D205-15-6b] TradeProcessor: entry_qty and exit_qty mismatch. "
                f"entry_qty={entry_qty}, exit_qty={exit_qty}, diff={qty_diff_pct:.2f}%. "
                f"MockAdapter contract violation: MARKET BUY must use quote_amount/filled_price."
            )
        
        # 보수적 계산: matched_qty = min(entry_qty, exit_qty)
        matched_qty = min(entry_qty, exit_qty)
        
        # 총 수수료 (matched_qty 기준 재계산)
        entry_fee_matched = calculate_fee(entry_price, matched_qty, entry_fee_bps)
        exit_fee_matched = calculate_fee(exit_price, matched_qty, exit_fee_bps)
        total_fee = entry_fee_matched + exit_fee_matched
        
        # PnL 계산 (gross, realized, win 판정) - matched_qty 기준
        gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
            entry_intent.side.value.upper(),
            exit_intent.side.value.upper(),
            entry_price,
            exit_price,
            matched_qty,
            total_fee
        )
        
        return TradeResult(
            entry_qty=entry_qty,
            entry_price=entry_price,
            entry_fee=entry_fee,
            entry_fee_currency=entry_fee_currency,
            exit_qty=exit_qty,
            exit_price=exit_price,
            exit_fee=exit_fee,
            exit_fee_currency=exit_fee_currency,
            total_fee=total_fee,
            gross_pnl=gross_pnl,
            realized_pnl=realized_pnl,
            is_win=is_win
        )
