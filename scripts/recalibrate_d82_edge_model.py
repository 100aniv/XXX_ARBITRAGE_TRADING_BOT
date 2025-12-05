#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-10: Edge 모델 재보정 & TP/Entry 후보 재선정

목적:
    D82-9 cost profile을 사용하여 D82-7 이론 Edge 모델을 현실에 맞게 재보정하고,
    Optimistic/Realistic/Conservative 시나리오별로 이론 Edge를 재계산하여
    실전 가능한 후보 세트를 도출.

출력:
    logs/d82-10/recalibrated_tp_entry_candidates.json
    logs/d82-10/edge_recalibration_report.json

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import logging
import sys
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Enums & Data Classes
# =============================================================================

class EdgeScenario(str, Enum):
    """Edge 계산 시나리오"""
    OPTIMISTIC = "optimistic"      # 중앙값 수준 비용
    REALISTIC = "realistic"         # 평균~상위 quartile 비용
    CONSERVATIVE = "conservative"   # 상위 quartile 비용


@dataclass
class ScenarioParams:
    """시나리오별 비용 파라미터"""
    scenario: EdgeScenario
    slippage_bps: float           # 편도 슬리피지
    fee_bps: float                # 편도 수수료
    buy_fill_ratio: float         # 매수 체결률 (0~1)
    description: str


@dataclass
class EdgeCalculation:
    """Edge 계산 결과"""
    entry_bps: float
    tp_bps: float
    scenario: EdgeScenario
    
    # 계산 과정
    gross_spread_bps: float       # (Entry + TP) / 2
    entry_slippage_bps: float     # Entry 시 슬리피지
    entry_fee_bps: float          # Entry 시 수수료
    exit_slippage_bps: float      # Exit 시 슬리피지
    exit_fee_bps: float           # Exit 시 수수료
    total_cost_bps: float         # 총 비용
    
    # 최종 Edge
    net_edge_bps: float           # Gross spread - Total cost
    
    # 판단
    is_viable: bool               # Edge >= 0
    is_recommended: bool          # Edge >= threshold


@dataclass
class RecalibratedCandidate:
    """재보정된 후보 조합"""
    entry_bps: float
    tp_bps: float
    edge_optimistic: float
    edge_realistic: float
    edge_conservative: float
    is_structurally_safe: bool    # Conservative >= 0
    is_recommended: bool          # Realistic >= 0.5
    rationale: str


# =============================================================================
# Cost Profile Loading
# =============================================================================

def load_cost_profile(profile_path: Path) -> Dict[str, Any]:
    """
    D82-9 비용 프로파일 JSON 로드.
    
    Args:
        profile_path: JSON 파일 경로
    
    Returns:
        비용 프로파일 dict
    """
    if not profile_path.exists():
        raise FileNotFoundError(f"Cost profile not found: {profile_path}")
    
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)
    
    logger.info(f"Loaded cost profile from {profile_path}")
    return profile


def create_scenario_params(cost_profile: Dict[str, Any]) -> Dict[EdgeScenario, ScenarioParams]:
    """
    비용 프로파일로부터 시나리오별 파라미터 생성.
    
    Args:
        cost_profile: D82-9 비용 프로파일
    
    Returns:
        시나리오별 파라미터 dict
    """
    # 기본 값
    fee_bps = cost_profile["fee_total_bps"]
    
    # 슬리피지 (편도, 총 왕복은 2배)
    slippage_avg = cost_profile["slippage_avg"]
    slippage_median = cost_profile["slippage_median"]
    slippage_p75 = cost_profile["slippage_p75"]
    slippage_p90 = cost_profile["slippage_p90"]
    
    # 필률
    buy_fill_avg = cost_profile["buy_fill_ratio_avg"] / 100  # % to ratio
    buy_fill_p25 = cost_profile["buy_fill_ratio_p25"] / 100
    
    scenarios = {
        EdgeScenario.OPTIMISTIC: ScenarioParams(
            scenario=EdgeScenario.OPTIMISTIC,
            slippage_bps=slippage_median,  # 중앙값
            fee_bps=fee_bps,
            buy_fill_ratio=buy_fill_avg,   # 평균 필률
            description="Median slippage, average fill ratio"
        ),
        EdgeScenario.REALISTIC: ScenarioParams(
            scenario=EdgeScenario.REALISTIC,
            slippage_bps=slippage_p75,     # 75% 백분위
            fee_bps=fee_bps,
            buy_fill_ratio=buy_fill_avg,   # 평균 필률
            description="P75 slippage, average fill ratio"
        ),
        EdgeScenario.CONSERVATIVE: ScenarioParams(
            scenario=EdgeScenario.CONSERVATIVE,
            slippage_bps=slippage_p90,     # 90% 백분위
            fee_bps=fee_bps,
            buy_fill_ratio=buy_fill_p25,   # 하위 quartile 필률 (pessimistic)
            description="P90 slippage, P25 fill ratio (pessimistic)"
        ),
    }
    
    return scenarios


