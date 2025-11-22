"""
D75-5: 4-Tier RiskGuard Unit Tests

각 Tier별 decision logic 검증:
- ExchangeGuard
- RouteGuard
- SymbolGuard
- GlobalGuard
- Aggregation logic
"""

import pytest
import time
from arbitrage.domain.risk_guard import (
    FourTierRiskGuard,
    FourTierRiskGuardConfig,
    ExchangeGuardConfig,
    RouteGuardConfig,
    SymbolGuardConfig,
    GlobalGuardConfig,
    ExchangeState,
    RouteState,
    SymbolState,
    GlobalState,
    GuardDecisionType,
    GuardReasonCode,
    GuardTier,
)
from arbitrage.domain.arb_route import RouteScore
from arbitrage.infrastructure.exchange_health import (
    ExchangeHealthStatus,
    HealthMetrics,
)


class TestExchangeGuard:
    """Exchange Guard 테스트"""
    
    def test_exchange_health_down_blocks_trades(self):
        """DOWN 상태 거래소는 차단"""
        config = FourTierRiskGuardConfig()
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.DOWN,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        symbol_states = {}
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=0.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.allow is False
        assert GuardReasonCode.EXCHANGE_HEALTH_DOWN in decision.tier_decisions[GuardTier.EXCHANGE].reasons
    
    def test_exchange_daily_loss_limit_blocks_trades(self):
        """일일 손실 한도 초과 시 차단"""
        config = FourTierRiskGuardConfig(
            exchange=ExchangeGuardConfig(max_daily_loss_usd=1000.0)
        )
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=1500.0,  # 한도 초과
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        symbol_states = {}
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=0.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.allow is False
        assert GuardReasonCode.EXCHANGE_DAILY_LOSS_LIMIT in decision.tier_decisions[GuardTier.EXCHANGE].reasons
    
    def test_exchange_degraded_status_degrades_notional(self):
        """DEGRADED 상태는 거래 금액 축소"""
        config = FourTierRiskGuardConfig()
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.DEGRADED,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        symbol_states = {}
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=0.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        # DEGRADED → DEGRADE decision
        assert decision.degraded is True
        assert GuardReasonCode.EXCHANGE_HEALTH_DEGRADED in decision.tier_decisions[GuardTier.EXCHANGE].reasons


class TestRouteGuard:
    """Route Guard 테스트"""
    
    def test_route_streak_loss_triggers_cooldown(self):
        """연속 손실 시 cooldown 발동"""
        config = FourTierRiskGuardConfig(
            route=RouteGuardConfig(max_streak_loss=3, cooldown_after_streak_loss=300.0)
        )
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        # 3회 연속 손실
        route_state = RouteState(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            recent_trades=[-10.0, -20.0, -30.0],  # 3회 연속 손실
        )
        symbol_states = {}
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=0.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.allow is False
        assert decision.cooldown_seconds > 0
        assert GuardReasonCode.ROUTE_STREAK_LOSS in decision.tier_decisions[GuardTier.ROUTE].reasons
        
        # 두 번째 평가 (cooldown 중)
        decision2 = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        assert decision2.allow is False
        assert decision2.tier_decisions[GuardTier.ROUTE].decision == GuardDecisionType.COOLDOWN_ONLY
    
    def test_route_score_low_blocks_trade(self):
        """낮은 route score는 차단"""
        config = FourTierRiskGuardConfig(
            route=RouteGuardConfig(min_route_score=50.0)
        )
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        # Low route score
        route_state = RouteState(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            route_score=RouteScore(
                spread_score=20.0,
                health_score=30.0,
                fee_score=40.0,
                inventory_penalty=50.0,
            ),  # total_score = 20*0.4 + 30*0.3 + 40*0.2 + 50*0.1 = 30 < 50
        )
        symbol_states = {}
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=0.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.allow is False
        assert GuardReasonCode.ROUTE_SCORE_LOW in decision.tier_decisions[GuardTier.ROUTE].reasons


