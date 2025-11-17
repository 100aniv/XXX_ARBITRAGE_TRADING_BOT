# -*- coding: utf-8 -*-
"""
D24 Tuning Session Runner Tests

실제 Paper Mode 튜닝 세션 실행 테스트.
Mock/Stub을 사용하여 실제 Docker 실행 없음.
"""

import pytest
import tempfile
import yaml
import os
from unittest.mock import MagicMock, patch, call
from scripts.run_d24_tuning_session import TuningSessionRunner


class TestTuningSessionRunner:
    """TuningSessionRunner 테스트"""
    
    @pytest.fixture
    def test_config_file(self):
        """테스트용 설정 파일 생성"""
        config_data = {
            "tuning": {
                "method": "grid",
                "scenarios": ["scenario1.yaml", "scenario2.yaml"],
                "search_space": {
                    "param1": {"type": "float", "bounds": [0.0, 1.0]},
                    "param2": {"type": "int", "bounds": [1, 10]}
                },
                "max_iterations": 3,
                "seed": 42,
                "grid_points": 2
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        yield config_path
        
        os.unlink(config_path)
    
    def test_runner_initialization(self, test_config_file):
        """TuningSessionRunner 초기화"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=3,
                mode="paper",
                env="docker"
            )
            
            assert runner.iterations == 3
            assert runner.mode == "paper"
            assert runner.env == "docker"
            assert runner.session_id is not None
            assert len(runner.results) == 0
    
    def test_runner_with_optimizer_override(self, test_config_file):
        """Optimizer 오버라이드"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=3,
                mode="paper",
                env="docker",
                optimizer_override="bayesian"
            )
            
            assert runner.config.method == "bayesian"
    
    def test_runner_with_csv_output(self, test_config_file):
        """CSV 출력 경로 설정"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=3,
                mode="paper",
                env="docker",
                output_csv="/tmp/test_output.csv"
            )
            
            assert runner.output_csv == "/tmp/test_output.csv"
    
    def test_objective_function(self, test_config_file):
        """목적 함수 실행"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=1,
                mode="paper",
                env="docker"
            )
            
            params = {"param1": 0.5, "param2": 5}
            result = runner._objective_function(params)
            
            assert result["session_id"] == runner.session_id
            assert result["iteration"] == 1
            assert result["params"] == params
            assert "metrics" in result
            assert "status" in result
            assert result["status"] == "completed"
    
    def test_run_session(self, test_config_file):
        """튜닝 세션 실행"""
        with patch('scripts.run_d24_tuning_session.StateManager') as mock_sm:
            mock_state_manager = MagicMock()
            mock_state_manager._get_key.return_value = "test_key"
            
            runner = TuningSessionRunner(
                config_path=test_config_file,
                iterations=2,
                mode="paper",
                env="docker"
            )
            runner.state_manager = mock_state_manager
            
            success = runner.run()
            
            assert success is True
            assert len(runner.results) == 2
            
            # StateManager 호출 확인
            assert mock_state_manager._set_redis_or_memory.call_count >= 2
    
    def test_save_csv(self, test_config_file):
        """CSV 파일 저장"""
        with patch('scripts.run_d24_tuning_session.StateManager'):
            with tempfile.TemporaryDirectory() as tmpdir:
                csv_path = os.path.join(tmpdir, "test_results.csv")
                
                runner = TuningSessionRunner(
                    config_path=test_config_file,
                    iterations=2,
                    mode="paper",
                    env="docker",
                    output_csv=csv_path
                )
                
                # 결과 추가
                runner.results = [
                    {
                        "session_id": "session1",
                        "iteration": 1,
                        "status": "completed",
                        "timestamp": "2025-11-16T12:00:00"
                    },
                    {
                        "session_id": "session1",
                        "iteration": 2,
                        "status": "completed",
                        "timestamp": "2025-11-16T12:01:00"
                    }
                ]
                
                success = runner.save_csv()
                
                assert success is True
                assert os.path.exists(csv_path)
                
                # CSV 내용 확인
                with open(csv_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    assert len(lines) == 3  # header + 2 rows
                    assert "session_id" in lines[0]
    
    def test_persist_result(self, test_config_file):
        """결과 저장"""
        with patch('scripts.run_d24_tuning_session.StateManager') as mock_sm:
            mock_state_manager = MagicMock()
            mock_state_manager._get_key.return_value = "test_key"
            
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
    
    def test_state_manager_namespace(self, test_config_file):
        """StateManager Namespace 확인"""
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
            mock_sm_class.assert_called_once()
            
            # 호출 인자 확인
            call_kwargs = mock_sm_class.call_args[1]
            assert call_kwargs["namespace"] == "tuning:docker:paper"
            assert call_kwargs["enabled"] is True


class TestTuningSessionRunnerCLI:
    """CLI 인터페이스 테스트"""
    
    @pytest.fixture
    def test_config_file(self):
        """테스트용 설정 파일"""
        config_data = {
            "tuning": {
                "method": "random",
                "scenarios": ["scenario1.yaml"],
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
    
    def test_cli_main_success(self, test_config_file):
        """CLI main 함수 성공"""
        from scripts.run_d24_tuning_session import main
        
        with patch('scripts.run_d24_tuning_session.StateManager'):
            with patch('sys.argv', [
                'run_d24_tuning_session.py',
                '--config', test_config_file,
                '--iterations', '2',
                '--mode', 'paper',
                '--env', 'docker'
            ]):
                exit_code = main()
                assert exit_code == 0
    
    def test_cli_with_optimizer_override(self, test_config_file):
        """CLI Optimizer 오버라이드"""
        from scripts.run_d24_tuning_session import main
        
        with patch('scripts.run_d24_tuning_session.StateManager'):
            with patch('sys.argv', [
                'run_d24_tuning_session.py',
                '--config', test_config_file,
                '--iterations', '2',
                '--optimizer', 'bayesian'
            ]):
                exit_code = main()
                assert exit_code == 0
    
    def test_cli_with_csv_output(self, test_config_file):
        """CLI CSV 출력"""
        from scripts.run_d24_tuning_session import main
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "results.csv")
            
            with patch('scripts.run_d24_tuning_session.StateManager'):
                with patch('sys.argv', [
                    'run_d24_tuning_session.py',
                    '--config', test_config_file,
                    '--iterations', '2',
                    '--output-csv', csv_path
                ]):
                    exit_code = main()
                    assert exit_code == 0


class TestObservabilityPolicyD24:
    """D24 Observability 정책 준수 테스트"""
    
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
    
    def test_no_hardcoded_fake_numbers(self):
        """하드코딩된 가짜 숫자 없음"""
        import scripts.run_d24_tuning_session as module
        
        with open(module.__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # 실제 메트릭 키는 허용하지만, 가짜 숫자는 금지
        # 예: "pnl": 1234.56 (금지)
        # 예: "pnl": 0.0 (허용, 초기값)
        
        # 목적 함수에서 0.0 초기값은 허용
        assert '"pnl": 0.0' in source  # 초기값
        
        # 하지만 "예상 PnL: 1234.56" 같은 패턴은 없어야 함
        assert "예상 pnl" not in source.lower()
        assert "expected pnl" not in source.lower()
