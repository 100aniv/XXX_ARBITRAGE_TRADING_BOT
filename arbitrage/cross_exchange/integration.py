# -*- coding: utf-8 -*-
"""
D79-3: Cross-Exchange Integration Layer

D75 Engine과 CrossExchange 계층을 연결하는 얇은 통합 레이어.

Features:
- D79-1 모듈 통합 (UniverseProvider, SpreadModel, FXConverter)
- D79-2 모듈 통합 (Strategy, PositionManager)
- D75 Infrastructure 연동 (HealthMonitor, RiskGuard)
- D78 Secrets Layer 연동
- Paper 모드 전용 (실 주문 없음)

Architecture:
    D75 Engine Loop
          ↓
    CrossExchangeIntegration
          ↓
    ├─> UniverseProvider (symbol selection)
    ├─> SpreadModel (spread calculation)
    ├─> FXConverter (KRW ↔ USDT conversion)
    ├─> Strategy (Entry/Exit signals)
    ├─> PositionManager (Position SSOT)
    └─> HealthMonitor, Settings/Secrets (validation)
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .universe_provider import CrossExchangeUniverseProvider
from .spread_model import SpreadModel, CrossSpread
from .fx_converter import FXConverter
from .strategy import CrossExchangeStrategy, CrossExchangeSignal, CrossExchangeAction
from .position_manager import CrossExchangePositionManager, CrossExchangePosition

logger = logging.getLogger(__name__)


@dataclass
class CrossExchangeDecision:
    """
    교차 거래소 의사결정 (Paper 모드)
    
    실제 주문은 D79-4에서 구현.
    현재는 log 및 테스트 검증용.
    """
    action: CrossExchangeAction
    symbol_upbit: str
    symbol_binance: str
    notional_krw: float
    spread_percent: float
    reason: str
    timestamp: float
    
    # Entry-specific
    entry_side: Optional[str] = None  # "positive" or "negative"
    
    # Exit-specific
    exit_pnl_krw: Optional[float] = None
    position_holding_time: Optional[float] = None


class CrossExchangeIntegration:
    """
    교차 거래소 통합 레이어
    
    D75 Engine과 CrossExchange 모듈을 연결.
    
    Responsibilities:
    - Universe 선택 (UniverseProvider)
    - Spread 계산 (SpreadModel + FXConverter)
    - Entry/Exit 신호 생성 (Strategy)
    - Position 관리 (PositionManager)
    - Health/Secrets 검증
    
    Example:
        integration = CrossExchangeIntegration(
            universe_provider=universe_provider,
            spread_model=spread_model,
            fx_converter=fx_converter,
            strategy=strategy,
            position_manager=position_manager,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        # Entry tick
        decisions = integration.tick_entry(context)
        
        # Exit tick
        exit_decisions = integration.tick_exit(context)
    """
    
    def __init__(
        self,
        universe_provider: CrossExchangeUniverseProvider,
        spread_model: SpreadModel,
        fx_converter: FXConverter,
        strategy: CrossExchangeStrategy,
        position_manager: CrossExchangePositionManager,
        health_monitor: Any,  # HealthMonitor (D75-3)
        settings: Any,  # Settings (D78)
        upbit_public_client: Any = None,  # UpbitPublicDataClient (D79-1)
        binance_public_client: Any = None,  # BinancePublicDataClient (D79-1)
    ):
        """
        Args:
            universe_provider: CrossExchangeUniverseProvider
            spread_model: SpreadModel
            fx_converter: FXConverter
            strategy: CrossExchangeStrategy
            position_manager: CrossExchangePositionManager
            health_monitor: HealthMonitor (D75-3)
            settings: Settings (D78)
            upbit_public_client: UpbitPublicDataClient (optional)
            binance_public_client: BinancePublicDataClient (optional)
        """
        self.universe_provider = universe_provider
        self.spread_model = spread_model
        self.fx_converter = fx_converter
        self.strategy = strategy
        self.position_manager = position_manager
        self.health_monitor = health_monitor
        self.settings = settings
        self.upbit_client = upbit_public_client
        self.binance_client = binance_public_client
        
        # Metrics
        self.tick_count = 0
        self.entry_signals_generated = 0
        self.exit_signals_generated = 0
        
        logger.info(
            "[D79-3] CrossExchangeIntegration initialized: "
            f"universe_mode={universe_provider.mode if universe_provider else 'None'}"
        )
    
    def tick_entry(self, context: Optional[Dict] = None) -> List[CrossExchangeDecision]:
        """
        Entry tick: 새로운 포지션 진입 기회 평가
        
        Flow:
        1. Universe selection (symbol 목록)
        2. Spread calculation (각 symbol)
        3. Health/Secrets validation
        4. Strategy.evaluate_entry()
        5. PositionManager.open_position() (if ENTRY signal)
        
        Args:
            context: Optional context (snapshot, health status, etc.)
        
        Returns:
            List[CrossExchangeDecision]: Entry decisions
        """
        decisions = []
        context = context or {}
        
        try:
            # 1. Universe selection
            symbol_mappings = self._get_universe_symbols()
            if not symbol_mappings:
                logger.debug("[D79-3] No symbols in universe")
                return decisions
            
            # 2. Health check
            health_ok = self._check_health()
            
            # 3. Secrets validation
            secrets_available = self._check_secrets()
            
            # 4. FX confidence
            fx_rate = self.fx_converter.get_fx_rate()
            fx_confidence = fx_rate.confidence if fx_rate else 0.0
            
            # 5. Evaluate each symbol
            for mapping in symbol_mappings:
                try:
                    # Calculate spread
                    spread = self._calculate_spread(mapping, context)
                    if spread is None:
                        continue
                    
                    # Check liquidity
                    liquidity_ok = self._check_liquidity(spread)
                    
                    # Evaluate entry
                    signal = self.strategy.evaluate_entry(
                        symbol_mapping=mapping,
                        cross_spread=spread,
                        fx_confidence=fx_confidence,
                        health_ok=health_ok,
                        secrets_available=secrets_available,
                        liquidity=spread.upbit_volume_krw if spread else 0.0,
                    )
                    
                    # Process signal
                    if signal.action in [
                        CrossExchangeAction.ENTRY_POSITIVE,
                        CrossExchangeAction.ENTRY_NEGATIVE,
                    ]:
                        # Open position
                        position = self.position_manager.open_position(
                            symbol_mapping=mapping.__dict__ if hasattr(mapping, '__dict__') else mapping,
                            entry_side=signal.entry_side,
                            entry_spread=spread,
                        )
                        
                        # Create decision
                        decision = CrossExchangeDecision(
                            action=signal.action,
                            symbol_upbit=mapping.upbit_symbol,
                            symbol_binance=mapping.binance_symbol,
                            notional_krw=100_000_000,  # Default 100M KRW (to be adjusted)
                            spread_percent=spread.spread_percent,
                            reason=signal.reason,
                            timestamp=signal.timestamp,
                            entry_side=signal.entry_side,
                        )
                        decisions.append(decision)
                        self.entry_signals_generated += 1
                        
                        logger.info(
                            f"[D79-3_ENTRY] {signal.action.value}: "
                            f"{mapping.upbit_symbol}/{mapping.binance_symbol}, "
                            f"spread={spread.spread_percent:.2f}%, "
                            f"reason={signal.reason}"
                        )
                
                except Exception as e:
                    logger.error(
                        f"[D79-3_ENTRY] Error evaluating {mapping.upbit_symbol}: {e}",
                        exc_info=True,
                    )
                    continue
            
            self.tick_count += 1
        
        except Exception as e:
            logger.error(f"[D79-3_ENTRY] tick_entry error: {e}", exc_info=True)
        
        return decisions
    
    def tick_exit(self, context: Optional[Dict] = None) -> List[CrossExchangeDecision]:
        """
        Exit tick: 기존 포지션 청산 기회 평가
        
        Flow:
        1. List open positions (PositionManager)
        2. Calculate current spread (각 position)
        3. Health check
        4. Strategy.evaluate_exit()
        5. PositionManager.close_position() (if EXIT signal)
        
        Args:
            context: Optional context
        
        Returns:
            List[CrossExchangeDecision]: Exit decisions
        """
        decisions = []
        context = context or {}
        
        try:
            # 1. Get open positions
            open_positions = self.position_manager.list_open_positions()
            if not open_positions:
                return decisions
            
            # 2. Health check
            health_ok = self._check_health()
            
            # 3. Evaluate each position
            for position in open_positions:
                try:
                    # Reconstruct symbol mapping
                    mapping = position.symbol_mapping
                    if isinstance(mapping, dict):
                        # Convert dict to object for spread calculation
                        mapping_obj = type('obj', (object,), mapping)()
                    else:
                        mapping_obj = mapping
                    
                    # Calculate current spread
                    spread = self._calculate_spread(mapping_obj, context)
                    if spread is None:
                        continue
                    
                    # Evaluate exit
                    signal = self.strategy.evaluate_exit(
                        position=position.__dict__ if hasattr(position, '__dict__') else position,
                        current_spread=spread,
                        health_ok=health_ok,
                    )
                    
                    # Process signal
                    if signal.action != CrossExchangeAction.NO_ACTION:
                        # Close position
                        closed_position = self.position_manager.close_position(
                            upbit_symbol=mapping.get('upbit_symbol') if isinstance(mapping, dict) else mapping.upbit_symbol,
                            exit_spread_percent=spread.spread_percent,
                            exit_reason=signal.reason,
                        )
                        
                        if closed_position:
                            # Create decision
                            decision = CrossExchangeDecision(
                                action=signal.action,
                                symbol_upbit=mapping.get('upbit_symbol') if isinstance(mapping, dict) else mapping.upbit_symbol,
                                symbol_binance=mapping.get('binance_symbol') if isinstance(mapping, dict) else mapping.binance_symbol,
                                notional_krw=100_000_000,  # Default
                                spread_percent=spread.spread_percent,
                                reason=signal.reason,
                                timestamp=signal.timestamp,
                                exit_pnl_krw=closed_position.exit_pnl_krw,
                                position_holding_time=closed_position.get_holding_time(),
                            )
                            decisions.append(decision)
                            self.exit_signals_generated += 1
                            
                            logger.info(
                                f"[D79-3_EXIT] {signal.action.value}: "
                                f"{decision.symbol_upbit}/{decision.symbol_binance}, "
                                f"spread={spread.spread_percent:.2f}%, "
                                f"pnl={closed_position.exit_pnl_krw:.0f} KRW, "
                                f"reason={signal.reason}"
                            )
                
                except Exception as e:
                    logger.error(
                        f"[D79-3_EXIT] Error evaluating position: {e}",
                        exc_info=True,
                    )
                    continue
        
        except Exception as e:
            logger.error(f"[D79-3_EXIT] tick_exit error: {e}", exc_info=True)
        
        return decisions
    
    def _get_universe_symbols(self) -> List:
        """
        Universe에서 symbol 목록 가져오기
        
        Returns:
            List[SymbolMapping]: Symbol mappings
        """
        try:
            # UniverseProvider에서 TopN 또는 CUSTOM_LIST 가져오기
            if self.upbit_client and self.binance_client:
                result = self.universe_provider.select_universe(
                    upbit_client=self.upbit_client,
                    binance_client=self.binance_client,
                )
                return result
            else:
                # Fallback: 기본 심볼 (테스트용)
                logger.warning("[D79-3] No public clients, using fallback symbols")
                return []
        
        except Exception as e:
            logger.error(f"[D79-3] Error getting universe symbols: {e}")
            return []
    
    def _calculate_spread(self, symbol_mapping: Any, context: Dict) -> Optional[CrossSpread]:
        """
        Spread 계산
        
        Args:
            symbol_mapping: SymbolMapping
            context: Context (tickers, etc.)
        
        Returns:
            CrossSpread or None
        """
        try:
            # Context에서 tickers 가져오기 (또는 직접 조회)
            upbit_ticker = context.get('upbit_ticker')
            binance_ticker = context.get('binance_ticker')
            
            # Tickers가 없으면 직접 조회 (Paper 모드에서는 mock)
            if not upbit_ticker or not binance_ticker:
                # Paper 모드에서는 mock spread 반환
                logger.debug("[D79-3] No tickers in context, skipping spread calculation")
                return None
            
            # SpreadModel로 spread 계산
            spread = self.spread_model.calculate_spread(
                upbit_price_krw=upbit_ticker.price,
                binance_price_usdt=binance_ticker.price,
                upbit_volume_krw=upbit_ticker.volume,
                binance_volume_usdt=binance_ticker.volume,
                symbol_mapping=symbol_mapping,
            )
            
            return spread
        
        except Exception as e:
            logger.error(f"[D79-3] Error calculating spread: {e}")
            return None
    
    def _check_health(self) -> bool:
        """
        Exchange health 확인
        
        Returns:
            bool: True if both exchanges are healthy
        """
        try:
            if self.health_monitor:
                upbit_status = self.health_monitor.get_status("upbit")
                binance_status = self.health_monitor.get_status("binance")
                
                # HEALTHY 또는 DEGRADED까지 허용
                from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
                return (
                    upbit_status in [ExchangeHealthStatus.HEALTHY, ExchangeHealthStatus.DEGRADED] and
                    binance_status in [ExchangeHealthStatus.HEALTHY, ExchangeHealthStatus.DEGRADED]
                )
            else:
                # HealthMonitor 없으면 True (테스트용)
                return True
        
        except Exception as e:
            logger.error(f"[D79-3] Error checking health: {e}")
            return False
    
    def _check_secrets(self) -> bool:
        """
        Secrets availability 확인 (D78)
        
        Returns:
            bool: True if API keys are available
        """
        try:
            if self.settings:
                # Upbit 또는 Binance API key 중 하나라도 있으면 True
                has_upbit = bool(self.settings.upbit_access_key and self.settings.upbit_secret_key)
                has_binance = bool(self.settings.binance_api_key and self.settings.binance_api_secret)
                return has_upbit or has_binance
            else:
                # Settings 없으면 True (테스트용)
                return True
        
        except Exception as e:
            logger.error(f"[D79-3] Error checking secrets: {e}")
            return False
    
    def _check_liquidity(self, spread: CrossSpread) -> bool:
        """
        Liquidity 확인
        
        Args:
            spread: CrossSpread
        
        Returns:
            bool: True if liquidity is sufficient
        """
        # Universe provider 기준 사용 (100M KRW, 100K USDT)
        min_upbit_volume = 100_000_000  # 100M KRW
        min_binance_volume = 100_000  # 100K USDT
        
        return (
            spread.upbit_volume_krw >= min_upbit_volume and
            spread.binance_volume_usdt >= min_binance_volume
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Integration 메트릭 반환
        
        Returns:
            Dict: Metrics
        """
        return {
            "tick_count": self.tick_count,
            "entry_signals_generated": self.entry_signals_generated,
            "exit_signals_generated": self.exit_signals_generated,
            "open_positions": len(self.position_manager.list_open_positions()),
            "inventory": self.position_manager.get_inventory(),
        }
