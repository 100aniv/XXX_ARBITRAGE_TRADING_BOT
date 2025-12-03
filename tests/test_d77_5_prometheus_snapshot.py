# -*- coding: utf-8 -*-
"""
D77-5: Prometheus 스냅샷 저장 테스트
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

from arbitrage.monitoring.prometheus_snapshot import save_prometheus_snapshot


class TestPrometheusSnapshot:
    """Prometheus 스냅샷 저장 기능 테스트"""
    
    @pytest.fixture
    def temp_dir(self):
        """임시 디렉토리 생성"""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # 정리
        if temp_path.exists():
            shutil.rmtree(temp_path, ignore_errors=True)
    
    def test_save_snapshot_success(self, temp_dir):
        """정상 케이스: 메트릭 스냅샷 저장 성공"""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain; version=0.0.4"}
        mock_response.text = """# HELP arb_topn_pnl_total Total PnL in USD
# TYPE arb_topn_pnl_total gauge
arb_topn_pnl_total{env="paper",strategy="topn_arb",universe="top20"} 3375.0
# HELP arb_topn_win_rate Win rate percentage (0-100)
# TYPE arb_topn_win_rate gauge
arb_topn_win_rate{env="paper",strategy="topn_arb",universe="top20"} 100.0
"""
        
        with patch('requests.get', return_value=mock_response):
            snapshot_path = save_prometheus_snapshot(
                run_id="test_run",
                output_dir=temp_dir,
                metrics_url="http://localhost:9100/metrics",
            )
        
        # 검증
        assert snapshot_path is not None
        assert snapshot_path.exists()
        assert snapshot_path.name == "prometheus_metrics.prom"
        
        # 파일 내용 확인
        content = snapshot_path.read_text(encoding='utf-8')
        assert "arb_topn_pnl_total" in content
        assert "arb_topn_win_rate" in content
        assert "3375.0" in content
    
    def test_save_snapshot_non_200_status(self, temp_dir):
        """비정상 케이스: Non-200 status code"""
        mock_response = Mock()
        mock_response.status_code = 404
        
        with patch('requests.get', return_value=mock_response):
            snapshot_path = save_prometheus_snapshot(
                run_id="test_run",
                output_dir=temp_dir,
                metrics_url="http://localhost:9100/metrics",
            )
        
        # 검증: None 반환
        assert snapshot_path is None
    
    def test_save_snapshot_empty_body(self, temp_dir):
        """비정상 케이스: Empty response body"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.text = ""
        
        with patch('requests.get', return_value=mock_response):
            snapshot_path = save_prometheus_snapshot(
                run_id="test_run",
                output_dir=temp_dir,
                metrics_url="http://localhost:9100/metrics",
            )
        
        # 검증: None 반환
        assert snapshot_path is None
    
    def test_save_snapshot_connection_error(self, temp_dir):
        """비정상 케이스: Connection error"""
        import requests
        
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Connection refused")):
            snapshot_path = save_prometheus_snapshot(
                run_id="test_run",
                output_dir=temp_dir,
                metrics_url="http://localhost:9100/metrics",
            )
        
        # 검증: None 반환 (예외를 던지지 않음)
        assert snapshot_path is None
    
    def test_save_snapshot_timeout(self, temp_dir):
        """비정상 케이스: Timeout"""
        import requests
        
        with patch('requests.get', side_effect=requests.exceptions.Timeout("Request timeout")):
            snapshot_path = save_prometheus_snapshot(
                run_id="test_run",
                output_dir=temp_dir,
                metrics_url="http://localhost:9100/metrics",
                timeout=5,
            )
        
        # 검증: None 반환
        assert snapshot_path is None
    
    def test_save_snapshot_creates_output_dir(self, temp_dir):
        """출력 디렉토리가 없는 경우 자동 생성"""
        output_dir = temp_dir / "subdir1" / "subdir2"
        assert not output_dir.exists()
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.text = "# Test metrics\ntest_metric 1.0"
        
        with patch('requests.get', return_value=mock_response):
            snapshot_path = save_prometheus_snapshot(
                run_id="test_run",
                output_dir=output_dir,
                metrics_url="http://localhost:9100/metrics",
            )
        
        # 검증: 디렉토리 생성됨
        assert output_dir.exists()
        assert snapshot_path is not None
        assert snapshot_path.exists()
    
    def test_save_snapshot_logs_metric_count(self, temp_dir, caplog):
        """메트릭 개수를 로그에 기록"""
        import logging
        caplog.set_level(logging.INFO)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "text/plain"}
        mock_response.text = """# Comment line
metric1 1.0
metric2 2.0
metric3 3.0
"""
        
        with patch('requests.get', return_value=mock_response):
            snapshot_path = save_prometheus_snapshot(
                run_id="test_run",
                output_dir=temp_dir,
                metrics_url="http://localhost:9100/metrics",
            )
        
        # 검증: 로그에 메트릭 개수 포함
        assert snapshot_path is not None
        assert "~3 metrics" in caplog.text
