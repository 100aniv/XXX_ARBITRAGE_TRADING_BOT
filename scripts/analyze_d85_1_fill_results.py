#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D85-1: Multi L2 Long PAPER Fill Results 분석 스크립트

목적:
- D85-1 PAPER 실행에서 수집한 Fill Events JSONL 분석
- Zone별 fill_ratio/slippage 통계 계산
- Entry/TP 조합별 분석
- Calibration 예측값 vs 실측값 비교
- available_volume 분포 분석
- 리포트 MD 파일 자동 생성

Usage:
    python scripts/analyze_d85_1_fill_results.py \\
        --events-file logs/d85-1/fill_events_<session_id>.jsonl \\
        --calibration-file logs/d84/d84_1_calibration.json \\
        --output-report docs/D85/D85-1_MULTI_L2_LONG_PAPER_REPORT.md
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import statistics

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_fill_events(events_file: Path) -> List[Dict[str, Any]]:
    """Fill Events JSONL 파일 로드"""
    events = []
    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line.strip())
            events.append(event)
    
    logger.info(f"Loaded {len(events)} events from {events_file}")
    return events


def load_calibration(calibration_file: Path) -> Dict[str, Any]:
    """Calibration JSON 파일 로드"""
    with open(calibration_file, "r", encoding="utf-8") as f:
        calibration = json.load(f)
    
    logger.info(f"Loaded calibration: version={calibration['version']}, zones={len(calibration['zones'])}")
    return calibration


def compute_stats(values: List[float]) -> Dict[str, float]:
    """통계 계산 (평균, 중앙값, 표준편차 등)"""
    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "std": 0.0,
        }
    
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def match_zone(entry_bps: float, calibration: Dict) -> str:
    """
    Entry BPS를 Zone에 매칭
    
    Args:
        entry_bps: Entry threshold (bps)
        calibration: Calibration 데이터
    
    Returns:
        Zone ID (Z1, Z2, Z3, Z4) or "unknown"
    """
    for zone in calibration["zones"]:
        entry_min = zone["entry_min"]
        entry_max = zone["entry_max"]
        
        if entry_min <= entry_bps < entry_max:
            return zone["zone_id"]
    
    # Zone 범위 밖인 경우 가장 가까운 Zone 반환
    if entry_bps < calibration["zones"][0]["entry_min"]:
        return calibration["zones"][0]["zone_id"]
    
    if entry_bps >= calibration["zones"][-1]["entry_max"]:
        return calibration["zones"][-1]["zone_id"]
    
    return "unknown"


def analyze_by_zone(events: List[Dict], calibration: Dict) -> Dict[str, Any]:
    """
    Zone별 분석
    
    Args:
        events: Fill Event 리스트
        calibration: Calibration 데이터
    
    Returns:
        Zone별 통계
    """
    zone_events = {}
    
    for event in events:
        entry_bps = event.get("entry_bps", 0.0)
        zone_id = match_zone(entry_bps, calibration)
        
        if zone_id not in zone_events:
            zone_events[zone_id] = []
        
        zone_events[zone_id].append(event)
    
    zone_stats = {}
    for zone_id, zone_evts in zone_events.items():
        buy_evts = [e for e in zone_evts if e["side"].upper() == "BUY"]
        sell_evts = [e for e in zone_evts if e["side"].upper() == "SELL"]
        
        zone_stats[zone_id] = {
            "total_events": len(zone_evts),
            "buy_events": len(buy_evts),
            "sell_events": len(sell_evts),
            "buy_fill_ratio": compute_stats([e["fill_ratio"] for e in buy_evts]),
            "sell_fill_ratio": compute_stats([e["fill_ratio"] for e in sell_evts]),
            "buy_slippage": compute_stats([e["slippage_bps"] for e in buy_evts]),
            "sell_slippage": compute_stats([e["slippage_bps"] for e in sell_evts]),
        }
    
    return zone_stats


