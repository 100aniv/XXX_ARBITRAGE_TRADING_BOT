"""
D77-0: Exit Strategy

Entry → Exit 완전한 arbitrage cycle 구현:
- Take Profit (TP)
- Stop Loss (SL)
- Time-based Exit
- Spread Reversal Exit

D64 Trade Lifecycle Fix 기반 확장.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class ExitReason(Enum):
    """Exit 사유"""
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TIME_LIMIT = "time_limit"
    SPREAD_REVERSAL = "spread_reversal"
    NONE = "none"


@dataclass
class ExitConfig:
    """Exit 설정"""
    # D95-2: Δspread 기준 TP/SL (arbitrage 전용)
    take_profit_delta_bps: float = -3.0  # Spread 3bps 축소 시 TP
    stop_loss_delta_bps: float = 5.0     # Spread 5bps 확대 시 SL
    
    # 기존 PnL% 기준 (fallback/호환성)
    tp_threshold_pct: float = 1.0  # 1% TP
    sl_threshold_pct: float = 0.5  # 0.5% SL
    
    max_hold_time_seconds: float = 180.0  # 3 minutes
    spread_reversal_threshold_bps: float = -10.0  # -10 bps (spread turned negative)
    
    def __post_init__(self):
        """D92-6: TP/SL 기본값 검증 (0이면 에러)"""
        if self.tp_threshold_pct == 0:
            raise ValueError(
                "[D92-6_EXIT] TP threshold cannot be 0 (意図しない 'TP off' 방지). "
                "Set a positive value or use a different exit condition."
            )
        if self.sl_threshold_pct == 0:
            raise ValueError(
                "[D92-6_EXIT] SL threshold cannot be 0 (意図しない 'SL off' 방지). "
                "Set a positive value or use a different exit condition."
            )


@dataclass
class PositionState:
    """Position 상태"""
    position_id: int
    symbol_a: str
    symbol_b: str
    open_time: float
    entry_price_a: float
    entry_price_b: float
    entry_spread_bps: float
    size: float
    
    # D95-2: Trajectory 추적
    min_spread_bps: float = float('inf')
    max_spread_bps: float = float('-inf')
    last_spread_bps: float = 0.0
    
    def time_held(self) -> float:
        """Position hold time (seconds)"""
        return time.time() - self.open_time


@dataclass
class ExitDecision:
    """Exit 판단"""
    should_exit: bool
    reason: ExitReason
    current_pnl_pct: float = 0.0
    current_spread_bps: float = 0.0
    time_held_seconds: float = 0.0
    message: str = ""


class ExitStrategy:
    """
    Exit Strategy Manager.
    
    TP/SL/Time-based/Spread reversal 조건 체크.
    
    D92-6: Exit 평가 카운트 추가 (DecisionTrace 유사)
    """
    
    def __init__(self, config: ExitConfig):
        """
        Args:
            config: Exit 설정
        """
        self.config = config
        
        # Position tracking
        self._positions: Dict[int, PositionState] = {}
        
        # D92-6: Exit 평가 카운트
        self.exit_eval_counts = {
            "tp_hit": 0,
            "sl_hit": 0,
            "time_limit_hit": 0,
            "none": 0,
        }
    
    def register_position(
        self,
        position_id: int,
        symbol_a: str,
        symbol_b: str,
        entry_price_a: float,
        entry_price_b: float,
        entry_spread_bps: float,
        size: float,
    ) -> None:
        """
        Position 등록 (Entry 시점).
        
        Args:
            position_id: Position ID
            symbol_a: Symbol A
            symbol_b: Symbol B
            entry_price_a: Entry price A
            entry_price_b: Entry price B
            entry_spread_bps: Entry spread (bps)
            size: Position size
        """
        self._positions[position_id] = PositionState(
            position_id=position_id,
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            open_time=time.time(),
            entry_price_a=entry_price_a,
            entry_price_b=entry_price_b,
            entry_spread_bps=entry_spread_bps,
            size=size,
        )
    
    def check_exit(
        self,
        position_id: int,
        current_price_a: float,
        current_price_b: float,
        current_spread_bps: float,
    ) -> ExitDecision:
        """
        Exit 조건 체크.
        
        Args:
            position_id: Position ID
            current_price_a: 현재 price A
            current_price_b: 현재 price B
            current_spread_bps: 현재 spread (bps)
        
        Returns:
            ExitDecision
        """
        position = self._positions.get(position_id)
        if position is None:
            return ExitDecision(
                should_exit=False,
                reason=ExitReason.NONE,
                message="Position not found",
            )
        
        # Calculate PnL%
        current_pnl_pct = self._calculate_pnl_percent(
            position,
            current_price_a,
            current_price_b,
        )
        
        time_held = position.time_held()
        
        # D95-2: Trajectory 업데이트
        delta_spread_bps = current_spread_bps - position.entry_spread_bps
        position.last_spread_bps = current_spread_bps
        position.min_spread_bps = min(position.min_spread_bps, current_spread_bps)
        position.max_spread_bps = max(position.max_spread_bps, current_spread_bps)
        
        # 1a. Take Profit (Δspread 기준 - 우선 체크)
        if delta_spread_bps <= self.config.take_profit_delta_bps:
            self.exit_eval_counts["tp_hit"] += 1
            return ExitDecision(
                should_exit=True,
                reason=ExitReason.TAKE_PROFIT,
                current_pnl_pct=current_pnl_pct,
                current_spread_bps=current_spread_bps,
                time_held_seconds=time_held,
                message=f"TP_DELTA: Δspread {delta_spread_bps:.2f} bps <= {self.config.take_profit_delta_bps:.2f} bps",
            )
        
        # 1b. Take Profit (PnL% 기준 - fallback)
        if current_pnl_pct >= self.config.tp_threshold_pct:
            self.exit_eval_counts["tp_hit"] += 1
            return ExitDecision(
                should_exit=True,
                reason=ExitReason.TAKE_PROFIT,
                current_pnl_pct=current_pnl_pct,
                current_spread_bps=current_spread_bps,
                time_held_seconds=time_held,
                message=f"TP: PnL {current_pnl_pct:.2f}% >= {self.config.tp_threshold_pct:.2f}%",
            )
        
        # 2a. Stop Loss (Δspread 기준 - 우선 체크)
        if delta_spread_bps >= self.config.stop_loss_delta_bps:
            self.exit_eval_counts["sl_hit"] += 1
            return ExitDecision(
                should_exit=True,
                reason=ExitReason.STOP_LOSS,
                current_pnl_pct=current_pnl_pct,
                current_spread_bps=current_spread_bps,
                time_held_seconds=time_held,
                message=f"SL_DELTA: Δspread {delta_spread_bps:.2f} bps >= {self.config.stop_loss_delta_bps:.2f} bps",
            )
        
        # 2b. Stop Loss (PnL% 기준 - fallback)
        if current_pnl_pct <= -self.config.sl_threshold_pct:
            self.exit_eval_counts["sl_hit"] += 1
            return ExitDecision(
                should_exit=True,
                reason=ExitReason.STOP_LOSS,
                current_pnl_pct=current_pnl_pct,
                current_spread_bps=current_spread_bps,
                time_held_seconds=time_held,
                message=f"SL: PnL {current_pnl_pct:.2f}% <= -{self.config.sl_threshold_pct:.2f}%",
            )
        
        # 3. Time Limit
        if time_held >= self.config.max_hold_time_seconds:
            self.exit_eval_counts["time_limit_hit"] += 1
            return ExitDecision(
                should_exit=True,
                reason=ExitReason.TIME_LIMIT,
                current_pnl_pct=current_pnl_pct,
                current_spread_bps=current_spread_bps,
                time_held_seconds=time_held,
                message=f"TIME: {time_held:.1f}s >= {self.config.max_hold_time_seconds:.1f}s",
            )
        
        # 4. Spread Reversal
        if current_spread_bps < self.config.spread_reversal_threshold_bps:
            return ExitDecision(
                should_exit=True,
                reason=ExitReason.SPREAD_REVERSAL,
                current_pnl_pct=current_pnl_pct,
                current_spread_bps=current_spread_bps,
                time_held_seconds=time_held,
                message=f"SPREAD_REV: {current_spread_bps:.1f} bps < {self.config.spread_reversal_threshold_bps:.1f} bps",
            )
        
        # Hold position
        self.exit_eval_counts["none"] += 1
        return ExitDecision(
            should_exit=False,
            reason=ExitReason.NONE,
            current_pnl_pct=current_pnl_pct,
            current_spread_bps=current_spread_bps,
            time_held_seconds=time_held,
            message="HOLD",
        )
    
    def unregister_position(self, position_id: int) -> None:
        """
        Position 제거 (Exit 완료 시).
        
        Args:
            position_id: Position ID
        """
        self._positions.pop(position_id, None)
    
    def get_open_positions(self) -> Dict[int, PositionState]:
        """
        열린 position 목록.
        
        Returns:
            {position_id: PositionState}
        """
        return dict(self._positions)
    
    def get_position_count(self) -> int:
        """
        열린 position 개수.
        
        Returns:
            Position count
        """
        return len(self._positions)
    
    def _calculate_pnl_percent(
        self,
        position: PositionState,
        current_price_a: float,
        current_price_b: float,
    ) -> float:
        """
        PnL% 계산 (simplified).
        
        Arbitrage PnL:
        - Buy A at entry_price_a, Sell B at entry_price_b
        - Now: Sell A at current_price_a, Buy B at current_price_b
        - PnL = (current_price_a - entry_price_a) - (current_price_b - entry_price_b)
        - PnL% = PnL / entry_price_a * 100
        
        Args:
            position: Position state
            current_price_a: 현재 price A
            current_price_b: 현재 price B
        
        Returns:
            PnL% (can be negative)
        """
        # Simplified: assume 1:1 position size ratio
        pnl_a = current_price_a - position.entry_price_a
        pnl_b = -(current_price_b - position.entry_price_b)  # Sold B at entry, buy back now
        
        total_pnl = pnl_a + pnl_b
        
        # PnL% relative to entry_price_a
        if position.entry_price_a == 0:
            return 0.0
        
        pnl_pct = (total_pnl / position.entry_price_a) * 100.0
        
        return pnl_pct
