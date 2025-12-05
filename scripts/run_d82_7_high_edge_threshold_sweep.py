#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-7: High-Edge Threshold Sweep Runner

목적:
    D82-7 Edge 분석 결과에서 계산된 "이길 수 있는 Threshold 레인지"로
    짧은 Real PAPER Sweep을 실행하여 구조적 타당성을 검증합니다.

작동 방식:
    1. edge_analysis_summary.json 로드
    2. 추천 Entry/TP 레인지 읽기
    3. run_d82_5_threshold_sweep.py 호출 (재사용)
    4. 결과를 logs/d82-7/high_edge_threshold_sweep_summary.json에 저장

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HighEdgeSweepRunner:
    """
    High-Edge Threshold Sweep Runner
    
    Edge 분석 결과를 읽어서 추천 Threshold 레인지로 Sweep을 실행합니다.
    """
    
    def __init__(
        self,
        edge_analysis_path: Path,
        output_dir: Path,
        duration_per_run_sec: int = 180,
        topn_size: int = 20,
        dry_run: bool = False
    ):
        """
        HighEdgeSweepRunner 초기화
        
        Args:
            edge_analysis_path: Edge 분석 결과 JSON 경로
            output_dir: Sweep 결과 저장 디렉토리
            duration_per_run_sec: 조합당 실행 시간 (초)
            topn_size: TopN universe 크기
            dry_run: True면 명령만 출력하고 실행하지 않음
        """
        self.edge_analysis_path = edge_analysis_path
        self.output_dir = output_dir
        self.duration_per_run_sec = duration_per_run_sec
        self.topn_size = topn_size
        self.dry_run = dry_run
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"[D82-7] HighEdgeSweepRunner initialized: "
            f"edge_analysis={edge_analysis_path}, "
            f"duration={duration_per_run_sec}s, "
            f"topn_size={topn_size}, "
            f"dry_run={dry_run}"
        )
    
    def load_edge_analysis(self) -> Dict[str, Any]:
        """Edge 분석 결과 로드"""
        if not self.edge_analysis_path.exists():
            raise FileNotFoundError(
                f"Edge analysis file not found: {self.edge_analysis_path}\n"
                f"Please run analyze_d82_7_edge_and_thresholds.py first."
            )
        
        with open(self.edge_analysis_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info("[D82-7] Edge analysis loaded successfully")
        return data
    
    def get_recommended_thresholds(
        self,
        edge_analysis: Dict[str, Any]
    ) -> tuple[List[float], List[float]]:
        """
        추천 Threshold 레인지 추출
        
        Args:
            edge_analysis: Edge 분석 결과 딕셔너리
        
        Returns:
            (entry_bps_list, tp_bps_list) 튜플
        """
        recommendation = edge_analysis['threshold_recommendation']
        entry_list = recommendation['recommended_entry_bps_list']
        tp_list = recommendation['recommended_tp_bps_list']
        
        logger.info(f"[D82-7] Recommended Entry: {entry_list}")
        logger.info(f"[D82-7] Recommended TP: {tp_list}")
        
        return entry_list, tp_list
    
    def run_sweep(
        self,
        entry_bps_list: List[float],
        tp_bps_list: List[float]
    ) -> Dict[str, Any]:
        """
        Threshold Sweep 실행
        
        기존 run_d82_5_threshold_sweep.py를 호출하여 실행합니다.
        
        Args:
            entry_bps_list: Entry threshold 리스트
            tp_bps_list: TP threshold 리스트
        
        Returns:
            Sweep 결과 딕셔너리
        """
        # 커맨드 구성
        entry_str = ",".join(str(e) for e in entry_bps_list)
        tp_str = ",".join(str(t) for t in tp_bps_list)
        
        cmd = [
            sys.executable,
            "scripts/run_d82_5_threshold_sweep.py",
            "--entry-bps-list", entry_str,
            "--tp-bps-list", tp_str,
            "--run-duration-seconds", str(self.duration_per_run_sec),
            "--topn-size", str(self.topn_size),
            "--validation-profile", "none",
            "--output-dir", str(self.output_dir)
        ]
        
        if self.dry_run:
            cmd.append("--dry-run")
        
        logger.info(f"[D82-7] Running sweep command: {' '.join(cmd)}")
        
        # 실행
        result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            capture_output=False,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"[D82-7] Sweep failed with exit code {result.returncode}")
            raise RuntimeError(f"Sweep execution failed: exit code {result.returncode}")
        
        # 결과 로드 (원본 스크립트는 threshold_sweep_summary.json 이름으로 저장)
        summary_path = self.output_dir / "threshold_sweep_summary.json"
        if summary_path.exists():
            with open(summary_path, 'r', encoding='utf-8') as f:
                sweep_result = json.load(f)
            logger.info("[D82-7] Sweep completed successfully")
            
            # D82-7용으로 복사 저장
            d82_7_summary_path = self.output_dir / "high_edge_threshold_sweep_summary.json"
            with open(d82_7_summary_path, 'w', encoding='utf-8') as f:
                json.dump(sweep_result, f, indent=2, ensure_ascii=False)
            logger.info(f"[D82-7] Summary also saved to {d82_7_summary_path}")
            
            return sweep_result
        else:
            logger.warning(f"[D82-7] Sweep summary not found at {summary_path}")
            return {}
    
    def execute(self) -> Dict[str, Any]:
        """
        전체 실행 플로우
        
        Returns:
            Sweep 결과 딕셔너리
        """
        logger.info("[D82-7] Starting high-edge threshold sweep...")
        
        # 1. Edge 분석 결과 로드
        edge_analysis = self.load_edge_analysis()
        
        # 2. 추천 Threshold 추출
        entry_list, tp_list = self.get_recommended_thresholds(edge_analysis)
        
        # 3. Sweep 실행
        sweep_result = self.run_sweep(entry_list, tp_list)
        
        logger.info("[D82-7] High-edge threshold sweep complete")
        
        return sweep_result


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='D82-7: High-Edge Threshold Sweep Runner'
    )
    parser.add_argument(
        '--edge-analysis',
        type=str,
        default='logs/d82-7/edge_analysis_summary.json',
        help='Edge 분석 결과 JSON 경로'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='logs/d82-7',
        help='Sweep 결과 저장 디렉토리'
    )
    parser.add_argument(
        '--duration-per-run',
        type=int,
        default=180,
        help='조합당 실행 시간 (초)'
    )
    parser.add_argument(
        '--topn-size',
        type=int,
        default=20,
        help='TopN universe 크기'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='명령만 출력하고 실행하지 않음'
    )
    
    args = parser.parse_args()
    
    runner = HighEdgeSweepRunner(
        edge_analysis_path=Path(args.edge_analysis),
        output_dir=Path(args.output_dir),
        duration_per_run_sec=args.duration_per_run,
        topn_size=args.topn_size,
        dry_run=args.dry_run
    )
    
    try:
        result = runner.execute()
        
        # 요약 출력
        if result and 'sweep_metadata' in result:
            print("\n" + "="*80)
            print("D82-7: High-Edge Threshold Sweep Summary")
            print("="*80)
            print(f"\nTotal runs: {result['sweep_metadata']['total_runs']}")
            print(f"Duration per run: {result['sweep_metadata']['duration_per_run_sec']}s")
            print(f"Entry thresholds: {result['sweep_metadata']['entry_bps_list']}")
            print(f"TP thresholds: {result['sweep_metadata']['tp_bps_list']}")
            
            if 'results' in result:
                print(f"\nResults:")
                for r in result['results']:
                    print(
                        f"  Entry={r['entry_bps']}, TP={r['tp_bps']}: "
                        f"Entries={r['entries']}, RT={r['round_trips']}, "
                        f"PnL=${r['pnl_usd']:.2f}"
                    )
            print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"[D82-7] Execution failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
