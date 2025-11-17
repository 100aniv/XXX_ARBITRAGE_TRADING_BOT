# -*- coding: utf-8 -*-
"""
D27 Real-time Monitoring & Health Status Tests

모니터링 모듈 및 watch_status.py 테스트.
"""

import pytest
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

from arbitrage.monitoring import (
    LiveStatusMonitor,
    TuningStatusMonitor,
    LiveStatusSnapshot,
    TuningStatusSnapshot
)
from arbitrage.state_manager import StateManager


class TestLiveStatusSnapshot:
    """LiveStatusSnapshot 테스트"""
    
    def test_live_status_snapshot_creation(self):
        """LiveStatusSnapshot 생성"""
        snapshot = LiveStatusSnapshot(
            mode="paper",
            env="docker",
            live_enabled=False,
            live_armed=False,
            last_heartbeat=None,
            trades_total=5,
            trades_today=2,
            safety_violations_total=0,
            circuit_breaker_triggers_total=0,
            total_balance=1000000.0,
            available_balance=900000.0,
            total_position_value=100000.0
        )
        
        assert snapshot.mode == "paper"
        assert snapshot.env == "docker"
        assert snapshot.trades_total == 5
        assert snapshot.total_balance == 1000000.0
        assert snapshot.timestamp is not None


class TestTuningStatusSnapshot:
    """TuningStatusSnapshot 테스트"""
    
    def test_tuning_status_snapshot_creation(self):
        """TuningStatusSnapshot 생성"""
        snapshot = TuningStatusSnapshot(
            session_id="session-123",
            total_iterations=10,
            completed_iterations=5,
            workers=["main", "worker-1"],
            metrics_keys=["pnl", "trades"],
            last_update=datetime.now()
        )
        
        assert snapshot.session_id == "session-123"
        assert snapshot.total_iterations == 10
        assert snapshot.completed_iterations == 5
        assert snapshot.progress_pct == 50.0
    
    def test_tuning_status_progress_pct(self):
        """진행률 계산"""
        snapshot = TuningStatusSnapshot(
            session_id="session-123",
            total_iterations=4,
            completed_iterations=1,
            workers=[],
            metrics_keys=[],
            last_update=None
        )
        
        assert snapshot.progress_pct == 25.0


class TestLiveStatusMonitor:
    """LiveStatusMonitor 테스트"""
    
    def test_live_status_monitor_creation(self):
        """LiveStatusMonitor 생성"""
        with patch('arbitrage.monitoring.StateManager'):
            monitor = LiveStatusMonitor(
                mode="paper",
                env="docker"
            )
            
            assert monitor.mode == "paper"
            assert monitor.env == "docker"
    
    def test_load_snapshot_with_mocked_state_manager(self):
        """StateManager 모킹으로 스냅샷 로드"""
        mock_state_manager = MagicMock()
        
        # 포트폴리오 상태
        mock_state_manager.get_portfolio_state.return_value = {
            'total_balance': '1000000.0',
            'available_balance': '900000.0',
            'total_position_value': '100000.0'
        }
        
        # 통계
        mock_state_manager.get_stat.side_effect = lambda x: {
            'trades_total': 5,
            'trades_today': 2,
            'safety_violations_total': 0,
            'circuit_breaker_triggers_total': 0,
            'live_enabled': 0,
            'live_armed': 0
        }.get(x, 0)
        
        # 하트비트
        mock_state_manager.get_heartbeat.return_value = datetime.now().isoformat()
        
        monitor = LiveStatusMonitor(
            mode="paper",
            env="docker",
            state_manager=mock_state_manager
        )
        
        snapshot = monitor.load_snapshot()
        
        assert snapshot.mode == "paper"
        assert snapshot.env == "docker"
        assert snapshot.trades_total == 5
        assert snapshot.total_balance == 1000000.0
    
    def test_load_snapshot_with_missing_data(self):
        """데이터 누락 시 처리"""
        mock_state_manager = MagicMock()
        mock_state_manager.get_portfolio_state.return_value = None
        mock_state_manager.get_stat.return_value = 0
        mock_state_manager.get_heartbeat.return_value = None
        
        monitor = LiveStatusMonitor(
            mode="paper",
            env="docker",
            state_manager=mock_state_manager
        )
        
        snapshot = monitor.load_snapshot()
        
        assert snapshot.total_balance is None
        assert snapshot.trades_total == 0


