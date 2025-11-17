# -*- coding: utf-8 -*-
"""
D23 Advanced Tuning Engine Tests

Bayesian/Hyperopt 기반 최적화 구조 테스트.
실제 최적화는 수행하지 않음 (구조만 검증).
"""

import pytest
from unittest.mock import MagicMock, patch
from arbitrage.tuning_advanced import (
    TuningMethod,
    ParameterBound,
    GridOptimizer,
    RandomOptimizer,
    BayesianOptimizer,
    create_optimizer,
    OptimizationResult,
    OptimizerState
)
from arbitrage.tuning import TuningConfig, TuningHarness, load_tuning_config
import tempfile
import yaml
import os


class TestParameterBound:
    """ParameterBound 테스트"""
    
    def test_float_bound_validation(self):
        """Float 파라미터 범위 검증"""
        bound = ParameterBound(
            name="min_spread_pct",
            param_type="float",
            bounds=(0.05, 0.50)
        )
        
        assert bound.validate(0.1)
        assert bound.validate(0.05)
        assert bound.validate(0.50)
        assert not bound.validate(0.01)
        assert not bound.validate(0.60)
    
    def test_int_bound_validation(self):
        """Int 파라미터 범위 검증"""
        bound = ParameterBound(
            name="slippage_bps",
            param_type="int",
            bounds=(1, 30)
        )
        
        assert bound.validate(1)
        assert bound.validate(15)
        assert bound.validate(30)
        assert not bound.validate(0)
        assert not bound.validate(31)
        assert not bound.validate(15.5)


class TestGridOptimizer:
    """Grid Search Optimizer 테스트"""
    
    def test_grid_optimizer_initialization(self):
        """Grid Optimizer 초기화"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0)),
            ParameterBound("param2", "int", (1, 10))
        ]
        
        optimizer = GridOptimizer(search_space, grid_points=3)
        assert optimizer.get_iteration_count() == 0
        assert len(optimizer.get_history()) == 0
    
    def test_grid_optimizer_ask(self):
        """Grid Optimizer ask() - 결정론적 순서"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer = GridOptimizer(search_space, grid_points=3)
        
        # 첫 번째 ask
        params1 = optimizer.ask()
        assert "param1" in params1
        assert 0.0 <= params1["param1"] <= 1.0
        
        # 두 번째 ask (다른 값)
        params2 = optimizer.ask()
        assert "param1" in params2
        assert 0.0 <= params2["param1"] <= 1.0
        
        # 세 번째 ask
        params3 = optimizer.ask()
        assert "param1" in params3
        assert 0.0 <= params3["param1"] <= 1.0
    
    def test_grid_optimizer_tell(self):
        """Grid Optimizer tell() - 결과 기록"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer = GridOptimizer(search_space, grid_points=2)
        
        params = optimizer.ask()
        result = {"status": "completed"}
        optimizer.tell(params, result)
        
        assert optimizer.get_iteration_count() == 1
        assert len(optimizer.get_history()) == 1
        
        history = optimizer.get_history()
        assert history[0].iteration == 1
        assert history[0].params == params
        assert history[0].result_summary == result


class TestRandomOptimizer:
    """Random Search Optimizer 테스트"""
    
    def test_random_optimizer_initialization(self):
        """Random Optimizer 초기화"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0)),
            ParameterBound("param2", "int", (1, 10))
        ]
        
        optimizer = RandomOptimizer(search_space, seed=42)
        assert optimizer.get_iteration_count() == 0
    
    def test_random_optimizer_ask_within_bounds(self):
        """Random Optimizer ask() - 범위 내 값"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0)),
            ParameterBound("param2", "int", (1, 10))
        ]
        
        optimizer = RandomOptimizer(search_space, seed=42)
        
        for _ in range(5):
            params = optimizer.ask()
            assert 0.0 <= params["param1"] <= 1.0
            assert 1 <= params["param2"] <= 10
    
    def test_random_optimizer_reproducibility(self):
        """Random Optimizer - 시드로 재현성 보장"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer1 = RandomOptimizer(search_space, seed=42)
        params1 = optimizer1.ask()
        
        optimizer2 = RandomOptimizer(search_space, seed=42)
        params2 = optimizer2.ask()
        
        assert params1["param1"] == params2["param1"]
    
    def test_random_optimizer_tell(self):
        """Random Optimizer tell() - 결과 기록"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer = RandomOptimizer(search_space, seed=42)
        
        params = optimizer.ask()
        result = {"status": "completed"}
        optimizer.tell(params, result)
        
        assert optimizer.get_iteration_count() == 1
        assert len(optimizer.get_history()) == 1


class TestBayesianOptimizer:
    """Bayesian Optimizer 테스트 (구조만)"""
    
    def test_bayesian_optimizer_initialization(self):
        """Bayesian Optimizer 초기화"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0)),
            ParameterBound("param2", "int", (1, 10))
        ]
        
        optimizer = BayesianOptimizer(
            search_space,
            acquisition_fn="ucb",
            seed=42
        )
        assert optimizer.get_iteration_count() == 0
        assert optimizer.acquisition_fn == "ucb"
    
    def test_bayesian_optimizer_ask(self):
        """Bayesian Optimizer ask() - 파라미터 제안"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0)),
            ParameterBound("param2", "int", (1, 10))
        ]
        
        optimizer = BayesianOptimizer(search_space, seed=42)
        
        params = optimizer.ask()
        assert "param1" in params
        assert "param2" in params
        assert 0.0 <= params["param1"] <= 1.0
        assert 1 <= params["param2"] <= 10
    
    def test_bayesian_optimizer_tell(self):
        """Bayesian Optimizer tell() - 결과 기록 및 상태 업데이트"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer = BayesianOptimizer(search_space, seed=42)
        
        params = optimizer.ask()
        result = {"status": "completed"}
        optimizer.tell(params, result)
        
        assert optimizer.get_iteration_count() == 1
        
        # Bayesian 상태 확인
        bayesian_state = optimizer.get_bayesian_state()
        assert bayesian_state.iteration_count == 1
        assert len(bayesian_state.history) == 1
    
    def test_bayesian_optimizer_acquisition_functions(self):
        """Bayesian Optimizer - 다양한 Acquisition Function"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        for acq_fn in ["ucb", "ei", "poi"]:
            optimizer = BayesianOptimizer(search_space, acquisition_fn=acq_fn, seed=42)
            assert optimizer.acquisition_fn == acq_fn
            
            params = optimizer.ask()
            optimizer.tell(params, {"status": "completed"})
            assert optimizer.get_iteration_count() == 1


class TestCreateOptimizer:
    """Optimizer 팩토리 함수 테스트"""
    
    def test_create_grid_optimizer(self):
        """Grid Optimizer 생성"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer = create_optimizer(
            TuningMethod.GRID,
            search_space,
            grid_points=3
        )
        
        assert isinstance(optimizer, GridOptimizer)
    
    def test_create_random_optimizer(self):
        """Random Optimizer 생성"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer = create_optimizer(
            TuningMethod.RANDOM,
            search_space,
            seed=42
        )
        
        assert isinstance(optimizer, RandomOptimizer)
    
    def test_create_bayesian_optimizer(self):
        """Bayesian Optimizer 생성"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        optimizer = create_optimizer(
            TuningMethod.BAYESIAN,
            search_space,
            acquisition_fn="ucb",
            seed=42
        )
        
        assert isinstance(optimizer, BayesianOptimizer)


