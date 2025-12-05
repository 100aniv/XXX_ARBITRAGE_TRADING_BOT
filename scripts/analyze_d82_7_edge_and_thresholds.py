#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-7: Edge Analysis & Threshold Recalibration

목적:
    D82-6 Sweep 결과를 기반으로 각 Entry/TP 조합의 Effective Edge를 분석하고,
    "이길 수 있는 Threshold 레인지"를 자동으로 계산합니다.

핵심 개념:
    - Effective Edge (bps) = avg_spread_bps - avg_slippage_bps
    - PnL (bps) = (pnl_usd / notional_usd) * 1e4
    - 추천 Threshold = 슬리피지 + 수수료 + 마진

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import logging
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import statistics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EdgeAnalysisResult:
    """Edge 분석 결과"""
    entry_bps: float
    tp_bps: float
    run_id: str
    
    # 원본 KPI 데이터
    entries: int
    round_trips: int
    win_rate_pct: float
    pnl_usd: float
    
    # Slippage 데이터
    avg_buy_slippage_bps: float
    avg_sell_slippage_bps: float
    avg_slippage_bps: float  # (buy + sell) / 2
    
    # Edge 계산 결과
    # Note: 실제 spread는 TradeLog에서 계산해야 하지만,
    # 현재는 Entry/TP threshold를 proxy로 사용
    estimated_avg_spread_bps: float  # (entry + tp) / 2 근사치
    effective_edge_bps: float  # spread - slippage
    
    # PnL bps (notional 기준)
    # TODO: 실제 notional_usd를 KPI에서 가져와야 정확함
    # 임시로 대략적인 값 사용 (round_trips * 평균 주문 크기)
    estimated_notional_usd: float
    pnl_bps: float
    
    # 종합 평가
    is_structurally_profitable: bool  # effective_edge_bps > 0
    
    # 수수료 (상수, TODO: 실제 Fee Model 연동 예정)
    fee_bps: float = 9.0  # Upbit 5bps + Binance 4bps


@dataclass
class ThresholdRecommendation:
    """Threshold 추천 결과"""
    # 슬리피지 통계
    avg_slippage_bps: float
    p50_slippage_bps: float
    p95_slippage_bps: float
    max_slippage_bps: float
    
    # 추천 레인지 (보수적)
    recommended_entry_bps_list: List[float]
    recommended_tp_bps_list: List[float]
    
    # 계산 로직
    calculation_logic: str
    rationale: str