# =============================================================================
# Edge Calculation
# =============================================================================

def compute_theoretical_edge(
    entry_bps: float,
    tp_bps: float,
    params: ScenarioParams,
) -> EdgeCalculation:
    """
    주어진 Entry/TP와 비용 파라미터로 이론 Edge 계산.
    
    Edge 계산 로직:
        1. Gross Spread = (Entry + TP) / 2
        2. Roundtrip Slippage = Slippage_per_trade * 2 (Entry + Exit)
        3. Roundtrip Fee = Fee (already total for both sides)
        4. Total Cost = Roundtrip Slippage + Roundtrip Fee
        5. Net Edge = Gross Spread - Total Cost
    
    Note:
        - D82-9 슬리피지 2.14 bps는 편도 (buy+sell 평균)
        - 왕복에는 Entry 슬리피지 + Exit 슬리피지 = 2.14 * 2
        - 수수료 9.0 bps는 이미 양쪽 거래소 합산 (Upbit 5 + Binance 4)
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        params: 시나리오 파라미터
    
    Returns:
        EdgeCalculation 객체
    """
    # Gross spread (이론적 평균 스프레드)
    gross_spread = (entry_bps + tp_bps) / 2
    
    # Roundtrip costs
    # Slippage: Entry + Exit (both directions)
    entry_slippage = params.slippage_bps
    exit_slippage = params.slippage_bps
    roundtrip_slippage = entry_slippage + exit_slippage
    
    # Fee: Already total (Upbit + Binance)
    roundtrip_fee = params.fee_bps
    
    # Total cost
    total_cost = roundtrip_slippage + roundtrip_fee
    
    # Net Edge
    net_edge = gross_spread - total_cost
    
    # Viability
    is_viable = net_edge >= 0
    is_recommended = net_edge >= 0.5  # 최소 0.5 bps Edge
    
    return EdgeCalculation(
        entry_bps=entry_bps,
        tp_bps=tp_bps,
        scenario=params.scenario,
        gross_spread_bps=gross_spread,
        entry_slippage_bps=entry_slippage,
        entry_fee_bps=0,  # Fee는 roundtrip total로 계산
        exit_slippage_bps=exit_slippage,
        exit_fee_bps=roundtrip_fee,  # Total fee를 exit에 몰아서 표시
        total_cost_bps=total_cost,
        net_edge_bps=net_edge,
        is_viable=is_viable,
        is_recommended=is_recommended,
    )


def generate_candidate_grid() -> List[Tuple[float, float]]:
    """
    후보 Grid 생성.
    
    D82-9 실패 조합: Entry [10, 12] × TP [13, 14, 15]
    D82-10 재보정: 
        - 최소 비용 13.28 bps를 커버하려면 Gross Spread > 13.28
        - (Entry + TP) / 2 > 13.28 → Entry + TP > 26.56
        - 예: Entry 14, TP 14 → Spread 14 → Edge +0.72
        - Entry 범위를 6~16으로 확장, TP도 8~18로 확장
    
    Returns:
        (Entry, TP) 튜플 리스트
    """
    entry_candidates = [6, 8, 10, 12, 14, 16]
    tp_candidates = [8, 10, 12, 14, 16, 18]
    
    grid = []
    for entry in entry_candidates:
        for tp in tp_candidates:
            # Entry <= TP 조건
            if entry <= tp:
                grid.append((entry, tp))
    
    return grid


