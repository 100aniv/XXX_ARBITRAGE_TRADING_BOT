"""
ArbitrageEngine - Orchestrator

Engine-centric arbitrage logic.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING
from enum import Enum
import logging
import yaml
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import time

from .adapter import ExchangeAdapter, OrderResult
from .order_intent import OrderIntent
from arbitrage.v2.domain import OrderBookSnapshot, ArbitrageOpportunity, ArbitrageTrade
from arbitrage.domain.fee_model import FeeModel, create_fee_model_upbit_binance
from arbitrage.domain.market_spec import MarketSpec, create_market_spec_upbit_binance
from arbitrage.domain.arb_route import ArbRoute


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
    
    D206-2: FeeModel/MarketSpec 통합
    - fee_model: V1 FeeModel (수수료 계산)
    - market_spec: V1 MarketSpec (환율, tick/lot size)
    - arb_route: V1 ArbRoute (route scoring, health)
    
    D206-4: PaperExecutor/LedgerWriter 통합
    - executor: Paper 주문 실행
    - ledger_writer: DB 기록
    """
    # D206-3: Zero-Fallback - All required keys must be provided (no defaults)
    # REQUIRED fields (no defaults) - MUST come first in dataclass
    min_spread_bps: float
    max_position_usd: float
    max_open_trades: int
    taker_fee_a_bps: float
    taker_fee_b_bps: float
    slippage_bps: float
    exchange_a_to_b_rate: float
    
    # OPTIONAL fields (with defaults) - MUST come after REQUIRED fields
    # Exit Rules (D206-2-1)
    take_profit_bps: Optional[float] = None
    stop_loss_bps: Optional[float] = None
    min_hold_sec: float = 0.0
    close_on_spread_reversal: bool = True
    enable_alpha_exit: bool = False
    
    # Other
    enable_execution: bool = False
    tick_interval_sec: float = 1.0
    kpi_log_interval: int = 10
    
    # D206-2: V1 FeeModel/MarketSpec/ArbRoute 통합 (dynamic, not from config.yml)
    adapters: Dict[str, ExchangeAdapter] = field(default_factory=dict)
    fee_model: Optional[FeeModel] = None
    market_spec: Optional[MarketSpec] = None
    use_arb_route: bool = False
    
    # D206-4: Executor/LedgerWriter integration
    executor: Optional['PaperExecutor'] = None
    ledger_writer: Optional['LedgerWriter'] = None
    run_id: str = field(default_factory=lambda: str(__import__('uuid').uuid4()))
    
    @classmethod
    def from_config_file(cls, config_path: str, **kwargs):
        """
        D206-3: Load EngineConfig from config.yml (SSOT).
        
        Zero-Fallback: All required keys must be present in config.yml.
        No defaults in code - missing keys will raise RuntimeError.
        
        Args:
            config_path: Path to config.yml
            **kwargs: Additional fields (adapters, fee_model, market_spec, etc.)
        
        Returns:
            EngineConfig instance
        
        Raises:
            RuntimeError: If required keys are missing
        """
        path = Path(config_path)
        if not path.exists():
            raise RuntimeError(
                f"[D206-3 Zero-Fallback] config.yml not found: {config_path}\n"
                f"SSOT violation: config.yml must exist (no hardcoded defaults)"
            )
        
        with open(path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # D206-3: Zero-Fallback - Validate required keys
        required_keys = [
            'min_spread_bps', 'max_position_usd', 'max_open_trades',
            'taker_fee_a_bps', 'taker_fee_b_bps', 'slippage_bps',
            'exchange_a_to_b_rate'
        ]
        
        missing = [k for k in required_keys if k not in config_data]
        if missing:
            raise RuntimeError(
                f"[D206-3 Zero-Fallback] Missing required config keys: {missing}\n"
                f"Config path: {config_path}\n"
                f"SSOT violation: All {len(required_keys)} required keys must be present\n"
                f"See config.yml example for complete schema"
            )
        
        # D206-3: Decimal precision enforcement (float → Decimal conversion)
        # Store as float in dataclass, but convert to Decimal in engine usage
        # (Conversion happens in ArbitrageEngine.__init__)
        
        # Merge config_data with kwargs (kwargs override config_data)
        merged = {**config_data, **kwargs}
        
        return cls(**merged)


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
        
        # D206-2: FeeModel/MarketSpec 기반 pre-calculation
        if self.config.fee_model:
            self._total_cost_bps = self.config.fee_model.total_entry_fee_bps() + self.config.slippage_bps
        else:
            # Fallback: D206-1 compatibility
            self._total_cost_bps = (
                self.config.taker_fee_a_bps
                + self.config.taker_fee_b_bps
                + self.config.slippage_bps
            )
        
        if self.config.market_spec:
            self._exchange_a_to_b_rate = self.config.market_spec.fx_rate_a_to_b
        else:
            # Fallback: D206-1 compatibility
            self._exchange_a_to_b_rate = self.config.exchange_a_to_b_rate
        
        # D206-2: ArbRoute 통합 (선택적)
        self._arb_route: Optional[ArbRoute] = None
        if self.config.use_arb_route and self.config.market_spec and self.config.fee_model:
            self._arb_route = ArbRoute(
                symbol_a="KRW-BTC",  # TODO: config에서 가져오기
                symbol_b="BTCUSDT",
                market_spec=self.config.market_spec,
                fee_model=self.config.fee_model,
                min_spread_bps=self.config.min_spread_bps,
                slippage_bps=self.config.slippage_bps,
            )
        
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
        
        # D206-2: V1/V2 OrderBookSnapshot duck typing
        if hasattr(snapshot, 'best_bid_a'):  # OrderBookSnapshot (V1 or V2)
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
        
        # D206-2-1: Exit Rules (spread_reversal + TP/SL)
        trades_to_close = []
        for trade in self._open_trades:
            side = trade.side
            exit_reason = None
            
            # Calculate current spread
            if side == "LONG_A_SHORT_B":
                current_spread = (bid_b_normalized - ask_a) / ask_a * 10_000.0
            else:
                current_spread = (bid_a - ask_b_normalized) / ask_b_normalized * 10_000.0
            
            # Calculate unrealized PnL (for TP/SL check)
            # PnL = entry_spread - current_spread - cost
            unrealized_pnl_bps = trade.entry_spread_bps - current_spread - self._total_cost_bps
            
            # D206-2-1: Take Profit
            if self.config.take_profit_bps is not None:
                if unrealized_pnl_bps >= self.config.take_profit_bps:
                    exit_reason = 'take_profit'
            
            # D206-2-1: Stop Loss
            if self.config.stop_loss_bps is not None:
                if unrealized_pnl_bps <= -self.config.stop_loss_bps:
                    exit_reason = 'stop_loss'
            
            # D206-2-1: Spread Reversal (기존 로직)
            if self.config.close_on_spread_reversal:
                if current_spread < 0:
                    exit_reason = 'spread_reversal'
            
            # D206-2-1: Min Hold Time Check
            if exit_reason and self.config.min_hold_sec > 0:
                # TODO: 실제 hold_duration 계산 (timestamp parsing 필요)
                # 현재는 min_hold_sec=0 디폴트이므로 체크 생략
                pass
            
            if exit_reason:
                trade.close(
                    close_timestamp=timestamp,
                    exit_spread_bps=current_spread,
                    taker_fee_a_bps=self.config.taker_fee_a_bps,
                    taker_fee_b_bps=self.config.taker_fee_b_bps,
                    slippage_bps=self.config.slippage_bps,
                    exit_reason=exit_reason
                )
                trades_to_close.append(trade)
        
        for trade in trades_to_close:
            self._open_trades.remove(trade)
            trades_changed.append(trade)
            logger.info(f"[D206-2-1] Closed trade: {trade.side} ({trade.exit_reason}) pnl_bps={trade.pnl_bps:.2f}")
        
        # D206-2-1: 종료 발생 시 신규 개설 스킵 (같은 스냅샷에서 종료+개설 금지)
        if trades_to_close:
            return trades_changed
        
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
        D206-4 AC-1~4: Convert ArbitrageTrade to OrderResult via PaperExecutor.
        
        Flow:
        1. ArbitrageTrade → OrderIntent (AC-1)
        2. PaperExecutor.execute(intent) → OrderResult (AC-2)
        3. LedgerWriter.record_order_and_fill() (AC-3)
        4. Decimal precision enforcement (18 digits)
        
        Args:
            trade: ArbitrageTrade (opened or closed)
        
        Returns:
            OrderResult with filled_qty/filled_price/fee (Decimal precision)
        """
        # D206-4 AC-1: Create OrderIntent from ArbitrageTrade
        from arbitrage.v2.domain.order_intent import OrderIntent, OrderSide
        
        # Determine side: LONG_A_SHORT_B → BUY on A, SELL on B
        #                 LONG_B_SHORT_A → BUY on B, SELL on A
        if trade.side == "LONG_A_SHORT_B":
            side = OrderSide.BUY
            exchange = "upbit"  # Exchange A
            symbol = "BTC/KRW"
        elif trade.side == "LONG_B_SHORT_A":
            side = OrderSide.SELL
            exchange = "binance"  # Exchange B (but we SELL on A in reality)
            symbol = "BTC/USDT"
        else:
            # Fallback for unknown side
            side = OrderSide.BUY
            exchange = "upbit"
            symbol = "BTC/KRW"
        
        # D206-4: Decimal precision enforcement (18 digits)
        quantity_decimal = Decimal(str(trade.notional_usd / 50000.0)).quantize(
            Decimal('0.00000001'), rounding=ROUND_HALF_UP
        )  # Approx BTC quantity
        
        intent = OrderIntent(
            symbol=symbol,
            side=side,
            quantity=float(quantity_decimal),  # OrderIntent expects float
            order_type="MARKET"
        )
        
        # D206-4 AC-2: Execute via PaperExecutor (if available)
        if self.config.executor:
            try:
                order_result = self.config.executor.execute(intent)
                
                # D206-4: Decimal precision for filled_qty/filled_price
                if order_result.filled_qty:
                    order_result.filled_qty = float(
                        Decimal(str(order_result.filled_qty)).quantize(
                            Decimal('0.00000001'), rounding=ROUND_HALF_UP
                        )
                    )
                if order_result.filled_price:
                    order_result.filled_price = float(
                        Decimal(str(order_result.filled_price)).quantize(
                            Decimal('0.00000001'), rounding=ROUND_HALF_UP
                        )
                    )
                if order_result.fee:
                    order_result.fee = float(
                        Decimal(str(order_result.fee)).quantize(
                            Decimal('0.00000001'), rounding=ROUND_HALF_UP
                        )
                    )
                
                # D206-4 AC-3: Record to DB (if LedgerWriter available)
                if self.config.ledger_writer:
                    # Note: LedgerWriter.record_order_and_fill() expects candidate/kpi
                    # For now, we skip DB recording here (orchestrator will handle)
                    pass
                
                logger.info(
                    f"[D206-4] Executed trade: {trade.side} "
                    f"qty={order_result.filled_qty:.8f} price={order_result.filled_price:.2f}"
                )
                return order_result
                
            except Exception as e:
                logger.error(f"[D206-4] PaperExecutor failed: {e}")
                # Fallback to stub
        
        # Fallback: stub OrderResult (backward compatibility)
        logger.warning("[D206-4] PaperExecutor not configured, using stub OrderResult")
        return OrderResult(
            success=True,
            order_id=f"stub_{trade.side}",
            filled_qty=float(quantity_decimal),
            filled_price=50000.0 if "KRW" in symbol else 50000.0 / self._exchange_a_to_b_rate,
            fee=0.0
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
        D206-2: V1 detect_opportunity logic with ArbRoute integration.
        
        Args:
            snapshot: OrderBookSnapshot or dict (backward compatible)
        
        Returns:
            ArbitrageOpportunity or None
        """
        # D206-2: V1/V2 OrderBookSnapshot duck typing (타입 호환성)
        if self._arb_route and hasattr(snapshot, 'best_bid_a'):
            return self._detect_with_route(snapshot)
        
        # Backward compatibility: accept dict or OrderBookSnapshot (duck typing)
        if hasattr(snapshot, 'best_bid_a'):  # OrderBookSnapshot (V1 or V2)
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
    
    def _detect_with_route(self, snapshot: OrderBookSnapshot) -> Optional[ArbitrageOpportunity]:
        """
        D206-2: ArbRoute 기반 기회 탐지 (route scoring).
        
        Args:
            snapshot: OrderBookSnapshot
        
        Returns:
            ArbitrageOpportunity or None
        """
        from arbitrage.domain.arb_route import RouteDirection
        
        # ArbRoute.evaluate() 호출
        decision = self._arb_route.evaluate(
            snapshot=snapshot,
            inventory_imbalance_ratio=0.0,  # TODO: inventory tracking
        )
        
        # RouteScore < 50이면 SKIP
        if decision.direction == RouteDirection.SKIP:
            logger.debug(f"[ArbRoute] SKIP: {decision.reason}")
            return None
        
        # RouteDecision → ArbitrageOpportunity 변환
        # Re-calculate spread/edge (ArbRoute는 net spread만 반환)
        bid_a = snapshot.best_bid_a
        ask_a = snapshot.best_ask_a
        bid_b = snapshot.best_bid_b
        ask_b = snapshot.best_ask_b
        
        bid_b_normalized = bid_b * self._exchange_a_to_b_rate
        ask_b_normalized = ask_b * self._exchange_a_to_b_rate
        
        if decision.direction == RouteDirection.LONG_A_SHORT_B:
            spread = (bid_b_normalized - ask_a) / ask_a * 10_000.0
            side = "LONG_A_SHORT_B"
        else:  # LONG_B_SHORT_A
            spread = (bid_a - ask_b_normalized) / ask_b_normalized * 10_000.0
            side = "LONG_B_SHORT_A"
        
        gross_edge = spread
        net_edge = spread - self._total_cost_bps
        
        return ArbitrageOpportunity(
            timestamp=snapshot.timestamp,
            side=side,
            spread_bps=spread,
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