def analyze_fill_events(events: List[Dict], calibration: Dict) -> Dict[str, Any]:
    """
    Fill Events 전체 분석
    
    Args:
        events: Fill Event 리스트
        calibration: Calibration 데이터
    
    Returns:
        분석 결과
    """
    if not events:
        logger.error("No events to analyze")
        return {}
    
    # 전체 이벤트 수
    total_events = len(events)
    
    # Side별 분리
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
    
    # Zone별 분석
    zone_stats = analyze_by_zone(events, calibration)
    
    # 분석 결과
    analysis = {
        "total_events": total_events,
        "buy_events": len(buy_events),
        "sell_events": len(sell_events),
        "buy_available_volume": compute_stats(buy_available_volumes),
        "sell_available_volume": compute_stats(sell_available_volumes),
        "buy_fill_ratio": compute_stats(buy_fill_ratios),
        "sell_fill_ratio": compute_stats(sell_fill_ratios),
        "buy_slippage": compute_stats(buy_slippage),
        "sell_slippage": compute_stats(sell_slippage),
        "zone_stats": zone_stats,
        "calibration_comparison": {
            "expected_buy_fill_ratio": calibration["default_buy_fill_ratio"],
            "actual_buy_fill_ratio_mean": statistics.mean(buy_fill_ratios) if buy_fill_ratios else 0.0,
            "expected_sell_fill_ratio": calibration["default_sell_fill_ratio"],
            "actual_sell_fill_ratio_mean": statistics.mean(sell_fill_ratios) if sell_fill_ratios else 0.0,
        },
    }
    
    return analysis