class TestSymbolGuard:
    """Symbol Guard 테스트"""
    
    def test_symbol_exposure_high_degrades_notional(self):
        """높은 symbol exposure는 거래 금액 축소"""
        config = FourTierRiskGuardConfig(
            symbol=SymbolGuardConfig(max_exposure_ratio=0.5)
        )
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        
        # BTC exposure 60% (> 50%)
        symbol_states = {
            "BTC": SymbolState(
                symbol="BTC",
                total_exposure_usd=60000.0,
                total_notional_usd=60000.0,
                unrealized_pnl_usd=0.0,
                intraday_pnl_usd=0.0,
                intraday_peak_usd=0.0,
            )
        }
        
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,  # 60k / 100k = 60% > 50%
            total_exposure_usd=60000.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.degraded is True
        assert GuardReasonCode.SYMBOL_EXPOSURE_HIGH in decision.tier_decisions[GuardTier.SYMBOL].reasons
    
    def test_symbol_dd_high_blocks_trade(self):
        """높은 drawdown은 차단"""
        config = FourTierRiskGuardConfig(
            symbol=SymbolGuardConfig(max_dd_ratio=0.2)
        )
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        
        # BTC drawdown 30% (> 20%)
        symbol_states = {
            "BTC": SymbolState(
                symbol="BTC",
                total_exposure_usd=10000.0,
                total_notional_usd=10000.0,
                unrealized_pnl_usd=-3000.0,
                intraday_pnl_usd=7000.0,
                intraday_peak_usd=10000.0,  # DD = (10k - 7k) / 10k = 30%
            )
        }
        
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=10000.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.allow is False
        assert GuardReasonCode.SYMBOL_DD_HIGH in decision.tier_decisions[GuardTier.SYMBOL].reasons


class TestGlobalGuard:
    """Global Guard 테스트"""
    
    def test_global_daily_loss_triggers_global_block(self):
        """글로벌 일일 손실 한도 초과 시 차단"""
        config = FourTierRiskGuardConfig(
            global_guard=GlobalGuardConfig(max_global_daily_loss_usd=50000.0)
        )
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        symbol_states = {}
        
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=10000.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=60000.0,  # > 50k
            global_cumulative_loss_usd=60000.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.allow is False
        assert GuardReasonCode.GLOBAL_DD_LIMIT in decision.tier_decisions[GuardTier.GLOBAL].reasons
    
    def test_global_imbalance_triggers_rebalance_only_mode(self):
        """높은 cross-exchange imbalance는 차단 (rebalance 우선)"""
        config = FourTierRiskGuardConfig(
            global_guard=GlobalGuardConfig(max_imbalance_ratio=0.5)
        )
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        symbol_states = {}
        
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=10000.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.7,  # > 0.5
            cross_exchange_exposure_risk=0.9,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        assert decision.allow is False
        assert GuardReasonCode.GLOBAL_IMBALANCE_HIGH in decision.tier_decisions[GuardTier.GLOBAL].reasons


class TestAggregation:
    """Aggregation logic 테스트"""
    
    def test_four_tier_aggregation_picks_strictest_decision(self):
        """가장 보수적인 Tier 결정 선택"""
        config = FourTierRiskGuardConfig(
            exchange=ExchangeGuardConfig(health_status_degrade_on_degraded=True),
            route=RouteGuardConfig(min_route_score=50.0),
        )
        guard = FourTierRiskGuard(config)
        
        # Exchange: DEGRADED (degrade)
        # Route: Low score (block)
        # Symbol: OK
        # Global: OK
        # → Strictest = BLOCK (Route)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.DEGRADED,  # → DEGRADE
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            route_score=RouteScore(
                spread_score=10.0,
                health_score=10.0,
                fee_score=10.0,
                inventory_penalty=10.0,
            ),  # total_score = 10 < 50 → BLOCK
        )
        
        symbol_states = {}
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=0.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        # Route의 BLOCK이 Exchange의 DEGRADE보다 엄격
        assert decision.allow is False
        assert decision.degraded is False
        assert decision.tier_decisions[GuardTier.EXCHANGE].decision == GuardDecisionType.DEGRADE
        assert decision.tier_decisions[GuardTier.ROUTE].decision == GuardDecisionType.BLOCK
    
    def test_risk_guard_decision_serialization(self):
        """RiskGuardDecision 직렬화 (로깅/모니터링용)"""
        config = FourTierRiskGuardConfig()
        guard = FourTierRiskGuard(config)
        
        exchange_states = {
            "UPBIT": ExchangeState(
                exchange_name="UPBIT",
                health_status=ExchangeHealthStatus.HEALTHY,
                health_metrics=HealthMetrics(),
                rate_limit_remaining_pct=1.0,
                daily_loss_usd=0.0,
            )
        }
        
        route_state = RouteState(symbol_a="KRW-BTC", symbol_b="BTCUSDT")
        symbol_states = {}
        global_state = GlobalState(
            total_portfolio_value_usd=100000.0,
            total_exposure_usd=0.0,
            total_margin_used_usd=0.0,
            global_daily_loss_usd=0.0,
            global_cumulative_loss_usd=0.0,
            cross_exchange_imbalance_ratio=0.0,
            cross_exchange_exposure_risk=0.0,
        )
        
        decision = guard.evaluate(exchange_states, route_state, symbol_states, global_state)
        
        # get_reason_summary() 정상 동작 확인
        summary = decision.get_reason_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0
        
        # allow=True 시나리오
        assert decision.allow is True
        assert "ALL_TIERS_OK" in summary
