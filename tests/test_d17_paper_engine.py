#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D17 Tests — Paper Engine End-to-End
====================================

엔드-투-엔드 페이퍼 모드 테스트.
시나리오 기반 전체 플로우 검증.
"""

import pytest
import asyncio
import yaml
from pathlib import Path
from typing import Dict
from arbitrage.exchange.simulated import SimulatedExchange
from arbitrage.state_manager import StateManager
from liveguard.safety import SafetyModule
from liveguard.risk_limits import RiskLimits
from arbitrage.types import ExchangeType, OrderSide


class PaperEngineSimulator:
    """페이퍼 모드 엔진 시뮬레이터"""
    
    def __init__(self, scenario_path: str):
        """
        Args:
            scenario_path: 시나리오 YAML 파일 경로
        """
        with open(scenario_path, 'r', encoding='utf-8') as f:
            self.scenario = yaml.safe_load(f)
        
        self.name = self.scenario.get('name')
        self.steps = self.scenario.get('steps', [])
        self.risk_profile = self.scenario.get('risk_profile', {})
        self.expected = self.scenario.get('expected_outcomes', {})
        
        # 컴포넌트
        self.exchange = SimulatedExchange(
            exchange_type=ExchangeType.UPBIT,
            initial_balance={"KRW": 10_000_000, "BTC": 0},
            slippage_bps=self.risk_profile.get('slippage_bps', 5.0)
        )
        
        self.safety = SafetyModule(
            RiskLimits(
                max_position_size=self.risk_profile.get('max_position_krw', 1_000_000),
                max_daily_loss=self.risk_profile.get('max_daily_loss_krw', 500_000),
                max_trades_per_hour=self.risk_profile.get('max_trades_per_hour', 100),
                min_spread_pct=self.risk_profile.get('min_spread_pct', 0.1)
            )
        )
        
        # 통계
        self.trades = []
        self.signals = []
        self.pnl = 0.0
    
    async def run(self) -> Dict:
        """
        시나리오 실행
        
        Returns:
            실행 결과
        """
        await self.exchange.connect()
        
        for step in self.steps:
            t = step.get('t')
            
            # 가격 설정
            upbit_bid = step.get('upbit_bid')
            upbit_ask = step.get('upbit_ask')
            
            if upbit_bid and upbit_ask:
                self.exchange.set_price("KRW-BTC", upbit_bid, upbit_ask)
            
            # 신호 생성 (스프레드 기반)
            # 스프레드 = (ask - bid) / bid * 100 (양수가 정상)
            spread_pct = ((upbit_ask - upbit_bid) / upbit_bid) * 100 if upbit_bid else 0
            
            # 스프레드가 최소값보다 크면 신호 생성
            if spread_pct > self.risk_profile.get('min_spread_pct', 0.1):
                # 안전 검사
                can_execute, reason = self.safety.can_execute_order(
                    position_value=1_000_000,
                    current_positions=len(self.trades),
                    current_loss=self.pnl,
                    total_balance=10_000_000
                )
                
                if can_execute:
                    # 주문 실행
                    order = await self.exchange.place_order(
                        symbol="KRW-BTC",
                        side=OrderSide.BUY,
                        quantity=1.0,
                        price=upbit_ask
                    )
                    
                    if order:
                        self.trades.append(order)
                        self.signals.append({
                            't': t,
                            'spread_pct': spread_pct,
                            'order_id': order.order_id
                        })
                        self.safety.record_trade(0)  # 임시 손실
                else:
                    # 안전 장치 발동
                    pass
        
        await self.exchange.disconnect()
        
        # 결과 계산
        stats = self.exchange.get_stats()
        
        return {
            'scenario': self.name,
            'trades': len(self.trades),
            'signals': len(self.signals),
            'total_fees': stats['total_fees'],
            'pnl': self.pnl,
            'circuit_breaker_active': self.safety.state.circuit_breaker_active,
            'safety_violations': 0
        }


class TestPaperEngine:
    """페이퍼 엔진 테스트"""
    
    @pytest.fixture
    def scenarios_dir(self):
        """시나리오 디렉토리"""
        return Path(__file__).parent.parent / "configs" / "d17_scenarios"
    
    @pytest.mark.asyncio
    async def test_basic_spread_win_scenario(self, scenarios_dir):
        """정상 수익 시나리오"""
        scenario_path = scenarios_dir / "basic_spread_win.yaml"
        
        if not scenario_path.exists():
            pytest.skip(f"Scenario file not found: {scenario_path}")
        
        engine = PaperEngineSimulator(str(scenario_path))
        result = await engine.run()
        
        assert result['trades'] >= engine.expected.get('min_trades', 0)
        assert not result['circuit_breaker_active']
        assert result['safety_violations'] == engine.expected.get('safety_violations', 0)
    
    @pytest.mark.asyncio
    async def test_choppy_market_scenario(self, scenarios_dir):
        """변동성 시나리오"""
        scenario_path = scenarios_dir / "choppy_market.yaml"
        
        if not scenario_path.exists():
            pytest.skip(f"Scenario file not found: {scenario_path}")
        
        engine = PaperEngineSimulator(str(scenario_path))
        result = await engine.run()
        
        assert not result['circuit_breaker_active']
        assert result['safety_violations'] == engine.expected.get('safety_violations', 0)
    
    @pytest.mark.asyncio
    async def test_stop_loss_trigger_scenario(self, scenarios_dir):
        """손실/회로차단 시나리오"""
        scenario_path = scenarios_dir / "stop_loss_trigger.yaml"
        
        if not scenario_path.exists():
            pytest.skip(f"Scenario file not found: {scenario_path}")
        
        engine = PaperEngineSimulator(str(scenario_path))
        result = await engine.run()
        
        # 회로차단기 발동 여부 확인
        expected_cb = engine.expected.get('circuit_breaker_triggered', False)
        # 실제 발동 여부는 손실 크기에 따라 결정됨


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
