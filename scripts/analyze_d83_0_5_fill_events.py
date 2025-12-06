#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D83-0.5: Fill Event 분석 스크립트

목적:
- FillEventCollector JSONL 파일 분석
- available_volume 분포 확인
- fill_ratio 분포 확인
- Zone별 Fill Ratio (가능한 경우)

Usage:
    python scripts/analyze_d83_0_5_fill_events.py logs/d83-0.5/fill_events_20251206_120000.jsonl
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Any

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_fill_events(jsonl_path: Path) -> List[Dict[str, Any]]:
    """
    JSONL 파일에서 Fill Event 로드
    
    Args:
        jsonl_path: JSONL 파일 경로
    
    Returns:
        Fill Event 리스트
    """
    events = []
    
    if not jsonl_path.exists():
        logger.error(f"File not found: {jsonl_path}")
        return events
    
    with open(jsonl_path, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    logger.info(f"Loaded {len(events)} events from {jsonl_path}")
    return events


def analyze_distribution(values: List[float], name: str) -> Dict[str, float]:
    """
    값 분포 분석
    
    Args:
        values: 값 리스트
        name: 값 이름
    
    Returns:
        분포 통계
    """
    if not values:
        logger.warning(f"No values for {name}")
        return {}
    
    stats = {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "median": sorted(values)[len(values) // 2],
    }
    
    # 표준편차
    mean = stats["mean"]
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    stats["std"] = variance ** 0.5
    
    return stats


def analyze_fill_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Fill Event 분석
    
    Args:
        events: Fill Event 리스트
    
    Returns:
        분석 결과
    """
    if not events:
        logger.error("No events to analyze")
        return {}
    
    # 전체 이벤트 수
    total_events = len(events)
    
    # Side별 분리 (OrderSide.value는 소문자)
    buy_events = [e for e in events if e["side"].upper() == "BUY"]
    sell_events = [e for e in events if e["side"].upper() == "SELL"]
    
    # available_volume 분포
    buy_available_volumes = [e["available_volume"] for e in buy_events]
    sell_available_volumes = [e["available_volume"] for e in sell_events]
    
    # fill_ratio 분포
    buy_fill_ratios = [e["fill_ratio"] for e in buy_events]
    sell_fill_ratios = [e["fill_ratio"] for e in sell_events]
    
    # slippage_bps 분포
    buy_slippage = [e["slippage_bps"] for e in buy_events]
    sell_slippage = [e["slippage_bps"] for e in sell_events]
    
    # 분석 결과
    result = {
        "total_events": total_events,
        "buy_events": len(buy_events),
        "sell_events": len(sell_events),
        "buy_available_volume": analyze_distribution(buy_available_volumes, "buy_available_volume"),
        "sell_available_volume": analyze_distribution(sell_available_volumes, "sell_available_volume"),
        "buy_fill_ratio": analyze_distribution(buy_fill_ratios, "buy_fill_ratio"),
        "sell_fill_ratio": analyze_distribution(sell_fill_ratios, "sell_fill_ratio"),
        "buy_slippage_bps": analyze_distribution(buy_slippage, "buy_slippage_bps"),
        "sell_slippage_bps": analyze_distribution(sell_slippage, "sell_slippage_bps"),
    }
    
    return result


def print_analysis_report(analysis: Dict[str, Any]) -> None:
    """
    분석 결과 리포트 출력
    
    Args:
        analysis: 분석 결과
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D83-0.5] Fill Event Analysis Report")
    logger.info("=" * 80)
    logger.info(f"Total Events: {analysis['total_events']}")
    logger.info(f"  - BUY Events: {analysis['buy_events']}")
    logger.info(f"  - SELL Events: {analysis['sell_events']}")
    logger.info("")
    
    # BUY available_volume
    logger.info("BUY available_volume:")
    buy_av = analysis["buy_available_volume"]
    if buy_av:
        logger.info(f"  Count: {buy_av['count']}")
        logger.info(f"  Min: {buy_av['min']:.6f}")
        logger.info(f"  Max: {buy_av['max']:.6f}")
        logger.info(f"  Mean: {buy_av['mean']:.6f}")
        logger.info(f"  Median: {buy_av['median']:.6f}")
        logger.info(f"  Std: {buy_av['std']:.6f}")
        
        # 분산 판정
        if buy_av['std'] > buy_av['mean'] * 0.1:
            logger.info("  ✅ DISPERSED (std > 10% of mean)")
        else:
            logger.warning("  ⚠️ LOW DISPERSION (std < 10% of mean)")
    logger.info("")
    
    # SELL available_volume
    logger.info("SELL available_volume:")
    sell_av = analysis["sell_available_volume"]
    if sell_av:
        logger.info(f"  Count: {sell_av['count']}")
        logger.info(f"  Min: {sell_av['min']:.6f}")
        logger.info(f"  Max: {sell_av['max']:.6f}")
        logger.info(f"  Mean: {sell_av['mean']:.6f}")
        logger.info(f"  Median: {sell_av['median']:.6f}")
        logger.info(f"  Std: {sell_av['std']:.6f}")
        
        if sell_av['std'] > sell_av['mean'] * 0.1:
            logger.info("  ✅ DISPERSED (std > 10% of mean)")
        else:
            logger.warning("  ⚠️ LOW DISPERSION (std < 10% of mean)")
    logger.info("")
    
    # BUY fill_ratio
    logger.info("BUY fill_ratio:")
    buy_fr = analysis["buy_fill_ratio"]
    if buy_fr:
        logger.info(f"  Count: {buy_fr['count']}")
        logger.info(f"  Min: {buy_fr['min']:.4f} ({buy_fr['min']*100:.2f}%)")
        logger.info(f"  Max: {buy_fr['max']:.4f} ({buy_fr['max']*100:.2f}%)")
        logger.info(f"  Mean: {buy_fr['mean']:.4f} ({buy_fr['mean']*100:.2f}%)")
        logger.info(f"  Median: {buy_fr['median']:.4f} ({buy_fr['median']*100:.2f}%)")
        logger.info(f"  Std: {buy_fr['std']:.4f}")
        
        # 고정값 판정 (모두 0.2615 = 26.15%)
        if buy_fr['std'] < 0.01:
            logger.warning("  ⚠️ FIXED (std < 0.01) - likely all same value")
        else:
            logger.info("  ✅ DISPERSED (std >= 0.01)")
    logger.info("")
    
    # SELL fill_ratio
    logger.info("SELL fill_ratio:")
    sell_fr = analysis["sell_fill_ratio"]
    if sell_fr:
        logger.info(f"  Count: {sell_fr['count']}")
        logger.info(f"  Min: {sell_fr['min']:.4f} ({sell_fr['min']*100:.2f}%)")
        logger.info(f"  Max: {sell_fr['max']:.4f} ({sell_fr['max']*100:.2f}%)")
        logger.info(f"  Mean: {sell_fr['mean']:.4f} ({sell_fr['mean']*100:.2f}%)")
        logger.info(f"  Median: {sell_fr['median']:.4f} ({sell_fr['median']*100:.2f}%)")
        logger.info(f"  Std: {sell_fr['std']:.4f}")
        
        if sell_fr['std'] < 0.01:
            logger.warning("  ⚠️ FIXED (std < 0.01) - likely all same value")
        else:
            logger.info("  ✅ DISPERSED (std >= 0.01)")
    logger.info("")
    
    # Slippage
    logger.info("Slippage (bps):")
    buy_slip = analysis["buy_slippage_bps"]
    sell_slip = analysis["sell_slippage_bps"]
    if buy_slip:
        logger.info(f"  BUY: mean={buy_slip['mean']:.2f} bps, std={buy_slip['std']:.2f} bps")
    if sell_slip:
        logger.info(f"  SELL: mean={sell_slip['mean']:.2f} bps, std={sell_slip['std']:.2f} bps")
    
    logger.info("=" * 80)


def main():
    """D83-0.5 Fill Event 분석"""
    parser = argparse.ArgumentParser(description="D83-0.5: Fill Event Analysis")
    parser.add_argument(
        "jsonl_path",
        type=str,
        help="Fill events JSONL 파일 경로",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="분석 결과 JSON 출력 경로 (선택사항)",
    )
    
    args = parser.parse_args()
    
    # 1. Fill Event 로드
    jsonl_path = Path(args.jsonl_path)
    events = load_fill_events(jsonl_path)
    
    if not events:
        logger.error("No events to analyze. Exiting.")
        sys.exit(1)
    
    # 2. 분석
    analysis = analyze_fill_events(events)
    
    # 3. 리포트 출력
    print_analysis_report(analysis)
    
    # 4. JSON 저장 (선택사항)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(analysis, f, indent=2)
        logger.info(f"Analysis saved to: {output_path}")


if __name__ == "__main__":
    main()