class EdgeAnalyzer:
    """
    Edge 분석기
    
    D82-6 Sweep 결과를 읽어서:
    1. 각 조합의 Effective Edge 계산
    2. 슬리피지 분포 분석
    3. 추천 Threshold 레인지 계산
    """
    
    def __init__(
        self,
        sweep_summary_path: Path,
        output_dir: Path,
        fee_bps: float = 9.0,
        estimated_notional_per_rt: float = 20000.0  # $20k per round trip (임시)
    ):
        """
        EdgeAnalyzer 초기화
        
        Args:
            sweep_summary_path: Sweep summary JSON 경로
            output_dir: 분석 결과 저장 디렉토리
            fee_bps: 거래소 수수료 합계 (Upbit 5 + Binance 4 = 9 bps)
            estimated_notional_per_rt: Round trip 당 예상 notional (USD)
        """
        self.sweep_summary_path = sweep_summary_path
        self.output_dir = output_dir
        self.fee_bps = fee_bps
        self.estimated_notional_per_rt = estimated_notional_per_rt
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"[D82-7] EdgeAnalyzer initialized: "
            f"sweep_summary={sweep_summary_path}, "
            f"fee_bps={fee_bps}, "
            f"output_dir={output_dir}"
        )
    
    def load_sweep_summary(self) -> Dict[str, Any]:
        """Sweep summary JSON 로드"""
        with open(self.sweep_summary_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(
            f"[D82-7] Loaded sweep summary: "
            f"total_runs={data['sweep_metadata']['total_runs']}"
        )
        return data
    
    def calculate_edge_for_result(self, result: Dict[str, Any]) -> EdgeAnalysisResult:
        """
        개별 결과의 Edge 계산
        
        Args:
            result: Sweep summary의 results 항목 하나
        
        Returns:
            EdgeAnalysisResult 객체
        """
        entry_bps = result['entry_bps']
        tp_bps = result['tp_bps']
        
        # Slippage 계산
        buy_slip = result.get('avg_buy_slippage_bps', 0.0)
        sell_slip = result.get('avg_sell_slippage_bps', 0.0)
        avg_slip = (buy_slip + sell_slip) / 2.0
        
        # Spread 추정 (실제 TradeLog가 없으므로 Entry/TP threshold 기반 근사)
        # 진입 시 spread ≈ entry_bps, 퇴출 시 spread ≈ tp_bps
        # 평균 spread ≈ (entry + tp) / 2
        estimated_spread = (entry_bps + tp_bps) / 2.0
        
        # Effective Edge = Spread - Slippage
        effective_edge = estimated_spread - avg_slip
        
        # PnL bps 계산
        pnl_usd = result.get('pnl_usd', 0.0)
        round_trips = result.get('round_trips', 0)
        
        # Notional 추정: round_trips * 평균 주문 크기
        estimated_notional = round_trips * self.estimated_notional_per_rt if round_trips > 0 else 1.0
        pnl_bps = (pnl_usd / estimated_notional) * 1e4 if estimated_notional > 0 else 0.0
        
        # 구조적 수익성 판단
        # Effective Edge > Fee를 기준으로 판단
        is_profitable = effective_edge > self.fee_bps
        
        return EdgeAnalysisResult(
            entry_bps=entry_bps,
            tp_bps=tp_bps,
            run_id=result.get('run_id', ''),
            entries=result.get('entries', 0),
            round_trips=round_trips,
            win_rate_pct=result.get('win_rate_pct', 0.0),
            pnl_usd=pnl_usd,
            avg_buy_slippage_bps=buy_slip,
            avg_sell_slippage_bps=sell_slip,
            avg_slippage_bps=avg_slip,
            estimated_avg_spread_bps=estimated_spread,
            effective_edge_bps=effective_edge,
            estimated_notional_usd=estimated_notional,
            pnl_bps=pnl_bps,
            fee_bps=self.fee_bps,
            is_structurally_profitable=is_profitable
        )
    
    def calculate_slippage_statistics(
        self,
        edge_results: List[EdgeAnalysisResult]
    ) -> Dict[str, float]:
        """
        슬리피지 통계 계산
        
        Args:
            edge_results: Edge 분석 결과 리스트
        
        Returns:
            슬리피지 통계 딕셔너리
        """
        slippages = [r.avg_slippage_bps for r in edge_results]
        
        if not slippages:
            return {
                'avg': 0.0,
                'median': 0.0,
                'p95': 0.0,
                'max': 0.0,
                'min': 0.0,
                'std': 0.0
            }
        
        sorted_slips = sorted(slippages)
        p95_idx = int(len(sorted_slips) * 0.95)
        
        return {
            'avg': statistics.mean(slippages),
            'median': statistics.median(slippages),
            'p95': sorted_slips[p95_idx] if p95_idx < len(sorted_slips) else sorted_slips[-1],
            'max': max(slippages),
            'min': min(slippages),
            'std': statistics.stdev(slippages) if len(slippages) > 1 else 0.0
        }
    
    def recommend_thresholds(
        self,
        slip_stats: Dict[str, float]
    ) -> ThresholdRecommendation:
        """
        추천 Threshold 레인지 계산
        
        전략:
        1. Entry Threshold = ceil(p95_slippage + fee + margin)
        2. TP Threshold = ceil(Entry + p95_slippage + margin)
        3. 보수적으로 계산하여 "이길 수 있는 Zone"으로 이동
        
        Args:
            slip_stats: 슬리피지 통계
        
        Returns:
            ThresholdRecommendation 객체
        """
        avg_slip = slip_stats['avg']
        p95_slip = slip_stats['p95']
        
        # 보수적 마진 (추가 안전 버퍼)
        safety_margin_bps = 2.0
        
        # Entry Threshold 계산
        # Entry >= p95_slippage + fee + margin
        min_entry_raw = p95_slip + self.fee_bps + safety_margin_bps
        min_entry = math.ceil(min_entry_raw)
        
        # TP Threshold 계산
        # TP >= Entry + p95_slippage + margin
        min_tp_raw = min_entry + p95_slip + safety_margin_bps
        min_tp = math.ceil(min_tp_raw)
        
        # 추천 레인지 생성
        # Entry: [min_entry, min_entry + 2, min_entry + 4]
        # TP: [min_tp, min_tp + 3, min_tp + 6]
        entry_list = [
            round(min_entry, 1),
            round(min_entry + 2.0, 1),
            round(min_entry + 4.0, 1)
        ]
        
        tp_list = [
            round(min_tp, 1),
            round(min_tp + 3.0, 1),
            round(min_tp + 6.0, 1)
        ]
        
        # Upper cap 적용 (너무 극단적인 값 방지)
        entry_list = [e for e in entry_list if e <= 30.0]
        tp_list = [t for t in tp_list if t <= 40.0]
        
        # 최소 3개 보장
        if len(entry_list) < 3:
            entry_list = [min_entry, min_entry + 1.0, min_entry + 2.0]
        if len(tp_list) < 3:
            tp_list = [min_tp, min_tp + 2.0, min_tp + 4.0]
        
        calculation_logic = (
            f"Entry = ceil(p95_slip={p95_slip:.2f} + fee={self.fee_bps:.2f} + margin={safety_margin_bps:.2f}) = {min_entry:.1f}\n"
            f"TP = ceil(Entry={min_entry:.1f} + p95_slip={p95_slip:.2f} + margin={safety_margin_bps:.2f}) = {min_tp:.1f}"
        )
        
        rationale = (
            f"D82-6 결과에서 모든 조합이 손실을 기록한 이유는 Entry/TP threshold (0.3~2.0 bps)가 "
            f"평균 슬리피지 (~{avg_slip:.2f} bps)보다 훨씬 작았기 때문입니다. "
            f"새 추천 레인지는 p95 슬리피지 ({p95_slip:.2f} bps)와 수수료 ({self.fee_bps:.1f} bps)를 "
            f"모두 커버하도록 설정되었습니다."
        )
        
        return ThresholdRecommendation(
            avg_slippage_bps=avg_slip,
            p50_slippage_bps=slip_stats['median'],
            p95_slippage_bps=p95_slip,
            max_slippage_bps=slip_stats['max'],
            recommended_entry_bps_list=entry_list,
            recommended_tp_bps_list=tp_list,
            calculation_logic=calculation_logic,
            rationale=rationale
        )
    
    def analyze(self) -> Dict[str, Any]:
        """
        전체 분석 실행
        
        Returns:
            분석 결과 딕셔너리
        """
        logger.info("[D82-7] Starting edge analysis...")
        
        # 1. Sweep summary 로드
        sweep_data = self.load_sweep_summary()
        
        # 2. 각 결과의 Edge 계산
        edge_results = []
        for result in sweep_data['results']:
            edge_result = self.calculate_edge_for_result(result)
            edge_results.append(edge_result)
            
            logger.info(
                f"[D82-7] Entry={edge_result.entry_bps} TP={edge_result.tp_bps}: "
                f"Edge={edge_result.effective_edge_bps:.2f} bps, "
                f"PnL={edge_result.pnl_bps:.2f} bps, "
                f"Profitable={edge_result.is_structurally_profitable}"
            )
        
        # 3. 슬리피지 통계 계산
        slip_stats = self.calculate_slippage_statistics(edge_results)
        
        logger.info(
            f"[D82-7] Slippage stats: "
            f"avg={slip_stats['avg']:.2f}, "
            f"p95={slip_stats['p95']:.2f}, "
            f"max={slip_stats['max']:.2f}"
        )
        
        # 4. Threshold 추천
        recommendation = self.recommend_thresholds(slip_stats)
        
        logger.info(
            f"[D82-7] Recommended Entry: {recommendation.recommended_entry_bps_list}"
        )
        logger.info(
            f"[D82-7] Recommended TP: {recommendation.recommended_tp_bps_list}"
        )
        
        # 5. 결과 종합
        analysis_result = {
            'sweep_metadata': sweep_data['sweep_metadata'],
            'edge_analysis_results': [asdict(r) for r in edge_results],
            'slippage_statistics': slip_stats,
            'threshold_recommendation': asdict(recommendation),
            'summary': {
                'total_combinations': len(edge_results),
                'structurally_profitable_count': sum(1 for r in edge_results if r.is_structurally_profitable),
                'avg_effective_edge_bps': statistics.mean([r.effective_edge_bps for r in edge_results]),
                'avg_pnl_bps': statistics.mean([r.pnl_bps for r in edge_results]),
                'conclusion': (
                    "D82-6의 Entry/TP 레인지 (0.3~0.7 / 1.0~2.0 bps)는 구조적으로 수익 불가능한 Zone이었습니다. "
                    f"평균 슬리피지 {slip_stats['avg']:.2f} bps와 수수료 {self.fee_bps:.1f} bps를 고려하면, "
                    f"최소 Entry {recommendation.recommended_entry_bps_list[0]:.1f} bps, "
                    f"TP {recommendation.recommended_tp_bps_list[0]:.1f} bps 이상이 필요합니다."
                )
            }
        }
        
        # 6. 결과 저장
        output_path = self.output_dir / 'edge_analysis_summary.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"[D82-7] Analysis complete. Results saved to {output_path}")
        
        return analysis_result


def main():
    """메인 실행 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='D82-7: Edge Analysis & Threshold Recalibration'
    )
    parser.add_argument(
        '--sweep-summary',
        type=str,
        default='logs/d82-5/threshold_sweep_summary.json',
        help='Sweep summary JSON 경로'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='logs/d82-7',
        help='분석 결과 저장 디렉토리'
    )
    parser.add_argument(
        '--fee-bps',
        type=float,
        default=9.0,
        help='거래소 수수료 합계 (bps)'
    )
    parser.add_argument(
        '--notional-per-rt',
        type=float,
        default=20000.0,
        help='Round trip 당 예상 notional (USD)'
    )
    
    args = parser.parse_args()
    
    analyzer = EdgeAnalyzer(
        sweep_summary_path=Path(args.sweep_summary),
        output_dir=Path(args.output_dir),
        fee_bps=args.fee_bps,
        estimated_notional_per_rt=args.notional_per_rt
    )
    
    result = analyzer.analyze()
    
    # 요약 출력
    print("\n" + "="*80)
    print("D82-7: Edge Analysis Summary")
    print("="*80)
    print(f"\nTotal combinations: {result['summary']['total_combinations']}")
    print(f"Structurally profitable: {result['summary']['structurally_profitable_count']}")
    print(f"Avg effective edge: {result['summary']['avg_effective_edge_bps']:.2f} bps")
    print(f"Avg PnL: {result['summary']['avg_pnl_bps']:.2f} bps")
    print(f"\nSlippage statistics:")
    print(f"  Avg: {result['slippage_statistics']['avg']:.2f} bps")
    print(f"  P95: {result['slippage_statistics']['p95']:.2f} bps")
    print(f"  Max: {result['slippage_statistics']['max']:.2f} bps")
    print(f"\nRecommended Entry: {result['threshold_recommendation']['recommended_entry_bps_list']}")
    print(f"Recommended TP: {result['threshold_recommendation']['recommended_tp_bps_list']}")
    print(f"\nConclusion:\n{result['summary']['conclusion']}")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
