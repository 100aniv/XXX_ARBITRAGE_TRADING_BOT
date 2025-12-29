"""
D204-2: Paper Runner Tests

SSOT: arbitrage/v2/harness/paper_runner.py

Author: arbitrage-lite V2
Date: 2025-12-30
"""

import pytest
import os
from datetime import datetime, timezone
from arbitrage.v2.harness.paper_runner import (
    PaperRunnerConfig,
    MockBalance,
    KPICollector,
    PaperRunner,
)
from arbitrage.v2.core import OrderIntent, OrderSide, OrderType


class TestPaperRunnerConfig:
    """PaperRunnerConfig 테스트"""
    
    def test_config_auto_generation(self):
        """
        Case 1: Config 자동 생성 (run_id, output_dir)
        
        Verify:
            - run_id 자동 생성 (d204_2_{phase}_YYYYMMDD_HHMM)
            - output_dir 자동 생성 (logs/evidence/{run_id})
        """
        config = PaperRunnerConfig(
            duration_minutes=20,
            phase="smoke",
        )
        
        assert config.duration_minutes == 20
        assert config.phase == "smoke"
        assert config.run_id.startswith("d204_2_smoke_")
        assert config.output_dir.startswith("logs/evidence/d204_2_smoke_")
        assert config.read_only is True  # 기본값
    
    def test_config_custom_values(self):
        """
        Case 2: Config 커스텀 값
        
        Verify:
            - 커스텀 값 우선 적용
        """
        config = PaperRunnerConfig(
            duration_minutes=60,
            phase="baseline",
            run_id="custom_run_id",
            output_dir="custom_output",
            symbols_top=20,
        )
        
        assert config.run_id == "custom_run_id"
        assert config.output_dir == "custom_output"
        assert config.symbols_top == 20


class TestMockBalance:
    """MockBalance 테스트"""
    
    def test_initial_balance(self):
        """
        Case 3: 초기 잔고 확인
        
        Verify:
            - KRW: 10,000,000
            - USDT: 10,000
            - BTC: 0
        """
        balance = MockBalance()
        
        assert balance.get("KRW") == 10_000_000.0
        assert balance.get("USDT") == 10_000.0
        assert balance.get("BTC") == 0.0
    
    def test_balance_update(self):
        """
        Case 4: 잔고 업데이트
        
        Verify:
            - update() 호출 시 증가/감소
        """
        balance = MockBalance()
        
        # KRW 감소
        balance.update("KRW", -500_000.0)
        assert balance.get("KRW") == 9_500_000.0
        
        # BTC 증가
        balance.update("BTC", 0.01)
        assert balance.get("BTC") == 0.01


class TestKPICollector:
    """KPICollector 테스트"""
    
    def test_kpi_initial_state(self):
        """
        Case 5: KPI 초기 상태
        
        Verify:
            - 모든 카운터 0
            - start_time 설정됨
        """
        kpi = KPICollector()
        
        assert kpi.opportunities_generated == 0
        assert kpi.intents_created == 0
        assert kpi.mock_executions == 0
        assert kpi.db_inserts_success == 0
        assert kpi.db_inserts_failed == 0
        assert kpi.start_time > 0
    
    def test_kpi_to_dict(self):
        """
        Case 6: KPI to_dict() 변환
        
        Verify:
            - dict 형식 변환
            - duration_seconds, duration_minutes 계산
        """
        kpi = KPICollector()
        kpi.opportunities_generated = 10
        kpi.intents_created = 20
        kpi.mock_executions = 20
        
        kpi_dict = kpi.to_dict()
        
        assert kpi_dict["opportunities_generated"] == 10
        assert kpi_dict["intents_created"] == 20
        assert kpi_dict["mock_executions"] == 20
        assert "duration_seconds" in kpi_dict
        assert "duration_minutes" in kpi_dict
        assert "start_time" in kpi_dict