class TestTuningStatusMonitor:
    """TuningStatusMonitor 테스트"""
    
    def test_tuning_status_monitor_creation(self):
        """TuningStatusMonitor 생성"""
        with patch('arbitrage.monitoring.StateManager'):
            monitor = TuningStatusMonitor(
                session_id="session-123",
                total_iterations=5,
                env="docker",
                mode="paper"
            )
            
            assert monitor.session_id == "session-123"
            assert monitor.total_iterations == 5
    
    def test_load_snapshot_with_mocked_state_manager(self):
        """StateManager 모킹으로 스냅샷 로드"""
        mock_state_manager = MagicMock()
        mock_state_manager._redis_connected = False
        mock_state_manager._in_memory_store = {
            "tuning:docker:paper:arbitrage:tuning_session:session-123:worker:main:iteration:1": {
                "timestamp": datetime.now().isoformat()
            },
            "tuning:docker:paper:arbitrage:tuning_session:session-123:worker:main:iteration:2": {
                "timestamp": datetime.now().isoformat()
            }
        }
        
        monitor = TuningStatusMonitor(
            session_id="session-123",
            total_iterations=5,
            env="docker",
            mode="paper",
            state_manager=mock_state_manager
        )
        
        snapshot = monitor.load_snapshot()
        
        assert snapshot.session_id == "session-123"
        assert snapshot.total_iterations == 5
        assert snapshot.completed_iterations == 2
        assert "main" in snapshot.workers


class TestWatchStatusScript:
    """watch_status.py 스크립트 테스트"""
    
    def test_format_live_status(self):
        """Live 상태 포맷팅"""
        from scripts.watch_status import format_live_status
        
        snapshot = LiveStatusSnapshot(
            mode="paper",
            env="docker",
            live_enabled=False,
            live_armed=False,
            last_heartbeat=datetime.now(),
            trades_total=5,
            trades_today=2,
            safety_violations_total=0,
            circuit_breaker_triggers_total=0,
            total_balance=1000000.0,
            available_balance=900000.0,
            total_position_value=100000.0
        )
        
        output = format_live_status(snapshot)
        
        assert "LIVE/PAPER STATUS" in output
        assert "paper" in output.lower()
        assert "docker" in output
    
    def test_format_tuning_status(self):
        """튜닝 상태 포맷팅"""
        from scripts.watch_status import format_tuning_status
        
        snapshot = TuningStatusSnapshot(
            session_id="session-123",
            total_iterations=5,
            completed_iterations=2,
            workers=["main"],
            metrics_keys=["pnl", "trades"],
            last_update=datetime.now()
        )
        
        output = format_tuning_status(snapshot)
        
        assert "TUNING STATUS" in output
        assert "session-123" in output
        assert "40.0%" in output  # 2/5 = 40%


class TestObservabilityPolicyD27:
    """D27 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_monitoring_scripts(self):
        """모니터링 스크립트에 가짜 메트릭 없음"""
        scripts = [
            "arbitrage/monitoring.py",
            "scripts/watch_status.py"
        ]
        
        forbidden_patterns = [
            "예상 출력",
            "expected output",
            "sample output",
            "샘플 결과"
        ]
        
        for script_path in scripts:
            full_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                script_path
            )
            
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                
                for pattern in forbidden_patterns:
                    assert pattern not in source.lower(), \
                        f"Found forbidden pattern '{pattern}' in {script_path}"
