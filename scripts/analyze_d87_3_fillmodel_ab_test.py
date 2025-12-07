#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3: FillModel Advisory vs Strict A/B Test Analysis

Advisory vs Strict 모드의 3h PAPER 실행 결과를 비교 분석한다.

핵심 비교 항목:
- Zone별 트레이드 수 & Notional 비중 (Z1/Z2/Z3/Z4)
- Zone별 평균 포지션 사이즈
- Zone별 PnL 기여도
- 전체 PnL / Max DD / Risk 사용량

Usage:
    python scripts/analyze_d87_3_fillmodel_ab_test.py \\
        --advisory-dir logs/d87-3/d87_3_advisory_3h \\
        --strict-dir logs/d87-3/d87_3_strict_3h \\
        --output logs/d87-3/d87_3_ab_summary.json
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
import sys

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_fill_events(fill_events_path: Path) -> List[Dict[str, Any]]:
    """
    Fill Events JSONL 파일 로드
    
    Args:
        fill_events_path: Fill Events JSONL 파일 경로
    
    Returns:
        Fill Events 리스트
    """
    events = []
    with open(fill_events_path, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def load_kpi(kpi_path: Path) -> Dict[str, Any]:
    """
    KPI JSON 파일 로드
    
    Args:
        kpi_path: KPI JSON 파일 경로
    
    Returns:
        KPI dict
    """
    with open(kpi_path, "r") as f:
        return json.load(f)


def analyze_session(session_dir: Path, session_name: str) -> Dict[str, Any]:
    """
    단일 세션 분석
    
    Args:
        session_dir: 세션 디렉토리
        session_name: 세션 이름 (Advisory/Strict)
    
    Returns:
        분석 결과 dict
    """
    logger.info(f"[{session_name}] 세션 분석 시작: {session_dir}")
    
    # 1. Fill Events 파일 찾기
    fill_events_files = list(session_dir.glob("fill_events_*.jsonl"))
    if not fill_events_files:
        logger.error(f"[{session_name}] Fill Events 파일을 찾을 수 없습니다: {session_dir}")
        return None
    
    fill_events_path = fill_events_files[0]
    logger.info(f"[{session_name}] Fill Events: {fill_events_path.name}")
    
    # 2. KPI 파일 찾기
    kpi_files = list(session_dir.glob("kpi_*.json"))
    kpi = None
    if kpi_files:
        kpi_path = kpi_files[0]
        kpi = load_kpi(kpi_path)
        logger.info(f"[{session_name}] KPI: {kpi_path.name}")
    
    # 3. Fill Events 로드
    events = load_fill_events(fill_events_path)
    logger.info(f"[{session_name}] Fill Events 수: {len(events)}")
    
    # 4. Zone별 통계 계산
    zone_stats = defaultdict(lambda: {
        "count": 0,
        "notional_sum": 0.0,
        "size_sum": 0.0,
        "pnl_sum": 0.0,
    })
    
    total_notional = 0.0
    total_pnl = 0.0
    entry_count = 0
    
    for event in events:
        # Entry 이벤트만 카운트 (BUY side)
        if event.get("side") == "buy":
            entry_count += 1
            
            zone_id = event.get("zone_id", "UNKNOWN")
            quantity = event.get("quantity", 0.0)
            price = event.get("price", 0.0)
            notional = quantity * price
            
            # PnL 추정 (매우 단순화: buy와 sell을 매칭해야 하지만 여기서는 생략)
            pnl = 0.0  # 실제로는 sell 이벤트와 매칭 필요
            
            zone_stats[zone_id]["count"] += 1
            zone_stats[zone_id]["notional_sum"] += notional
            zone_stats[zone_id]["size_sum"] += quantity
            zone_stats[zone_id]["pnl_sum"] += pnl
            
            total_notional += notional
            total_pnl += pnl
    
    # 5. Zone별 비중 계산
    zone_analysis = {}
    for zone_id, stats in zone_stats.items():
        zone_analysis[zone_id] = {
            "trade_count": stats["count"],
            "trade_percentage": (stats["count"] / entry_count * 100) if entry_count > 0 else 0.0,
            "notional_sum": stats["notional_sum"],
            "notional_percentage": (stats["notional_sum"] / total_notional * 100) if total_notional > 0 else 0.0,
            "avg_size": stats["size_sum"] / stats["count"] if stats["count"] > 0 else 0.0,
            "pnl_sum": stats["pnl_sum"],
        }
    
    # 6. 요약
    summary = {
        "session_name": session_name,
        "total_events": len(events),
        "entry_trades": entry_count,
        "total_notional": total_notional,
        "total_pnl": total_pnl,
        "zone_analysis": zone_analysis,
        "kpi": kpi,
    }
    
    logger.info(f"[{session_name}] Entry Trades: {entry_count}")
    logger.info(f"[{session_name}] Total Notional: ${total_notional:.2f}")
    logger.info(f"[{session_name}] Zone 분포:")
    for zone_id, stats in sorted(zone_analysis.items()):
        logger.info(
            f"  - {zone_id}: {stats['trade_count']} trades ({stats['trade_percentage']:.1f}%), "
            f"${stats['notional_sum']:.2f} ({stats['notional_percentage']:.1f}%), "
            f"avg_size={stats['avg_size']:.6f}"
        )
    
    return summary


def compare_ab(advisory_summary: Dict[str, Any], strict_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Advisory vs Strict A/B 비교
    
    Args:
        advisory_summary: Advisory 세션 요약
        strict_summary: Strict 세션 요약
    
    Returns:
        비교 결과 dict
    """
    logger.info("")
    logger.info("=" * 100)
    logger.info("A/B 비교 분석")
    logger.info("=" * 100)
    
    # 1. 전체 메트릭 비교
    comparison = {
        "advisory": {
            "entry_trades": advisory_summary["entry_trades"],
            "total_notional": advisory_summary["total_notional"],
            "total_pnl": advisory_summary["total_pnl"],
        },
        "strict": {
            "entry_trades": strict_summary["entry_trades"],
            "total_notional": strict_summary["total_notional"],
            "total_pnl": strict_summary["total_pnl"],
        },
        "delta": {},
        "zone_comparison": {},
    }
    
    # 2. Delta 계산
    comparison["delta"]["entry_trades"] = strict_summary["entry_trades"] - advisory_summary["entry_trades"]
    comparison["delta"]["entry_trades_pct"] = (
        (strict_summary["entry_trades"] / advisory_summary["entry_trades"] - 1) * 100
        if advisory_summary["entry_trades"] > 0 else 0.0
    )
    comparison["delta"]["total_notional"] = strict_summary["total_notional"] - advisory_summary["total_notional"]
    comparison["delta"]["total_pnl"] = strict_summary["total_pnl"] - advisory_summary["total_pnl"]
    
    logger.info(f"Entry Trades: Advisory={comparison['advisory']['entry_trades']}, Strict={comparison['strict']['entry_trades']}, Delta={comparison['delta']['entry_trades']} ({comparison['delta']['entry_trades_pct']:.1f}%)")
    logger.info(f"Total Notional: Advisory=${comparison['advisory']['total_notional']:.2f}, Strict=${comparison['strict']['total_notional']:.2f}, Delta=${comparison['delta']['total_notional']:.2f}")
    logger.info(f"Total PnL: Advisory=${comparison['advisory']['total_pnl']:.2f}, Strict=${comparison['strict']['total_pnl']:.2f}, Delta=${comparison['delta']['total_pnl']:.2f}")
    
    # 3. Zone별 비교
    all_zones = set(advisory_summary["zone_analysis"].keys()) | set(strict_summary["zone_analysis"].keys())
    
    logger.info("")
    logger.info("Zone별 비교:")
    for zone_id in sorted(all_zones):
        advisory_zone = advisory_summary["zone_analysis"].get(zone_id, {
            "trade_count": 0,
            "trade_percentage": 0.0,
            "notional_percentage": 0.0,
            "avg_size": 0.0,
        })
        strict_zone = strict_summary["zone_analysis"].get(zone_id, {
            "trade_count": 0,
            "trade_percentage": 0.0,
            "notional_percentage": 0.0,
            "avg_size": 0.0,
        })
        
        comparison["zone_comparison"][zone_id] = {
            "advisory": {
                "trade_count": advisory_zone["trade_count"],
                "trade_percentage": advisory_zone["trade_percentage"],
                "notional_percentage": advisory_zone["notional_percentage"],
                "avg_size": advisory_zone["avg_size"],
            },
            "strict": {
                "trade_count": strict_zone["trade_count"],
                "trade_percentage": strict_zone["trade_percentage"],
                "notional_percentage": strict_zone["notional_percentage"],
                "avg_size": strict_zone["avg_size"],
            },
            "delta": {
                "trade_count": strict_zone["trade_count"] - advisory_zone["trade_count"],
                "trade_percentage": strict_zone["trade_percentage"] - advisory_zone["trade_percentage"],
                "notional_percentage": strict_zone["notional_percentage"] - advisory_zone["notional_percentage"],
                "avg_size": strict_zone["avg_size"] - advisory_zone["avg_size"],
            },
        }
        
        logger.info(f"  {zone_id}:")
        logger.info(f"    - Trades: Advisory={advisory_zone['trade_count']} ({advisory_zone['trade_percentage']:.1f}%), Strict={strict_zone['trade_count']} ({strict_zone['trade_percentage']:.1f}%), Delta={comparison['zone_comparison'][zone_id]['delta']['trade_percentage']:.1f}%p")
        logger.info(f"    - Notional: Advisory={advisory_zone['notional_percentage']:.1f}%, Strict={strict_zone['notional_percentage']:.1f}%, Delta={comparison['zone_comparison'][zone_id]['delta']['notional_percentage']:.1f}%p")
        logger.info(f"    - Avg Size: Advisory={advisory_zone['avg_size']:.6f}, Strict={strict_zone['avg_size']:.6f}, Delta={comparison['zone_comparison'][zone_id]['delta']['avg_size']:.6f}")
    
    logger.info("")
    logger.info("핵심 결론:")
    
    # Z2 비중 비교
    z2_advisory_pct = advisory_summary["zone_analysis"].get("Z2", {}).get("trade_percentage", 0.0)
    z2_strict_pct = strict_summary["zone_analysis"].get("Z2", {}).get("trade_percentage", 0.0)
    z2_delta = z2_strict_pct - z2_advisory_pct
    
    if z2_delta > 5.0:
        logger.info(f"  ✅ Z2 집중 성공: Strict가 Advisory보다 Z2 비중 {z2_delta:.1f}%p 더 높음")
    elif z2_delta > 0:
        logger.info(f"  ⚠️ Z2 집중 약함: Strict가 Advisory보다 Z2 비중 {z2_delta:.1f}%p 높지만 차이 작음")
    else:
        logger.info(f"  ❌ Z2 집중 실패: Strict가 Advisory보다 Z2 비중 오히려 낮음 ({z2_delta:.1f}%p)")
    
    # 총 트레이드 수 비교
    if comparison["delta"]["entry_trades_pct"] < -10:
        logger.info(f"  ⚠️ Strict 모드에서 총 트레이드 수 {-comparison['delta']['entry_trades_pct']:.1f}% 감소 (Z2 집중으로 인한 선택성 증가)")
    
    return comparison


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D87-3: FillModel Advisory vs Strict A/B Test Analysis"
    )
    parser.add_argument(
        "--advisory-dir",
        type=str,
        required=True,
        help="Advisory 세션 디렉토리 (예: logs/d87-3/d87_3_advisory_3h)"
    )
    parser.add_argument(
        "--strict-dir",
        type=str,
        required=True,
        help="Strict 세션 디렉토리 (예: logs/d87-3/d87_3_strict_3h)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="logs/d87-3/d87_3_ab_summary.json",
        help="출력 JSON 경로 (기본값: logs/d87-3/d87_3_ab_summary.json)"
    )
    
    args = parser.parse_args()
    
    advisory_dir = Path(args.advisory_dir)
    strict_dir = Path(args.strict_dir)
    output_path = Path(args.output)
    
    if not advisory_dir.exists():
        logger.error(f"Advisory 디렉토리가 존재하지 않습니다: {advisory_dir}")
        sys.exit(1)
    
    if not strict_dir.exists():
        logger.error(f"Strict 디렉토리가 존재하지 않습니다: {strict_dir}")
        sys.exit(1)
    
    logger.info("=" * 100)
    logger.info("D87-3: FillModel Advisory vs Strict A/B Test Analysis")
    logger.info("=" * 100)
    logger.info(f"Advisory Dir: {advisory_dir}")
    logger.info(f"Strict Dir: {strict_dir}")
    logger.info(f"Output: {output_path}")
    logger.info("")
    
    # 1. Advisory 세션 분석
    advisory_summary = analyze_session(advisory_dir, "Advisory")
    if not advisory_summary:
        logger.error("Advisory 세션 분석 실패")
        sys.exit(1)
    
    logger.info("")
    
    # 2. Strict 세션 분석
    strict_summary = analyze_session(strict_dir, "Strict")
    if not strict_summary:
        logger.error("Strict 세션 분석 실패")
        sys.exit(1)
    
    logger.info("")
    
    # 3. A/B 비교
    comparison = compare_ab(advisory_summary, strict_summary)
    
    # 4. 결과 저장
    output_data = {
        "advisory_summary": advisory_summary,
        "strict_summary": strict_summary,
        "comparison": comparison,
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info("")
    logger.info(f"분석 결과 저장: {output_path}")
    logger.info("")
    logger.info("=" * 100)
    logger.info("D87-3 A/B Analysis Complete")
    logger.info("=" * 100)


if __name__ == "__main__":
    main()
