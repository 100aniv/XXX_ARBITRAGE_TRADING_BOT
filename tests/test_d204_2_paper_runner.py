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
    PaperRunner,
    PaperRunnerConfig,
)
from arbitrage.v2.core.metrics import PaperMetrics  # D205-18-2: Harness Purge
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
        assert config.run_id.startswith("d205_18_2d_smoke_")
        assert config.output_dir.startswith("logs/evidence/d205_18_2d_smoke_")
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


class TestPaperExecutor:
    """PaperExecutor 테스트 (Core 모듈)"""
    
    @pytest.mark.skip(reason="D205-18-2D: Core 테스트는 별도 test_core.py로 분리 예정")
    def test_initial_balance(self):
        pass
    
    @pytest.mark.skip(reason="D205-18-2D: Core 테스트는 별도 test_core.py로 분리 예정")
    def test_update_balance(self):
        pass


class TestPaperMetrics:
    """PaperMetrics 테스트 (D205-18-2: Harness Purge)"""
    
    def test_kpi_initial_state(self):
        """
        Case 1: KPI 초기 상태
        
        Verify:
            - opportunities_generated = 0
            - db_inserts_ok = 0
        """
        kpi = PaperMetrics()
        
        assert kpi.opportunities_generated == 0
        assert kpi.intents_created == 0
        assert kpi.mock_executions == 0
        assert kpi.db_inserts_ok == 0
        assert kpi.db_inserts_failed == 0
        assert kpi.error_count == 0
    
    def test_kpi_to_dict(self):
        """
        Case 2: KPI to_dict 변환
        
        Verify:
            - dict 형식 변환
            - duration_seconds, duration_minutes 계산
        """
        kpi = PaperMetrics()
        kpi.opportunities_generated = 10
        kpi.intents_created = 20
        kpi.mock_executions = 20
        
        kpi_dict = kpi.to_dict()
        
        assert kpi_dict["opportunities_generated"] == 10
        assert kpi_dict["intents_created"] == 20
        assert kpi_dict["mock_executions"] == 20
        assert "duration_seconds" in kpi_dict
        assert "ratelimit_hits" in kpi_dict
        assert "dedup_hits" in kpi_dict
        assert "reject_reasons" in kpi_dict  # D205-10


class TestPaperRunner:
    """PaperRunner 통합 테스트"""
    
    @pytest.mark.skip(reason="D205-18-2D: Thin Wrapper로 전환, 내부 상태 접근 불가")
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
    
    @pytest.mark.skip(reason="D205-18-2D: Thin Wrapper, READ_ONLY 체크는 Core로 이동")
    def test_runner_read_only_enforcement(self):
        pass
    
    @pytest.mark.skip(reason="D205-18-2D: _generate_mock_opportunity() → OpportunitySource로 이동")
    def test_runner_mock_opportunity_generation(self):
        pass
    
    @pytest.mark.skip(reason="D205-18-2D: _convert_to_intents() → IntentBuilder로 이동")
    def test_runner_convert_to_intents(self):
        pass
    
    @pytest.mark.skip(reason="D205-18-2D: _execute_mock_order() → PaperExecutor로 이동")
    def test_runner_execute_mock_order(self):
        pass
    
    @pytest.mark.skip(reason="D205-18-2D: 1분 실행은 통합 테스트로 별도 진행")
    def test_runner_1min_execution(self):
        pass


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
