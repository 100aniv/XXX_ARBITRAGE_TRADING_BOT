#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-9: TP 10-12 bps 후보 분석 & 선정

목적:
    D82-8 결과 분석 기반으로 TP Threshold를 10-12 bps로 하향 조정한
    후보 조합을 선정하여 Real PAPER 검증 준비.

배경:
    - D82-8: Entry 10-14, TP 15-20 bps → 거래 발생 but Win Rate 0%
    - 문제: TP가 너무 높아 time_limit 청산
    - 해결: TP를 10-12 bps로 낮춰 TP 도달 가능성 증가

선정 기준:
    1. Entry <= TP (필수)
    2. Effective Edge = Entry + TP - Slippage - Fee > 0 (구조적 안전성)
    3. Entry가 낮을수록 거래 기회 증가 (D82-8에서 검증)
    4. TP가 낮을수록 Win Rate 증가 가능성
    5. 다양한 Trade-off 포인트 탐색

후보 조합 (초안):
    Entry [10, 12, 14] × TP [10, 11, 12]
    → 총 9개 조합에서 4-5개 선정

Usage:
    python scripts/analyze_d82_9_tp_candidates.py
    
    # 출력: logs/d82-9/selected_candidates.json

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import logging
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any

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
# Constants from D82-7/8 Analysis
# =============================================================================

# D82-8 실측 슬리피지 (평균)
AVG_SLIPPAGE_BPS = 2.14

# 수수료
FEE_BPS = 9.0  # Upbit 5 + Binance 4

# 최소 안전 마진 (보수적)
MIN_SAFETY_MARGIN_BPS = 0.5


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ThresholdCandidate:
    """Threshold 후보 조합"""
    entry_bps: float
    tp_bps: float
    rationale: str
    
    # 계산된 지표
    estimated_spread_bps: float  # (entry + tp) / 2
    effective_edge_bps: float    # spread - slippage - fee
    structural_safety: bool      # effective_edge > 0
    
    # 우선순위 (1=최고, 낮을수록 우선)
    priority: int
    
    # 예상 Trade Activity (D82-8 대비)
    expected_trade_activity: str  # "high", "medium", "low"
    
    # 예상 Win Rate (정성적)
    expected_win_rate: str  # "high", "medium", "low"


# =============================================================================
# Analysis Functions
# =============================================================================

def calculate_effective_edge(entry_bps: float, tp_bps: float) -> float:
    """
    Effective Edge 계산.
    
    Effective Edge = Estimated_Spread - Slippage - Fee
    Estimated_Spread = (Entry + TP) / 2
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
    
    Returns:
        Effective Edge (bps)
    """
    estimated_spread = (entry_bps + tp_bps) / 2
    effective_edge = estimated_spread - AVG_SLIPPAGE_BPS - FEE_BPS
    return effective_edge


def estimate_trade_activity(entry_bps: float) -> str:
    """
    Entry threshold 기반 거래 활동 추정.
    
    D82-8 결과:
    - Entry 10: 7 entries (highest)
    - Entry 12: 6 entries
    - Entry 14: 7 entries
    
    → Entry가 낮을수록 거래 기회 증가
    
    Args:
        entry_bps: Entry threshold (bps)
    
    Returns:
        "high", "medium", "low"
    """
    if entry_bps <= 10:
        return "high"
    elif entry_bps <= 12:
        return "medium"
    else:
        return "low"


def estimate_win_rate(tp_bps: float) -> str:
    """
    TP threshold 기반 Win Rate 추정.
    
    D82-8 결과:
    - TP 15-20: Win Rate 0% (모두 time_limit)
    
    → TP가 낮을수록 도달 가능성 증가
    
    Args:
        tp_bps: TP threshold (bps)
    
    Returns:
        "high", "medium", "low"
    """
    if tp_bps <= 10:
        return "high"
    elif tp_bps <= 11:
        return "medium"
    else:
        return "low"


