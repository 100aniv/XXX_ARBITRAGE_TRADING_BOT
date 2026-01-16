"""
ArbitrageEngine - Orchestrator

Engine-centric arbitrage logic.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
import logging
import time

from .adapter import ExchangeAdapter, OrderResult
from .order_intent import OrderIntent
from arbitrage.v2.domain import OrderBookSnapshot, ArbitrageOpportunity, ArbitrageTrade


logger = logging.getLogger(__name__)


class EngineState(Enum):
    """Engine 실행 상태 (D205-12-2)"""
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    PANIC = "PANIC"


@dataclass
class EngineConfig:
    """
    Configuration for ArbitrageEngine.
    
    Attributes:
        min_spread_bps: Minimum spread in basis points
        max_position_usd: Maximum position size in USD
        enable_execution: Whether to execute orders (False = dry-run)
        adapters: Dictionary of exchange adapters
        taker_fee_a_bps: Exchange A taker fee (bps)
        taker_fee_b_bps: Exchange B taker fee (bps)
        slippage_bps: Total slippage (bps)
        max_open_trades: Maximum concurrent trades
        close_on_spread_reversal: Close trade when spread reverses
        exchange_a_to_b_rate: Exchange rate normalization (1 A_unit = N B_unit)
    """
    min_spread_bps: float = 30.0
    max_position_usd: float = 1000.0
    enable_execution: bool = False
    adapters: Dict[str, ExchangeAdapter] = field(default_factory=dict)
    
    # D206-1: V1 ArbitrageConfig fields (ProfitCore Bootstrap)
    taker_fee_a_bps: float = 10.0
    taker_fee_b_bps: float = 10.0
    slippage_bps: float = 5.0
    max_open_trades: int = 1
    close_on_spread_reversal: bool = True
    exchange_a_to_b_rate: float = 1.0
    
    # D205-12-2: Engine Loop 설정
    tick_interval_sec: float = 1.0  # Tick 간격
    kpi_log_interval: int = 10  # KPI 로그 출력 간격 (iterations)


class ArbitrageEngine:
    """
    V2 Arbitrage Engine.
    
    Responsibility:
    1. Market data collection (placeholder in V2)
    2. Opportunity detection (placeholder in V2)
    3. OrderIntent generation
    4. Adapter orchestration
    5. Result aggregation
    
    This is a minimal stub for V2 kickoff. Full implementation
    will be added incrementally.
    """
    
    def __init__(self, config: EngineConfig, admin_control: Optional['AdminControl'] = None):
        """
        Initialize engine.
        
        Args:
            config: Engine configuration
            admin_control: AdminControl instance (D205-12-2)
        """
        self.config = config
        self.adapters = config.adapters
        self.admin_control = admin_control
        self.state = EngineState.STOPPED
        
        # D206-1: V1 ArbitrageEngine state (Domain Model Integration)
        self._open_trades: List[ArbitrageTrade] = []  # Type-safe trade tracking
        self._last_snapshot: Optional[OrderBookSnapshot] = None
        
        # D206-1: Pre-calculated values (V1 optimization)
        self._total_cost_bps = (
            self.config.taker_fee_a_bps
            + self.config.taker_fee_b_bps
            + self.config.slippage_bps
        )
        self._exchange_a_to_b_rate = self.config.exchange_a_to_b_rate
        
        logger.info(f"[V2 Engine] Initialized with {len(self.adapters)} adapters")
        logger.info(f"[D206-1] ProfitCore: total_cost={self._total_cost_bps:.2f} bps, fx_rate={self._exchange_a_to_b_rate}")
        if admin_control:
            logger.info(f"[D205-12-2] AdminControl enabled: {admin_control.state_key}")
    
    def run_cycle(self) -> List[OrderResult]:
        """
        Run one arbitrage cycle.
        
        D206-1: V1 on_snapshot logic integrated.
        
        Flow:
        1. Fetch market data (orderbook snapshot)
        2. Close existing trades if spread reverses
        3. Detect new opportunities
        4. Open new trades
        5. Return results
        
        Returns:
            List of order results
        """
        logger.debug("[V2 Engine] Starting arbitrage cycle")
        
        market_data = self._fetch_market_data()
        
        # D206-1: Process snapshot (close + open trades)
        trades_changed = self._process_snapshot(market_data)
        
        # Convert trades to OrderResults (stub for now)
        results = [self._trade_to_result(t) for t in trades_changed]
        
        logger.debug(f"[V2 Engine] Cycle completed: {len(trades_changed)} trades changed")
        return results
    
    def _process_snapshot(self, snapshot) -> List[ArbitrageTrade]:
        """
        D206-1: V1 on_snapshot logic (core trade management).
        
        Args:
            snapshot: OrderBookSnapshot or dict (backward compatible) or None
        
        Returns:
            List of ArbitrageTrade that were opened/closed
        """
        if snapshot is None:
            return []
        if isinstance(snapshot, dict) and snapshot.get('stub'):
            return []
        
        self._last_snapshot = snapshot
        trades_changed = []
        
        # Extract prices (backward compatible)
        if isinstance(snapshot, OrderBookSnapshot):
            bid_a = snapshot.best_bid_a
            ask_a = snapshot.best_ask_a
            bid_b = snapshot.best_bid_b
            ask_b = snapshot.best_ask_b
            timestamp = snapshot.timestamp
        elif isinstance(snapshot, dict):
            bid_a = snapshot.get('best_bid_a', 0)
            ask_a = snapshot.get('best_ask_a', 0)
            bid_b = snapshot.get('best_bid_b', 0)
            ask_b = snapshot.get('best_ask_b', 0)
            timestamp = snapshot.get('timestamp', '')
        else:
            return []
        
        if bid_a <= 0 or ask_a <= 0 or bid_b <= 0 or ask_b <= 0:
            return []
        
        # Normalize exchange rates (V1 optimization)
        bid_b_normalized = bid_b * self._exchange_a_to_b_rate
        ask_b_normalized = ask_b * self._exchange_a_to_b_rate
        
        # Close existing trades if spread reverses
        if self.config.close_on_spread_reversal:
            trades_to_close = []
            for trade in self._open_trades:
                side = trade.side
                
                # Calculate current spread
                if side == "LONG_A_SHORT_B":
                    current_spread = (bid_b_normalized - ask_a) / ask_a * 10_000.0
                else:
                    current_spread = (bid_a - ask_b_normalized) / ask_b_normalized * 10_000.0
                
                # Close if spread becomes negative
                if current_spread < 0:
                    trade.close(
                        close_timestamp=timestamp,
                        exit_spread_bps=0.0,
                        taker_fee_a_bps=self.config.taker_fee_a_bps,
                        taker_fee_b_bps=self.config.taker_fee_b_bps,
                        slippage_bps=self.config.slippage_bps,
                        exit_reason='spread_reversal'
                    )
                    trades_to_close.append(trade)
            
            for trade in trades_to_close:
                self._open_trades.remove(trade)
                trades_changed.append(trade)
                logger.info(f"[D206-1] Closed trade: {trade.side} (spread_reversal)")
        
        # Detect new opportunities and open trades
        opportunity = self._detect_single_opportunity(snapshot)
        if opportunity:
            new_trade = ArbitrageTrade(
                open_timestamp=timestamp,
                side=opportunity.side,
                entry_spread_bps=opportunity.spread_bps,
                notional_usd=opportunity.notional_usd,
                is_open=True,
                meta={'net_edge_bps': str(opportunity.net_edge_bps)}
            )
            self._open_trades.append(new_trade)
            trades_changed.append(new_trade)
            logger.info(f"[D206-1] Opened trade: {opportunity.side} at {opportunity.spread_bps:.2f} bps (edge={opportunity.net_edge_bps:.2f})")
        
        return trades_changed
    
    def _trade_to_result(self, trade: ArbitrageTrade) -> OrderResult:
        """
        Convert ArbitrageTrade to OrderResult (stub).
        
        D206-1: Type-safe conversion.
        """
        return OrderResult(
            exchange="stub",
            symbol="stub",
            side="buy" if "LONG" in trade.side else "sell",
            filled_qty=trade.notional_usd / 100,  # Stub conversion
            filled_price=100.0,  # Stub
            fee_paid=0.0,
            timestamp=trade.open_timestamp,
            metadata={'trade': trade.to_dict()}
        )
    
    def _fetch_market_data(self) -> Optional[OrderBookSnapshot]:
        """
        Fetch market data (stub).
        
        In full V2, this will:
        - Query WebSocket orderbook feeds
        - Aggregate L2 data
        - Calculate spreads
        
        Returns:
            OrderBookSnapshot or None (stub returns None)
        """
        logger.debug("[V2 Engine] Fetching market data (stub)")
        return None  # Stub: no real data
    
    def _detect_opportunities(self, market_data) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities.
        
        D206-1: V1 detect_opportunity logic ported to V2.
        
        Args:
            market_data: OrderBookSnapshot or dict or list (backward compatible)
            
        Returns:
            List of ArbitrageOpportunity
        """
        # D205-13-1: Backward compatibility
        if market_data is None:
            return []
        if isinstance(market_data, dict) and 'stub' in market_data:
            return []
        if not isinstance(market_data, list):
            market_data = [market_data]
        
        opportunities = []
        for snapshot in market_data:
            opp = self._detect_single_opportunity(snapshot)
            if opp:
                opportunities.append(opp)
        return opportunities
    
    def _detect_single_opportunity(self, snapshot) -> Optional[ArbitrageOpportunity]:
        """
        D206-1: V1 detect_opportunity logic (core profit logic).
        
        Args:
            snapshot: OrderBookSnapshot or dict (backward compatible)
        
        Returns:
            ArbitrageOpportunity or None
        """
        # Backward compatibility: accept dict or OrderBookSnapshot
        if isinstance(snapshot, OrderBookSnapshot):
            bid_a = snapshot.best_bid_a
            ask_a = snapshot.best_ask_a
            bid_b = snapshot.best_bid_b
            ask_b = snapshot.best_ask_b
            timestamp = snapshot.timestamp
        elif isinstance(snapshot, dict):
            bid_a = snapshot.get('best_bid_a', 0)
            ask_a = snapshot.get('best_ask_a', 0)
            bid_b = snapshot.get('best_bid_b', 0)
            ask_b = snapshot.get('best_ask_b', 0)
            timestamp = snapshot.get('timestamp', '')
        else:
            return None
        
        if bid_a <= 0 or ask_a <= 0 or bid_b <= 0 or ask_b <= 0:
            return None
        if bid_a >= ask_a or bid_b >= ask_b:
            return None
        
        # Exchange rate normalization (V1 D45)
        bid_b_normalized = bid_b * self._exchange_a_to_b_rate
        ask_b_normalized = ask_b * self._exchange_a_to_b_rate
        
        # Calculate spreads (both directions)
        spread_a_to_b = (bid_b_normalized - ask_a) / ask_a * 10_000.0
        spread_b_to_a = (bid_a - ask_b_normalized) / ask_b_normalized * 10_000.0
        
        best_spread = max(spread_a_to_b, spread_b_to_a)
        net_edge = best_spread - self._total_cost_bps
        
        # V1 D45: Accept if net_edge >= 0 (not < min_spread_bps)
        if net_edge < 0:
            return None
        
        # Check max open trades
        if len(self._open_trades) >= self.config.max_open_trades:
            return None
        
        # Determine best side
        if spread_a_to_b >= spread_b_to_a:
            side = "LONG_A_SHORT_B"
            gross_edge = spread_a_to_b
        else:
            side = "LONG_B_SHORT_A"
            gross_edge = spread_b_to_a
        
        return ArbitrageOpportunity(
            timestamp=timestamp,
            side=side,
            spread_bps=best_spread,
            gross_edge_bps=gross_edge,
            net_edge_bps=net_edge,
            notional_usd=self.config.max_position_usd,
        )
    
    def _create_intents(self, opportunities: List[ArbitrageOpportunity]) -> List[OrderIntent]:
        """
        Create OrderIntents from opportunities (stub).
        
        In full V2, this will:
        - Convert opportunities to OrderIntents
        - Apply position sizing
        - Validate risk limits
        
        Args:
            opportunities: Detected opportunities
            
        Returns:
            List of OrderIntents
        """
        logger.debug(f"[V2 Engine] Creating intents from {len(opportunities)} opportunities (stub)")
        return []
    
    def _execute_intents(self, intents: List[OrderIntent]) -> List[OrderResult]:
        """
        Execute OrderIntents via adapters.
        
        This is the core execution logic that's functional in V2 kickoff.
        
        Args:
            intents: List of OrderIntents to execute
            
        Returns:
            List of OrderResults
        """
        if not self.config.enable_execution:
            logger.info("[V2 Engine] Execution disabled (dry-run mode)")
            return []
        
        results = []
        for intent in intents:
            try:
                adapter = self.adapters.get(intent.exchange)
                if not adapter:
                    logger.error(f"[V2 Engine] No adapter for exchange: {intent.exchange}")
                    results.append(OrderResult(
                        success=False,
                        error_message=f"No adapter for {intent.exchange}"
                    ))
                    continue
                
                logger.info(f"[V2 Engine] Executing {intent}")
                result = adapter.execute(intent)
                results.append(result)
                
            except Exception as e:
                logger.error(f"[V2 Engine] Execution failed for {intent}: {e}")
                results.append(OrderResult(
                    success=False,
                    error_message=str(e)
                ))
        
        return results
    
    def run(self, 
            duration_minutes: Optional[float] = None,
            fetch_tick_data: Optional[Callable] = None,
            process_tick: Optional[Callable] = None) -> int:
        """
        유일한 엔진 루프 (D205-12-2 Engine Unification).
        
        모든 실행 모드(paper/live/replay)를 이 단일 루프로 통합.
        
        Args:
            duration_minutes: 실행 시간 (None이면 무한 루프)
            fetch_tick_data: Tick 데이터 생성 콜백 (Optional)
            process_tick: Tick 처리 콜백 (Optional)
        
        Returns:
            0: 성공
            1: 실패
        """
        logger.info("[D205-12-2] ========================================")
        logger.info("[D205-12-2] Engine Loop Starting (Single SSOT Loop)")
        logger.info("[D205-12-2] ========================================")
        
        self.state = EngineState.RUNNING
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60) if duration_minutes else None
        iteration = 0
        
        try:
            while self.state == EngineState.RUNNING:
                iteration += 1
                elapsed = int(time.time() - start_time)
                
                # Duration 체크 (D205-13-1: PAUSED 모드에서도 duration 준수)
                if end_time and time.time() >= end_time:
                    logger.info(f"[D205-12-2] Duration reached: {duration_minutes} minutes")
                    break
                
                # Tick 데이터 생성 (콜백 또는 기본 로직)
                if fetch_tick_data:
                    tick_data = fetch_tick_data(iteration)
                else:
                    tick_data = self._fetch_market_data()
                
                # Opportunity 감지
                opportunities = self._detect_opportunities(tick_data)
                
                # OrderIntent 생성 (stub)
                intents = self._create_intents(opportunities)
                
                # Tick 처리 콜백 (Optional)
                if process_tick:
                    process_tick(iteration, opportunities, intents)
                
                # Intent 실행
                if intents:
                    results = self._execute_intents(intents)
                    logger.debug(f"[D205-12-2] Iteration {iteration}: {len(results)} intents executed")
                
                # KPI 로그 출력 (주기적)
                if iteration % self.config.kpi_log_interval == 0:
                    logger.info(f"[D205-12-2] Iteration {iteration} (elapsed: {elapsed}s)")
                
                # Tick 간격 대기
                time.sleep(self.config.tick_interval_sec)
            
            # 정상 종료
            self.state = EngineState.STOPPED
            logger.info("[D205-12-2] ========================================")
            logger.info("[D205-12-2] Engine Loop Complete (STOPPED)")
            logger.info("[D205-12-2] ========================================")
            return 0
        
        except KeyboardInterrupt:
            logger.warning("[D205-12-2] Engine interrupted by user (Ctrl+C)")
            self.state = EngineState.STOPPED
            return 1
        
        except Exception as e:
            logger.error(f"[D205-12-2] Engine fatal error: {e}", exc_info=True)
            self.state = EngineState.PANIC
            return 1
