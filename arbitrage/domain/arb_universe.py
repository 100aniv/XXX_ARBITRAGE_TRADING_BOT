"""
D75-4: Arbitrage Universe

Multi-symbol arbitrage universe 관리:
- Universe Mode (TOP_N, ALL_SYMBOLS, CUSTOM_LIST)
- Route ranking (score-based)
- Spread normalization
- Dynamic symbol selection
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from arbitrage.arbitrage_core import OrderBookSnapshot
from arbitrage.domain.arb_route import ArbRoute, ArbRouteDecision, RouteDirection
from arbitrage.domain.fee_model import FeeModel
from arbitrage.domain.market_spec import MarketSpec
from arbitrage.infrastructure.exchange_health import HealthMonitor


class UniverseMode(Enum):
    """Universe 모드"""
    TOP_N = "top_n"  # Top N symbols (by volume/liquidity)
    ALL_SYMBOLS = "all_symbols"  # All available symbols
    CUSTOM_LIST = "custom_list"  # Custom symbol list


@dataclass
class RouteRanking:
    """Route ranking 결과"""
    symbol_a: str
    symbol_b: str
    direction: RouteDirection
    score: float
    reason: str
    decision: Optional[ArbRouteDecision] = None


@dataclass
class UniverseDecision:
    """Universe decision"""
    ranked_routes: List[RouteRanking] = field(default_factory=list)
    timestamp: float = 0.0
    mode: UniverseMode = UniverseMode.TOP_N
    total_candidates: int = 0
    valid_routes: int = 0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def get_top_route(self) -> Optional[RouteRanking]:
        """최상위 route 반환"""
        if not self.ranked_routes:
            return None
        return self.ranked_routes[0]
    
    def get_top_n_routes(self, n: int) -> List[RouteRanking]:
        """Top N routes 반환"""
        return self.ranked_routes[:n]


class UniverseProvider:
    """
    Arbitrage Universe Provider.
    
    여러 symbol에 대해 route를 평가하고 ranking.
    """
    
    def __init__(
        self,
        mode: UniverseMode = UniverseMode.TOP_N,
        top_n: int = 10,
        custom_symbols: Optional[List[Tuple[str, str]]] = None,
        min_score_threshold: float = 50.0,
    ):
        """
        Args:
            mode: Universe 모드
            top_n: TOP_N 모드일 때 상위 N개 symbol
            custom_symbols: CUSTOM_LIST 모드일 때 symbol 리스트
                [(symbol_a, symbol_b), ...]
            min_score_threshold: 최소 score threshold (이하는 필터링)
        """
        self.mode = mode
        self.top_n = top_n
        self.custom_symbols = custom_symbols or []
        self.min_score_threshold = min_score_threshold
        
        # Route cache
        self._route_cache: Dict[Tuple[str, str], ArbRoute] = {}
    
    def register_route(
        self,
        symbol_a: str,
        symbol_b: str,
        market_spec: MarketSpec,
        fee_model: FeeModel,
        health_monitor_a: Optional[HealthMonitor] = None,
        health_monitor_b: Optional[HealthMonitor] = None,
        min_spread_bps: float = 30.0,
    ) -> None:
        """Route 등록"""
        route = ArbRoute(
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            market_spec=market_spec,
            fee_model=fee_model,
            health_monitor_a=health_monitor_a,
            health_monitor_b=health_monitor_b,
            min_spread_bps=min_spread_bps,
        )
        self._route_cache[(symbol_a, symbol_b)] = route
    
    def evaluate_universe(
        self,
        snapshots: Dict[Tuple[str, str], OrderBookSnapshot],
        inventory_state: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> UniverseDecision:
        """
        Universe 전체 평가.
        
        Args:
            snapshots: {(symbol_a, symbol_b): OrderBookSnapshot}
            inventory_state: {(symbol_a, symbol_b): imbalance_ratio}
        
        Returns:
            UniverseDecision
        """
        inventory_state = inventory_state or {}
        
        # 1. 모든 route 평가
        rankings: List[RouteRanking] = []
        total_candidates = 0
        
        for (symbol_a, symbol_b), snapshot in snapshots.items():
            total_candidates += 1
            
            # Route 조회
            route = self._route_cache.get((symbol_a, symbol_b))
            if route is None:
                continue
            
            # Inventory imbalance
            imbalance = inventory_state.get((symbol_a, symbol_b), 0.0)
            
            # Route decision
            decision = route.evaluate(snapshot, imbalance)
            
            # Skip 제외
            if decision.direction == RouteDirection.SKIP:
                continue
            
            # Score threshold 필터
            if decision.score < self.min_score_threshold:
                continue
            
            rankings.append(
                RouteRanking(
                    symbol_a=symbol_a,
                    symbol_b=symbol_b,
                    direction=decision.direction,
                    score=decision.score,
                    reason=decision.reason,
                    decision=decision,
                )
            )
        
        # 2. Score 기준 정렬 (내림차순)
        rankings.sort(key=lambda r: r.score, reverse=True)
        
        # 3. Mode 기반 필터링
        if self.mode == UniverseMode.TOP_N:
            rankings = rankings[:self.top_n]
        elif self.mode == UniverseMode.CUSTOM_LIST:
            # Custom list에 있는 symbol만 필터
            custom_set = set(self.custom_symbols)
            rankings = [r for r in rankings if (r.symbol_a, r.symbol_b) in custom_set]
        
        return UniverseDecision(
            ranked_routes=rankings,
            mode=self.mode,
            total_candidates=total_candidates,
            valid_routes=len(rankings),
        )
    
    def add_symbol(self, symbol_a: str, symbol_b: str) -> None:
        """Symbol 추가 (CUSTOM_LIST 모드)"""
        if self.mode != UniverseMode.CUSTOM_LIST:
            raise ValueError("add_symbol is only for CUSTOM_LIST mode")
        self.custom_symbols.append((symbol_a, symbol_b))
    
    def remove_symbol(self, symbol_a: str, symbol_b: str) -> None:
        """Symbol 제거 (CUSTOM_LIST 모드)"""
        if self.mode != UniverseMode.CUSTOM_LIST:
            raise ValueError("remove_symbol is only for CUSTOM_LIST mode")
        self.custom_symbols = [
            (a, b) for (a, b) in self.custom_symbols
            if not (a == symbol_a and b == symbol_b)
        ]
    
    def get_registered_routes(self) -> List[Tuple[str, str]]:
        """등록된 route 목록 반환"""
        return list(self._route_cache.keys())