class TestTuningConfig:
    """TuningConfig 테스트"""
    
    def test_tuning_config_creation(self):
        """TuningConfig 생성"""
        config = TuningConfig(
            method="bayesian",
            scenarios=["scenario1.yaml", "scenario2.yaml"],
            search_space={
                "param1": {"type": "float", "bounds": [0.0, 1.0]},
                "param2": {"type": "int", "bounds": [1, 10]}
            },
            max_iterations=10,
            seed=42
        )
        
        assert config.method == "bayesian"
        assert len(config.scenarios) == 2
        assert len(config.search_space) == 2
        assert config.max_iterations == 10


class TestTuningHarness:
    """TuningHarness 통합 테스트"""
    
    def test_tuning_harness_initialization(self):
        """TuningHarness 초기화"""
        config = TuningConfig(
            method="grid",
            scenarios=["scenario1.yaml"],
            search_space={
                "param1": {"type": "float", "bounds": [0.0, 1.0]}
            },
            max_iterations=3,
            grid_points=2
        )
        
        with patch('arbitrage.tuning.StateManager'):
            harness = TuningHarness(config)
            assert harness.config.method == "grid"
            assert isinstance(harness.optimizer, GridOptimizer)
    
    def test_tuning_harness_run_iteration(self):
        """TuningHarness - 반복 실행"""
        config = TuningConfig(
            method="random",
            scenarios=["scenario1.yaml"],
            search_space={
                "param1": {"type": "float", "bounds": [0.0, 1.0]}
            },
            max_iterations=3,
            seed=42
        )
        
        with patch('arbitrage.tuning.StateManager'):
            harness = TuningHarness(config)
            
            # Mock 목적 함수
            def mock_objective(params):
                return {"status": "completed", "iteration": 1}
            
            result = harness.run_iteration(1, mock_objective)
            
            assert result["status"] == "completed"
            assert len(harness.get_results()) == 1
    
    def test_tuning_harness_multiple_iterations(self):
        """TuningHarness - 여러 반복"""
        config = TuningConfig(
            method="random",
            scenarios=["scenario1.yaml"],
            search_space={
                "param1": {"type": "float", "bounds": [0.0, 1.0]}
            },
            max_iterations=3,
            seed=42
        )
        
        with patch('arbitrage.tuning.StateManager'):
            harness = TuningHarness(config)
            
            def mock_objective(params):
                return {"status": "completed"}
            
            for i in range(3):
                harness.run_iteration(i + 1, mock_objective)
            
            assert len(harness.get_results()) == 3
            assert harness.optimizer.get_iteration_count() == 3
    
    def test_tuning_harness_with_state_manager(self):
        """TuningHarness - StateManager 통합"""
        config = TuningConfig(
            method="grid",
            scenarios=["scenario1.yaml"],
            search_space={
                "param1": {"type": "float", "bounds": [0.0, 1.0]}
            },
            max_iterations=2,
            grid_points=2
        )
        
        mock_state_manager = MagicMock()
        mock_state_manager._get_key.return_value = "tuning:docker:paper:tuning_result:1"
        
        harness = TuningHarness(config, state_manager=mock_state_manager)
        
        def mock_objective(params):
            return {"status": "completed"}
        
        harness.run_iteration(1, mock_objective)
        
        # StateManager 호출 확인
        mock_state_manager._get_key.assert_called()
        mock_state_manager._set_redis_or_memory.assert_called()


