# -*- coding: utf-8 -*-
"""
D79-2: Cross-Exchange Strategy

Upbit ↔ Binance 교차 거래소 아비트라지 Entry/Exit 전략.

Features:
- Entry: Spread-based positive/negative direction
- Exit: TP/SL/Time-based/Spread reversal
- Integration with D75 RiskGuard
- D78 Secrets Layer validation
"""

import logging
import time
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CrossExchangeAction(str, Enum):
    """교차 거래소 액션"""
    ENTRY_POSITIVE = "entry_positive"  # Upbit SELL / Binance BUY
    ENTRY_NEGATIVE = "entry_negative"  # Upbit BUY / Binance SELL
    EXIT_TP = "exit_tp"  # Take Profit
    EXIT_SL = "exit_sl"  # Stop Loss
    EXIT_TIMEOUT = "exit_timeout"  # Time-based exit
    EXIT_REVERSAL = "exit_reversal"  # Spread reversal
    EXIT_HEALTH = "exit_health"  # Exchange health degradation
    NO_ACTION = "no_action"


@dataclass
class CrossExchangeSignal:
    """
    교차 거래소 신호
    """
    action: CrossExchangeAction
    symbol_mapping: any  # SymbolMapping
    cross_spread: any  # CrossSpread
    reason: str  # 신호 발생 이유
    timestamp: float
    
    # Entry-specific
    entry_side: Optional[str] = None  # "positive" or "negative"
    
    # Exit-specific
    exit_pnl: Optional[float] = None  # 예상 PnL (KRW)
    exit_spread_change: Optional[float] = None  # Spread 변화 (%)