def generate_candidate_combinations() -> List[Dict[str, float]]:
    """
    후보 조합 생성 (Entry × TP grid).
    
    현실적 범위:
    - D82-7 분석: min_entry=14, min_tp=19 (구조적 최소값)
    - D82-8 실험: Entry 10-14, TP 15-20 (Win Rate 0%)
    - D82-9 목표: TP를 13-15로 낮춰 TP 도달 가능성 증가
    
    Returns:
        List of {"entry_bps", "tp_bps"} dicts
    """
    # 현실적인 범위로 조정
    entry_values = [10.0, 12.0, 14.0]
    tp_values = [13.0, 14.0, 15.0]  # 10-12는 너무 낮음
    
    combinations = []
    for entry in entry_values:
        for tp in tp_values:
            # Entry <= TP 조건 (필수)
            if entry <= tp:
                combinations.append({
                    "entry_bps": entry,
                    "tp_bps": tp,
                })
    
    return combinations


def select_top_candidates(
    all_candidates: List[ThresholdCandidate],
    max_candidates: int = 5
) -> List[ThresholdCandidate]:
    """
    우선순위 기반 상위 후보 선정.
    
    선정 기준:
    1. Structural safety (effective_edge > 0) 필수
    2. Priority 낮은 순 (1=최고)
    3. Effective Edge 높은 순
    
    Args:
        all_candidates: 모든 후보 리스트
        max_candidates: 최대 선정 개수
    
    Returns:
        선정된 후보 리스트 (우선순위 순)
    """
    # 구조적 안전성 필터
    safe_candidates = [c for c in all_candidates if c.structural_safety]
    
    if not safe_candidates:
        logger.warning("구조적으로 안전한 후보가 없습니다!")
        return []
    
    # Priority → Effective Edge 순 정렬
    safe_candidates.sort(key=lambda c: (c.priority, -c.effective_edge_bps))
    
    # 상위 N개 선정
    selected = safe_candidates[:max_candidates]
    
    logger.info(f"전체 후보: {len(all_candidates)}, 안전한 후보: {len(safe_candidates)}, 선정: {len(selected)}")
    
    return selected


# =============================================================================
# Main Analysis
# =============================================================================