class TestLoadTuningConfig:
    """YAML 설정 로드 테스트"""
    
    def test_load_tuning_config_from_yaml(self):
        """YAML 파일에서 설정 로드"""
        config_data = {
            "tuning": {
                "method": "bayesian",
                "scenarios": ["scenario1.yaml", "scenario2.yaml"],
                "search_space": {
                    "param1": {"type": "float", "bounds": [0.0, 1.0]},
                    "param2": {"type": "int", "bounds": [1, 10]}
                },
                "max_iterations": 10,
                "seed": 42,
                "acquisition_fn": "ucb"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = load_tuning_config(config_path)
            
            assert config.method == "bayesian"
            assert len(config.scenarios) == 2
            assert len(config.search_space) == 2
            assert config.max_iterations == 10
            assert config.seed == 42
            assert config.acquisition_fn == "ucb"
        finally:
            os.unlink(config_path)


class TestObservabilityPolicy:
    """Observability 정책 준수 테스트"""
    
    def test_no_fake_metrics_in_tuning_advanced(self):
        """tuning_advanced.py에 가짜 메트릭 없음"""
        import arbitrage.tuning_advanced as module
        
        with open(module.__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        
        # 가짜 메트릭 패턴 확인
        forbidden_patterns = [
            "trades_total",
            "win_rate",
            "drawdown",
            "pnl",
            "예상 출력",
            "expected output",
            "sample output"
        ]
        
        for pattern in forbidden_patterns:
            assert pattern not in source.lower(), \
                f"Found forbidden pattern '{pattern}' in tuning_advanced.py"
    
    def test_no_fake_metrics_in_tuning(self):
        """tuning.py에 가짜 메트릭 없음"""
        import arbitrage.tuning as module
        
        with open(module.__file__, 'r', encoding='utf-8') as f:
            source = f.read()
        
        forbidden_patterns = [
            "trades_total",
            "win_rate",
            "drawdown",
            "pnl",
            "예상 출력",
            "expected output",
            "sample output"
        ]
        
        for pattern in forbidden_patterns:
            assert pattern not in source.lower(), \
                f"Found forbidden pattern '{pattern}' in tuning.py"


class TestOptimizerState:
    """OptimizerState 테스트"""
    
    def test_optimizer_state_add_result(self):
        """OptimizerState - 결과 추가"""
        search_space = [
            ParameterBound("param1", "float", (0.0, 1.0))
        ]
        
        state = OptimizerState(search_space=search_space)
        
        params = {"param1": 0.5}
        result = {"status": "completed"}
        
        state.add_result(params, result)
        
        assert state.iteration_count == 1
        assert len(state.history) == 1
        assert state.history[0].iteration == 1
        assert state.history[0].params == params