# =============================================================================
# Candidate Selection
# =============================================================================

def select_recalibrated_candidates(
    edge_calculations: Dict[Tuple[float, float], Dict[EdgeScenario, EdgeCalculation]]
) -> List[RecalibratedCandidate]:
    """
    Edge 계산 결과로부터 실전 후보 선정.
    
    선정 기준:
        1. Conservative Edge >= 0 (구조적 안전성)
        2. Realistic Edge >= 0.5 (실전 권장)
        3. 다양한 Entry/TP 조합 포함
    
    Args:
        edge_calculations: (Entry, TP) -> {Scenario -> EdgeCalculation}
    
    Returns:
        RecalibratedCandidate 리스트
    """
    candidates = []
    
    for (entry, tp), scenario_edges in edge_calculations.items():
        edge_opt = scenario_edges[EdgeScenario.OPTIMISTIC].net_edge_bps
        edge_real = scenario_edges[EdgeScenario.REALISTIC].net_edge_bps
        edge_cons = scenario_edges[EdgeScenario.CONSERVATIVE].net_edge_bps
        
        # 구조적 안전성
        is_safe = edge_cons >= 0
        
        # 실전 권장
        is_recommended = edge_real >= 0.5
        
        # Rationale 생성
        rationale_parts = []
        if is_recommended:
            rationale_parts.append("Realistic Edge >= 0.5 bps (recommended)")
        elif is_safe:
            rationale_parts.append("Conservative Edge >= 0 (structurally safe)")
        else:
            rationale_parts.append("All scenarios Edge < 0 (NOT RECOMMENDED)")
        
        # Entry/TP 특성
        if entry <= 8:
            rationale_parts.append("Low entry → high trade activity")
        if tp <= 10:
            rationale_parts.append("Low TP → high Win Rate potential")
        
        rationale = "; ".join(rationale_parts)
        
        candidate = RecalibratedCandidate(
            entry_bps=entry,
            tp_bps=tp,
            edge_optimistic=edge_opt,
            edge_realistic=edge_real,
            edge_conservative=edge_cons,
            is_structurally_safe=is_safe,
            is_recommended=is_recommended,
            rationale=rationale,
        )
        
        # 최소한 구조적으로 안전한 조합만 선택
        if is_safe:
            candidates.append(candidate)
    
    # 정렬: Realistic Edge 기준 내림차순
    candidates.sort(key=lambda c: c.edge_realistic, reverse=True)
    
    return candidates


# =============================================================================
# Report Generation
# =============================================================================

def generate_edge_comparison_table(
    edge_calculations: Dict[Tuple[float, float], Dict[EdgeScenario, EdgeCalculation]],
    d82_9_combinations: List[Tuple[float, float]]
) -> List[Dict[str, Any]]:
    """
    D82-9 실패 조합과 재보정 Edge 비교 테이블 생성.
    
    Args:
        edge_calculations: Edge 계산 결과
        d82_9_combinations: D82-9에서 사용한 조합
    
    Returns:
        비교 테이블 리스트
    """
    comparison = []
    
    for entry, tp in d82_9_combinations:
        if (entry, tp) in edge_calculations:
            edges = edge_calculations[(entry, tp)]
            comparison.append({
                "entry_bps": entry,
                "tp_bps": tp,
                "used_in_d82_9": True,
                "d82_9_result": "FAILED (0% WR, timeout)",
                "edge_optimistic": edges[EdgeScenario.OPTIMISTIC].net_edge_bps,
                "edge_realistic": edges[EdgeScenario.REALISTIC].net_edge_bps,
                "edge_conservative": edges[EdgeScenario.CONSERVATIVE].net_edge_bps,
            })
    
    return comparison


# =============================================================================
# Main
# =============================================================================

