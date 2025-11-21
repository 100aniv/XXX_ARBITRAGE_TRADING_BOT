# -*- coding: utf-8 -*-
"""
D73-3: Multi-Symbol RiskGuard Implementation

3-Tier Risk Management Architecture:
- GlobalGuard: Portfolio-level limits (total exposure, daily loss)
- PortfolioGuard: Symbol allocation and portfolio balance
- SymbolGuard: Per-symbol limits (position size, cooldown, circuit breaker)

Redis Keyspace (D72-2 규격 준수):
- {ns}:{env}:{run_id}:risk:global:state
- {ns}:{env}:{run_id}:risk:portfolio:state
- {ns}:{env}:{run_id}:risk:symbol:{symbol}:state
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# ============================================================================
# Risk Guard Decision
# ============================================================================

class RiskGuardDecision(Enum):
    """RiskGuard 판정 결과"""
    OK = "OK"
    REJECTED_SYMBOL = "REJECTED_SYMBOL"  # Symbol-level rejection
    REJECTED_PORTFOLIO = "REJECTED_PORTFOLIO"  # Portfolio-level rejection
    REJECTED_GLOBAL = "REJECTED_GLOBAL"  # Global-level rejection
    SESSION_STOP = "SESSION_STOP"  # 세션 종료 필요


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class GlobalRiskState:
    """Global Risk 상태"""
    total_exposure_usd: float = 0.0
    total_daily_loss_usd: float = 0.0
    total_trades_executed: int = 0
    total_trades_rejected: int = 0
    session_start_time: float = field(default_factory=time.time)
    emergency_stop_triggered: bool = False


@dataclass
class PortfolioRiskState:
    """Portfolio Risk 상태"""
    symbol_exposures: Dict[str, float] = field(default_factory=dict)  # {symbol: exposure_usd}
    symbol_allocations: Dict[str, float] = field(default_factory=dict)  # {symbol: allocated_capital}
    total_allocated_capital: float = 0.0
    rebalance_count: int = 0


@dataclass
class SymbolRiskState:
    """Symbol-specific Risk 상태"""
    symbol: str = ""
    current_exposure_usd: float = 0.0
    current_position_count: int = 0
    daily_loss_usd: float = 0.0
    trades_executed: int = 0
    trades_rejected: int = 0
    last_entry_time: float = 0.0
    cooldown_until: float = 0.0
    circuit_breaker_triggered: bool = False
    circuit_breaker_until: float = 0.0


# ============================================================================
# Global Guard
# ============================================================================

class GlobalGuard:
    """
    Global Risk Guard (Portfolio-level)
    
    전체 포트폴리오에 대한 리스크 한도를 관리:
    - max_total_exposure: 전체 노출 한도
    - max_daily_loss: 일일 최대 손실
    - emergency_stop_loss: 긴급 중단 손실
    """
    
    def __init__(
        self,
        max_total_exposure_usd: float = 10000.0,
        max_daily_loss_usd: float = 500.0,
        emergency_stop_loss_usd: float = 1000.0,
    ):
        """
        Args:
            max_total_exposure_usd: 전체 최대 노출 (USD)
            max_daily_loss_usd: 일일 최대 손실 (USD)
            emergency_stop_loss_usd: 긴급 중단 손실 (USD)
        """
        self.max_total_exposure_usd = max_total_exposure_usd
        self.max_daily_loss_usd = max_daily_loss_usd
        self.emergency_stop_loss_usd = emergency_stop_loss_usd
        
        self.state = GlobalRiskState()
        
        logger.info(
            f"[D73-3_GLOBAL_GUARD] Initialized: "
            f"max_exposure={max_total_exposure_usd}, "
            f"max_daily_loss={max_daily_loss_usd}, "
            f"emergency_stop={emergency_stop_loss_usd}"
        )
    
    def check_global_limits(
        self,
        additional_exposure_usd: float = 0.0,
    ) -> RiskGuardDecision:
        """
        Global 한도 체크
        
        Args:
            additional_exposure_usd: 추가 노출 금액
        
        Returns:
            RiskGuardDecision
        """
        # 1. Emergency stop 체크
        if self.state.emergency_stop_triggered:
            logger.error("[D73-3_GLOBAL_GUARD] Emergency stop triggered")
            return RiskGuardDecision.SESSION_STOP
        
        if self.state.total_daily_loss_usd >= self.emergency_stop_loss_usd:
            logger.error(
                f"[D73-3_GLOBAL_GUARD] Emergency stop: "
                f"daily_loss={self.state.total_daily_loss_usd} >= {self.emergency_stop_loss_usd}"
            )
            self.state.emergency_stop_triggered = True
            return RiskGuardDecision.SESSION_STOP
        
        # 2. 일일 최대 손실 체크
        if self.state.total_daily_loss_usd >= self.max_daily_loss_usd:
            logger.warning(
                f"[D73-3_GLOBAL_GUARD] Max daily loss reached: "
                f"daily_loss={self.state.total_daily_loss_usd} >= {self.max_daily_loss_usd}"
            )
            return RiskGuardDecision.REJECTED_GLOBAL
        
        # 3. 전체 노출 한도 체크
        new_total_exposure = self.state.total_exposure_usd + additional_exposure_usd
        if new_total_exposure > self.max_total_exposure_usd:
            logger.warning(
                f"[D73-3_GLOBAL_GUARD] Max total exposure exceeded: "
                f"new_exposure={new_total_exposure} > {self.max_total_exposure_usd}"
            )
            return RiskGuardDecision.REJECTED_GLOBAL
        
        return RiskGuardDecision.OK
    
    def update_exposure(self, delta_usd: float) -> None:
        """노출 업데이트 (양수=증가, 음수=감소)"""
        self.state.total_exposure_usd += delta_usd
        logger.debug(
            f"[D73-3_GLOBAL_GUARD] Exposure updated: {self.state.total_exposure_usd:.2f} USD"
        )
    
    def update_daily_loss(self, loss_usd: float) -> None:
        """일일 손실 업데이트 (양수=손실)"""
        if loss_usd > 0:
            self.state.total_daily_loss_usd += loss_usd
            logger.debug(
                f"[D73-3_GLOBAL_GUARD] Daily loss updated: {self.state.total_daily_loss_usd:.2f} USD"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Global Guard 통계"""
        return {
            "total_exposure_usd": self.state.total_exposure_usd,
            "max_total_exposure_usd": self.max_total_exposure_usd,
            "total_daily_loss_usd": self.state.total_daily_loss_usd,
            "max_daily_loss_usd": self.max_daily_loss_usd,
            "trades_executed": self.state.total_trades_executed,
            "trades_rejected": self.state.total_trades_rejected,
            "emergency_stop_triggered": self.state.emergency_stop_triggered,
        }


