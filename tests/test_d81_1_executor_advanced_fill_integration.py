# -*- coding: utf-8 -*-
"""
D81-1: Executor + AdvancedFillModel Integration Tests

Settings.FillModelConfig를 통해 AdvancedFillModel이 정상적으로
Executor에 주입되고, ExecutionResult에 올바른 fill_ratio/slippage가
반영되는지 검증하는 테스트.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from arbitrage.execution.executor_factory import ExecutorFactory
from arbitrage.execution.executor import ExecutionResult
from arbitrage.config.settings import FillModelConfig
from arbitrage.types import PortfolioState, OrderSide
from arbitrage.live_runner import RiskGuard


class TestExecutorAdvancedFillIntegration:
    """Executor + AdvancedFillModel Integration Tests"""
    
    def test_executor_factory_creates_advanced_fill_model(self):
        """ExecutorFactory가 AdvancedFillModel을 생성하는지 확인"""
        factory = ExecutorFactory()
        
        fill_model_config = FillModelConfig(
            enable_fill_model=True,
            enable_partial_fill=True,
            enable_slippage=True,
            slippage_alpha=0.0002,
            fill_model_type="advanced",  # ← advanced 모드
            available_volume_factor=2.0,
            advanced_num_levels=5,
            advanced_level_spacing_bps=1.0,
            advanced_decay_rate=0.3,
            advanced_slippage_exponent=1.2,
            advanced_base_volume_multiplier=0.8,
        )
        
        portfolio_state = MagicMock(spec=PortfolioState)
        risk_guard = MagicMock()
        
        executor = factory.create_paper_executor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=fill_model_config,
        )
        
        # Executor가 생성되었는지 확인
        assert executor is not None
        assert executor.symbol == "BTC/USDT"
        assert executor.enable_fill_model is True
        
        # Fill Model이 AdvancedFillModel인지 확인
        from arbitrage.execution.fill_model import AdvancedFillModel
        assert isinstance(executor.fill_model, AdvancedFillModel)
        assert executor.fill_model.num_levels == 5
        assert executor.fill_model.level_spacing_bps == 1.0
    
    def test_executor_with_advanced_fill_model_direct(self):
        """AdvancedFillModel이 Executor에 정상 주입되는지 직접 검증"""
        factory = ExecutorFactory()
        
        fill_model_config = FillModelConfig(
            enable_fill_model=True,
            enable_partial_fill=True,
            enable_slippage=True,
            slippage_alpha=0.0002,
            fill_model_type="advanced",
            available_volume_factor=2.0,
            advanced_num_levels=5,
            advanced_level_spacing_bps=1.0,
            advanced_decay_rate=0.3,
            advanced_slippage_exponent=1.2,
            advanced_base_volume_multiplier=0.5,  # 낮은 유동성
        )
        
        portfolio_state = MagicMock(spec=PortfolioState)
        portfolio_state.cash = 1000000.0
        portfolio_state.holdings = {"BTC/USDT": 0.0}
        
        risk_guard = MagicMock()
        risk_guard.can_trade = MagicMock(return_value=(True, None))
        
        executor = factory.create_paper_executor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=fill_model_config,
        )
        
        # Fill Model이 정상 주입되었는지 검증
        from arbitrage.execution.fill_model import AdvancedFillModel, FillContext
        assert isinstance(executor.fill_model, AdvancedFillModel)
        
        # Fill Model의 파라미터 확인
        assert executor.fill_model.num_levels == 5
        assert executor.fill_model.level_spacing_bps == 1.0
        assert executor.fill_model.decay_rate == 0.3
        assert executor.fill_model.slippage_exponent == 1.2
        assert executor.fill_model.base_volume_multiplier == 0.5
        
        # Fill Model 직접 실행 테스트
        from arbitrage.types import OrderSide
        context = FillContext(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_quantity=10.0,  # 큰 주문
            target_price=50000.0,
            available_volume=1.0,  # 제한된 유동성
            slippage_alpha=None,
        )
        result = executor.fill_model.execute(context)
        
        # Partial fill 발생 확인
        assert 0 < result.fill_ratio < 1.0
        assert result.status == "partially_filled"
        assert result.slippage_bps > 0
    
    def test_executor_with_simple_vs_advanced_type_check(self):
        """SimpleFillModel vs AdvancedFillModel 타입 확인"""
        factory = ExecutorFactory()
        
        # SimpleFillModel Config
        config_simple = FillModelConfig(
            enable_fill_model=True,
            fill_model_type="simple",
        )
        
        # AdvancedFillModel Config
        config_advanced = FillModelConfig(
            enable_fill_model=True,
            fill_model_type="advanced",
            advanced_num_levels=5,
            advanced_level_spacing_bps=1.0,
            advanced_decay_rate=0.3,
            advanced_slippage_exponent=1.2,
            advanced_base_volume_multiplier=0.8,
        )
        
        portfolio_state = MagicMock(spec=PortfolioState)
        portfolio_state.cash = 1000000.0
        portfolio_state.holdings = {"BTC/USDT": 0.0}
        
        risk_guard = MagicMock()
        
        executor_simple = factory.create_paper_executor(
            symbol="BTC_SIMPLE",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=config_simple,
        )
        
        executor_advanced = factory.create_paper_executor(
            symbol="BTC_ADVANCED",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=config_advanced,
        )
        
        # SimpleFillModel vs AdvancedFillModel 타입 확인
        from arbitrage.execution.fill_model import SimpleFillModel, AdvancedFillModel
        assert isinstance(executor_simple.fill_model, SimpleFillModel)
        assert isinstance(executor_advanced.fill_model, AdvancedFillModel)
    
    def test_backward_compatibility_default_simple(self):
        """Backward Compatibility: 기본값은 SimpleFillModel"""
        factory = ExecutorFactory()
        
        # fill_model_type을 지정하지 않으면 기본값 "simple"
        fill_model_config = FillModelConfig()  # 기본값 사용
        
        portfolio_state = MagicMock(spec=PortfolioState)
        risk_guard = MagicMock()
        
        executor = factory.create_paper_executor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=fill_model_config,
        )
        
        # SimpleFillModel이 기본값
        from arbitrage.execution.fill_model import SimpleFillModel
        assert isinstance(executor.fill_model, SimpleFillModel)
    
    def test_unknown_fill_model_type_fallback(self):
        """알 수 없는 fill_model_type: SimpleFillModel로 fallback"""
        factory = ExecutorFactory()
        
        fill_model_config = FillModelConfig(
            enable_fill_model=True,
            fill_model_type="unknown_type",  # 알 수 없는 타입
        )
        
        portfolio_state = MagicMock(spec=PortfolioState)
        risk_guard = MagicMock()
        
        executor = factory.create_paper_executor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=fill_model_config,
        )
        
        # Fallback: SimpleFillModel
        from arbitrage.execution.fill_model import SimpleFillModel
        assert isinstance(executor.fill_model, SimpleFillModel)
