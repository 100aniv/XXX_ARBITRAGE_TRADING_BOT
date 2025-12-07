"""
D75-4: Arbitrage Route

Exchange A ↔ Exchange B 간 라우팅 로직:
- RouteDecision (direction, score, reason)
- RouteScore 계산 (Spread, Health, Fee, Inventory)
- Health/Fee/Inventory penalty 반영
"""

import logging
import time

logger = logging.getLogger(__name__)
from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

from arbitrage.arbitrage_core import OrderBookSnapshot
from arbitrage.domain.fee_model import FeeModel

if TYPE_CHECKING:
    from arbitrage.execution.fill_model_integration import FillModelIntegration
from arbitrage.domain.market_spec import MarketSpec
from arbitrage.infrastructure.exchange_health import HealthMonitor, ExchangeHealthStatus


class RouteDirection(Enum):
    """Route 방향"""
    LONG_A_SHORT_B = "LONG_A_SHORT_B"  # Buy A, Sell B
    LONG_B_SHORT_A = "LONG_B_SHORT_A"  # Buy B, Sell A
    SKIP = "SKIP"  # 거래 없음


@dataclass
class RouteScore:
    """
    Route 점수 (0~100).
    
    가중치:
    - Spread Score: 40%
    - Health Score: 30%
    - Fee Impact Score: 20%
    - Inventory Risk Penalty: 10%
    """
    spread_score: float  # 0~100
    health_score: float  # 0~100
    fee_score: float     # 0~100
    inventory_penalty: float  # 0~100 (낮을수록 penalty 큼)
    
    def total_score(self) -> float:
        """총점 계산 (가중 평균)"""
        return (
            self.spread_score * 0.4 +
            self.health_score * 0.3 +
            self.fee_score * 0.2 +
            self.inventory_penalty * 0.1
        )


