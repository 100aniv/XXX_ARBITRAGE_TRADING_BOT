# -*- coding: utf-8 -*-
"""
D26 Parallel Tuning & Distributed Structure Tests

병렬 실행, 분산 구조, 결과 분석 테스트.
"""

import pytest
import tempfile
import yaml
import os
from unittest.mock import MagicMock, patch, AsyncMock
from scripts.run_d24_tuning_session import TuningSessionRunner
from arbitrage.tuning import build_tuning_key
from arbitrage.tuning_analysis import (
    TuningResult,
    TuningAnalyzer,
    load_results_from_csv,
    format_result_summary
)


class TestParallelExecution:
    """병렬 실행 테스트"""
    
    @pytest.fixture
    def test_config_file(self):
        """테스트용 설정 파일"""
        config_data = {
            "tuning": {
                "method": "random",
                "scenarios": ["configs/d17_scenarios/basic_spread_win.yaml"],
                "search_space": {
                    "param1": {"type": "float", "bounds": [0.0, 1.0]}
                },
                "max_iterations": 2,
                "seed": 42
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        yield config_path
        
        os.unlink(config_path)
    
    def test_sequential_execution(self, test_config_file):
        """순차 실행 (workers=1)"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=2,
                mode="paper",
                env="docker",
                parallel_workers=1
            )
            
            assert runner.parallel_workers == 1
            assert runner.worker_id == "main"
    
    def test_parallel_workers_parameter(self, test_config_file):
        """병렬 워커 파라미터"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=2,
                mode="paper",
                env="docker",
                parallel_workers=4
            )
            
            assert runner.parallel_workers == 4
    
    def test_worker_id_parameter(self, test_config_file):
        """워커 ID 파라미터"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=2,
                mode="paper",
                env="docker",
                worker_id="worker_1"
            )
            
            assert runner.worker_id == "worker_1"


class TestDistributedStructure:
    """분산 구조 테스트"""
    
    def test_build_tuning_key(self):
        """튜닝 키 생성"""
        key = build_tuning_key(
            session_id="session123",
            worker_id="worker1",
            iteration=1
        )
        
        assert "session123" in key
        assert "worker1" in key
        assert "1" in key
        assert "tuning_session:" in key
    
    def test_build_tuning_key_with_suffix(self):
        """접미사 포함 튜닝 키 생성"""
        key = build_tuning_key(
            session_id="session123",
            worker_id="worker1",
            iteration=1,
            suffix="result"
        )
        
        assert "result" in key
    
    def test_multiple_workers_same_session(self):
        """같은 세션, 다른 워커"""
        session_id = "session123"
        
        key1 = build_tuning_key(session_id, "worker1", 1)
        key2 = build_tuning_key(session_id, "worker2", 1)
        
        # 다른 워커는 다른 키
        assert key1 != key2
        assert "worker1" in key1
        assert "worker2" in key2
    
    @pytest.fixture
    def test_config_file(self):
        """테스트용 설정 파일"""
        config_data = {
            "tuning": {
                "method": "random",
                "scenarios": ["configs/d17_scenarios/basic_spread_win.yaml"],
                "search_space": {
                    "param1": {"type": "float", "bounds": [0.0, 1.0]}
                },
                "max_iterations": 1,
                "seed": 42
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        yield config_path
        
        os.unlink(config_path)
    
    def test_distributed_persist_result(self, test_config_file):
        """분산 결과 저장"""
        with patch('scripts.run_d24_tuning_session.StateManager') as mock_sm_class:
            mock_state_manager = MagicMock()
            mock_state_manager._get_key.return_value = "test_key"
            mock_sm_class.return_value = mock_state_manager
            
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=1,
                mode="paper",
                env="docker",
                session_id="session123",
                worker_id="worker1"
            )
            runner.state_manager = mock_state_manager
            
            result = {
                "session_id": "session123",
                "worker_id": "worker1",
                "iteration": 1,
                "status": "completed",
                "timestamp": "2025-11-16T12:00:00"
            }
            
            runner._persist_result(1, result)
            
            # StateManager 호출 확인
            mock_state_manager._get_key.assert_called()
            mock_state_manager._set_redis_or_memory.assert_called_once()


class TestTuningAnalysis:
    """튜닝 분석 테스트"""
    
    def test_tuning_result_creation(self):
        """TuningResult 생성"""
        result = TuningResult(
            session_id="session1",
            worker_id="worker1",
            iteration=1,
            params={"param1": 0.5},
            metrics={"pnl": 100.0, "trades": 5},
            timestamp="2025-11-16T12:00:00"
        )
        
        assert result.session_id == "session1"
        assert result.worker_id == "worker1"
        assert result.iteration == 1
        assert result.params["param1"] == 0.5
        assert result.metrics["pnl"] == 100.0
    
    def test_tuning_analyzer_summarize(self):
        """분석기 요약"""
        results = [
            TuningResult(
                session_id="session1",
                worker_id="worker1",
                iteration=1,
                params={"param1": 0.5},
                metrics={"pnl": 100.0, "trades": 5},
                timestamp="2025-11-16T12:00:00"
            ),
            TuningResult(
                session_id="session1",
                worker_id="worker1",
                iteration=2,
                params={"param1": 0.6},
                metrics={"pnl": 150.0, "trades": 6},
                timestamp="2025-11-16T12:01:00"
            )
        ]
        
        analyzer = TuningAnalyzer(results)
        summary = analyzer.summarize()
        
        assert summary["total_iterations"] == 2
        assert summary["total_workers"] == 1
        assert summary["unique_sessions"] == 1
        assert "pnl" in summary["metrics_keys"]
        assert "trades" in summary["metrics_keys"]
        assert "param1" in summary["param_keys"]
    
    def test_tuning_analyzer_rank_by_metric(self):
        """메트릭 기준 랭킹"""
        results = [
            TuningResult(
                session_id="session1",
                worker_id="worker1",
                iteration=1,
                params={"param1": 0.5},
                metrics={"pnl": 100.0},
                timestamp="2025-11-16T12:00:00"
            ),
            TuningResult(
                session_id="session1",
                worker_id="worker1",
                iteration=2,
                params={"param1": 0.6},
                metrics={"pnl": 150.0},
                timestamp="2025-11-16T12:01:00"
            ),
            TuningResult(
                session_id="session1",
                worker_id="worker1",
                iteration=3,
                params={"param1": 0.7},
                metrics={"pnl": 120.0},
                timestamp="2025-11-16T12:02:00"
            )
        ]
        
        analyzer = TuningAnalyzer(results)
        ranked = analyzer.rank_by_metric("pnl", top_n=2, ascending=False)
        
        assert len(ranked) == 2
        assert ranked[0].metrics["pnl"] == 150.0
        assert ranked[1].metrics["pnl"] == 120.0
    
    def test_tuning_analyzer_get_best_params(self):
        """최고 성능 파라미터"""
        results = [
            TuningResult(
                session_id="session1",
                worker_id="worker1",
                iteration=1,
                params={"param1": 0.5},
                metrics={"pnl": 100.0},
                timestamp="2025-11-16T12:00:00"
            ),
            TuningResult(
                session_id="session1",
                worker_id="worker1",
                iteration=2,
                params={"param1": 0.6},
                metrics={"pnl": 150.0},
                timestamp="2025-11-16T12:01:00"
            )
        ]
        
        analyzer = TuningAnalyzer(results)
        best_params = analyzer.get_best_params("pnl")
        
        assert best_params is not None
        assert best_params["param1"] == 0.6
    
    def test_format_result_summary(self):
        """결과 포맷팅"""
        result = TuningResult(
            session_id="session1",
            worker_id="worker1",
            iteration=1,
            params={"param1": 0.5},
            metrics={"pnl": 100.0},
            timestamp="2025-11-16T12:00:00"
        )
        
        summary = format_result_summary(result)
        
        assert "Iteration 1" in summary
        assert "param1" in summary
        assert "pnl" in summary


class TestObservabilityPolicyD26:
    """D26 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_scripts(self):
        """스크립트에 가짜 메트릭 없음"""
        scripts = [
            "scripts/run_d24_tuning_session.py",
            "scripts/show_tuning_summary.py"
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