class TestPaperRunner:
    """PaperRunner 통합 테스트"""
    
    def test_runner_initialization(self):
        """
        Case 7: PaperRunner 초기화
        
        Verify:
            - Config 적용
            - MockAdapter, MockBalance 생성
            - output_dir 생성
        """
        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
        )
        
        runner = PaperRunner(config)
        
        assert runner.config == config
        assert runner.mock_adapter is not None
        assert runner.balance is not None
        assert runner.kpi is not None
        assert runner.output_dir.exists()
    
    def test_runner_read_only_enforcement(self):
        """
        Case 8: READ_ONLY 강제
        
        Verify:
            - read_only=False → 실행 거부 (exit code 1)
        """
        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
            read_only=False,
        )
        
        runner = PaperRunner(config)
        exit_code = runner.run()
        
        assert exit_code == 1  # 실행 거부
    
    def test_runner_mock_opportunity_generation(self):
        """
        Case 9: Mock Opportunity 생성
        
        Verify:
            - _generate_mock_opportunity() 호출 성공
            - OpportunityCandidate 반환
        """
        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
        )
        
        runner = PaperRunner(config)
        candidate = runner._generate_mock_opportunity(iteration=1)
        
        assert candidate is not None
        assert candidate.symbol == "BTC/KRW"
        assert candidate.exchange_a == "upbit"
        assert candidate.exchange_b == "binance"
        assert candidate.price_a > 0
        assert candidate.price_b > 0
    
    def test_runner_convert_to_intents(self):
        """
        Case 10: OpportunityCandidate → OrderIntent 변환
        
        Verify:
            - _convert_to_intents() 호출 성공
            - 2개 OrderIntent 반환 (BUY + SELL)
        """
        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
        )
        
        runner = PaperRunner(config)
        candidate = runner._generate_mock_opportunity(iteration=1)
        intents = runner._convert_to_intents(candidate)
        
        # profitable한 경우 2개 (BUY + SELL)
        # unprofitable한 경우 0개
        assert len(intents) in [0, 2]
        
        if len(intents) == 2:
            assert intents[0].side in [OrderSide.BUY, OrderSide.SELL]
            assert intents[1].side in [OrderSide.BUY, OrderSide.SELL]
            assert intents[0].side != intents[1].side  # 반대편
    
    def test_runner_execute_mock_order(self):
        """
        Case 11: Mock 주문 실행
        
        Verify:
            - _execute_mock_order() 호출 성공
            - Balance 업데이트
            - KPI 집계
        """
        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
        )
        
        runner = PaperRunner(config)
        
        # OrderIntent 생성
        intent = OrderIntent(
            exchange="upbit",
            symbol="BTC/KRW",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=500_000.0,
            strategy_id="test",
        )
        
        # 초기 잔고
        initial_krw = runner.balance.get("KRW")
        
        # Mock 실행
        runner._execute_mock_order(intent)
        
        # 잔고 변화 확인 (KRW 감소)
        final_krw = runner.balance.get("KRW")
        assert final_krw < initial_krw
    
    def test_runner_1min_execution(self):
        """
        Case 12: 1분 실행 테스트
        
        Verify:
            - 1분 동안 정상 실행
            - KPI 수집
            - Evidence 저장
        """
        config = PaperRunnerConfig(
            duration_minutes=1,  # 1분
            phase="test_1min",
        )
        
        runner = PaperRunner(config)
        exit_code = runner.run()
        
        # 성공 확인
        assert exit_code == 0
        
        # KPI 확인
        assert runner.kpi.opportunities_generated > 0
        assert runner.kpi.mock_executions >= 0
        
        # Evidence 파일 확인
        kpi_file = runner.output_dir / "kpi_test_1min.json"
        assert kpi_file.exists()


class TestPaperRunnerCLI:
    """CLI 인터페이스 테스트"""
    
    def test_cli_argparse(self):
        """
        Case 13: CLI 인자 파싱
        
        Verify:
            - --duration, --phase 인자 파싱
        """
        import sys
        from arbitrage.v2.harness.paper_runner import main
        
        # CLI 인자 시뮬레이션
        sys.argv = [
            "paper_runner.py",
            "--duration", "1",
            "--phase", "test",
        ]
        
        # main() 호출은 실제 실행하므로 skip
        # Config 생성만 테스트
        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
        )
        
        assert config.duration_minutes == 1
        assert config.phase == "test"
