#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D24 Tuning Session Runner

실제 Paper Mode 시나리오를 실행하는 튜닝 세션 러너.
D23 Tuning Engine과 D18 Paper Engine을 통합하여 end-to-end 튜닝 실행.
"""

import argparse
import os
import sys
import csv
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbitrage.tuning import load_tuning_config, TuningHarness, build_tuning_key
from arbitrage.state_manager import StateManager
from arbitrage.paper_trader import PaperTrader

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


class TuningSessionRunner:
    """Tuning 세션 실행 엔진"""
    
    def __init__(
        self,
        config_path: str,
        iterations: int = 5,
        mode: str = "paper",
        env: str = "docker",
        optimizer_override: Optional[str] = None,
        output_csv: Optional[str] = None,
        session_id: Optional[str] = None,
        worker_id: str = "main",
        parallel_workers: int = 1
    ):
        """
        Args:
            config_path: 튜닝 설정 파일 경로
            iterations: 실행할 반복 횟수
            mode: 모드 (paper, shadow, live)
            env: 환경 (docker, local)
            optimizer_override: Optimizer 방법 오버라이드
            output_csv: CSV 출력 경로
            session_id: 세션 ID (기본: 자동 생성)
            worker_id: 워커 ID (기본: "main")
            parallel_workers: 병렬 워커 수 (기본: 1)
        """
        self.config_path = config_path
        self.iterations = iterations
        self.mode = mode
        self.env = env
        self.optimizer_override = optimizer_override
        self.output_csv = output_csv
        self.worker_id = worker_id
        self.parallel_workers = parallel_workers
        
        # 세션 ID (기존 세션 재사용 또는 새로 생성)
        self.session_id = session_id or str(uuid.uuid4())
        
        # 설정 로드
        self.config = load_tuning_config(config_path)
        
        # Optimizer 오버라이드
        if optimizer_override:
            self.config.method = optimizer_override
        
        # StateManager 초기화
        self.state_manager = self._create_state_manager()
        
        # TuningHarness 생성
        self.harness = TuningHarness(self.config, state_manager=self.state_manager)
        
        # 결과 저장소
        self.results = []
        
        logger.info(f"[D24_TUNING] Session initialized: session_id={self.session_id}")
        logger.info(f"[D24_TUNING] Config: method={self.config.method}, "
                   f"scenarios={len(self.config.scenarios)}, "
                   f"iterations={self.iterations}")
    
    def _create_state_manager(self) -> StateManager:
        """StateManager 생성"""
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        
        namespace = f"tuning:{self.env}:{self.mode}"
        
        state_manager = StateManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            namespace=namespace,
            enabled=True,
            key_prefix="arbitrage"
        )
        
        logger.info(f"[D24_TUNING] StateManager initialized: namespace={namespace}")
        return state_manager
    
    async def _objective_function_async(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        목적 함수: Paper Mode에서 시나리오 실행 (async)
        
        Args:
            params: 파라미터 딕셔너리
        
        Returns:
            결과 요약 (메트릭 키만)
        """
        logger.info(f"[D24_TUNING] Running objective with params: {params}")
        
        iteration = len(self.results) + 1
        metrics_aggregated = {
            "trades": 0,
            "total_fees": 0.0,
            "pnl": 0.0,
            "circuit_breaker_active": False,
            "safety_violations": 0
        }
        
        # 각 시나리오에 대해 PaperTrader 실행
        for scenario_file in self.config.scenarios:
            try:
                logger.info(f"[D24_TUNING] Running scenario: {scenario_file}")
                
                # PaperTrader 생성 및 실행
                redis_host = os.getenv("REDIS_HOST", "localhost")
                redis_port = int(os.getenv("REDIS_PORT", "6379"))
                
                paper_trader = PaperTrader(
                    scenario_path=scenario_file,
                    redis_host=redis_host,
                    redis_port=redis_port
                )
                
                # 시나리오 실행 (async)
                result = await paper_trader.run()
                
                # 결과 수집
                metrics_aggregated["trades"] += result.get("trades", 0)
                metrics_aggregated["total_fees"] += result.get("total_fees", 0.0)
                metrics_aggregated["pnl"] += result.get("pnl", 0.0)
                metrics_aggregated["circuit_breaker_active"] = result.get("circuit_breaker_active", False)
                metrics_aggregated["safety_violations"] += result.get("safety_violations", 0)
                
                logger.info(f"[D24_TUNING] Scenario completed: {scenario_file}")
            
            except Exception as e:
                logger.warning(f"[D24_TUNING] Scenario failed: {scenario_file}, error: {e}")
        
        result_summary = {
            "session_id": self.session_id,
            "iteration": iteration,
            "params": params,
            "metrics": metrics_aggregated,
            "scenario_files": self.config.scenarios,
            "timestamp": datetime.now().isoformat(),
            "status": "completed"
        }
        
        logger.info(f"[D24_RESULT] Iteration {result_summary['iteration']}: "
                   f"status={result_summary['status']}, "
                   f"trades={metrics_aggregated['trades']}, "
                   f"pnl={metrics_aggregated['pnl']}")
        
        return result_summary
    
    def _objective_function(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        목적 함수: Paper Mode에서 시나리오 실행 (동기 래퍼)
        
        Args:
            params: 파라미터 딕셔너리
        
        Returns:
            결과 요약 (메트릭 키만)
        """
        # asyncio 이벤트 루프에서 async 함수 실행
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self._objective_function_async(params))
    
    def run(self) -> bool:
        """
        튜닝 세션 실행 (병렬 실행 지원)
        
        Returns:
            성공 여부
        """
        logger.info(f"[D24_TUNING] Starting tuning session: {self.iterations} iterations, workers={self.parallel_workers}")
        
        try:
            if self.parallel_workers == 1:
                # 순차 실행
                return self._run_sequential()
            else:
                # 병렬 실행
                return self._run_parallel()
        
        except Exception as e:
            logger.error(f"[D24_TUNING] Session failed: {e}", exc_info=True)
            return False
    
    def _run_sequential(self) -> bool:
        """순차 실행"""
        for iteration in range(1, self.iterations + 1):
            logger.info(f"[D24_TUNING] Iteration {iteration}/{self.iterations}")
            
            # 반복 실행
            result = self.harness.run_iteration(iteration, self._objective_function)
            self.results.append(result)
            
            # StateManager에 저장
            self._persist_result(iteration, result)
        
        logger.info(f"[D24_TUNING] Session completed: {len(self.results)} iterations")
        return True
    
    def _run_parallel(self) -> bool:
        """병렬 실행"""
        results_by_iteration = {}
        
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            # 모든 반복을 병렬로 제출
            futures = {}
            for iteration in range(1, self.iterations + 1):
                future = executor.submit(self._run_iteration, iteration)
                futures[future] = iteration
            
            # 완료된 것부터 처리
            for future in as_completed(futures):
                iteration = futures[future]
                try:
                    result = future.result()
                    results_by_iteration[iteration] = result
                    self._persist_result(iteration, result)
                    logger.info(f"[D24_TUNING] Iteration {iteration} completed")
                except Exception as e:
                    logger.error(f"[D24_TUNING] Iteration {iteration} failed: {e}")
        
        # 순서대로 정렬하여 저장
        for iteration in range(1, self.iterations + 1):
            if iteration in results_by_iteration:
                self.results.append(results_by_iteration[iteration])
        
        logger.info(f"[D24_TUNING] Session completed: {len(self.results)} iterations")
        return len(self.results) == self.iterations
    
    def _run_iteration(self, iteration: int) -> Dict[str, Any]:
        """단일 반복 실행"""
        logger.info(f"[D24_TUNING] Iteration {iteration}/{self.iterations}")
        result = self.harness.run_iteration(iteration, self._objective_function)
        return result
    
    def _persist_result(self, iteration: int, result: Dict[str, Any]) -> None:
        """결과를 StateManager에 저장 (분산 구조 지원)"""
        try:
            # 분산 키 생성 (session_id + worker_id + iteration)
            tuning_key = build_tuning_key(
                session_id=self.session_id,
                worker_id=self.worker_id,
                iteration=iteration
            )
            
            key = self.state_manager._get_key(tuning_key)
            self.state_manager._set_redis_or_memory(
                key,
                {
                    "session_id": self.session_id,
                    "worker_id": self.worker_id,
                    "iteration": str(iteration),
                    "status": result.get("status", "unknown"),
                    "timestamp": result.get("timestamp", "")
                }
            )
            logger.info(f"[D24_TUNING] Result persisted: worker={self.worker_id}, iteration={iteration}")
        except Exception as e:
            logger.warning(f"[D24_TUNING] Failed to persist result: {e}")
    
    def save_csv(self) -> bool:
        """결과를 CSV 파일로 저장 (분산 구조 지원)"""
        if not self.output_csv:
            return True
        
        try:
            os.makedirs(os.path.dirname(self.output_csv), exist_ok=True)
            
            with open(self.output_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=['session_id', 'worker_id', 'iteration', 'status', 'timestamp']
                )
                writer.writeheader()
                
                for result in self.results:
                    writer.writerow({
                        'session_id': result.get('session_id', ''),
                        'worker_id': result.get('worker_id', self.worker_id),
                        'iteration': result.get('iteration', ''),
                        'status': result.get('status', ''),
                        'timestamp': result.get('timestamp', '')
                    })
            
            logger.info(f"[D24_TUNING] Results saved to CSV: {self.output_csv}")
            return True
        
        except Exception as e:
            logger.error(f"[D24_TUNING] Failed to save CSV: {e}")
            return False
    
    def print_summary(self) -> None:
        """실행 요약 출력"""
        print("\n" + "="*70)
        print("[D24_TUNING] SESSION SUMMARY")
        print("="*70)
        print(f"Session ID:        {self.session_id}")
        print(f"Iterations:        {len(self.results)}/{self.iterations}")
        print(f"Mode:              {self.mode}")
        print(f"Environment:       {self.env}")
        print(f"Optimizer:         {self.config.method}")
        print(f"Namespace:         tuning:{self.env}:{self.mode}")
        print(f"Scenarios:         {len(self.config.scenarios)}")
        print(f"Search Space:      {len(self.config.search_space)} parameters")
        
        if self.output_csv:
            print(f"CSV Output:        {self.output_csv}")
        
        print(f"Timestamp:         {datetime.now().isoformat()}")
        print("="*70 + "\n")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D24 Tuning Session Runner - Real end-to-end paper mode tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # Bayesian 최적화, 5 반복
  python scripts/run_d24_tuning_session.py \\
    --config configs/d23_tuning/advanced_baseline.yaml \\
    --iterations 5 \\
    --mode paper \\
    --env docker \\
    --optimizer bayesian \\
    --output-csv outputs/d24_tuning_session.csv
  
  # Grid Search, 3 반복
  python scripts/run_d24_tuning_session.py \\
    --config configs/d23_tuning/advanced_baseline.yaml \\
    --iterations 3 \\
    --mode paper \\
    --env docker \\
    --optimizer grid
        """
    )
    
    parser.add_argument(
        "--config",
        default="configs/d23_tuning/advanced_baseline.yaml",
        help="튜닝 설정 파일 경로 (기본값: configs/d23_tuning/advanced_baseline.yaml)"
    )
    
    parser.add_argument(
        "--iterations",
        type=int,
        default=5,
        help="실행할 반복 횟수 (기본값: 5)"
    )
    
    parser.add_argument(
        "--mode",
        choices=["paper", "shadow", "live"],
        default="paper",
        help="모드 (기본값: paper)"
    )
    
    parser.add_argument(
        "--env",
        choices=["local", "docker"],
        default="docker",
        help="환경 (기본값: docker)"
    )
    
    parser.add_argument(
        "--optimizer",
        choices=["grid", "random", "bayesian"],
        default=None,
        help="Optimizer 방법 (설정 파일 오버라이드)"
    )
    
    parser.add_argument(
        "--output-csv",
        default=None,
        help="CSV 출력 파일 경로 (선택사항)"
    )
    
    parser.add_argument(
        "--session-id",
        default=None,
        help="세션 ID (기본값: 자동 생성)"
    )
    
    parser.add_argument(
        "--worker-id",
        default="main",
        help="워커 ID (기본값: main)"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="병렬 워커 수 (기본값: 1)"
    )
    
    args = parser.parse_args()
    
    try:
        # 세션 러너 생성
        runner = TuningSessionRunner(
            config_path=args.config,
            iterations=args.iterations,
            mode=args.mode,
            env=args.env,
            optimizer_override=args.optimizer,
            output_csv=args.output_csv,
            session_id=args.session_id,
            worker_id=args.worker_id,
            parallel_workers=args.workers
        )
        
        # 세션 실행
        success = runner.run()
        
        # CSV 저장
        if success and args.output_csv:
            runner.save_csv()
        
        # 요약 출력
        runner.print_summary()
        
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"[D24_TUNING] Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