def analyze_and_select_candidates() -> List[ThresholdCandidate]:
    """
    D82-9 후보 분석 및 선정.
    
    Returns:
        선정된 후보 리스트
    """
    logger.info("=" * 80)
    logger.info("[D82-9] TP 10-12 bps 후보 분석 시작")
    logger.info("=" * 80)
    
    # 1. 조합 생성
    logger.info("\n[Step 1] 후보 조합 생성")
    raw_combinations = generate_candidate_combinations()
    logger.info(f"생성된 조합: {len(raw_combinations)}개")
    
    # 2. 각 조합 평가
    logger.info("\n[Step 2] 조합별 지표 계산")
    candidates = []
    
    for combo in raw_combinations:
        entry = combo["entry_bps"]
        tp = combo["tp_bps"]
        
        # Effective Edge 계산
        estimated_spread = (entry + tp) / 2
        effective_edge = calculate_effective_edge(entry, tp)
        structural_safety = effective_edge > 0
        
        # Trade Activity & Win Rate 추정
        trade_activity = estimate_trade_activity(entry)
        win_rate = estimate_win_rate(tp)
        
        # Rationale 생성
        if entry == 10 and tp == 13:
            rationale = "Entry 최저 + TP 최저. 거래 기회 최대화 + TP 도달 가능성 향상. D82-8 (10/15) 대비 TP -2 bps"
            priority = 1  # 최우선
        elif entry == 10 and tp == 14:
            rationale = "Entry 최저 + TP 중간. Trade Activity 최고, Win Rate 기대. D82-8 대비 TP -1 bps"
            priority = 2
        elif entry == 10 and tp == 15:
            rationale = "Entry 최저 + TP 중상. D82-8 (10/15)와 동일. 재검증 목적"
            priority = 5
        elif entry == 12 and tp == 13:
            rationale = "Entry 중간 + TP 최저. 균형적 접근. D82-8 (12/18) 대비 TP -5 bps"
            priority = 3
        elif entry == 12 and tp == 14:
            rationale = "Entry 중간 + TP 중간. 보수적 균형점. D82-8 대비 TP -4 bps"
            priority = 4
        elif entry == 12 and tp == 15:
            rationale = "Entry 중간 + TP 중상. D82-8 (12/18) 대비 TP -3 bps"
            priority = 6
        elif entry == 14 and tp == 14:
            rationale = "Entry/TP 동일 최상단. 구조적 안전성, 거래 기회 최소. D82-7 하한(14/19) 근접"
            priority = 7
        elif entry == 14 and tp == 15:
            rationale = "Entry/TP 상단. 구조적 안전성 우선. D82-8 (14/20) 대비 TP -5 bps"
            priority = 8
        else:
            rationale = f"Entry {entry}, TP {tp}"
            priority = 10
        
        candidate = ThresholdCandidate(
            entry_bps=entry,
            tp_bps=tp,
            rationale=rationale,
            estimated_spread_bps=round(estimated_spread, 2),
            effective_edge_bps=round(effective_edge, 2),
            structural_safety=structural_safety,
            priority=priority,
            expected_trade_activity=trade_activity,
            expected_win_rate=win_rate,
        )
        
        candidates.append(candidate)
        
        logger.info(
            f"  Entry={entry:4.1f}, TP={tp:4.1f} → "
            f"Edge={effective_edge:+5.2f}, Safe={structural_safety}, "
            f"Priority={priority}, Trade={trade_activity}, WinRate={win_rate}"
        )
    
    # 3. 상위 후보 선정
    logger.info("\n[Step 3] 상위 후보 선정 (최대 5개)")
    selected = select_top_candidates(candidates, max_candidates=5)
    
    logger.info(f"\n선정된 후보: {len(selected)}개")
    for i, c in enumerate(selected, 1):
        logger.info(
            f"  [{i}] Entry={c.entry_bps}, TP={c.tp_bps}, "
            f"Edge={c.effective_edge_bps:+.2f}, Priority={c.priority}"
        )
        logger.info(f"      → {c.rationale}")
    
    return selected


def save_candidates_to_json(
    candidates: List[ThresholdCandidate],
    output_path: Path
):
    """
    선정된 후보를 JSON 파일로 저장.
    
    Args:
        candidates: 후보 리스트
        output_path: 출력 파일 경로
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "metadata": {
            "task": "D82-9: TP 10-12 bps Fine-tuning",
            "analysis_date": "2025-12-05",
            "total_candidates": len(candidates),
            "avg_slippage_bps": AVG_SLIPPAGE_BPS,
            "fee_bps": FEE_BPS,
        },
        "candidates": [asdict(c) for c in candidates]
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n후보 저장 완료: {output_path}")


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """메인 함수."""
    try:
        # 후보 분석 & 선정
        selected_candidates = analyze_and_select_candidates()
        
        if not selected_candidates:
            logger.error("선정된 후보가 없습니다. 종료.")
            return 1
        
        # JSON 저장
        output_dir = Path("logs/d82-9")
        output_path = output_dir / "selected_candidates.json"
        save_candidates_to_json(selected_candidates, output_path)
        
        logger.info("\n" + "=" * 80)
        logger.info("[D82-9] 후보 분석 완료!")
        logger.info("=" * 80)
        logger.info(f"\n다음 단계:")
        logger.info(f"  1. 후보 확인: {output_path}")
        logger.info(f"  2. Real PAPER Runner 실행:")
        logger.info(f"     python scripts/run_d82_9_paper_candidates_longrun.py")
        
        return 0
        
    except Exception as e:
        logger.exception(f"분석 중 오류 발생: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