def generate_report(
    analysis: Dict[str, Any],
    events_file: Path,
    calibration_file: Path,
    output_report: Path,
):
    """리포트 MD 파일 생성"""
    report_lines = []
    
    # 헤더
    report_lines.append("# D85-1: Multi L2 Long PAPER & Calibration Data Collection 리포트")
    report_lines.append("")
    report_lines.append(f"**작성일:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"**상태:** ✅ **COMPLETE**")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    
    # 개요
    report_lines.append("## 📋 실행 개요")
    report_lines.append("")
    report_lines.append(f"- **Events 파일**: `{events_file}`")
    report_lines.append(f"- **Calibration 파일**: `{calibration_file}`")
    report_lines.append(f"- **L2 Source**: Multi (Upbit + Binance)")
    report_lines.append(f"- **총 이벤트 수**: {analysis['total_events']}")
    report_lines.append(f"- **BUY 이벤트**: {analysis['buy_events']}")
    report_lines.append(f"- **SELL 이벤트**: {analysis['sell_events']}")
    report_lines.append("")
    
    # available_volume 분석
    report_lines.append("## 📊 available_volume 분석")
    report_lines.append("")
    report_lines.append("### BUY available_volume")
    report_lines.append("")
    buy_av = analysis["buy_available_volume"]
    report_lines.append(f"- Count: {buy_av['count']}")
    report_lines.append(f"- Min: {buy_av['min']:.6f}")
    report_lines.append(f"- Max: {buy_av['max']:.6f}")
    report_lines.append(f"- Mean: {buy_av['mean']:.6f}")
    report_lines.append(f"- Median: {buy_av['median']:.6f}")
    report_lines.append(f"- Std: {buy_av['std']:.6f}")
    
    if buy_av['mean'] > 0:
        dispersion_pct = (buy_av['std'] / buy_av['mean']) * 100
        if dispersion_pct > 10:
            report_lines.append(f"- **✅ DISPERSED** (std={dispersion_pct:.1f}% of mean)")
        else:
            report_lines.append(f"- **⚠️ FIXED** (std={dispersion_pct:.1f}% of mean)")
    report_lines.append("")
    
    report_lines.append("### SELL available_volume")
    report_lines.append("")
    sell_av = analysis["sell_available_volume"]
    report_lines.append(f"- Count: {sell_av['count']}")
    report_lines.append(f"- Min: {sell_av['min']:.6f}")
    report_lines.append(f"- Max: {sell_av['max']:.6f}")
    report_lines.append(f"- Mean: {sell_av['mean']:.6f}")
    report_lines.append(f"- Median: {sell_av['median']:.6f}")
    report_lines.append(f"- Std: {sell_av['std']:.6f}")
    
    if sell_av['mean'] > 0:
        dispersion_pct = (sell_av['std'] / sell_av['mean']) * 100
        if dispersion_pct > 10:
            report_lines.append(f"- **✅ DISPERSED** (std={dispersion_pct:.1f}% of mean)")
        else:
            report_lines.append(f"- **⚠️ FIXED** (std={dispersion_pct:.1f}% of mean)")
    report_lines.append("")
    
    # fill_ratio 분석
    report_lines.append("## 📊 fill_ratio 분석")
    report_lines.append("")
    report_lines.append("### BUY fill_ratio (전체)")
    report_lines.append("")
    buy_fr = analysis["buy_fill_ratio"]
    report_lines.append(f"- Count: {buy_fr['count']}")
    report_lines.append(f"- Min: {buy_fr['min']:.4f} ({buy_fr['min']*100:.2f}%)")
    report_lines.append(f"- Max: {buy_fr['max']:.4f} ({buy_fr['max']*100:.2f}%)")
    report_lines.append(f"- Mean: {buy_fr['mean']:.4f} ({buy_fr['mean']*100:.2f}%)")
    report_lines.append(f"- Median: {buy_fr['median']:.4f} ({buy_fr['median']*100:.2f}%)")
    report_lines.append(f"- Std: {buy_fr['std']:.4f}")
    report_lines.append("")
    
    report_lines.append("### SELL fill_ratio (전체)")
    report_lines.append("")
    sell_fr = analysis["sell_fill_ratio"]
    report_lines.append(f"- Count: {sell_fr['count']}")
    report_lines.append(f"- Min: {sell_fr['min']:.4f} ({sell_fr['min']*100:.2f}%)")
    report_lines.append(f"- Max: {sell_fr['max']:.4f} ({sell_fr['max']*100:.2f}%)")
    report_lines.append(f"- Mean: {sell_fr['mean']:.4f} ({sell_fr['mean']*100:.2f}%)")
    report_lines.append(f"- Median: {sell_fr['median']:.4f} ({sell_fr['median']*100:.2f}%)")
    report_lines.append(f"- Std: {sell_fr['std']:.4f}")
    report_lines.append("")
    
    # Zone별 분석
    report_lines.append("## 📊 Zone별 fill_ratio 분석")
    report_lines.append("")
    
    zone_stats = analysis.get("zone_stats", {})
    if zone_stats:
        for zone_id in sorted(zone_stats.keys()):
            zone = zone_stats[zone_id]
            report_lines.append(f"### {zone_id}")
            report_lines.append("")
            report_lines.append(f"- **총 이벤트**: {zone['total_events']} (BUY={zone['buy_events']}, SELL={zone['sell_events']})")
            report_lines.append("")
            
            if zone['buy_events'] > 0:
                buy_zone_fr = zone['buy_fill_ratio']
                report_lines.append(f"- **BUY fill_ratio**: mean={buy_zone_fr['mean']:.4f} ({buy_zone_fr['mean']*100:.2f}%), std={buy_zone_fr['std']:.4f}")
            
            if zone['sell_events'] > 0:
                sell_zone_fr = zone['sell_fill_ratio']
                report_lines.append(f"- **SELL fill_ratio**: mean={sell_zone_fr['mean']:.4f} ({sell_zone_fr['mean']*100:.2f}%), std={sell_zone_fr['std']:.4f}")
            
            if zone['buy_events'] > 0:
                buy_zone_slip = zone['buy_slippage']
                report_lines.append(f"- **BUY slippage**: mean={buy_zone_slip['mean']:.2f} bps, std={buy_zone_slip['std']:.2f} bps")
            
            if zone['sell_events'] > 0:
                sell_zone_slip = zone['sell_slippage']
                report_lines.append(f"- **SELL slippage**: mean={sell_zone_slip['mean']:.2f} bps, std={sell_zone_slip['std']:.2f} bps")
            
            report_lines.append("")
        
        # Zone 간 비교
        report_lines.append("### Zone 간 비교")
        report_lines.append("")
        report_lines.append("| Zone | BUY Events | BUY Fill Ratio (mean) | SELL Events | SELL Fill Ratio (mean) |")
        report_lines.append("|------|------------|----------------------|-------------|------------------------|")
        for zone_id in sorted(zone_stats.keys()):
            zone = zone_stats[zone_id]
            buy_mean = zone['buy_fill_ratio']['mean'] if zone['buy_events'] > 0 else 0.0
            sell_mean = zone['sell_fill_ratio']['mean'] if zone['sell_events'] > 0 else 0.0
            report_lines.append(
                f"| {zone_id} | {zone['buy_events']} | {buy_mean:.4f} ({buy_mean*100:.2f}%) | "
                f"{zone['sell_events']} | {sell_mean:.4f} ({sell_mean*100:.2f}%) |"
            )
        report_lines.append("")
    else:
        report_lines.append("⚠️ Zone별 데이터 없음")
        report_lines.append("")
    
    # Calibration 비교
    report_lines.append("## 📊 Calibration 예측 vs 실측")
    report_lines.append("")
    cal_cmp = analysis["calibration_comparison"]
    report_lines.append(f"- **BUY Fill Ratio**:")
    report_lines.append(f"  - Calibration 예측: {cal_cmp['expected_buy_fill_ratio']:.4f}")
    report_lines.append(f"  - 실측 평균: {cal_cmp['actual_buy_fill_ratio_mean']:.4f}")
    delta_buy = abs(cal_cmp['actual_buy_fill_ratio_mean'] - cal_cmp['expected_buy_fill_ratio'])
    report_lines.append(f"  - 차이: {delta_buy:.4f}")
    report_lines.append("")
    report_lines.append(f"- **SELL Fill Ratio**:")
    report_lines.append(f"  - Calibration 예측: {cal_cmp['expected_sell_fill_ratio']:.4f}")
    report_lines.append(f"  - 실측 평균: {cal_cmp['actual_sell_fill_ratio_mean']:.4f}")
    delta_sell = abs(cal_cmp['actual_sell_fill_ratio_mean'] - cal_cmp['expected_sell_fill_ratio'])
    report_lines.append(f"  - 차이: {delta_sell:.4f}")
    report_lines.append("")
    
    # Slippage
    report_lines.append("## 📊 Slippage (bps)")
    report_lines.append("")
    buy_slip = analysis["buy_slippage"]
    sell_slip = analysis["sell_slippage"]
    report_lines.append(f"- **BUY**: mean={buy_slip['mean']:.2f} bps, std={buy_slip['std']:.2f} bps")
    report_lines.append(f"- **SELL**: mean={sell_slip['mean']:.2f} bps, std={sell_slip['std']:.2f} bps")
    report_lines.append("")
    
    # Acceptance Criteria 판정
    report_lines.append("## 🎯 Acceptance Criteria")
    report_lines.append("")
    
    acceptance_checks = []
    
    # C2: Fill Events 수
    if analysis['total_events'] >= 100:
        acceptance_checks.append(f"✅ **C2: Fill Events 수 충족**: {analysis['total_events']}개 (≥ 100)")
    else:
        acceptance_checks.append(f"⚠️ **C2: Fill Events 수 부족**: {analysis['total_events']}개 (< 100)")
    
    # C4: 분산
    if buy_av['mean'] > 0 and sell_av['mean'] > 0:
        buy_disp = (buy_av['std'] / buy_av['mean']) * 100
        sell_disp = (sell_av['std'] / sell_av['mean']) * 100
        if buy_disp > 10 and sell_disp > 10:
            acceptance_checks.append(f"✅ **C4: available_volume 분산 확인**: BUY {buy_disp:.1f}%, SELL {sell_disp:.1f}%")
        else:
            acceptance_checks.append(f"⚠️ **C4: available_volume 분산 부족**: BUY {buy_disp:.1f}%, SELL {sell_disp:.1f}%")
    
    for check in acceptance_checks:
        report_lines.append(f"- {check}")
    
    report_lines.append("")
    
    # 결론
    report_lines.append("## 🏁 결론")
    report_lines.append("")
    
    # Zone별 차이 발견 여부
    if zone_stats and len(zone_stats) > 1:
        zone_means = {}
        for zone_id, zone in zone_stats.items():
            if zone['buy_events'] > 0:
                zone_means[zone_id] = zone['buy_fill_ratio']['mean']
        
        if len(zone_means) > 1:
            min_mean = min(zone_means.values())
            max_mean = max(zone_means.values())
            diff = max_mean - min_mean
            
            if diff > 0.05:  # 5% 이상 차이
                report_lines.append(f"✅ **Zone별 Fill Ratio 차이 관측**: 최대 차이 {diff:.4f} ({diff*100:.2f}%)")
            else:
                report_lines.append(f"⚠️ **Zone별 Fill Ratio 차이 미미**: 최대 차이 {diff:.4f} ({diff*100:.2f}%)")
        else:
            report_lines.append("⚠️ **Zone별 비교 불가**: 단일 Zone만 데이터 존재")
    else:
        report_lines.append("⚠️ **Zone별 데이터 부족**: Multi-zone 분석 불가")
    
    report_lines.append("")
    report_lines.append("**현재까지의 한계:**")
    report_lines.append("")
    report_lines.append("- D85-1은 데이터 수집 단계이며, Zone별 차이가 명확히 드러나지 않을 수 있음")
    report_lines.append("- 더 많은 데이터(500+ events)와 다양한 시장 조건이 필요")
    report_lines.append("- 현재 Calibration은 D82 데이터 기반이므로, Zone별 보정 효과가 제한적")
    report_lines.append("")
    report_lines.append("**다음 단계:**")
    report_lines.append("")
    report_lines.append("1. **D85-2**: 장기 실행 (1시간+, 500+ events) 재실행")
    report_lines.append("2. **D85-3**: 다양한 시장 조건 (변동성 높은 구간) 데이터 수집")
    report_lines.append("3. **D86**: Zone별 차이가 명확한 Calibration 재작성")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("**리포트 생성 완료**")
    
    # 파일 저장
    output_report.parent.mkdir(parents=True, exist_ok=True)
    with open(output_report, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    logger.info(f"리포트 저장 완료: {output_report}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D85-1: Multi L2 Long PAPER Fill Results 분석"
    )
    parser.add_argument(
        "--events-file",
        type=str,
        required=True,
        help="Fill Events JSONL 파일 경로"
    )
    parser.add_argument(
        "--calibration-file",
        type=str,
        default="logs/d84/d84_1_calibration.json",
        help="Calibration JSON 파일 경로"
    )
    parser.add_argument(
        "--output-report",
        type=str,
        default="docs/D85/D85-1_MULTI_L2_LONG_PAPER_REPORT.md",
        help="출력 리포트 MD 파일 경로"
    )
    
    args = parser.parse_args()
    
    events_file = Path(args.events_file)
    calibration_file = Path(args.calibration_file)
    output_report = Path(args.output_report)
    
    if not events_file.exists():
        logger.error(f"Events 파일이 존재하지 않습니다: {events_file}")
        sys.exit(1)
    
    if not calibration_file.exists():
        logger.error(f"Calibration 파일이 존재하지 않습니다: {calibration_file}")
        sys.exit(1)
    
    logger.info("")
    logger.info("=" * 100)
    logger.info("[D85-1] Fill Results 분석 시작")
    logger.info("=" * 100)
    logger.info("")
    
    # 1. 데이터 로드
    events = load_fill_events(events_file)
    calibration = load_calibration(calibration_file)
    
    # 2. 분석
    analysis = analyze_fill_events(events, calibration)
    
    # 3. 콘솔 요약 출력
    logger.info("")
    logger.info("=" * 100)
    logger.info("[D85-1] 분석 요약")
    logger.info("=" * 100)
    logger.info(f"총 이벤트: {analysis['total_events']}")
    logger.info(f"  - BUY: {analysis['buy_events']}")
    logger.info(f"  - SELL: {analysis['sell_events']}")
    logger.info("")
    logger.info("BUY available_volume:")
    buy_av = analysis['buy_available_volume']
    logger.info(f"  Min: {buy_av['min']:.6f}, Max: {buy_av['max']:.6f}")
    logger.info(f"  Mean: {buy_av['mean']:.6f}, Std: {buy_av['std']:.6f}")
    if buy_av['mean'] > 0:
        logger.info(f"  Dispersion: {(buy_av['std'] / buy_av['mean']) * 100:.1f}%")
    logger.info("")
    logger.info("BUY fill_ratio:")
    buy_fr = analysis['buy_fill_ratio']
    logger.info(f"  Mean: {buy_fr['mean']:.4f} ({buy_fr['mean']*100:.2f}%)")
    logger.info(f"  Std: {buy_fr['std']:.4f}")
    logger.info("")
    
    # Zone별 요약
    zone_stats = analysis.get("zone_stats", {})
    if zone_stats:
        logger.info("Zone별 요약:")
        for zone_id in sorted(zone_stats.keys()):
            zone = zone_stats[zone_id]
            logger.info(f"  {zone_id}: {zone['total_events']} events (BUY={zone['buy_events']}, SELL={zone['sell_events']})")
            if zone['buy_events'] > 0:
                logger.info(f"    - BUY fill_ratio mean: {zone['buy_fill_ratio']['mean']:.4f}")
    
    logger.info("")
    logger.info("=" * 100)
    logger.info("")
    
    # 4. 리포트 생성
    generate_report(analysis, events_file, calibration_file, output_report)
    
    logger.info(f"[D85-1] 분석 완료. 리포트: {output_report}")


if __name__ == "__main__":
    main()
