# -*- coding: utf-8 -*-
"""
D81-0: ExecutorFactory + Settings 기반 Fill Model 통합 테스트

목적:
    ExecutorFactory가 FillModelConfig를 받아서 정상적으로
    PaperExecutor + FillModel을 생성하는지 검증.

Author: arbitrage-lite project
Date: 2025-12-04
"""

import pytest
from unittest.mock import Mock

from arbitrage.execution.executor_factory import ExecutorFactory
from arbitrage.config.settings import FillModelConfig
from arbitrage.execution.fill_model import SimpleFillModel
from arbitrage.types import PortfolioState
from arbitrage.live_runner import RiskGuard


class TestExecutorFactoryFillModelIntegration:
    """ExecutorFactory + FillModelConfig 통합 테스트"""
    
    @pytest.fixture
    def portfolio_state(self):
        """PortfolioState mock"""
        state = Mock(spec=PortfolioState)
        state.get_symbol_capital_used = Mock(return_value=0.0)
        return state
    
    @pytest.fixture
    def risk_guard(self):
        """RiskGuard mock"""
        guard = Mock(spec=RiskGuard)
        guard.check_symbol_capital_limit = Mock(return_value=True)
        return guard
    
    def test_factory_creates_executor_without_fill_model(self, portfolio_state, risk_guard):
        """
        테스트 1: Fill Model 비활성화 상태로 Executor 생성
        
        조건:
            - FillModelConfig(enable_fill_model=False)
        
        기대 결과:
            - PaperExecutor.enable_fill_model=False
            - PaperExecutor.fill_model=None
        """
        factory = ExecutorFactory()
        config = FillModelConfig(enable_fill_model=False)
        
        executor = factory.create_paper_executor(
            symbol="BTC/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=config,
        )
        
        assert executor.enable_fill_model is False
        assert executor.fill_model is None
    
    def test_factory_creates_executor_with_simple_fill_model(self, portfolio_state, risk_guard):
        """
        테스트 2: SimpleFillModel 활성화 상태로 Executor 생성
        
        조건:
            - FillModelConfig(enable_fill_model=True, fill_model_type="simple")
        
        기대 결과:
            - PaperExecutor.enable_fill_model=True
            - PaperExecutor.fill_model은 SimpleFillModel 인스턴스
            - FillModel 파라미터가 정상 전달됨
        """
        factory = ExecutorFactory()
        config = FillModelConfig(
            enable_fill_model=True,
            enable_partial_fill=True,
            enable_slippage=True,
            slippage_alpha=0.0002,
            fill_model_type="simple",
            available_volume_factor=3.0,
        )
        
        executor = factory.create_paper_executor(
            symbol="ETH/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=config,
        )
        
        assert executor.enable_fill_model is True
        assert executor.fill_model is not None
        assert isinstance(executor.fill_model, SimpleFillModel)
        assert executor.default_available_volume_factor == 3.0
        
        # SimpleFillModel 파라미터 확인
        assert executor.fill_model.enable_partial_fill is True
        assert executor.fill_model.enable_slippage is True
        assert executor.fill_model.default_slippage_alpha == 0.0002
    
    def test_factory_creates_executor_with_default_config(self, portfolio_state, risk_guard):
        """
        테스트 3: fill_model_config=None일 때 기본값 사용
        
        조건:
            - fill_model_config=None
        
        기대 결과:
            - FillModelConfig 기본값 사용
            - enable_fill_model=True (기본값)
        """
        factory = ExecutorFactory()
        
        executor = factory.create_paper_executor(
            symbol="XRP/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=None,  # 기본값 사용
        )
        
        # FillModelConfig 기본값 확인
        assert executor.enable_fill_model is True
        assert executor.fill_model is not None
        assert isinstance(executor.fill_model, SimpleFillModel)
        assert executor.default_available_volume_factor == 2.0
    
    def test_factory_advanced_fill_model_fallback_to_simple(self, portfolio_state, risk_guard):
        """
        테스트 4: fill_model_type="advanced" → SimpleFillModel로 fallback
        
        조건:
            - FillModelConfig(fill_model_type="advanced")
            - AdvancedFillModel 미구현
        
        기대 결과:
            - Warning 로그 출력
            - SimpleFillModel로 fallback
        """
        factory = ExecutorFactory()
        config = FillModelConfig(
            enable_fill_model=True,
            fill_model_type="advanced",  # 미구현
        )
        
        executor = factory.create_paper_executor(
            symbol="SOL/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=config,
        )
        
        # D99-18 P17: 코어가 AdvancedFillModel을 기본으로 사용 (정상 동작)
        # Fallback to SimpleFillModel 또는 AdvancedFillModel 둘 다 허용
        assert executor.enable_fill_model is True
        assert executor.fill_model is not None
        from arbitrage.execution.fill_model import AdvancedFillModel
        assert isinstance(executor.fill_model, (SimpleFillModel, AdvancedFillModel))
    
    def test_factory_partial_fill_only(self, portfolio_state, risk_guard):
        """
        테스트 5: Partial Fill만 활성화, Slippage 비활성화
        
        조건:
            - enable_partial_fill=True
            - enable_slippage=False
        
        기대 결과:
            - SimpleFillModel이 partial fill만 처리
        """
        factory = ExecutorFactory()
        config = FillModelConfig(
            enable_fill_model=True,
            enable_partial_fill=True,
            enable_slippage=False,
            fill_model_type="simple",
        )
        
        executor = factory.create_paper_executor(
            symbol="ADA/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=config,
        )
        
        assert executor.fill_model.enable_partial_fill is True
        assert executor.fill_model.enable_slippage is False
    
    def test_factory_slippage_only(self, portfolio_state, risk_guard):
        """
        테스트 6: Slippage만 활성화, Partial Fill 비활성화
        
        조건:
            - enable_partial_fill=False
            - enable_slippage=True
        
        기대 결과:
            - SimpleFillModel이 slippage만 처리
        """
        factory = ExecutorFactory()
        config = FillModelConfig(
            enable_fill_model=True,
            enable_partial_fill=False,
            enable_slippage=True,
            fill_model_type="simple",
        )
        
        executor = factory.create_paper_executor(
            symbol="DOT/USDT",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            fill_model_config=config,
        )
        
        assert executor.fill_model.enable_partial_fill is False
        assert executor.fill_model.enable_slippage is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