def main():
    """메인 함수."""
    logger.info("=" * 80)
    logger.info("[D82-10] Edge 모델 재보정 & 후보 재선정")
    logger.info("=" * 80)
    
    # 1. 비용 프로파일 로드
    profile_path = Path("logs/d82-10/d82_9_cost_profile.json")
    cost_profile = load_cost_profile(profile_path)
    
    # 2. 시나리오 파라미터 생성
    logger.info("")
    logger.info("Creating scenario parameters...")
    scenarios = create_scenario_params(cost_profile)
    
    for scenario, params in scenarios.items():
        logger.info(f"  {scenario.value}:")
        logger.info(f"    Slippage: {params.slippage_bps:.2f} bps")
        logger.info(f"    Fee:      {params.fee_bps:.2f} bps")
        logger.info(f"    Buy Fill: {params.buy_fill_ratio:.2%}")
        logger.info(f"    Desc:     {params.description}")
    
    # 3. 후보 Grid 생성
    logger.info("")
    logger.info("Generating candidate grid...")
    grid = generate_candidate_grid()
    logger.info(f"  Total combinations: {len(grid)}")
    
    # 4. Edge 계산
    logger.info("")
    logger.info("Computing theoretical edges...")
    edge_calculations = {}
    
    for entry, tp in grid:
        edge_calculations[(entry, tp)] = {}
        for scenario, params in scenarios.items():
            edge = compute_theoretical_edge(entry, tp, params)
            edge_calculations[(entry, tp)][scenario] = edge
    
    logger.info(f"  Computed {len(grid)} × {len(scenarios)} = {len(grid) * len(scenarios)} edges")
    
    # 5. 후보 선정
    logger.info("")
    logger.info("Selecting recalibrated candidates...")
    candidates = select_recalibrated_candidates(edge_calculations)
    logger.info(f"  Selected {len(candidates)} candidates")
    logger.info(f"  Recommended (Realistic >= 0.5): {sum(c.is_recommended for c in candidates)}")
    logger.info(f"  Safe (Conservative >= 0): {sum(c.is_structurally_safe for c in candidates)}")
    
    # 6. D82-9 조합 비교
    logger.info("")
    logger.info("Comparing with D82-9 combinations...")
    d82_9_combinations = [
        (10, 13), (10, 14), (10, 15),
        (12, 13), (12, 14),
    ]
    comparison_table = generate_edge_comparison_table(edge_calculations, d82_9_combinations)
    
    for row in comparison_table:
        logger.info(f"  Entry {row['entry_bps']}, TP {row['tp_bps']}:")
        logger.info(f"    Optimistic:   {row['edge_optimistic']:+.2f} bps")
        logger.info(f"    Realistic:    {row['edge_realistic']:+.2f} bps")
        logger.info(f"    Conservative: {row['edge_conservative']:+.2f} bps")
        logger.info(f"    D82-9 Result: {row['d82_9_result']}")
    
    # 7. JSON 출력
    output_dir = Path("logs/d82-10")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Candidates JSON
    candidates_path = output_dir / "recalibrated_tp_entry_candidates.json"
    candidates_data = {
        "metadata": {
            "source": "D82-9 recalibrated edge model",
            "scenarios": [s.value for s in EdgeScenario],
            "created_at": "2025-12-05",
            "cost_profile_source": str(profile_path),
        },
        "candidates": [asdict(c) for c in candidates],
    }
    
    with open(candidates_path, "w", encoding="utf-8") as f:
        json.dump(candidates_data, f, indent=2, ensure_ascii=False)
    
    logger.info("")
    logger.info(f"Candidates saved to: {candidates_path}")
    
    # Report JSON
    report_path = output_dir / "edge_recalibration_report.json"
    report_data = {
        "scenario_params": {k.value: asdict(v) for k, v in scenarios.items()},
        "grid_size": len(grid),
        "total_calculations": len(grid) * len(scenarios),
        "selected_candidates_count": len(candidates),
        "recommended_count": sum(c.is_recommended for c in candidates),
        "d82_9_comparison": comparison_table,
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Report saved to: {report_path}")
    
    # 8. 요약
    logger.info("")
    logger.info("=" * 80)
    logger.info("Summary")
    logger.info("=" * 80)
    logger.info(f"Top 5 recommended candidates:")
    for i, candidate in enumerate(candidates[:5], 1):
        logger.info(f"  {i}. Entry {candidate.entry_bps}, TP {candidate.tp_bps}")
        logger.info(f"     Edge (Real): {candidate.edge_realistic:+.2f} bps")
        logger.info(f"     {candidate.rationale}")
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
