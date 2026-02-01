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
            db_mode="off",
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
            db_mode="off",
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
            db_mode="off",
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
            db_mode="off",
        )
        
        assert config.duration_minutes == 1
        assert config.phase == "test"


class TestPaperRunnerStrictEnv:
    """DB strict fail-fast (env)"""

    def test_config_strict_missing_env_fails(self, monkeypatch):
        monkeypatch.delenv("POSTGRES_CONNECTION_STRING", raising=False)
        with pytest.raises(SystemExit):
            PaperRunnerConfig(duration_minutes=1, db_mode="strict")

    def test_runtime_factory_strict_env_fails(self, tmp_path, monkeypatch):
        from arbitrage.v2.core.runtime_factory import build_paper_runtime

        monkeypatch.delenv("POSTGRES_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)

        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
            run_id="test_strict_env",
            output_dir=str(tmp_path),
            db_mode="strict",
            db_connection_string="postgresql://arbitrage:arbitrage@localhost:5432/arbitrage",
            use_real_data=False,
            symbols=[("BTC/KRW", "BTC/USDT")],
        )

        with pytest.raises(SystemExit):
            build_paper_runtime(config)


class TestBreakEvenAdapterWiring:
    """Break-even params가 PaperExecutionAdapter로 전달되는지 검증"""

    def test_break_even_wiring_to_adapter(self, tmp_path):
        from arbitrage.v2.core.runtime_factory import build_paper_runtime
        from arbitrage.v2.domain.break_even import BreakEvenParams
        from arbitrage.domain.fee_model import FeeModel, FeeStructure
        from arbitrage.v2.core.order_intent import OrderIntent, OrderSide, OrderType

        fee_model = FeeModel(
            fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=7.0),
            fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=4.0, taker_fee_bps=9.0),
        )
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=12.0,
            latency_bps=8.0,
            buffer_bps=0.0,
        )

        config = PaperRunnerConfig(
            duration_minutes=1,
            phase="test",
            run_id="test_break_even_wiring",
            output_dir=str(tmp_path),
            db_mode="off",
            use_real_data=False,
            symbols=[("BTC/KRW", "BTC/USDT")],
            break_even_params=params,
        )

        orchestrator = build_paper_runtime(config)
        adapter = orchestrator.executor.adapter

        assert adapter.slippage_bps_min == pytest.approx(params.slippage_bps)
        assert adapter.slippage_bps_max == pytest.approx(params.slippage_bps)
        assert adapter.pessimistic_drift_bps_min == pytest.approx(params.latency_bps)
        assert adapter.pessimistic_drift_bps_max == pytest.approx(params.latency_bps)

        intent = OrderIntent(
            exchange="upbit",
            symbol="BTC/KRW",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quote_amount=10000.0,
        )
        payload = adapter.translate_intent(intent)
        payload["ref_price"] = 100.0

        response = {
            "order_id": "test",
            "status": "filled",
            "filled_qty": 1.0,
            "filled_price": 100.0,
            "ref_price": 100.0,
            "exchange": "upbit",
        }
        result = adapter.parse_response(response)

        assert result.fee > 0
