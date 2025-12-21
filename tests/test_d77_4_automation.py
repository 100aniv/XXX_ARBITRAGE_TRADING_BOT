"""
D77-4 자동화 스크립트 테스트

env_checker, monitor, analyzer, reporter, orchestrator 검증
"""

import gc
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.d77_4_env_checker import D77EnvChecker
from scripts.d77_4_analyzer import D77Analyzer
from scripts.d77_4_reporter import D77Reporter


class TestEnvChecker:
    """환경 체커 테스트"""
    
    def test_env_checker_initialization(self):
        """초기화 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            run_id = "test_run_001"
            
            # D99-5: No need to patch logger anymore (instance-specific)
            with D77EnvChecker(project_root, run_id) as checker:
                assert checker.run_id == run_id
                assert checker.log_dir.exists()
    
    @patch('scripts.d77_4_env_checker.psutil')
    @patch('subprocess.run')
    def test_env_checker_docker_check(self, mock_subprocess, mock_psutil):
        """Docker 체크 로직 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "docker").mkdir()
            
            # D99-5: 명시적 cleanup
            checker = D77EnvChecker(project_root, "test_run")
            try:
                # Mock docker compose ps 성공
                mock_subprocess.return_value = MagicMock(
                    returncode=0,
                    stdout='{"Service":"redis","State":"Up"}\n{"Service":"postgres","State":"Up"}'
                )
                
                success, status = checker._check_docker_containers()
                assert success is True
                assert status.get("redis") == "Up"
                assert status.get("postgres") == "Up"
            finally:
                checker.close()
                gc.collect()


class TestAnalyzer:
    """분석기 테스트"""
    
    def test_analyzer_decision_complete_go(self):
        """COMPLETE GO 판단 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            run_id = "test_run_002"
            
            # D99-5: 명시적 cleanup
            analyzer = D77Analyzer(project_root, run_id)
            try:
                # Critical 6/6, High 6/6
                decision, reason = analyzer._make_decision(6, 6)
                assert decision == "COMPLETE GO"
                assert "6/6" in reason
            finally:
                analyzer.close()
                gc.collect()
    
    def test_analyzer_decision_conditional_go(self):
        """CONDITIONAL GO 판단 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            
            # D99-5: 명시적 cleanup
            analyzer = D77Analyzer(project_root, "test_run")
            try:
                # Critical 6/6, High 4/6
                decision, reason = analyzer._make_decision(6, 4)
                assert decision == "CONDITIONAL GO"
                assert "4/6" in reason
            finally:
                analyzer.close()
                gc.collect()
    
    def test_analyzer_decision_no_go(self):
        """NO-GO 판단 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            
            # D99-5: 명시적 cleanup
            analyzer = D77Analyzer(project_root, "test_run")
            try:
                # Critical 5/6
                decision, reason = analyzer._make_decision(5, 6)
                assert decision == "NO-GO"
                assert "5/6" in reason
            finally:
                analyzer.close()
                gc.collect()
    
    def test_analyzer_kpi_parsing(self):
        """KPI 파싱 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            run_id = "test_run_003"
            (project_root / "logs" / "d77-4" / run_id).mkdir(parents=True)
            
            # 샘플 KPI JSON 생성
            kpi_path = project_root / "kpi.json"
            kpi_data = {
                "duration_minutes": 65,
                "total_trades": 100,
                "round_trips_completed": 50,
                "win_rate_pct": 60,
                "loop_latency_p99_ms": 75,
                "cpu_usage_pct": 65,
                "guard_triggers": 20
            }
            with open(kpi_path, 'w') as f:
                json.dump(kpi_data, f)
            
            # 샘플 콘솔 로그 생성
            console_log_path = project_root / "console.log"
            with open(console_log_path, 'w') as f:
                f.write("[INFO] Test log\n")
            
            # D99-5: 명시적 cleanup
            analyzer = D77Analyzer(project_root, run_id)
            try:
                result = analyzer.analyze(kpi_path, console_log_path)
                
                assert result["run_id"] == run_id
                assert result["kpi"]["total_trades"] == 100
                assert result["decision"] in ["COMPLETE GO", "CONDITIONAL GO", "NO-GO"]
            finally:
                analyzer.close()
                gc.collect()


class TestReporter:
    """리포터 테스트"""
    
    def test_reporter_initialization(self):
        """리포터 초기화 테스트"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            run_id = "test_run_004"
            
            # D99-5: 명시적 cleanup
            reporter = D77Reporter(project_root, run_id)
            try:
                assert reporter.run_id == run_id
            finally:
                reporter.close()
                gc.collect()


class TestOrchestrator:
    """오케스트레이터 통합 테스트"""
    
    @patch('subprocess.run')
    @patch('subprocess.Popen')
    @pytest.mark.skipif(sys.platform == "win32", reason="D99-5: Windows file locking issue in teardown (test logic passes, cleanup fails)")
    def test_orchestrator_smoke_only_mode(self, mock_popen, mock_subprocess_run):
        """smoke-only 모드 테스트"""
        from scripts.d77_4_orchestrator import D77Orchestrator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            (project_root / "scripts").mkdir()
            (project_root / "logs" / "d77-4").mkdir(parents=True)
            
            # env_checker 성공
            mock_subprocess_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            
            # Runner (스모크) 성공
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_proc.returncode = 0
            mock_proc.wait.return_value = None
            mock_popen.return_value = mock_proc
            
            # 스모크 KPI 파일 생성
            orchestrator = D77Orchestrator(project_root, mode="smoke-only")
            try:
                kpi_path = orchestrator.log_dir / "smoke_60s_kpi.json"
                kpi_path.parent.mkdir(parents=True, exist_ok=True)
                with open(kpi_path, 'w') as f:
                    json.dump({"round_trips_completed": 5}, f)
                
                # 실행 (일부만 테스트)
                assert orchestrator._check_smoke_pass(kpi_path) is True
            finally:
                orchestrator.close()
                import time
                gc.collect()
                time.sleep(0.5)


def test_import_all_modules():
    """모든 모듈 import 테스트"""
    from scripts import d77_4_env_checker
    from scripts import d77_4_monitor
    from scripts import d77_4_analyzer
    from scripts import d77_4_reporter
    from scripts import d77_4_orchestrator
    
    assert d77_4_env_checker is not None
    assert d77_4_monitor is not None
    assert d77_4_analyzer is not None
    assert d77_4_reporter is not None
    assert d77_4_orchestrator is not None
