# -*- coding: utf-8 -*-
"""
D23 Advanced Tuning Engine

Bayesian Optimization / Hyperparameter Optimization 기반 구조.
실제 최적화는 수행하지 않으며, 향후 D24+에서 scikit-opt, hyperopt, optuna 등을 플러그인할 수 있도록 설계됨.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


class TuningMethod(Enum):
    """튜닝 방법"""
    GRID = "grid"
    RANDOM = "random"
    BAYESIAN = "bayesian"


@dataclass
class ParameterBound:
    """파라미터 범위 정의"""
    name: str
    param_type: str  # "float", "int"
    bounds: Tuple[float, float]  # (min, max)
    
    def validate(self, value: Any) -> bool:
        """값이 범위 내인지 확인"""
        min_val, max_val = self.bounds
        if self.param_type == "float":
            return isinstance(value, (int, float)) and min_val <= value <= max_val
        elif self.param_type == "int":
            return isinstance(value, int) and min_val <= value <= max_val
        return False


@dataclass
class OptimizationResult:
    """최적화 결과 기록"""
    iteration: int
    params: Dict[str, Any]
    result_summary: Dict[str, Any]  # 메트릭 저장 (숫자 없음, 키만)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class OptimizerState:
    """Optimizer 내부 상태"""
    search_space: List[ParameterBound]
    history: List[OptimizationResult] = field(default_factory=list)
    iteration_count: int = 0
    
    def add_result(self, params: Dict[str, Any], result_summary: Dict[str, Any]) -> None:
        """결과 기록"""
        self.iteration_count += 1
        result = OptimizationResult(
            iteration=self.iteration_count,
            params=params,
            result_summary=result_summary
        )
        self.history.append(result)
        logger.info(f"[TUNING] Iteration {self.iteration_count}: params={params}")


class BaseOptimizer(ABC):
    """최적화 알고리즘 기본 인터페이스"""
    
    def __init__(self, search_space: List[ParameterBound]):
        """
        Args:
            search_space: 파라미터 범위 리스트
        """
        self.search_space = search_space
        self.state = OptimizerState(search_space=search_space)
    
    @abstractmethod
    def ask(self) -> Dict[str, Any]:
        """
        다음 시도할 파라미터 제안
        
        Returns:
            파라미터 딕셔너리
        """
        pass
    
    @abstractmethod
    def tell(self, params: Dict[str, Any], result_summary: Dict[str, Any]) -> None:
        """
        결과 기록 (내부 모델 업데이트 가능)
        
        Args:
            params: 사용한 파라미터
            result_summary: 결과 요약 (메트릭 키만, 값 없음)
        """
        pass
    
    def get_history(self) -> List[OptimizationResult]:
        """최적화 히스토리 조회"""
        return self.state.history
    
    def get_iteration_count(self) -> int:
        """현재 반복 횟수"""
        return self.state.iteration_count


class GridOptimizer(BaseOptimizer):
    """Grid Search 최적화"""
    
    def __init__(self, search_space: List[ParameterBound], grid_points: int = 3):
        """
        Args:
            search_space: 파라미터 범위 리스트
            grid_points: 각 차원당 그리드 포인트 수
        """
        super().__init__(search_space)
        self.grid_points = grid_points
        self._grid_index = 0
        self._grid = self._generate_grid()
    
    def _generate_grid(self) -> List[Dict[str, Any]]:
        """그리드 생성"""
        import itertools
        
        grids = []
        for bound in self.search_space:
            min_val, max_val = bound.bounds
            if bound.param_type == "float":
                grid_vals = [min_val + (max_val - min_val) * i / (self.grid_points - 1) 
                            for i in range(self.grid_points)]
            else:  # int
                step = max(1, (max_val - min_val) // (self.grid_points - 1))
                grid_vals = list(range(int(min_val), int(max_val) + 1, step))[:self.grid_points]
            grids.append(grid_vals)
        
        # 모든 조합 생성
        combinations = []
        for combo in itertools.product(*grids):
            param_dict = {}
            for bound, value in zip(self.search_space, combo):
                param_dict[bound.name] = value
            combinations.append(param_dict)
        
        return combinations
    
    def ask(self) -> Dict[str, Any]:
        """다음 그리드 포인트 반환"""
        if self._grid_index >= len(self._grid):
            logger.warning("[TUNING] Grid exhausted, returning last point")
            return self._grid[-1] if self._grid else {}
        
        params = self._grid[self._grid_index]
        self._grid_index += 1
        return params
    
    def tell(self, params: Dict[str, Any], result_summary: Dict[str, Any]) -> None:
        """결과 기록"""
        self.state.add_result(params, result_summary)


class RandomOptimizer(BaseOptimizer):
    """Random Search 최적화"""
    
    def __init__(self, search_space: List[ParameterBound], seed: Optional[int] = None):
        """
        Args:
            search_space: 파라미터 범위 리스트
            seed: 난수 시드 (재현성)
        """
        super().__init__(search_space)
        self.seed = seed
        
        import random
        if seed is not None:
            random.seed(seed)
        self._random = random
    
    def ask(self) -> Dict[str, Any]:
        """무작위 파라미터 샘플링"""
        params = {}
        for bound in self.search_space:
            min_val, max_val = bound.bounds
            if bound.param_type == "float":
                value = self._random.uniform(min_val, max_val)
            else:  # int
                value = self._random.randint(int(min_val), int(max_val))
            params[bound.name] = value
        return params
    
    def tell(self, params: Dict[str, Any], result_summary: Dict[str, Any]) -> None:
        """결과 기록"""
        self.state.add_result(params, result_summary)


@dataclass
class BayesianState:
    """Bayesian Optimizer 내부 상태"""
    search_space: List[ParameterBound]
    history: List[OptimizationResult] = field(default_factory=list)
    iteration_count: int = 0
    
    # Placeholder: 향후 D24+에서 실제 GP 모델로 대체
    gp_model: Optional[Any] = None
    acquisition_function: Optional[str] = None


class BayesianOptimizer(BaseOptimizer):
    """
    Bayesian Optimization 기반 최적화 (구조만, 실제 최적화 없음)
    
    향후 D24+에서 다음 라이브러리 중 하나로 구현 가능:
    - scikit-opt (skopt)
    - hyperopt
    - optuna
    - GPy
    """
    
    def __init__(
        self,
        search_space: List[ParameterBound],
        acquisition_fn: str = "ucb",
        seed: Optional[int] = None
    ):
        """
        Args:
            search_space: 파라미터 범위 리스트
            acquisition_fn: Acquisition function (ucb, ei, poi)
            seed: 난수 시드
        """
        super().__init__(search_space)
        self.acquisition_fn = acquisition_fn
        self.seed = seed
        
        # 내부 상태
        self._bayesian_state = BayesianState(
            search_space=search_space,
            acquisition_function=acquisition_fn
        )
        
        # 초기 Random sampling 사용 (GP 모델 없음)
        import random
        if seed is not None:
            random.seed(seed)
        self._random = random
    
    def ask(self) -> Dict[str, Any]:
        """
        다음 시도할 파라미터 제안
        
        현재: Random sampling (향후 GP 기반 제안으로 대체)
        """
        params = {}
        for bound in self.search_space:
            min_val, max_val = bound.bounds
            if bound.param_type == "float":
                value = self._random.uniform(min_val, max_val)
            else:  # int
                value = self._random.randint(int(min_val), int(max_val))
            params[bound.name] = value
        return params
    
    def tell(self, params: Dict[str, Any], result_summary: Dict[str, Any]) -> None:
        """
        결과 기록 및 내부 모델 업데이트
        
        현재: 히스토리만 저장 (향후 GP 모델 학습으로 대체)
        """
        self._bayesian_state.iteration_count += 1
        result = OptimizationResult(
            iteration=self._bayesian_state.iteration_count,
            params=params,
            result_summary=result_summary
        )
        self._bayesian_state.history.append(result)
        self.state.add_result(params, result_summary)
        
        logger.info(f"[TUNING] Bayesian iteration {self._bayesian_state.iteration_count}: "
                   f"acquisition_fn={self.acquisition_fn}")
    
    def get_bayesian_state(self) -> BayesianState:
        """Bayesian 내부 상태 조회 (테스트용)"""
        return self._bayesian_state


def create_optimizer(
    method: TuningMethod,
    search_space: List[ParameterBound],
    **kwargs
) -> BaseOptimizer:
    """
    최적화 방법에 따라 Optimizer 생성
    
    Args:
        method: 튜닝 방법 (GRID, RANDOM, BAYESIAN)
        search_space: 파라미터 범위 리스트
        **kwargs: 각 Optimizer별 추가 파라미터
    
    Returns:
        BaseOptimizer 인스턴스
    """
    if method == TuningMethod.GRID:
        grid_points = kwargs.get("grid_points", 3)
        return GridOptimizer(search_space, grid_points=grid_points)
    elif method == TuningMethod.RANDOM:
        seed = kwargs.get("seed", None)
        return RandomOptimizer(search_space, seed=seed)
    elif method == TuningMethod.BAYESIAN:
        acquisition_fn = kwargs.get("acquisition_fn", "ucb")
        seed = kwargs.get("seed", None)
        return BayesianOptimizer(search_space, acquisition_fn=acquisition_fn, seed=seed)
    else:
        raise ValueError(f"Unknown tuning method: {method}")