@dataclass
class ArbRouteDecision:
    """Route 결정"""
    direction: RouteDirection
    score: float  # 0~100
    reason: str
    route_score: Optional[RouteScore] = None
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class ArbRoute:
    """
    Arbitrage Route.
    
    두 거래소 간 거래 경로를 평가하고 decision을 생성.
    """
    
    def __init__(
        self,
        symbol_a: str,
        symbol_b: str,
        market_spec: MarketSpec,
        fee_model: FeeModel,
        health_monitor_a: Optional[HealthMonitor] = None,
        health_monitor_b: Optional[HealthMonitor] = None,
        min_spread_bps: float = 30.0,
        slippage_bps: float = 5.0,
        fill_model_integration: Optional["FillModelIntegration"] = None,
    ):
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self.market_spec = market_spec
        self.fee_model = fee_model
        self.health_monitor_a = health_monitor_a
        self.health_monitor_b = health_monitor_b
        self.min_spread_bps = min_spread_bps
        self.slippage_bps = slippage_bps
        self.fill_model_integration = fill_model_integration
    
    def evaluate(
        self,
        snapshot: OrderBookSnapshot,
        inventory_imbalance_ratio: float = 0.0,
        fill_model_advice=None,  # D87-0: FillModelAdvice 통합 훅 (D87-1에서 구현 예정)
    ) -> ArbRouteDecision:
        """
        Route 평가 및 decision 생성.
        
        Args:
            snapshot: Orderbook snapshot
            inventory_imbalance_ratio: Inventory 불균형 비율 (-1.0 ~ 1.0)
                양수: A가 많음, 음수: B가 많음
            fill_model_advice: D87-0: Fill Model Advice (Optional, D87-1+)
        
        Returns:
            ArbRouteDecision
        """
        # 1. Spread 계산
        spread_a_to_b = self._calculate_spread_a_to_b(snapshot)
        spread_b_to_a = self._calculate_spread_b_to_a(snapshot)
        
        # 2. Direction 결정
        if spread_a_to_b >= self.min_spread_bps:
            direction = RouteDirection.LONG_B_SHORT_A
            gross_spread = spread_a_to_b
        elif spread_b_to_a >= self.min_spread_bps:
            direction = RouteDirection.LONG_A_SHORT_B
            gross_spread = spread_b_to_a
        else:
            return ArbRouteDecision(
                direction=RouteDirection.SKIP,
                score=0.0,
                reason=f"Spread too low: A→B={spread_a_to_b:.2f}, B→A={spread_b_to_a:.2f} bps"
            )
        
        # 3. Score 계산
        route_score = self._calculate_route_score(
            gross_spread=gross_spread,
            inventory_imbalance_ratio=inventory_imbalance_ratio,
            direction=direction,
        )
        
        total_score = route_score.total_score()
        
        # D87-1: Fill Model Advice 반영 (Advisory Mode)
        if fill_model_advice and self.fill_model_integration:
            # FillModelIntegration을 통해 score 보정
            adjusted_score = self.fill_model_integration.adjust_route_score(
                base_score=total_score,
                advice=fill_model_advice
            )
            logger.debug(
                f"[ARB_ROUTE] Fill Model Score 보정: "
                f"base={total_score:.1f} → adjusted={adjusted_score:.1f}, "
                f"zone={fill_model_advice.zone_id}"
            )
            total_score = adjusted_score
        
        # 4. Score 기반 최종 결정
        if total_score < 50.0:
            return ArbRouteDecision(
                direction=RouteDirection.SKIP,
                score=total_score,
                reason=f"Score too low: {total_score:.1f}/100",
                route_score=route_score,
            )
        
        return ArbRouteDecision(
            direction=direction,
            score=total_score,
            reason=f"Good opportunity: spread={gross_spread:.2f}bps, score={total_score:.1f}",
            route_score=route_score,
        )
    
    def _calculate_spread_a_to_b(self, snapshot: OrderBookSnapshot) -> float:
        """
        A → B 방향 spread (Buy A, Sell B).
        
        Returns:
            Spread in bps
        """
        # Normalize price A to B currency
        ask_a_norm = self.market_spec.normalize_price_a_to_b(snapshot.best_ask_a)
        bid_b = snapshot.best_bid_b
        
        # Spread = (Sell Price - Buy Price) / Buy Price * 10000
        spread = (bid_b - ask_a_norm) / ask_a_norm * 10_000.0
        
        # Fee & slippage 차감
        total_cost = self.fee_model.total_entry_fee_bps() + self.slippage_bps
        return spread - total_cost
    
    def _calculate_spread_b_to_a(self, snapshot: OrderBookSnapshot) -> float:
        """
        B → A 방향 spread (Buy B, Sell A).
        
        Returns:
            Spread in bps
        """
        # Normalize price A to B currency
        bid_a_norm = self.market_spec.normalize_price_a_to_b(snapshot.best_bid_a)
        ask_b = snapshot.best_ask_b
        
        # Spread = (Sell Price - Buy Price) / Buy Price * 10000
        spread = (bid_a_norm - ask_b) / ask_b * 10_000.0
        
        # Fee & slippage 차감
        total_cost = self.fee_model.total_entry_fee_bps() + self.slippage_bps
        return spread - total_cost
    
    def _calculate_route_score(
        self,
        gross_spread: float,
        inventory_imbalance_ratio: float,
        direction: RouteDirection,
    ) -> RouteScore:
        """Route score 계산"""
        # 1. Spread Score (0~100)
        # 30 bps = 50점, 100 bps = 100점 (linear)
        spread_score = min(100.0, max(0.0, (gross_spread - 30.0) / 0.7 + 50.0))
        
        # 2. Health Score (0~100)
        health_score = self._calculate_health_score()
        
        # 3. Fee Score (0~100)
        fee_score = self._calculate_fee_score(gross_spread)
        
        # 4. Inventory Penalty (0~100, 낮을수록 penalty)
        inventory_penalty = self._calculate_inventory_penalty(
            inventory_imbalance_ratio, direction
        )
        
        return RouteScore(
            spread_score=spread_score,
            health_score=health_score,
            fee_score=fee_score,
            inventory_penalty=inventory_penalty,
        )
    
    def _calculate_health_score(self) -> float:
        """
        Health Score 계산.
        
        공식:
        score = max(0, 100 - (latA + latB)/2 * 0.1 - errorA*200 - errorB*200 - freshnessPenalty)
        
        Returns:
            0~100
        """
        if not self.health_monitor_a or not self.health_monitor_b:
            return 100.0  # No monitoring = assume healthy
        
        metrics_a = self.health_monitor_a.metrics
        metrics_b = self.health_monitor_b.metrics
        
        # Latency penalty (0.1 per ms)
        avg_latency = (metrics_a.rest_latency_ms + metrics_b.rest_latency_ms) / 2.0
        latency_penalty = avg_latency * 0.1
        
        # Error penalty (200 per 1% error)
        error_penalty_a = metrics_a.error_ratio * 200.0
        error_penalty_b = metrics_b.error_ratio * 200.0
        
        # Freshness penalty (orderbook age > 1s)
        freshness_penalty_a = max(0.0, (metrics_a.orderbook_age_ms - 1000.0) / 100.0)
        freshness_penalty_b = max(0.0, (metrics_b.orderbook_age_ms - 1000.0) / 100.0)
        
        score = (
            100.0
            - latency_penalty
            - error_penalty_a
            - error_penalty_b
            - freshness_penalty_a
            - freshness_penalty_b
        )
        
        return max(0.0, min(100.0, score))
    
    def _calculate_fee_score(self, gross_spread: float) -> float:
        """
        Fee Impact Score.
        
        Spread 대비 수수료 비율이 낮을수록 높은 점수.
        
        Returns:
            0~100
        """
        fee_impact = self.fee_model.fee_impact_on_spread(gross_spread)
        
        # fee_impact = 0 (수수료 없음) → 100점
        # fee_impact = 1 (수수료 = spread) → 0점
        return max(0.0, (1.0 - fee_impact) * 100.0)
    
    def _calculate_inventory_penalty(
        self,
        inventory_imbalance_ratio: float,
        direction: RouteDirection,
    ) -> float:
        """
        Inventory Risk Penalty.
        
        방향성과 불균형이 일치하면 penalty (더 불균형 악화)
        방향성과 불균형이 반대면 bonus (불균형 완화)
        
        Args:
            inventory_imbalance_ratio: -1.0 ~ 1.0
                양수: A가 많음, 음수: B가 많음
            direction: Route direction
        
        Returns:
            0~100 (낮을수록 penalty)
        """
        if direction == RouteDirection.SKIP:
            return 100.0
        
        # Direction에 따른 inventory 변화
        # LONG_A_SHORT_B → A 증가 (imbalance += 0.1)
        # LONG_B_SHORT_A → B 증가 (imbalance -= 0.1)
        
        if direction == RouteDirection.LONG_A_SHORT_B:
            # A가 이미 많으면 penalty
            if inventory_imbalance_ratio > 0.3:
                penalty = inventory_imbalance_ratio * 100.0  # 30% → 30점 감점
                return max(0.0, 100.0 - penalty)
        else:  # LONG_B_SHORT_A
            # B가 이미 많으면 penalty
            if inventory_imbalance_ratio < -0.3:
                penalty = abs(inventory_imbalance_ratio) * 100.0
                return max(0.0, 100.0 - penalty)
        
        return 100.0  # No penalty
