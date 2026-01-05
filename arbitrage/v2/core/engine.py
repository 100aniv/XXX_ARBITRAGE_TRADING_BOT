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


logger = logging.getLogger(__name__)


class EngineState(Enum):
    """Engine 실행 상태 (D206-0)"""
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
    """
    min_spread_bps: float = 30.0
    max_position_usd: float = 1000.0
    enable_execution: bool = False
    adapters: Dict[str, ExchangeAdapter] = field(default_factory=dict)
    
    # D206-0: Engine Loop 설정
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
            admin_control: AdminControl instance (D206-0)
        """
        self.config = config
        self.adapters = config.adapters
        self.admin_control = admin_control
        self.state = EngineState.STOPPED
        
        logger.info(f"[V2 Engine] Initialized with {len(self.adapters)} adapters")
        if admin_control:
            logger.info(f"[D206-0] AdminControl enabled: {admin_control.state_key}")
    
    def run_cycle(self) -> List[OrderResult]:
        """
        Run one arbitrage cycle.
        
        In V2 kickoff, this is a stub that demonstrates the flow:
        1. Detect opportunities (stub)
        2. Create intents (stub)
        3. Execute via adapters
        4. Aggregate results
        
        Returns:
            List of order results
        """
        logger.info("[V2 Engine] Starting arbitrage cycle")
        
        market_data = self._fetch_market_data()
        
        opportunities = self._detect_opportunities(market_data)
        
        intents = self._create_intents(opportunities)
        
        results = self._execute_intents(intents)
        
        logger.info(f"[V2 Engine] Cycle completed with {len(results)} results")
        return results
    
    def _fetch_market_data(self) -> Dict:
        """
        Fetch market data (stub).
        
        In full V2, this will:
        - Query WebSocket orderbook feeds
        - Aggregate L2 data
        - Calculate spreads
        
        Returns:
            Market data dictionary
        """
        logger.debug("[V2 Engine] Fetching market data (stub)")
        return {"stub": True}
    
    def _detect_opportunities(self, market_data: Dict) -> List[Dict]:
        """
        Detect arbitrage opportunities (stub).
        
        In full V2, this will:
        - Calculate cross-exchange spreads
        - Apply RiskGuard filters
        - Rank by profitability
        
        Args:
            market_data: Market data from _fetch_market_data()
            
        Returns:
            List of opportunities
        """
        logger.debug("[V2 Engine] Detecting opportunities (stub)")
        return []
    
    def _create_intents(self, opportunities: List[Dict]) -> List[OrderIntent]:
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
        유일한 엔진 루프 (D206-0 Engine Unification).
        
        모든 실행 모드(paper/live/replay)를 이 단일 루프로 통합.
        
        Args:
            duration_minutes: 실행 시간 (None이면 무한 루프)
            fetch_tick_data: Tick 데이터 생성 콜백 (Optional)
            process_tick: Tick 처리 콜백 (Optional)
        
        Returns:
            0: 성공
            1: 실패
        """
        logger.info("[D206-0] ========================================")
        logger.info("[D206-0] Engine Loop Starting (Single SSOT Loop)")
        logger.info("[D206-0] ========================================")
        
        self.state = EngineState.RUNNING
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60) if duration_minutes else None
        iteration = 0
        
        try:
            while self.state == EngineState.RUNNING:
                iteration += 1
                elapsed = int(time.time() - start_time)
                
                # AdminControl 훅 - PAUSED/STOPPING/PANIC 체크 (D206-0)
                if self.admin_control:
                    if not self.admin_control.should_process_tick():
                        logger.info(f"[D206-0] Iteration {iteration} skipped: AdminControl state != RUNNING")
                        time.sleep(self.config.tick_interval_sec)
                        continue
                
                # Tick 데이터 생성 (콜백 또는 기본 로직)
                if fetch_tick_data:
                    tick_data = fetch_tick_data(iteration)
                else:
                    tick_data = self._fetch_market_data()
                
                # Opportunity 감지
                opportunities = self._detect_opportunities(tick_data)
                
                # AdminControl 훅 - Symbol Blacklist 체크 (D206-0)
                if self.admin_control:
                    opportunities = [
                        opp for opp in opportunities
                        if not self.admin_control.is_symbol_blacklisted(
                            opp.get('symbol', 'UNKNOWN')
                        )
                    ]
                
                # OrderIntent 생성 및 실행
                intents = self._create_intents(opportunities)
                
                # Tick 처리 콜백 (Optional)
                if process_tick:
                    process_tick(iteration, opportunities, intents)
                
                # Intent 실행
                if intents:
                    results = self._execute_intents(intents)
                    logger.debug(f"[D206-0] Iteration {iteration}: {len(results)} intents executed")
                
                # KPI 로그 출력 (주기적)
                if iteration % self.config.kpi_log_interval == 0:
                    logger.info(f"[D206-0] Iteration {iteration} (elapsed: {elapsed}s)")
                
                # Duration 체크
                if end_time and time.time() >= end_time:
                    logger.info(f"[D206-0] Duration reached: {duration_minutes} minutes")
                    break
                
                # Tick 간격 대기
                time.sleep(self.config.tick_interval_sec)
            
            # 정상 종료
            self.state = EngineState.STOPPED
            logger.info("[D206-0] ========================================")
            logger.info("[D206-0] Engine Loop Complete (STOPPED)")
            logger.info("[D206-0] ========================================")
            return 0
        
        except KeyboardInterrupt:
            logger.warning("[D206-0] Engine interrupted by user (Ctrl+C)")
            self.state = EngineState.STOPPED
            return 1
        
        except Exception as e:
            logger.error(f"[D206-0] Engine fatal error: {e}", exc_info=True)
            self.state = EngineState.PANIC
            return 1