# ============================================================================
# Portfolio Guard
# ============================================================================

class PortfolioGuard:
    """
    Portfolio Risk Guard
    
    심볼별 자본 할당 및 포트폴리오 밸런스 관리:
    - 심볼별 예산 할당
    - 포트폴리오 리밸런싱
    - 심볼 가중치 기반 자본 분배
    """
    
    def __init__(
        self,
        total_capital_usd: float = 10000.0,
        max_symbol_allocation_pct: float = 0.3,  # 심볼당 최대 30%
    ):
        """
        Args:
            total_capital_usd: 전체 자본
            max_symbol_allocation_pct: 심볼당 최대 할당 비율
        """
        self.total_capital_usd = total_capital_usd
        self.max_symbol_allocation_pct = max_symbol_allocation_pct
        
        self.state = PortfolioRiskState()
        
        logger.info(
            f"[D73-3_PORTFOLIO_GUARD] Initialized: "
            f"total_capital={total_capital_usd}, "
            f"max_symbol_alloc={max_symbol_allocation_pct*100}%"
        )
    
    def allocate_capital(self, symbols: List[str], weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """
        심볼별 자본 할당
        
        Args:
            symbols: 심볼 리스트
            weights: 심볼별 가중치 {symbol: weight} (None이면 균등 분배)
        
        Returns:
            {symbol: allocated_capital}
        """
        if not symbols:
            return {}
        
        # 가중치 없으면 균등 분배
        if weights is None:
            weights = {symbol: 1.0 / len(symbols) for symbol in symbols}
        
        # 가중치 정규화
        total_weight = sum(weights.values())
        normalized_weights = {s: w / total_weight for s, w in weights.items()}
        
        # 심볼별 할당
        allocations = {}
        for symbol in symbols:
            weight = normalized_weights.get(symbol, 0.0)
            allocated = self.total_capital_usd * weight
            
            # 최대 할당 비율 제한
            max_allocated = self.total_capital_usd * self.max_symbol_allocation_pct
            allocated = min(allocated, max_allocated)
            
            allocations[symbol] = allocated
        
        self.state.symbol_allocations = allocations
        self.state.total_allocated_capital = sum(allocations.values())
        self.state.rebalance_count += 1
        
        logger.info(
            f"[D73-3_PORTFOLIO_GUARD] Capital allocated to {len(symbols)} symbols: "
            f"total={self.state.total_allocated_capital:.2f} USD"
        )
        
        return allocations
    
    def check_symbol_allocation(self, symbol: str, additional_exposure_usd: float) -> RiskGuardDecision:
        """
        심볼별 할당 한도 체크
        
        Args:
            symbol: 심볼
            additional_exposure_usd: 추가 노출
        
        Returns:
            RiskGuardDecision
        """
        allocated = self.state.symbol_allocations.get(symbol, 0.0)
        current_exposure = self.state.symbol_exposures.get(symbol, 0.0)
        new_exposure = current_exposure + additional_exposure_usd
        
        if new_exposure > allocated:
            logger.warning(
                f"[D73-3_PORTFOLIO_GUARD] Symbol allocation exceeded for {symbol}: "
                f"new_exposure={new_exposure:.2f} > allocated={allocated:.2f}"
            )
            return RiskGuardDecision.REJECTED_PORTFOLIO
        
        return RiskGuardDecision.OK
    
    def update_symbol_exposure(self, symbol: str, delta_usd: float) -> None:
        """심볼별 노출 업데이트"""
        current = self.state.symbol_exposures.get(symbol, 0.0)
        self.state.symbol_exposures[symbol] = current + delta_usd
        logger.debug(
            f"[D73-3_PORTFOLIO_GUARD] {symbol} exposure updated: {self.state.symbol_exposures[symbol]:.2f} USD"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Portfolio Guard 통계"""
        return {
            "total_capital_usd": self.total_capital_usd,
            "total_allocated_capital": self.state.total_allocated_capital,
            "symbol_allocations": dict(self.state.symbol_allocations),
            "symbol_exposures": dict(self.state.symbol_exposures),
            "rebalance_count": self.state.rebalance_count,
        }


# ============================================================================
# Symbol Guard
# ============================================================================

class SymbolGuard:
    """
    Symbol-specific Risk Guard
    
    개별 심볼에 대한 리스크 한도:
    - max_position_size: 심볼별 최대 포지션 크기
    - max_position_count: 심볼별 최대 포지션 수
    - cooldown_seconds: 진입 후 쿨다운
    - circuit_breaker: 연속 손실 시 자동 차단
    """
    
    def __init__(
        self,
        symbol: str,
        max_position_size_usd: float = 1000.0,
        max_position_count: int = 3,
        cooldown_seconds: float = 60.0,
        max_symbol_daily_loss_usd: float = 200.0,
        circuit_breaker_loss_count: int = 3,  # 연속 3회 손실 시 차단
        circuit_breaker_duration: float = 300.0,  # 5분간 차단
    ):
        """
        Args:
            symbol: 심볼명
            max_position_size_usd: 최대 포지션 크기 (USD)
            max_position_count: 최대 동시 포지션 수
            cooldown_seconds: 쿨다운 시간 (초)
            max_symbol_daily_loss_usd: 심볼별 일일 최대 손실
            circuit_breaker_loss_count: Circuit breaker 발동 손실 횟수
            circuit_breaker_duration: Circuit breaker 지속 시간 (초)
        """
        self.symbol = symbol
        self.max_position_size_usd = max_position_size_usd
        self.max_position_count = max_position_count
        self.cooldown_seconds = cooldown_seconds
        self.max_symbol_daily_loss_usd = max_symbol_daily_loss_usd
        self.circuit_breaker_loss_count = circuit_breaker_loss_count
        self.circuit_breaker_duration = circuit_breaker_duration
        
        self.state = SymbolRiskState(symbol=symbol)
        self._consecutive_losses = 0
        
        logger.info(
            f"[D73-3_SYMBOL_GUARD] {symbol} Initialized: "
            f"max_size={max_position_size_usd}, "
            f"max_count={max_position_count}, "
            f"cooldown={cooldown_seconds}s"
        )
    
    def check_symbol_limits(
        self,
        position_size_usd: float,
    ) -> RiskGuardDecision:
        """
        Symbol 한도 체크
        
        Args:
            position_size_usd: 포지션 크기 (USD)
        
        Returns:
            RiskGuardDecision
        """
        now = time.time()
        
        # 1. Circuit breaker 체크
        if self.state.circuit_breaker_triggered:
            if now < self.state.circuit_breaker_until:
                remaining = self.state.circuit_breaker_until - now
                logger.warning(
                    f"[D73-3_SYMBOL_GUARD] {self.symbol} circuit breaker active "
                    f"(remaining {remaining:.0f}s)"
                )
                return RiskGuardDecision.REJECTED_SYMBOL
            else:
                # Circuit breaker 해제
                self.state.circuit_breaker_triggered = False
                self._consecutive_losses = 0
                logger.info(f"[D73-3_SYMBOL_GUARD] {self.symbol} circuit breaker released")
        
        # 2. Cooldown 체크
        if now < self.state.cooldown_until:
            remaining = self.state.cooldown_until - now
            logger.debug(
                f"[D73-3_SYMBOL_GUARD] {self.symbol} in cooldown (remaining {remaining:.0f}s)"
            )
            return RiskGuardDecision.REJECTED_SYMBOL
        
        # 3. 포지션 크기 체크
        if position_size_usd > self.max_position_size_usd:
            logger.warning(
                f"[D73-3_SYMBOL_GUARD] {self.symbol} position size exceeded: "
                f"{position_size_usd} > {self.max_position_size_usd}"
            )
            return RiskGuardDecision.REJECTED_SYMBOL
        
        # 4. 포지션 수 체크
        if self.state.current_position_count >= self.max_position_count:
            logger.warning(
                f"[D73-3_SYMBOL_GUARD] {self.symbol} max position count reached: "
                f"{self.state.current_position_count} >= {self.max_position_count}"
            )
            return RiskGuardDecision.REJECTED_SYMBOL
        
        # 5. 심볼별 일일 손실 체크
        if self.state.daily_loss_usd >= self.max_symbol_daily_loss_usd:
            logger.warning(
                f"[D73-3_SYMBOL_GUARD] {self.symbol} max daily loss reached: "
                f"{self.state.daily_loss_usd} >= {self.max_symbol_daily_loss_usd}"
            )
            return RiskGuardDecision.REJECTED_SYMBOL
        
        return RiskGuardDecision.OK
    
    def on_entry(self, position_size_usd: float) -> None:
        """진입 시 호출"""
        now = time.time()
        self.state.current_exposure_usd += position_size_usd
        self.state.current_position_count += 1
        self.state.trades_executed += 1
        self.state.last_entry_time = now
        self.state.cooldown_until = now + self.cooldown_seconds
        
        logger.debug(
            f"[D73-3_SYMBOL_GUARD] {self.symbol} entry: "
            f"exposure={self.state.current_exposure_usd:.2f}, "
            f"count={self.state.current_position_count}"
        )
    
    def on_exit(self, pnl_usd: float) -> None:
        """청산 시 호출"""
        self.state.current_position_count = max(0, self.state.current_position_count - 1)
        
        # 손실 처리
        if pnl_usd < 0:
            loss = abs(pnl_usd)
            self.state.daily_loss_usd += loss
            self._consecutive_losses += 1
            
            # Circuit breaker 체크
            if self._consecutive_losses >= self.circuit_breaker_loss_count:
                self.state.circuit_breaker_triggered = True
                self.state.circuit_breaker_until = time.time() + self.circuit_breaker_duration
                logger.warning(
                    f"[D73-3_SYMBOL_GUARD] {self.symbol} circuit breaker triggered "
                    f"(consecutive_losses={self._consecutive_losses})"
                )
        else:
            # 이익이면 연속 손실 카운터 리셋
            self._consecutive_losses = 0
        
        logger.debug(
            f"[D73-3_SYMBOL_GUARD] {self.symbol} exit: "
            f"pnl={pnl_usd:.2f}, "
            f"daily_loss={self.state.daily_loss_usd:.2f}, "
            f"count={self.state.current_position_count}"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Symbol Guard 통계"""
        return {
            "symbol": self.symbol,
            "current_exposure_usd": self.state.current_exposure_usd,
            "current_position_count": self.state.current_position_count,
            "daily_loss_usd": self.state.daily_loss_usd,
            "max_symbol_daily_loss_usd": self.max_symbol_daily_loss_usd,
            "trades_executed": self.state.trades_executed,
            "trades_rejected": self.state.trades_rejected,
            "circuit_breaker_triggered": self.state.circuit_breaker_triggered,
            "consecutive_losses": self._consecutive_losses,
        }


# ============================================================================
# Multi-Symbol Risk Coordinator
# ============================================================================

class MultiSymbolRiskCoordinator:
    """
    Multi-Symbol Risk Coordinator
    
    3-Tier Risk Guard를 조정:
    1. GlobalGuard: 전체 포트폴리오 한도
    2. PortfolioGuard: 심볼별 자본 할당
    3. SymbolGuard: 개별 심볼 리스크
    
    평가 순서 (엄격):
    1. Global check
    2. Portfolio check
    3. Symbol check
    
    하나라도 FAIL이면 거래 차단.
    """
    
    def __init__(
        self,
        global_guard: GlobalGuard,
        portfolio_guard: PortfolioGuard,
        symbols: Optional[List[str]] = None,
        symbol_guard_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            global_guard: GlobalGuard 인스턴스
            portfolio_guard: PortfolioGuard 인스턴스
            symbols: 심볼 리스트
            symbol_guard_config: SymbolGuard 설정 (공통 설정)
        """
        self.global_guard = global_guard
        self.portfolio_guard = portfolio_guard
        
        # Symbol Guards
        self.symbol_guards: Dict[str, SymbolGuard] = {}
        if symbols:
            self._initialize_symbol_guards(symbols, symbol_guard_config or {})
        
        logger.info(
            f"[D73-3_COORDINATOR] Initialized with {len(self.symbol_guards)} symbols"
        )
    
    def _initialize_symbol_guards(self, symbols: List[str], config: Dict[str, Any]) -> None:
        """Symbol Guards 초기화"""
        for symbol in symbols:
            self.symbol_guards[symbol] = SymbolGuard(
                symbol=symbol,
                max_position_size_usd=config.get("max_position_size_usd", 1000.0),
                max_position_count=config.get("max_position_count", 3),
                cooldown_seconds=config.get("cooldown_seconds", 60.0),
                max_symbol_daily_loss_usd=config.get("max_symbol_daily_loss_usd", 200.0),
                circuit_breaker_loss_count=config.get("circuit_breaker_loss_count", 3),
                circuit_breaker_duration=config.get("circuit_breaker_duration", 300.0),
            )
    
    def check_trade_allowed(
        self,
        symbol: str,
        position_size_usd: float,
    ) -> RiskGuardDecision:
        """
        거래 허용 여부 체크 (3-tier 순차 평가)
        
        Args:
            symbol: 심볼
            position_size_usd: 포지션 크기 (USD)
        
        Returns:
            RiskGuardDecision
        """
        # 1. Global Guard 체크
        decision = self.global_guard.check_global_limits(position_size_usd)
        if decision != RiskGuardDecision.OK:
            logger.warning(
                f"[D73-3_COORDINATOR] {symbol} rejected by GlobalGuard: {decision.value}"
            )
            return decision
        
        # 2. Portfolio Guard 체크
        decision = self.portfolio_guard.check_symbol_allocation(symbol, position_size_usd)
        if decision != RiskGuardDecision.OK:
            logger.warning(
                f"[D73-3_COORDINATOR] {symbol} rejected by PortfolioGuard: {decision.value}"
            )
            return decision
        
        # 3. Symbol Guard 체크
        symbol_guard = self.symbol_guards.get(symbol)
        if symbol_guard:
            decision = symbol_guard.check_symbol_limits(position_size_usd)
            if decision != RiskGuardDecision.OK:
                logger.warning(
                    f"[D73-3_COORDINATOR] {symbol} rejected by SymbolGuard: {decision.value}"
                )
                symbol_guard.state.trades_rejected += 1
                return decision
        
        logger.debug(f"[D73-3_COORDINATOR] {symbol} trade allowed (size={position_size_usd:.2f})")
        return RiskGuardDecision.OK
    
    def on_trade_entry(self, symbol: str, position_size_usd: float) -> None:
        """거래 진입 시 호출"""
        # Global update
        self.global_guard.update_exposure(position_size_usd)
        self.global_guard.state.total_trades_executed += 1
        
        # Portfolio update
        self.portfolio_guard.update_symbol_exposure(symbol, position_size_usd)
        
        # Symbol update
        symbol_guard = self.symbol_guards.get(symbol)
        if symbol_guard:
            symbol_guard.on_entry(position_size_usd)
    
    def on_trade_exit(self, symbol: str, position_size_usd: float, pnl_usd: float) -> None:
        """거래 청산 시 호출"""
        # Global update
        self.global_guard.update_exposure(-position_size_usd)
        if pnl_usd < 0:
            self.global_guard.update_daily_loss(abs(pnl_usd))
        
        # Portfolio update
        self.portfolio_guard.update_symbol_exposure(symbol, -position_size_usd)
        
        # Symbol update
        symbol_guard = self.symbol_guards.get(symbol)
        if symbol_guard:
            symbol_guard.on_exit(pnl_usd)
    
    def get_symbol_guard(self, symbol: str) -> Optional[SymbolGuard]:
        """특정 심볼의 Guard 조회"""
        return self.symbol_guards.get(symbol)
    
    def add_symbol(self, symbol: str, config: Optional[Dict[str, Any]] = None) -> None:
        """신규 심볼 추가"""
        if symbol in self.symbol_guards:
            logger.warning(f"[D73-3_COORDINATOR] {symbol} already exists")
            return
        
        self.symbol_guards[symbol] = SymbolGuard(
            symbol=symbol,
            **(config or {})
        )
        logger.info(f"[D73-3_COORDINATOR] Added symbol: {symbol}")
    
    def get_stats(self) -> Dict[str, Any]:
        """전체 통계"""
        return {
            "global": self.global_guard.get_stats(),
            "portfolio": self.portfolio_guard.get_stats(),
            "symbols": {
                symbol: guard.get_stats()
                for symbol, guard in self.symbol_guards.items()
            },
        }
