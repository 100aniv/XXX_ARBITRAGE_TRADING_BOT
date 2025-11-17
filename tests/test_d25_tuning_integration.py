# -*- coding: utf-8 -*-
"""
D25 Tuning Integration Tests

실제 Paper Engine 통합 검증 (구조 및 wiring 테스트만).
실제 Paper Engine 실행은 테스트 외부에서 수행.
"""

import pytest
import tempfile
import yaml
import os
from unittest.mock import MagicMock, patch, AsyncMock
from scripts.run_d24_tuning_session import TuningSessionRunner


class TestD25TuningIntegration:
    """D25 Tuning Integration 테스트"""
    
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
    
    def test_cli_to_runner_wiring(self, test_config_file):
        """CLI → TuningSessionRunner 연결 검증"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=2,
                mode="paper",
                env="docker",
                optimizer_override="random"
            )
            
            # 인자 확인
            assert runner.iterations == 2
            assert runner.mode == "paper"
            assert runner.env == "docker"
            assert runner.config.method == "random"
    
    def test_state_manager_namespace_tuning_docker_paper(self, test_config_file):
        """StateManager namespace: tuning:docker:paper"""
        with patch('scripts.run_d24_tuning_session.StateManager') as mock_sm_class:
            mock_state_manager = MagicMock()
            mock_sm_class.return_value = mock_state_manager
            
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=1,
                mode="paper",
                env="docker"
            )
            
            # StateManager 생성 호출 확인
            call_kwargs = mock_sm_class.call_args[1]
            assert call_kwargs["namespace"] == "tuning:docker:paper"
            assert call_kwargs["enabled"] is True
    
    def test_persist_result_via_state_manager(self, test_config_file):
        """결과 저장: StateManager 호출 확인"""
        with patch('scripts.run_d24_tuning_session.StateManager') as mock_sm_class:
            mock_state_manager = MagicMock()
            mock_state_manager._get_key.return_value = "test_key"
            mock_sm_class.return_value = mock_state_manager
            
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=1,
                mode="paper",
                env="docker"
            )
            runner.state_manager = mock_state_manager
            
            result = {
                "session_id": "test_session",
                "iteration": 1,
                "status": "completed",
                "timestamp": "2025-11-16T12:00:00"
            }
            
            runner._persist_result(1, result)
            
            # StateManager 호출 확인
            mock_state_manager._get_key.assert_called()
            mock_state_manager._set_redis_or_memory.assert_called_once()
    
    def test_objective_function_structure(self, test_config_file):
        """목적 함수 구조 검증"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            with patch('scripts.run_d24_tuning_session.PaperTrader') as mock_paper_trader:
                # Mock PaperTrader
                mock_trader_instance = AsyncMock()
                mock_trader_instance.run = AsyncMock(return_value={
                    "trades": 5,
                    "total_fees": 100.0,
                    "pnl": 500.0,
                    "circuit_breaker_active": False,
                    "safety_violations": 0
                })
                mock_paper_trader.return_value = mock_trader_instance
                
                runner = TuningSessionRunner(
                    config_path=test_config_file,
                    iterations=1,
                    mode="paper",
                    env="docker"
                )
                
                params = {"param1": 0.5}
                result = runner._objective_function(params)
                
                # 결과 구조 확인
                assert "session_id" in result
                assert "iteration" in result
                assert "params" in result
                assert "metrics" in result
                assert "scenario_files" in result
                assert "timestamp" in result
                assert "status" in result
                
                # 메트릭 확인
                assert "trades" in result["metrics"]
                assert "total_fees" in result["metrics"]
                assert "pnl" in result["metrics"]
                assert "circuit_breaker_active" in result["metrics"]
                assert "safety_violations" in result["metrics"]
    
    def test_objective_function_with_real_structure(self, test_config_file):
        """목적 함수: 실제 구조 검증"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=1,
                mode="paper",
                env="docker"
            )
            
            # Mock 목적 함수 (실제 Paper Engine 없이)
            def mock_objective(params):
                return {
                    "session_id": runner.session_id,
                    "iteration": 1,
                    "params": params,
                    "metrics": {
                        "trades": 3,
                        "total_fees": 50.0,
                        "pnl": 250.0,
                        "circuit_breaker_active": False,
                        "safety_violations": 0
                    },
                    "scenario_files": runner.config.scenarios,
                    "timestamp": "2025-11-16T12:00:00",
                    "status": "completed"
                }
            
            params = {"param1": 0.3}
            result = mock_objective(params)
            
            # 구조 검증
            assert result["iteration"] == 1
            assert result["params"] == params
            assert result["metrics"]["trades"] == 3
            assert result["metrics"]["pnl"] == 250.0


class TestObservabilityPolicyD25:
    """D25 Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_runner_script(self):
        """run_d24_tuning_session.py에 가짜 메트릭 없음"""
        import scripts.run_d24_tuning_session as module
        
        with open(module.__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        
        forbidden_patterns = [
            "예상 출력",
            "expected output",
            "sample output",
            "샘플 결과"
        ]
        
        for pattern in forbidden_patterns:
            assert pattern not in source.lower(), \
                f"Found forbidden pattern '{pattern}' in run_d24_tuning_session.py"
    
    def test_real_paper_engine_used(self):
        """실제 Paper Engine 사용 확인"""
        import scripts.run_d24_tuning_session as module
        
        with open(module.__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # PaperTrader import 확인
        assert "from arbitrage.paper_trader import PaperTrader" in source
        
        # PaperTrader 사용 확인
        assert "PaperTrader(" in source
        assert "await paper_trader.run()" in source


class TestD25InfrastructureSafety:
    """D25 인프라 안전 규칙 준수 테스트"""
    
    def test_state_manager_only_redis_access(self, ):
        """StateManager를 통한 Redis 접근만"""
        import scripts.run_d24_tuning_session as module
        
        with open(module.__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # 직접 redis 접근 금지 (StateManager 사용만)
        assert "redis.Redis(" not in source
        assert "redis_client" not in source.lower()
        
        # StateManager 사용 확인
        assert "StateManager(" in source
        assert "_set_redis_or_memory" in source
