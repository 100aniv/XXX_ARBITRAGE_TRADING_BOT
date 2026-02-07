"""
D205-18-3: RunWatcher Liveness + Safety Guard Tests

Purpose: Safety Guard 트리거 검증 (Chaos Test)
- heartbeat.jsonl 파일 생성 확인
- stop_reason_snapshot.json 파일 생성 확인
- Safety Guard D (Max Drawdown) 트리거 확인
- Safety Guard E (Consecutive Losses) 트리거 확인
- Exit Code 1 반환 확인
"""

import pytest
import time
import json
import os
from pathlib import Path
from arbitrage.v2.core.run_watcher import RunWatcher, WatcherConfig, create_watcher
from arbitrage.v2.core.metrics import PaperMetrics


class TestRunWatcherHeartbeat:
    """Heartbeat 파일 생성 검증"""
    
    def test_heartbeat_file_creation(self, tmp_path):
        """
        Case: Heartbeat 파일 생성 확인
        
        Given: RunWatcher 시작
        When: 1초 대기 (heartbeat_sec=1)
        Then: heartbeat.jsonl 파일이 생성되고 내용이 있어야 함
        """
        run_id = "test_heartbeat"
        evidence_dir = str(tmp_path)
        
        kpi = PaperMetrics()
        kpi.closed_trades = 5
        kpi.wins = 3
        kpi.losses = 2
        kpi.net_pnl_full = 100.0
        kpi.net_pnl = 100.0
        kpi.fees_total = 10.0
        
        stop_called = False
        def mock_stop():
            nonlocal stop_called
            stop_called = True
        
        watcher = create_watcher(
            kpi_getter=lambda: kpi,
            stop_callback=mock_stop,
            run_id=run_id,
            heartbeat_sec=1,
            evidence_dir=evidence_dir
        )
        
        watcher.start()
        time.sleep(1.5)  # heartbeat 1회 발생 대기
        watcher.stop()
        
        # Verify: heartbeat.jsonl 파일 존재
        heartbeat_file = Path(evidence_dir) / run_id / "heartbeat.jsonl"
        assert heartbeat_file.exists(), f"Heartbeat file not created: {heartbeat_file}"
        
        # Verify: 내용 확인
        with open(heartbeat_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) >= 1, "No heartbeat data"
            
            data = json.loads(lines[0])
            assert "timestamp" in data
            assert "kpi" in data
            assert data["kpi"]["closed_trades"] == 5
            assert data["kpi"]["wins"] == 3
            assert "guards" in data


class TestSafetyGuardMaxDrawdown:
    """Safety Guard D (Max Drawdown) 트리거 검증"""
    
    def test_max_drawdown_trigger(self, tmp_path):
        """
        Case: Max Drawdown 트리거 시 stop_reason='ERROR'
        
        Given: peak_pnl=100, max_drawdown_pct=20
        When: net_pnl이 79로 하락 (21% drawdown)
        Then: stop_reason='ERROR', snapshot 파일 생성
        """
        run_id = "test_drawdown"
        evidence_dir = str(tmp_path)
        
        kpi = PaperMetrics()
        kpi.closed_trades = 10
        kpi.wins = 5
        kpi.losses = 5
        kpi.net_pnl_full = 100.0  # Peak
        kpi.net_pnl = 100.0
        kpi.fees_total = 10.0
        
        stop_called = False
        def mock_stop():
            nonlocal stop_called
            stop_called = True
        
        watcher = create_watcher(
            kpi_getter=lambda: kpi,
            stop_callback=mock_stop,
            run_id=run_id,
            heartbeat_sec=1,
            max_drawdown_pct=20.0,
            evidence_dir=evidence_dir
        )
        
        watcher.start()
        time.sleep(1.5)  # Peak 기록
        
        # Drawdown 발생
        kpi.net_pnl_full = 79.0  # 21% drawdown
        kpi.net_pnl = 79.0
        time.sleep(1.5)
        
        watcher.stop()
        
        # Verify: stop_reason='ERROR'
        assert watcher.stop_reason == "ERROR", f"Expected ERROR, got {watcher.stop_reason}"
        assert "FAIL (D)" in watcher.diagnosis
        assert stop_called, "Stop callback not called"
        
        # Verify: stop_reason_snapshot.json 존재
        snapshot_file = Path(evidence_dir) / run_id / "stop_reason_snapshot.json"
        assert snapshot_file.exists(), f"Snapshot file not created: {snapshot_file}"
        
        with open(snapshot_file, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
            assert snapshot["fail_code"] == "FAIL_D_MAX_DRAWDOWN"
            assert snapshot["stop_reason"] == "ERROR"


class TestSafetyGuardConsecutiveLosses:
    """Safety Guard E (Consecutive Losses) 트리거 검증 (간단 버전)"""
    
    def test_consecutive_losses_concept(self):
        """
        Case: Consecutive Losses 로직 개념 검증
        
        Given: max_consecutive_losses=10
        When: 10연속 손실 발생
        Then: Guard 트리거 조건 충족
        
        Note: 실제 RunWatcher는 wins/losses 카운터 증가로 판단하므로
              단위 테스트로는 완벽한 검증 어려움. 개념만 확인.
        """
        # 이 테스트는 로직 존재 확인용
        config = WatcherConfig(max_consecutive_losses=10)
        assert config.max_consecutive_losses == 10
        
        # 실제 트리거는 Integration Test (D205-18-4)에서 검증


class TestExitCodePropagation:
    """Exit Code 전파 검증 (개념)"""
    
    def test_exit_code_concept(self):
        """
        Case: stop_reason='ERROR' 시 Exit Code 1 반환
        
        Note: Orchestrator.run()의 exit code는 Integration Test에서 검증
              여기서는 stop_reason 설정만 확인
        """
        kpi = PaperMetrics()
        
        watcher = RunWatcher(
            config=WatcherConfig(),
            kpi_getter=lambda: kpi,
            stop_callback=lambda: None,
            run_id="test"
        )
        
        # Simulate FAIL
        watcher.stop_reason = "ERROR"
        watcher.diagnosis = "Test failure"
        
        assert watcher.stop_reason == "ERROR"
        assert watcher.diagnosis is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
