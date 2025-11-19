"""
D68/D69 - Parameter Tuning & Robustness Test Module
전략 파라미터 자동 튜닝 및 결과 저장 + Robustness 테스트
"""

# Parameter Tuner (psycopg2 필요)
try:
    from .parameter_tuner import ParameterTuner, TuningConfig, TuningResult
    __all__ = ['ParameterTuner', 'TuningConfig', 'TuningResult']
except ImportError:
    # psycopg2가 없으면 parameter_tuner는 사용 불가
    __all__ = []

# Robustness Scenarios (독립적으로 사용 가능)
from .robustness_scenarios import (
    RobustnessScenario,
    ScenarioConfig,
    RobustnessInjector,
    create_scenario_config,
    SCENARIO_EXPECTATIONS
)

__all__ += [
    'RobustnessScenario',
    'ScenarioConfig',
    'RobustnessInjector',
    'create_scenario_config',
    'SCENARIO_EXPECTATIONS'
]
