# -*- coding: utf-8 -*-
"""
D82-0: D77 Runner + Real PaperExecutor + Fill Model 통합 테스트

목적:
    Runner가 Settings + ExecutorFactory + PaperExecutor + Fill Model을
    정상적으로 통합하여 동작하는지 검증.

Author: arbitrage-lite project
Date: 2025-12-04
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch
import os

from scripts.run_d77_0_topn_arbitrage_paper import D77PAPERRunner, MockTrade
from arbitrage.domain.topn_provider import TopNMode
from arbitrage.config.settings import Settings, FillModelConfig


class TestD82RunnerExecutorIntegration:
    """D82-0: Runner + PaperExecutor + Fill Model 통합 테스트"""
    
    @pytest.fixture
    def mock_env_paper(self):
        """PAPER 환경변수 mock"""
        with patch.dict(os.environ, {
            "ARBITRAGE_ENV": "paper",
            "FILL_MODEL_ENABLE": "true",
            "FILL_MODEL_PARTIAL_ENABLE": "true",
            "FILL_MODEL_SLIPPAGE_ENABLE": "true",
            "FILL_MODEL_SLIPPAGE_ALPHA": "0.0001",
            "UPBIT_ACCESS_KEY": "test_key",
            "UPBIT_SECRET_KEY": "test_secret",
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        }, clear=True):
            yield
    
    def test_runner_initialization_with_settings(self, mock_env_paper):
        """
        테스트 1: Runner 초기화 시 Settings + ExecutorFactory 정상 로드
        
        기대 결과:
            - Settings.fill_model.enable_fill_model=True
            - ExecutorFactory 인스턴스 존재
            - TradeLogger 인스턴스 존재
        """
        runner = D77PAPERRunner(
            universe_mode=TopNMode.TOP_20,
            duration_minutes=0.01,  # 매우 짧은 시간
            config_path="configs/paper/topn_arb_baseline.yaml",
            data_source="mock",
        )
        
        # Settings 로드 확인
        assert runner.settings is not None
        assert runner.settings.fill_model.enable_fill_model is True
        
        # ExecutorFactory 확인
        assert runner.executor_factory is not None
        
        # TradeLogger 확인
        assert runner.trade_logger is not None
        
        # PortfolioState & RiskGuard 확인
        assert runner.portfolio_state is not None
        assert runner.risk_guard is not None
    
    def test_mock_trade_structure(self):
        """
        테스트 2: MockTrade가 PaperExecutor 호환 필드를 가지는지 확인
        
        기대 결과:
            - trade_id, buy_exchange, sell_exchange, quantity, buy_price, sell_price 필드 존재
        """
        trade = MockTrade(
            trade_id="TEST_001",
            buy_exchange="binance",
            sell_exchange="upbit",
            quantity=0.1,
            buy_price=50000.0,
            sell_price=50100.0,
        )
        
        assert trade.trade_id == "TEST_001"
        assert trade.buy_exchange == "binance"
        assert trade.sell_exchange == "upbit"
        assert trade.quantity == 0.1
        assert trade.buy_price == 50000.0
        assert trade.sell_price == 50100.0
    
    def test_executor_creation_lazy_initialization(self, mock_env_paper):
        """
        테스트 3: Executor Lazy Initialization 동작 확인
        
        기대 결과:
            - _get_or_create_executor() 호출 시 PaperExecutor 생성
            - 같은 symbol에 대해 재호출 시 캐싱된 인스턴스 반환
        """
        runner = D77PAPERRunner(
            universe_mode=TopNMode.TOP_20,
            duration_minutes=0.01,
            config_path="configs/paper/topn_arb_baseline.yaml",
            data_source="mock",
        )
        
        # 첫 번째 호출: 새 인스턴스 생성
        executor1 = runner._get_or_create_executor("BTC/USDT")
        assert executor1 is not None
        assert "BTC/USDT" in runner.executors
        
        # 두 번째 호출: 캐싱된 인스턴스 반환
        executor2 = runner._get_or_create_executor("BTC/USDT")
        assert executor2 is executor1  # 같은 인스턴스
        
        # 다른 symbol: 새 인스턴스 생성
        executor3 = runner._get_or_create_executor("ETH/USDT")
        assert executor3 is not executor1
        assert "ETH/USDT" in runner.executors
    
    def test_kpi_metrics_has_fill_model_fields(self, mock_env_paper):
        """
        테스트 4: KPI metrics에 Fill Model 필드가 존재하는지 확인
        
        기대 결과:
            - avg_buy_slippage_bps, avg_sell_slippage_bps 존재
            - avg_buy_fill_ratio, avg_sell_fill_ratio 존재
            - partial_fills_count, failed_fills_count 존재
        """
        runner = D77PAPERRunner(
            universe_mode=TopNMode.TOP_20,
            duration_minutes=0.01,
            config_path="configs/paper/topn_arb_baseline.yaml",
            data_source="mock",
        )
        
        assert "avg_buy_slippage_bps" in runner.metrics
        assert "avg_sell_slippage_bps" in runner.metrics
        assert "avg_buy_fill_ratio" in runner.metrics
        assert "avg_sell_fill_ratio" in runner.metrics
        assert "partial_fills_count" in runner.metrics
        assert "failed_fills_count" in runner.metrics
        
        # 기본값 확인
        assert runner.metrics["avg_buy_slippage_bps"] == 0.0
        assert runner.metrics["avg_sell_slippage_bps"] == 0.0
        assert runner.metrics["avg_buy_fill_ratio"] == 1.0
        assert runner.metrics["avg_sell_fill_ratio"] == 1.0
        assert runner.metrics["partial_fills_count"] == 0
        assert runner.metrics["failed_fills_count"] == 0
    
    @pytest.mark.asyncio
    async def test_runner_short_execution_no_crash(self, mock_env_paper):
        """
        테스트 5: 매우 짧은 시간(0.1분=6초) Runner 실행 시 크래시 없이 동작하는지 확인
        
        조건:
            - duration_minutes=0.1 (6초)
            - data_source=mock
        
        기대 결과:
            - 크래시 없이 정상 실행
            - metrics 반환
            - session_id 존재
        """
        runner = D77PAPERRunner(
            universe_mode=TopNMode.TOP_20,
            duration_minutes=0.1,  # 6초
            config_path="configs/paper/topn_arb_baseline.yaml",
            data_source="mock",
            monitoring_enabled=False,
        )
        
        # 실행
        metrics = await runner.run()
        
        # 기본 검증
        assert metrics is not None
        assert "session_id" in metrics
        assert "total_trades" in metrics
        assert "win_rate_pct" in metrics
        
        # Fill Model KPI 필드 존재 확인
        assert "avg_buy_slippage_bps" in metrics
        assert "partial_fills_count" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
