#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-12: Lowered TP/Entry Candidates Generation

D77-4에서 검증된 낮은 threshold 구간 (5-10 bps)으로 회귀하여
실전 Trade Activity 및 수익성을 재검증하기 위한 후보 생성.

출력:
    logs/d82-12/lowered_tp_entry_candidates.json

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
import argparse

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
# Constants
# =============================================================================

# D77-4 검증된 낮은 threshold 구간
DEFAULT_ENTRY_CANDIDATES = [5.0, 7.0, 10.0]
DEFAULT_TP_CANDIDATES = [7.0, 10.0, 12.0]

# D82-9 실측 비용 구조 (D82-10에서 사용한 동일한 값)
SLIPPAGE_PER_TRADE_BPS = 2.14  # 편도 슬리피지
FEE_TOTAL_BPS = 9.0            # Upbit 5 + Binance 4
ROUNDTRIP_COST_BPS = SLIPPAGE_PER_TRADE_BPS * 2 + FEE_TOTAL_BPS  # 13.28 bps


# =============================================================================
# Edge Calculation
# =============================================================================

def calculate_edge(entry_bps: float, tp_bps: float) -> Dict[str, float]:
    """
    D82-10과 동일한 Edge 계산 로직
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
    
    Returns:
        Dict with gross_spread, roundtrip_cost, edge
    """
    # Gross spread (평균)
    gross_spread_bps = (entry_bps + tp_bps) / 2.0
    
    # Roundtrip cost
    roundtrip_cost_bps = ROUNDTRIP_COST_BPS
    
    # Net edge
    edge_bps = gross_spread_bps - roundtrip_cost_bps
    
    return {
        "gross_spread_bps": gross_spread_bps,
        "roundtrip_cost_bps": roundtrip_cost_bps,
        "edge_bps": edge_bps,
    }


# =============================================================================
# Candidate Generation
# =============================================================================

def generate_candidates(
    entry_list: List[float],
    tp_list: List[float],
) -> List[Dict[str, Any]]:
    """
    TP > Entry 조합만 생성
    
    Args:
        entry_list: Entry threshold 후보 리스트
        tp_list: TP threshold 후보 리스트
    
    Returns:
        List of candidate dicts
    """
    candidates = []
    
    for entry_bps in entry_list:
        for tp_bps in tp_list:
            # TP > Entry 조건만 유효
            if tp_bps <= entry_bps:
                continue
            
            # Edge 계산
            edge_calc = calculate_edge(entry_bps, tp_bps)
            
            # 후보 생성 (D82-10 호환 스키마)
            candidate = {
                "entry_bps": entry_bps,
                "tp_bps": tp_bps,
                "gross_spread_bps": edge_calc["gross_spread_bps"],
                "roundtrip_cost_bps": edge_calc["roundtrip_cost_bps"],
                "edge_bps": edge_calc["edge_bps"],
                "edge_optimistic": edge_calc["edge_bps"],  # D82-10 호환
                "edge_realistic": edge_calc["edge_bps"],   # D82-10 호환
                "edge_conservative": edge_calc["edge_bps"], # D82-10 호환
                "is_viable": edge_calc["edge_bps"] >= 0,
                "is_structurally_safe": edge_calc["edge_bps"] >= 0,  # D82-10 호환
                "is_recommended": True,  # D77-4 검증된 구간
                "is_d77_4_baseline": True,
                "rationale": f"D77-4 baseline zone (Entry={entry_bps}, TP={tp_bps})",
            }
            
            candidates.append(candidate)
    
    # Edge 내림차순 정렬
    candidates.sort(key=lambda x: x["edge_bps"], reverse=True)
    
    return candidates


# =============================================================================
# Output Generation
# =============================================================================

