#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D86: Fill Event 데이터 분석 및 Zone 재정의

목적:
- D86 smoke test 데이터 분석
- Entry/TP BPS 분포 확인
- Zone 재정의 설계
- 새 Calibration JSON 생성

Author: arbitrage-lite project
Date: 2025-12-07
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict
from datetime import datetime
import sys

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_fill_events(jsonl_path: Path) -> List[Dict[str, Any]]:
    """
    JSONL 파일에서 Fill Events 로드
    
    Args:
        jsonl_path: JSONL 파일 경로
    
    Returns:
        Fill Event 리스트
    """
    events = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


def analyze_entry_tp_distribution(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Entry/TP BPS 분포 분석
    
    Args:
        events: Fill Event 리스트
    
    Returns:
        분포 통계
    """
    entry_bps_list = [e["entry_bps"] for e in events]
    tp_bps_list = [e["tp_bps"] for e in events]
    
    return {
        "entry_bps": {
            "min": min(entry_bps_list),
            "max": max(entry_bps_list),
            "unique_values": sorted(set(entry_bps_list)),
            "count": len(entry_bps_list),
        },
        "tp_bps": {
            "min": min(tp_bps_list),
            "max": max(tp_bps_list),
            "unique_values": sorted(set(tp_bps_list)),
            "count": len(tp_bps_list),
        },
    }


def design_zones(distribution: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    데이터 기반 Zone 재정의
    
    Args:
        distribution: Entry/TP 분포 정보
    
    Returns:
        Zone 정의 리스트
    """
    entry_values = distribution["entry_bps"]["unique_values"]
    
    # Entry BPS 기반으로 Zone 정의 (3-4개 Zone)
    # 데이터: 5, 7, 10, 12, 15, 20, 25 bps
    zones = [
        {
            "zone_id": "Z1",
            "entry_min": 5.0,
            "entry_max": 7.0,
            "tp_min": 7.0,
            "tp_max": 12.0,
            "description": "Low Entry (5-7 bps)",
        },
        {
            "zone_id": "Z2",
            "entry_min": 7.0,
            "entry_max": 12.0,
            "tp_min": 10.0,
            "tp_max": 20.0,
            "description": "Medium Entry (7-12 bps)",
        },
        {
            "zone_id": "Z3",
            "entry_min": 12.0,
            "entry_max": 20.0,
            "tp_min": 15.0,
            "tp_max": 30.0,
            "description": "High Entry (12-20 bps)",
        },
        {
            "zone_id": "Z4",
            "entry_min": 20.0,
            "entry_max": 30.0,
            "tp_min": 25.0,
            "tp_max": 40.0,
            "description": "Very High Entry (20-30 bps)",
        },
    ]
    
    logger.info(f"[D86] Designed {len(zones)} zones based on data distribution")
    for zone in zones:
        logger.info(
            f"  {zone['zone_id']}: Entry {zone['entry_min']}-{zone['entry_max']} bps, "
            f"TP {zone['tp_min']}-{zone['tp_max']} bps"
        )
    
    return zones


def match_zone(entry_bps: float, tp_bps: float, zones: List[Dict[str, Any]]) -> str:
    """
    Entry/TP에 해당하는 Zone 매칭
    
    Args:
        entry_bps: Entry Threshold
        tp_bps: TP Threshold
        zones: Zone 정의 리스트
    
    Returns:
        Zone ID (매칭 실패 시 None)
    """
    for zone in zones:
        if (zone["entry_min"] <= entry_bps <= zone["entry_max"] and
            zone["tp_min"] <= tp_bps <= zone["tp_max"]):
            return zone["zone_id"]
    return None


def calculate_zone_statistics(
    events: List[Dict[str, Any]],
    zones: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Zone별 Fill Ratio 통계 계산
    
    Args:
        events: Fill Event 리스트
        zones: Zone 정의 리스트
    
    Returns:
        Zone별 통계
    """
    zone_stats = defaultdict(lambda: {
        "buy_events": [],
        "sell_events": [],
    })
    
    unmatched = 0
    
    for event in events:
        entry_bps = event["entry_bps"]
        tp_bps = event["tp_bps"]
        side = event["side"]
        fill_ratio = event["fill_ratio"]
        
        zone_id = match_zone(entry_bps, tp_bps, zones)
        
        if zone_id is None:
            unmatched += 1
            continue
        
        if side == "buy":
            zone_stats[zone_id]["buy_events"].append(fill_ratio)
        elif side == "sell":
            zone_stats[zone_id]["sell_events"].append(fill_ratio)
    
    # 통계 계산
    result = {}
    for zone_id, data in zone_stats.items():
        buy_events = data["buy_events"]
        sell_events = data["sell_events"]
        
        result[zone_id] = {
            "buy_samples": len(buy_events),
            "sell_samples": len(sell_events),
            "total_samples": len(buy_events) + len(sell_events),
            "buy_fill_ratio_mean": sum(buy_events) / len(buy_events) if buy_events else 0.0,
            "sell_fill_ratio_mean": sum(sell_events) / len(sell_events) if sell_events else 1.0,
        }
    
    logger.info(f"[D86] Zone statistics calculated: {len(result)} zones, {unmatched} unmatched events")
    
    return result, unmatched


def generate_calibration_json(
    zones: List[Dict[str, Any]],
    zone_stats: Dict[str, Any],
    total_events: int,
    unmatched_events: int,
    output_path: Path,
):
    """
    새 Calibration JSON 생성
    
    Args:
        zones: Zone 정의
        zone_stats: Zone별 통계
        total_events: 총 이벤트 수
        unmatched_events: 미매칭 이벤트 수
        output_path: 출력 파일 경로
    """
    calibration = {
        "version": "d86_0",
        "created_at": datetime.utcnow().isoformat(),
        "source": "D86 Smoke Test (5min, Multi L2)",
        "total_events": total_events,
        "unmatched_events": unmatched_events,
        "zones": [],
        "default_buy_fill_ratio": 0.2615,  # D84-1 기본값 유지
        "default_sell_fill_ratio": 1.0,
    }
    
    for zone in zones:
        zone_id = zone["zone_id"]
        stats = zone_stats.get(zone_id, {})
        
        calibration["zones"].append({
            "zone_id": zone_id,
            "entry_min": zone["entry_min"],
            "entry_max": zone["entry_max"],
            "tp_min": zone["tp_min"],
            "tp_max": zone["tp_max"],
            "buy_fill_ratio": stats.get("buy_fill_ratio_mean", 0.2615),
            "sell_fill_ratio": stats.get("sell_fill_ratio_mean", 1.0),
            "samples": stats.get("total_samples", 0),
            "buy_samples": stats.get("buy_samples", 0),
            "sell_samples": stats.get("sell_samples", 0),
        })
    
    # 출력
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(calibration, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D86] Calibration JSON generated: {output_path}")


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="D86 Fill Event 데이터 분석")
    parser.add_argument(
        "--input",
        type=str,
        default="logs/d86/fill_events_20251207_120533.jsonl",
        help="입력 Fill Events JSONL 파일 경로"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="출력 Calibration JSON 파일 경로 (기본값: 입력 파일과 같은 디렉토리)"
    )
    
    args = parser.parse_args()
    
    # 입력 파일
    jsonl_path = Path(args.input)
    
    if not jsonl_path.exists():
        logger.error(f"[D86] Fill events file not found: {jsonl_path}")
        sys.exit(1)
    
    # 출력 파일 경로 결정
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = jsonl_path.parent / f"{jsonl_path.stem.replace('fill_events', 'calibration')}.json"
    
    logger.info("=" * 80)
    logger.info("[D86] Fill Event 데이터 분석 시작")
    logger.info("=" * 80)
    logger.info(f"Input: {jsonl_path}")
    logger.info(f"Output: {output_path}")
    logger.info("")
    
    # 1. 데이터 로드
    events = load_fill_events(jsonl_path)
    logger.info(f"[D86] Loaded {len(events)} fill events")
    
    # 2. Entry/TP 분포 분석
    distribution = analyze_entry_tp_distribution(events)
    logger.info("[D86] Entry BPS distribution:")
    logger.info(f"  Min: {distribution['entry_bps']['min']}")
    logger.info(f"  Max: {distribution['entry_bps']['max']}")
    logger.info(f"  Unique values: {distribution['entry_bps']['unique_values']}")
    logger.info("[D86] TP BPS distribution:")
    logger.info(f"  Min: {distribution['tp_bps']['min']}")
    logger.info(f"  Max: {distribution['tp_bps']['max']}")
    logger.info(f"  Unique values: {distribution['tp_bps']['unique_values']}")
    logger.info("")
    
    # 3. Zone 재정의
    zones = design_zones(distribution)
    logger.info("")
    
    # 4. Zone별 통계 계산
    zone_stats, unmatched = calculate_zone_statistics(events, zones)
    logger.info("")
    logger.info("[D86] Zone별 통계:")
    for zone_id in sorted(zone_stats.keys()):
        stats = zone_stats[zone_id]
        logger.info(
            f"  {zone_id}: {stats['total_samples']} samples "
            f"(BUY={stats['buy_samples']}, SELL={stats['sell_samples']}), "
            f"BUY fill_ratio={stats['buy_fill_ratio_mean']:.4f}, "
            f"SELL fill_ratio={stats['sell_fill_ratio_mean']:.4f}"
        )
    logger.info("")
    
    # 5. Calibration JSON 생성
    generate_calibration_json(zones, zone_stats, len(events), unmatched, output_path)
    logger.info("")
    
    logger.info("=" * 80)
    logger.info("[D86] 분석 완료")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