class CrossExchangeStrategy:
    """
    교차 거래소 아비트라지 전략
    
    Entry Logic:
    - POSITIVE spread (Upbit > Binance):
      → Upbit SELL / Binance BUY
    - NEGATIVE spread (Upbit < Binance):
      → Upbit BUY / Binance SELL
    
    Entry Conditions:
    - abs(spread_percent) >= min_spread_percent
    - FX confidence >= min_fx_confidence
    - Liquidity >= Universe standards
    - D75 RateLimiter / HealthCheck OK
    - D78 Secrets available
    
    Exit Logic:
    - TP: Spread reversal (profit realized)
    - SL: Spread worsening
    - Time-based: Max holding time
    - Health: Exchange degradation
    
    Example:
        strategy = CrossExchangeStrategy(
            min_spread_percent=0.5,
            tp_spread_percent=0.2,
            sl_spread_percent=-0.3,
            max_holding_seconds=3600,
        )
        
        # Entry signal
        signal = strategy.evaluate_entry(
            symbol_mapping=mapping,
            cross_spread=spread,
            fx_confidence=1.0,
            health_ok=True,
            secrets_available=True,
        )
        
        # Exit signal
        exit_signal = strategy.evaluate_exit(
            position=position,
            current_spread=current_spread,
        )
    """
    
    def __init__(
        self,
        min_spread_percent: float = 0.5,
        min_fx_confidence: float = 0.8,
        tp_spread_percent: float = 0.2,  # TP threshold (spread reversal)
        sl_spread_percent: float = -0.3,  # SL threshold (spread worsening)
        max_holding_seconds: float = 3600.0,  # 1 hour
        min_liquidity_krw: float = 100_000_000.0,  # 100M KRW
    ):
        """
        Initialize CrossExchangeStrategy
        
        Args:
            min_spread_percent: 최소 entry spread (%)
            min_fx_confidence: 최소 FX confidence
            tp_spread_percent: TP threshold (%)
            sl_spread_percent: SL threshold (%)
            max_holding_seconds: 최대 보유 시간 (초)
            min_liquidity_krw: 최소 유동성 (KRW)
        """
        self.min_spread_percent = min_spread_percent
        self.min_fx_confidence = min_fx_confidence
        self.tp_spread_percent = tp_spread_percent
        self.sl_spread_percent = sl_spread_percent
        self.max_holding_seconds = max_holding_seconds
        self.min_liquidity_krw = min_liquidity_krw
        
        logger.info(
            f"[CROSS_STRATEGY] Initialized: "
            f"min_spread={min_spread_percent}%, "
            f"tp={tp_spread_percent}%, "
            f"sl={sl_spread_percent}%, "
            f"max_holding={max_holding_seconds}s"
        )
    
    def evaluate_entry(
        self,
        symbol_mapping: any,
        cross_spread: any,
        fx_confidence: float,
        health_ok: bool,
        secrets_available: bool,
        liquidity_krw: Optional[float] = None,
    ) -> CrossExchangeSignal:
        """
        Entry 신호 평가
        
        Args:
            symbol_mapping: SymbolMapping
            cross_spread: CrossSpread
            fx_confidence: FX confidence (0.0 ~ 1.0)
            health_ok: Exchange health OK
            secrets_available: API keys available (from D78)
            liquidity_krw: 유동성 (KRW)
        
        Returns:
            CrossExchangeSignal (action=ENTRY_* or NO_ACTION)
        """
        # 1. Secrets validation (D78)
        if not secrets_available:
            return self._no_action_signal(
                symbol_mapping, cross_spread, "Secrets not available (D78)"
            )
        
        # 2. Health check (D75)
        if not health_ok:
            return self._no_action_signal(
                symbol_mapping, cross_spread, "Exchange health degraded (D75)"
            )
        
        # 3. FX confidence check
        if fx_confidence < self.min_fx_confidence:
            return self._no_action_signal(
                symbol_mapping, cross_spread,
                f"FX confidence too low ({fx_confidence:.2f} < {self.min_fx_confidence})"
            )
        
        # 4. Liquidity check
        if liquidity_krw is not None and liquidity_krw < self.min_liquidity_krw:
            return self._no_action_signal(
                symbol_mapping, cross_spread,
                f"Liquidity too low ({liquidity_krw:,.0f} < {self.min_liquidity_krw:,.0f})"
            )
        
        # 5. Spread check
        if not cross_spread.is_profitable(min_spread_percent=self.min_spread_percent):
            return self._no_action_signal(
                symbol_mapping, cross_spread,
                f"Spread too low ({cross_spread.spread_percent:.2f}% < {self.min_spread_percent}%)"
            )
        
        # 6. Determine action based on spread direction
        from .spread_model import SpreadDirection
        
        if cross_spread.direction == SpreadDirection.POSITIVE:
            # Upbit > Binance → SELL Upbit / BUY Binance
            return CrossExchangeSignal(
                action=CrossExchangeAction.ENTRY_POSITIVE,
                symbol_mapping=symbol_mapping,
                cross_spread=cross_spread,
                reason=f"Positive spread {cross_spread.spread_percent:.2f}%",
                timestamp=time.time(),
                entry_side="positive",
            )
        
        elif cross_spread.direction == SpreadDirection.NEGATIVE:
            # Upbit < Binance → BUY Upbit / SELL Binance
            return CrossExchangeSignal(
                action=CrossExchangeAction.ENTRY_NEGATIVE,
                symbol_mapping=symbol_mapping,
                cross_spread=cross_spread,
                reason=f"Negative spread {cross_spread.spread_percent:.2f}%",
                timestamp=time.time(),
                entry_side="negative",
            )
        
        else:
            # NEUTRAL
            return self._no_action_signal(
                symbol_mapping, cross_spread, "Spread direction neutral"
            )
    
    def evaluate_exit(
        self,
        position: Dict,
        current_spread: any,
        health_ok: bool = True,
    ) -> CrossExchangeSignal:
        """
        Exit 신호 평가
        
        Args:
            position: Position dict from PositionManager
            current_spread: 현재 CrossSpread
            health_ok: Exchange health OK
        
        Returns:
            CrossExchangeSignal (action=EXIT_* or NO_ACTION)
        """
        # 1. Health check (emergency exit)
        if not health_ok:
            return self._exit_signal(
                position=position,
                current_spread=current_spread,
                action=CrossExchangeAction.EXIT_HEALTH,
                reason="Exchange health degraded",
            )
        
        # 2. Time-based exit
        holding_time = time.time() - position.get("entry_timestamp", time.time())
        if holding_time > self.max_holding_seconds:
            return self._exit_signal(
                position=position,
                current_spread=current_spread,
                action=CrossExchangeAction.EXIT_TIMEOUT,
                reason=f"Max holding time exceeded ({holding_time:.0f}s > {self.max_holding_seconds}s)",
            )
        
        # 3. Spread-based exit
        entry_spread_percent = position.get("entry_spread_percent", 0.0)
        current_spread_percent = current_spread.spread_percent
        spread_change = current_spread_percent - entry_spread_percent
        entry_side = position.get("entry_side", "positive")
        
        # 3-1. Spread reversal (check first - strong signal)
        if self._is_reversal_condition(entry_side, current_spread_percent):
            return self._exit_signal(
                position=position,
                current_spread=current_spread,
                action=CrossExchangeAction.EXIT_REVERSAL,
                reason=f"Spread reversal ({current_spread_percent:.2f}%)",
            )
        
        # 3-2. Take Profit
        if self._is_tp_condition(entry_side, spread_change):
            return self._exit_signal(
                position=position,
                current_spread=current_spread,
                action=CrossExchangeAction.EXIT_TP,
                reason=f"TP: Spread reversed ({spread_change:+.2f}%)",
            )
        
        # 3-3. Stop Loss
        if self._is_sl_condition(entry_side, spread_change):
            return self._exit_signal(
                position=position,
                current_spread=current_spread,
                action=CrossExchangeAction.EXIT_SL,
                reason=f"SL: Spread worsened ({spread_change:+.2f}%)",
            )
        
        # 4. No exit condition met
        return CrossExchangeSignal(
            action=CrossExchangeAction.NO_ACTION,
            symbol_mapping=position.get("symbol_mapping"),
            cross_spread=current_spread,
            reason="No exit condition met",
            timestamp=time.time(),
        )
    
    def _is_tp_condition(self, entry_side: str, spread_change: float) -> bool:
        """
        TP 조건 확인
        
        Logic:
        - POSITIVE entry (Upbit SELL / Binance BUY):
          → Spread가 작아지면 수익 (spread_change < 0)
        - NEGATIVE entry (Upbit BUY / Binance SELL):
          → Spread가 커지면 수익 (spread_change > 0)
        """
        if entry_side == "positive":
            # Spread 감소 → TP (but must be significant decrease)
            return spread_change <= -abs(self.tp_spread_percent)
        else:  # negative
            # Spread 증가 → TP
            return spread_change >= abs(self.tp_spread_percent)
    
    def _is_sl_condition(self, entry_side: str, spread_change: float) -> bool:
        """
        SL 조건 확인
        
        Logic:
        - POSITIVE entry:
          → Spread가 더 커지면 손실 (spread_change > 0)
        - NEGATIVE entry:
          → Spread가 더 작아지면 손실 (spread_change < 0)
        """
        if entry_side == "positive":
            # Spread 증가 → SL
            return spread_change >= abs(self.sl_spread_percent)
        else:  # negative
            # Spread 감소 → SL
            return spread_change <= self.sl_spread_percent
    
    def _is_reversal_condition(self, entry_side: str, current_spread_percent: float) -> bool:
        """
        Spread reversal 조건 확인
        
        Logic:
        - POSITIVE entry (Upbit > Binance):
          → Spread가 negative로 반전되면 exit
        - NEGATIVE entry (Upbit < Binance):
          → Spread가 positive로 반전되면 exit
        """
        if entry_side == "positive":
            return current_spread_percent < 0
        else:  # negative
            return current_spread_percent > 0
    
    def _no_action_signal(
        self,
        symbol_mapping: any,
        cross_spread: any,
        reason: str,
    ) -> CrossExchangeSignal:
        """NO_ACTION 신호 생성"""
        return CrossExchangeSignal(
            action=CrossExchangeAction.NO_ACTION,
            symbol_mapping=symbol_mapping,
            cross_spread=cross_spread,
            reason=reason,
            timestamp=time.time(),
        )
    
    def _exit_signal(
        self,
        position: Dict,
        current_spread: any,
        action: CrossExchangeAction,
        reason: str,
    ) -> CrossExchangeSignal:
        """Exit 신호 생성"""
        entry_spread_percent = position.get("entry_spread_percent", 0.0)
        current_spread_percent = current_spread.spread_percent
        spread_change = current_spread_percent - entry_spread_percent
        
        # PnL 추정 (간단 계산)
        # 실제로는 entry/exit 가격, 수량, 수수료 등을 고려해야 함
        exit_pnl = spread_change * 1000000.0  # Placeholder (1M KRW base)
        
        return CrossExchangeSignal(
            action=action,
            symbol_mapping=position.get("symbol_mapping"),
            cross_spread=current_spread,
            reason=reason,
            timestamp=time.time(),
            exit_pnl=exit_pnl,
            exit_spread_change=spread_change,
        )
    
    def get_config(self) -> Dict:
        """전략 설정 반환"""
        return {
            "min_spread_percent": self.min_spread_percent,
            "min_fx_confidence": self.min_fx_confidence,
            "tp_spread_percent": self.tp_spread_percent,
            "sl_spread_percent": self.sl_spread_percent,
            "max_holding_seconds": self.max_holding_seconds,
            "min_liquidity_krw": self.min_liquidity_krw,
        }
