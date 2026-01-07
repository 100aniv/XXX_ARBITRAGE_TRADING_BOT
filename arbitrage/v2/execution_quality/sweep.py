"""
D205-7: Parameter Sweep v1

ExecutionQuality 파라미터 튜닝을 위한 Grid/Random Sweep 엔진

Inputs:
- market.ndjson (기존 Replay 입력 재사용)
- 파라미터 범위 (slippage_alpha, partial_fill_penalty_bps 등)

Outputs:
- leaderboard.json (상위 N개 조합)
- best_params.json (최적 1세트)
- manifest.json (git_sha, branch, cmdline, python, platform, input_hash, ticks_count)

Metrics:
- positive_net_edge_rate: net_edge > 0 비율
- mean_net_edge_bps: 평균 순수익
- p10_net_edge_bps: 하방 리스크 (하위 10%)
"""

import json
import logging
import sys
import platform
import subprocess
import itertools
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

from arbitrage.v2.replay.replay_runner import ReplayRunner
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logger = logging.getLogger(__name__)


class ParameterSweep:
    """
    Parameter Sweep 엔진 (Grid Search v1)
    
    Args:
        input_path: market.ndjson 파일 경로
        output_dir: sweep 결과 출력 디렉토리
        param_grid: 파라미터 범위 딕셔너리
        break_even_params: 고정 BreakEvenParams
    """
    
    def __init__(
        self,
        input_path: Path,
        output_dir: Path,
        param_grid: Dict[str, List[float]],
        break_even_params: BreakEvenParams,
        notional: float = 100000.0,
    ):
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.param_grid = param_grid
        self.break_even_params = break_even_params
        self.notional = notional
        
        self.results: List[Dict[str, Any]] = []
        
        logger.info(f"[D205-7_SWEEP] Initialized: input={input_path}, output={output_dir}")
        logger.info(f"[D205-7_SWEEP] Param grid: {param_grid}")
    
    def run(self) -> Dict[str, Any]:
        """
        Sweep 실행
        
        Returns:
            실행 결과 딕셔너리
        """
        start_time = datetime.now()
        
        # 1. Grid 생성
        combinations = self._generate_grid()
        
        logger.info(f"[D205-7_SWEEP] Total combinations: {len(combinations)}")
        
        # 2. 각 조합 평가
        for idx, params in enumerate(combinations):
            logger.info(f"[D205-7_SWEEP] Evaluating {idx+1}/{len(combinations)}: {params}")
            
            metrics = self._evaluate_params(params)
            
            result = {
                "rank": idx + 1,
                "params": params,
                "metrics": metrics,
            }
            
            self.results.append(result)
        
        # 3. Leaderboard 정렬 (positive_net_edge_rate 높은 순)
        self.results.sort(key=lambda x: x["metrics"]["positive_net_edge_rate"], reverse=True)
        
        # Rank 재부여
        for idx, result in enumerate(self.results):
            result["rank"] = idx + 1
        
        # 4. 결과 저장
        self._save_results()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        summary = {
            "status": "PASS",
            "duration_sec": duration,
            "combinations_total": len(combinations),
            "best_params": self.results[0]["params"] if self.results else {},
            "best_metrics": self.results[0]["metrics"] if self.results else {},
        }
        
        logger.info(f"[D205-7_SWEEP] Completed: {summary}")
        
        return summary
    
    def _generate_grid(self) -> List[Dict[str, float]]:
        """
        Grid 조합 생성
        
        Returns:
            파라미터 조합 리스트
        """
        keys = list(self.param_grid.keys())
        values = [self.param_grid[k] for k in keys]
        
        combinations = []
        for combo in itertools.product(*values):
            param_dict = {k: v for k, v in zip(keys, combo)}
            combinations.append(param_dict)
        
        return combinations
    
    def _evaluate_params(self, params: Dict[str, float]) -> Dict[str, float]:
        """
        단일 파라미터 조합 평가
        
        Args:
            params: 파라미터 딕셔너리
        
        Returns:
            Metric 딕셔너리
        """
        # ReplayRunner 생성 (파라미터 주입)
        # 임시 출력 디렉토리
        temp_output = self.output_dir / f"temp_{hash(tuple(params.items()))}"
        temp_output.mkdir(parents=True, exist_ok=True)
        
        # D205-14-6: params.json 저장 (Traceability)
        params_file = temp_output / "params.json"
        with open(params_file, 'w', encoding='utf-8') as f:
            json.dump({
                "slippage_alpha": params.get("slippage_alpha", 10.0),
                "partial_fill_penalty_bps": params.get("partial_fill_penalty_bps", 20.0),
                "max_safe_ratio": params.get("max_safe_ratio", 0.3),
                "min_spread_bps": params.get("min_spread_bps", None),
                "notional": self.notional,
            }, f, indent=2, ensure_ascii=False)
        
        runner = ReplayRunner(
            input_path=self.input_path,
            output_dir=temp_output,
            break_even_params=self.break_even_params,
            notional=self.notional,  # D205-14-6
        )
        
        # ExecutionQuality 모델 파라미터 주입
        from arbitrage.v2.execution_quality.model_v1 import SimpleExecutionQualityModel
        runner.exec_quality_model = SimpleExecutionQualityModel(
            slippage_alpha=params.get("slippage_alpha", 10.0),
            partial_fill_penalty_bps=params.get("partial_fill_penalty_bps", 20.0),
            max_safe_ratio=params.get("max_safe_ratio", 0.3),
        )
        
        # Replay 실행
        result = runner.run()
        
        if result["status"] == "FAIL":
            logger.error(f"[D205-7_SWEEP] Replay FAIL: {params}")
            return {
                "positive_net_edge_rate": 0.0,
                "mean_net_edge_bps": 0.0,
                "p10_net_edge_bps": 0.0,
            }
        
        # Decision 결과 로드
        decisions_path = temp_output / "decisions.ndjson"
        net_edges = []
        
        try:
            with open(decisions_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("net_edge_after_exec_bps") is not None:
                        net_edges.append(data["net_edge_after_exec_bps"])
        except Exception as e:
            logger.error(f"[D205-7_SWEEP] Decision load error: {e}")
        
        # Metrics 계산
        if not net_edges:
            return {
                "positive_net_edge_rate": 0.0,
                "mean_net_edge_bps": 0.0,
                "p10_net_edge_bps": 0.0,
            }
        
        positive_count = sum(1 for x in net_edges if x > 0)
        positive_rate = positive_count / len(net_edges)
        mean_net_edge = sum(net_edges) / len(net_edges)
        
        # p10 계산 (하위 10%)
        sorted_edges = sorted(net_edges)
        p10_index = int(len(sorted_edges) * 0.1)
        p10_net_edge = sorted_edges[p10_index] if p10_index < len(sorted_edges) else sorted_edges[0]
        
        return {
            "positive_net_edge_rate": round(positive_rate, 4),
            "mean_net_edge_bps": round(mean_net_edge, 2),
            "p10_net_edge_bps": round(p10_net_edge, 2),
        }
    
    def _save_results(self):
        """
        결과 저장 (leaderboard, best_params, manifest)
        """
        # 1. Leaderboard (상위 10개)
        leaderboard = self.results[:10]
        leaderboard_path = self.output_dir / "leaderboard.json"
        with open(leaderboard_path, "w", encoding="utf-8") as f:
            json.dump(leaderboard, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[D205-7_SWEEP] Saved leaderboard to {leaderboard_path}")
        
        # 2. Best params
        if self.results:
            best_params = self.results[0]["params"]
            best_params_path = self.output_dir / "best_params.json"
            with open(best_params_path, "w", encoding="utf-8") as f:
                json.dump(best_params, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[D205-7_SWEEP] Saved best_params to {best_params_path}")
        
        # 3. Manifest (git_sha, branch 등)
        git_sha_full = ""
        git_sha_short = ""
        git_branch = ""
        try:
            git_sha_full = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            git_sha_short = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
        except Exception as e:
            logger.warning(f"[D205-7_SWEEP] Git info collection failed: {e}")
        
        manifest = {
            "run_id": self.output_dir.name,
            "mode": "parameter_sweep",
            "timestamp": datetime.now().isoformat(),
            "input_path": str(self.input_path.relative_to(Path.cwd())) if self.input_path.is_relative_to(Path.cwd()) else str(self.input_path),
            "combinations_total": len(self.results),
            "param_grid": self.param_grid,
            "git_sha_full": git_sha_full,
            "git_sha_short": git_sha_short,
            "branch": git_branch,
            "cmdline": " ".join(sys.argv),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        }
        
        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[D205-7_SWEEP] Saved manifest to {manifest_path}")
