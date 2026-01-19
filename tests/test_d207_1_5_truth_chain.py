"""
D207-1-5: StopReason Single Truth Chain Tests

Purpose:
- T1: stop_reason_consistency - 모든 Artifact에 동일한 stop_reason 기록 검증
- T2: manifest_completeness - manifest.json 완전성 검증

Author: D207-1-5 Gate Wiring & Evidence Atomicity
Date: 2026-01-19
"""

import pytest
from unittest.mock import Mock

from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.engine_report import generate_engine_report


class TestStopReasonConsistency:
    """T1: stop_reason_consistency"""
    
    def test_model_anomaly_stop_reason(self):
        """MODEL_ANOMALY 발생 시 stop_reason 기록"""
        kpi = PaperMetrics()
        kpi.stop_reason = "MODEL_ANOMALY"
        kpi.stop_message = "winrate >= 95%"
        kpi.closed_trades = 100
        kpi.winrate_pct = 100.0
        kpi.fees = 1000.0
        
        config = Mock()
        config.mode = "paper"
        config.exchanges = ["upbit", "binance"]
        config.symbols = ["BTC"]
        
        report = generate_engine_report(
            run_id="test_run_001",
            config=config,
            kpi=kpi,
            warning_counts={"warning_count": 0, "error_count": 0},
            wallclock_duration=120.0,
            expected_duration=120.0,
            db_counts=None,
            exit_code=1,
            stop_reason="MODEL_ANOMALY",
            stop_message="winrate >= 95%"
        )
        
        assert report["stop_reason"] == "MODEL_ANOMALY"
        assert report["stop_message"] == "winrate >= 95%"
        assert report["gate_validation"]["exit_code"] == 1
        assert report["status"] == "FAIL"
        
        kpi_dict = kpi.to_dict()
        assert kpi_dict["stop_reason"] == "MODEL_ANOMALY"
    
    def test_time_reached_on_normal_exit(self):
        """정상 종료 시 TIME_REACHED"""
        kpi = PaperMetrics()
        kpi.stop_reason = "TIME_REACHED"
        kpi.stop_message = "Normal completion"
        
        config = Mock()
        config.mode = "paper"
        config.exchanges = ["upbit", "binance"]
        config.symbols = ["BTC"]
        
        report = generate_engine_report(
            run_id="test_run_002",
            config=config,
            kpi=kpi,
            warning_counts={"warning_count": 0, "error_count": 0},
            wallclock_duration=120.0,
            expected_duration=120.0,
            db_counts=None,
            exit_code=0,
            stop_reason="TIME_REACHED",
            stop_message="Normal completion"
        )
        
        assert report["stop_reason"] == "TIME_REACHED"
        assert report["gate_validation"]["exit_code"] == 0
        assert report["status"] == "PASS"


class TestDbIntegrity:
    """D207-1-4: db_integrity.enabled 필드 검증"""
    
    def test_db_disabled_in_paper_mode(self):
        """Paper mode에서 DB 비활성"""
        kpi = PaperMetrics()
        kpi.closed_trades = 100
        
        config = Mock()
        config.mode = "paper"
        config.exchanges = ["upbit", "binance"]
        config.symbols = ["BTC"]
        
        report = generate_engine_report(
            run_id="test_run_003",
            config=config,
            kpi=kpi,
            warning_counts={"warning_count": 0, "error_count": 0},
            wallclock_duration=120.0,
            expected_duration=120.0,
            db_counts={"total_inserts": 0, "failed_inserts": 0},
            exit_code=0,
            stop_reason="TIME_REACHED"
        )
        
        assert report["db_integrity"]["enabled"] == False
        assert "Paper mode" in report["db_integrity"]["reason"]


class TestKpiStopReasonFields:
    """KPI에 stop_reason 필드 검증"""
    
    def test_kpi_has_stop_reason_fields(self):
        """PaperMetrics에 stop_reason 필드 존재"""
        kpi = PaperMetrics()
        
        assert hasattr(kpi, 'stop_reason')
        assert hasattr(kpi, 'stop_message')
        assert kpi.stop_reason == ""
        assert kpi.stop_message == ""
    
    def test_kpi_to_dict_includes_stop_reason(self):
        """to_dict()에 stop_reason 포함"""
        kpi = PaperMetrics()
        kpi.stop_reason = "MODEL_ANOMALY"
        kpi.stop_message = "Test message"
        
        kpi_dict = kpi.to_dict()
        
        assert "stop_reason" in kpi_dict
        assert "stop_message" in kpi_dict
        assert kpi_dict["stop_reason"] == "MODEL_ANOMALY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
