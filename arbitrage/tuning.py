# -*- coding: utf-8 -*-
"""
D22/D23 Tuning Harness

파라미터 튜닝 실행 및 결과 관리.
"""

import logging
import os
import yaml
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from arbitrage.state_manager import StateManager
from arbitrage.tuning_advanced import (
    TuningMethod,
    ParameterBound,
    BaseOptimizer,
    create_optimizer
)

logger = logging.getLogger(__name__)


def build_tuning_key(
    session_id: str,
    worker_id: str,
    iteration: int,
    suffix: str = ""
) -> str:
    """
    튜닝 결과 키 생성
    
    Args:
        session_id: 세션 ID
        worker_id: 워커 ID
        iteration: 반복 번호
        suffix: 추가 접미사
    
    Returns:
        키 문자열
    """
    key = f"tuning_session:{session_id}:worker:{worker_id}:iteration:{iteration}"
    if suffix:
        key += f":{suffix}"
    return key


@dataclass
class TuningConfig:
    """튜닝 설정"""
    method: str  # grid, random, bayesian
    scenarios: List[str]  # 시나리오 파일 경로 리스트
    search_space: Dict[str, Dict[str, Any]]  # 파라미터 범위
    max_iterations: int = 10
    seed: Optional[int] = None
    grid_points: int = 3
    acquisition_fn: str = "ucb"


class TuningHarness:
    """튜닝 실행 엔진"""
    
    def __init__(self, config: TuningConfig, state_manager: Optional[StateManager] = None):
        """
        Args:
            config: 튜닝 설정
            state_manager: StateManager (Redis 연동)
        """
        self.config = config
        self.state_manager = state_manager or self._create_default_state_manager()
        self.optimizer = self._create_optimizer()
        self.results = []
    
    def _create_default_state_manager(self) -> StateManager:
        """기본 StateManager 생성"""
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        
        env = os.getenv("APP_ENV", "docker")
        mode = os.getenv("TUNING_MODE", "paper")
        
        return StateManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            namespace=f"tuning:{env}:{mode}",
            enabled=True,
            key_prefix="arbitrage"
        )
    
    def _create_optimizer(self) -> BaseOptimizer:
        """Optimizer 생성"""
        # 파라미터 범위 변환
        search_space = []
        for param_name, param_config in self.config.search_space.items():
            param_type = param_config.get("type", "float")
            bounds = param_config.get("bounds", [0, 1])
            
            bound = ParameterBound(
                name=param_name,
                param_type=param_type,
                bounds=tuple(bounds)
            )
            search_space.append(bound)
        
        # Optimizer 생성
        method = TuningMethod(self.config.method)
        kwargs = {
            "seed": self.config.seed,
            "grid_points": self.config.grid_points,
            "acquisition_fn": self.config.acquisition_fn
        }
        
        optimizer = create_optimizer(method, search_space, **kwargs)
        logger.info(f"[TUNING] Created {method.value} optimizer with {len(search_space)} parameters")
        return optimizer
    
    def run_iteration(self, iteration: int, objective_fn) -> Dict[str, Any]:
        """
        한 번의 튜닝 반복 실행
        
        Args:
            iteration: 반복 번호
            objective_fn: 목적 함수 (params -> result_summary)
        
        Returns:
            결과 요약
        """
        # 파라미터 제안
        params = self.optimizer.ask()
        logger.info(f"[TUNING] Iteration {iteration}: asking for params")
        
        # 목적 함수 실행
        result_summary = objective_fn(params)
        
        # 결과 기록
        self.optimizer.tell(params, result_summary)
        self.results.append({
            "iteration": iteration,
            "params": params,
            "result": result_summary
        })
        
        # StateManager에 저장
        if self.state_manager:
            key = self.state_manager._get_key("tuning_result", str(iteration))
            self.state_manager._set_redis_or_memory(
                key,
                {
                    "iteration": str(iteration),
                    "params": str(params),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        return result_summary
    
    def get_results(self) -> List[Dict[str, Any]]:
        """모든 결과 조회"""
        return self.results
    
    def get_optimizer_history(self):
        """Optimizer 히스토리 조회"""
        return self.optimizer.get_history()


def load_tuning_config(config_path: str) -> TuningConfig:
    """
    YAML 파일에서 튜닝 설정 로드
    
    Args:
        config_path: 설정 파일 경로
    
    Returns:
        TuningConfig 인스턴스
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    tuning_data = data.get("tuning", {})
    
    config = TuningConfig(
        method=tuning_data.get("method", "grid"),
        scenarios=tuning_data.get("scenarios", []),
        search_space=tuning_data.get("search_space", {}),
        max_iterations=tuning_data.get("max_iterations", 10),
        seed=tuning_data.get("seed", None),
        grid_points=tuning_data.get("grid_points", 3),
        acquisition_fn=tuning_data.get("acquisition_fn", "ucb")
    )
    
    logger.info(f"[TUNING] Loaded config: method={config.method}, "
               f"scenarios={len(config.scenarios)}, "
               f"search_space={len(config.search_space)}")
    
    return config
