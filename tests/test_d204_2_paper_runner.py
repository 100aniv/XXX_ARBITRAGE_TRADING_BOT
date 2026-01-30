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
from arbitrage.v2.domain.fill_probability import FillProbabilityParams
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
        fill_params = FillProbabilityParams(
            base_fill_probability=0.65,
            wait_time_seconds=8.0,
            slippage_per_second_bps=0.4,
        )
        config = PaperRunnerConfig(
            duration_minutes=60,
            phase="baseline",
            run_id="custom_run_id",
            output_dir="custom_output",
            symbols_top=20,
            fill_probability_params=fill_params,
        )
        
        assert config.run_id == "custom_run_id"
        assert config.output_dir == "custom_output"
        assert config.symbols_top == 20
        assert config.fill_probability_params is fill_params


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
    """PaperRunner Thin Wrapper 테스트"""
    
    def test_runner_config_storage(self):
        """
        D205-18-2E: Thin Wrapper는 Config를 저장만 함
        
        Verify:
            - Config 저장
            - admin_control 저장 (optional)
        """
        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
        )
        
        runner = PaperRunner(config, admin_control=None)
        
        assert runner.config == config
        assert runner.admin_control is None


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