def save_candidates_json(
    candidates: List[Dict[str, Any]],
    output_path: Path,
):
    """
    D82-10과 동일한 JSON 스키마로 저장
    """
    # Candidates already have D82-10 compatible fields from generate_candidates()
    output_data = {
        "metadata": {
            "source": "D82-12 lowered TP/Entry re-baseline (D77-4 zone)",
            "created_at": "2025-12-05",
            "cost_profile": {
                "slippage_per_trade_bps": SLIPPAGE_PER_TRADE_BPS,
                "fee_total_bps": FEE_TOTAL_BPS,
                "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
            },
            "grid": {
                "entry_candidates": DEFAULT_ENTRY_CANDIDATES,
                "tp_candidates": DEFAULT_TP_CANDIDATES,
            },
            "note": "D77-4 baseline zone (Entry/TP 5-10 bps) for Quick Win validation",
        },
        "candidates": candidates,
    }
    
    # 디렉터리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # JSON 저장
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Candidates JSON saved: {output_path}")
    logger.info(f"Total candidates: {len(candidates)}")


def print_summary(candidates: List[Dict[str, Any]]):
    """후보 요약 출력"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("D82-12 Lowered TP/Entry Candidates Summary")
    logger.info("=" * 80)
    
    logger.info(f"Total candidates: {len(candidates)}")
    logger.info(f"Entry range: {min(c['entry_bps'] for c in candidates):.1f} - {max(c['entry_bps'] for c in candidates):.1f} bps")
    logger.info(f"TP range: {min(c['tp_bps'] for c in candidates):.1f} - {max(c['tp_bps'] for c in candidates):.1f} bps")
    logger.info(f"Edge range: {min(c['edge_bps'] for c in candidates):.2f} - {max(c['edge_bps'] for c in candidates):.2f} bps")
    
    viable_count = sum(1 for c in candidates if c["is_viable"])
    logger.info(f"Viable (Edge >= 0): {viable_count} / {len(candidates)}")
    
    logger.info("")
    logger.info("Candidates (sorted by Edge):")
    logger.info("-" * 80)
    for i, cand in enumerate(candidates, 1):
        logger.info(
            f"{i}. Entry={cand['entry_bps']:.1f}, TP={cand['tp_bps']:.1f}: "
            f"Edge={cand['edge_bps']:.2f} bps "
            f"({'VIABLE' if cand['is_viable'] else 'NOT VIABLE'})"
        )
    logger.info("=" * 80)
    logger.info("")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="D82-12: Generate lowered TP/Entry candidates (D77-4 baseline zone)"
    )
    parser.add_argument(
        "--output-path",
        default="logs/d82-12/lowered_tp_entry_candidates.json",
        help="Output JSON path (default: logs/d82-12/lowered_tp_entry_candidates.json)",
    )
    parser.add_argument(
        "--entry-list",
        nargs="+",
        type=float,
        default=DEFAULT_ENTRY_CANDIDATES,
        help=f"Entry candidates (default: {DEFAULT_ENTRY_CANDIDATES})",
    )
    parser.add_argument(
        "--tp-list",
        nargs="+",
        type=float,
        default=DEFAULT_TP_CANDIDATES,
        help=f"TP candidates (default: {DEFAULT_TP_CANDIDATES})",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("D82-12: Lowered TP/Entry Candidates Generation")
    logger.info("=" * 80)
    logger.info(f"Entry candidates: {args.entry_list}")
    logger.info(f"TP candidates: {args.tp_list}")
    logger.info(f"Roundtrip cost: {ROUNDTRIP_COST_BPS:.2f} bps")
    logger.info(f"Output path: {args.output_path}")
    logger.info("=" * 80)
    logger.info("")
    
    # 후보 생성
    candidates = generate_candidates(args.entry_list, args.tp_list)
    
    # 요약 출력
    print_summary(candidates)
    
    # JSON 저장
    output_path = Path(args.output_path)
    save_candidates_json(candidates, output_path)
    
    logger.info("")
    logger.info("✅ D82-12 candidates generation complete!")
    logger.info(f"   Output: {output_path}")
    logger.info(f"   Total candidates: {len(candidates)}")
    logger.info("")


if __name__ == "__main__":
    main()
