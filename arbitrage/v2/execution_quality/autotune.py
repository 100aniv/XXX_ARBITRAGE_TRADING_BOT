"""
D205-14: Auto Tuning (v1) - Config SSOT 기반 파라미터 튜닝

ParameterSweep 재사용 기반 AutoTuner 클래스

Usage:
    from arbitrage.v2.execution_quality.autotune import AutoTuner
    tuner = AutoTuner(config=config, input_path=Path(...), output_dir=Path(...))
    result = tuner.run()
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from arbitrage.v2.execution_quality.sweep import ParameterSweep
from arbitrage.v2.core.config import V2Config
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logger = logging.getLogger(__name__)


class AutoTuner:
    """
    Auto Tuning Runner (v1)
    
    Config SSOT 기반 파라미터 자동 튜닝
    - ParameterSweep 재사용
    - Grid Search v1 (Random/Bayesian은 v2 이후)
    - leaderboard.json, best_params.json 생성
    
    Args:
        config: V2Config (tuning.param_ranges 포함)
        input_path: Replay market.ndjson 파일 경로
        output_dir: 결과 출력 디렉토리
    """
    
    def __init__(
        self,
        config: V2Config,
        input_path: Path,
        output_dir: Path,
    ):
        self.config = config
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Config에서 param_ranges 추출
        if not hasattr(config, 'tuning'):
            raise ValueError("config.tuning not found - check config.yml")
        
        self.param_ranges = config.tuning.param_ranges
        if not self.param_ranges:
            raise ValueError("config.tuning.param_ranges is empty")
        
        logger.info(f"[D205-14_AUTOTUNE] Initialized: input={input_path}, output={output_dir}")
        logger.info(f"[D205-14_AUTOTUNE] Param ranges: {self.param_ranges}")
    
    def run(self) -> Dict[str, Any]:
        """
        Auto Tuning 실행
        
        Returns:
            실행 결과 딕셔너리 (leaderboard, best_params)
        """
        logger.info("[D205-14_AUTOTUNE] Starting auto tuning...")
        
        # BreakEvenParams 고정 (ExecutionQuality 외부 파라미터)
        fee_a = FeeStructure(
            "upbit",
            maker_fee_bps=self.config.exchanges['upbit'].taker_fee_bps,
            taker_fee_bps=self.config.exchanges['upbit'].taker_fee_bps,
        )
        fee_b = FeeStructure(
            "binance",
            maker_fee_bps=self.config.exchanges['binance'].taker_fee_bps,
            taker_fee_bps=self.config.exchanges['binance'].taker_fee_bps,
        )
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=self.config.strategy.threshold.slippage_bps,
            buffer_bps=self.config.strategy.threshold.buffer_bps,
        )
        
        # ParameterSweep 생성 (재사용)
        sweep = ParameterSweep(
            input_path=self.input_path,
            output_dir=self.output_dir,
            param_grid=self.param_ranges,
            break_even_params=break_even_params,
        )
        
        # Sweep 실행
        result = sweep.run()
        
        logger.info(f"[D205-14_AUTOTUNE] Sweep completed: {result.get('combinations_total', 0)} combinations")
        
        # ParameterSweep가 이미 leaderboard.json과 best_params.json을 저장했으므로 다시 로드
        leaderboard_path = self.output_dir / "leaderboard.json"
        best_params_path = self.output_dir / "best_params.json"
        
        leaderboard = []
        best_params = {}
        
        if leaderboard_path.exists():
            with open(leaderboard_path, 'r') as f:
                leaderboard = json.load(f)
            logger.info(f"[D205-14_AUTOTUNE] Loaded leaderboard: {len(leaderboard)} entries")
        
        if best_params_path.exists():
            with open(best_params_path, 'r') as f:
                best_params = json.load(f)
            logger.info(f"[D205-14_AUTOTUNE] Loaded best_params: {best_params}")
        
        return {
            "leaderboard": leaderboard,
            "best_params": best_params,
            "output_dir": str(self.output_dir),
        }
