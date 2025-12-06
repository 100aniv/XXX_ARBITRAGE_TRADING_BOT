#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D84-2: Fill Results 분석 스크립트

목적:
- D84-2 PAPER 실행에서 수집한 Fill Events JSONL 분석
- Zone별 fill_ratio 통계 계산
- Calibration 예측값 vs 실측값 비교
- available_volume 분포 분석
- 리포트 MD 파일 자동 생성

Usage:
    python scripts/analyze_d84_2_fill_results.py \\
        --events-file logs/d84-2/fill_events_<session_id>.jsonl \\
        --calibration-file logs/d84/d84_1_calibration.json \\
        --output-report docs/D84/D84-2_FILL_MODEL_VALIDATION_REPORT.md
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
    """
    Fill Events JSONL 파일 로드
    
    Args:
        events_file: JSONL 파일 경로
    
    Returns:
        Fill Event 리스트
    """
    events = []
    with open(events_file, "r") as f:
        for line in f:
            event = json.loads(line.strip())
            events.append(event)
    
    logger.info(f"Loaded {len(events)} events from {events_file}")
    return events


def load_calibration(calibration_file: Path) -> Dict[str, Any]:
    """
    Calibration JSON 파일 로드
    
    Args:
        calibration_file: JSON 파일 경로
    
    Returns:
        Calibration 데이터
    """
    with open(calibration_file, "r") as f:
        calibration = json.load(f)
    
    logger.info(f"Loaded calibration: version={calibration['version']}, zones={len(calibration['zones'])}")
    return calibration


def compute_stats(values: List[float]) -> Dict[str, float]:
    """
    통계 계산 (평균, 중앙값, 표준편차 등)
    
    Args:
        values: 값 리스트
    
    Returns:
        통계 dict
    """
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


def analyze_fill_events(events: List[Dict], calibration: Dict) -> Dict[str, Any]:
    """
    Fill Events 분석
    
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
    
    # Calibration 예측값 vs 실측값 비교
    calibration_zones = {z["zone_id"]: z for z in calibration["zones"]}
    
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
    """
    리포트 MD 파일 생성
    
    Args:
        analysis: 분석 결과
        events_file: Events JSONL 파일 경로
        calibration_file: Calibration JSON 파일 경로
        output_report: 출력 리포트 MD 파일 경로
    """
    report_lines = []
    
    # 헤더
    report_lines.append("# D84-2: CalibratedFillModel 장기 PAPER 검증 리포트")
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
    
    # 분산 판정
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
    
    # 분산 판정
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
    report_lines.append("### BUY fill_ratio")
    report_lines.append("")
    buy_fr = analysis["buy_fill_ratio"]
    report_lines.append(f"- Count: {buy_fr['count']}")
    report_lines.append(f"- Min: {buy_fr['min']:.4f} ({buy_fr['min']*100:.2f}%)")
    report_lines.append(f"- Max: {buy_fr['max']:.4f} ({buy_fr['max']*100:.2f}%)")
    report_lines.append(f"- Mean: {buy_fr['mean']:.4f} ({buy_fr['mean']*100:.2f}%)")
    report_lines.append(f"- Median: {buy_fr['median']:.4f} ({buy_fr['median']*100:.2f}%)")
    report_lines.append(f"- Std: {buy_fr['std']:.4f}")
    
    # 분산 판정
    if buy_fr['std'] < 0.01:
        report_lines.append(f"- **⚠️ FIXED** (std < 0.01)")
    else:
        report_lines.append(f"- **✅ DISPERSED** (std={buy_fr['std']:.4f})")
    report_lines.append("")
    
    report_lines.append("### SELL fill_ratio")
    report_lines.append("")
    sell_fr = analysis["sell_fill_ratio"]
    report_lines.append(f"- Count: {sell_fr['count']}")
    report_lines.append(f"- Min: {sell_fr['min']:.4f} ({sell_fr['min']*100:.2f}%)")
    report_lines.append(f"- Max: {sell_fr['max']:.4f} ({sell_fr['max']*100:.2f}%)")
    report_lines.append(f"- Mean: {sell_fr['mean']:.4f} ({sell_fr['mean']*100:.2f}%)")
    report_lines.append(f"- Median: {sell_fr['median']:.4f} ({sell_fr['median']*100:.2f}%)")
    report_lines.append(f"- Std: {sell_fr['std']:.4f}")
    
    # 분산 판정
    if sell_fr['std'] < 0.01:
        report_lines.append(f"- **⚠️ FIXED** (std < 0.01)")
    else:
        report_lines.append(f"- **✅ DISPERSED** (std={sell_fr['std']:.4f})")
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
    
    # 결론
    report_lines.append("## 🏁 결론")
    report_lines.append("")
    
    # Acceptance 판정
    acceptance_checks = []
    
    # 1. Fill Events 수
    if analysis['total_events'] >= 50:
        acceptance_checks.append(f"✅ Fill Events 수 충족: {analysis['total_events']}개 (≥ 50)")
    else:
        acceptance_checks.append(f"⚠️ Fill Events 수 부족: {analysis['total_events']}개 (< 50)")
    
    # 2. available_volume 분산
    if buy_av['mean'] > 0 and sell_av['mean'] > 0:
        buy_disp = (buy_av['std'] / buy_av['mean']) * 100
        sell_disp = (sell_av['std'] / sell_av['mean']) * 100
        if buy_disp > 10 and sell_disp > 10:
            acceptance_checks.append(f"✅ available_volume 분산 확인: BUY {buy_disp:.1f}%, SELL {sell_disp:.1f}%")
        else:
            acceptance_checks.append(f"⚠️ available_volume 분산 부족: BUY {buy_disp:.1f}%, SELL {sell_disp:.1f}%")
    
    # 3. Calibration 적용 여부
    if delta_buy < 0.05:  # 5% 이내 차이면 정상
        acceptance_checks.append(f"✅ BUY Fill Ratio Calibration 적용 확인 (차이 {delta_buy:.4f})")
    else:
        acceptance_checks.append(f"⚠️ BUY Fill Ratio Calibration 적용 불일치 (차이 {delta_buy:.4f})")
    
    for check in acceptance_checks:
        report_lines.append(f"- {check}")
    
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("**리포트 생성 완료**")
    
    # 파일 저장
    with open(output_report, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    logger.info(f"리포트 저장 완료: {output_report}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D84-2: Fill Results 분석"
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
        default="docs/D84/D84-2_FILL_MODEL_VALIDATION_REPORT.md",
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
    logger.info("[D84-2] Fill Results 분석 시작")
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
    logger.info("[D84-2] 분석 요약")
    logger.info("=" * 100)
    logger.info(f"총 이벤트: {analysis['total_events']}")
    logger.info(f"  - BUY: {analysis['buy_events']}")
    logger.info(f"  - SELL: {analysis['sell_events']}")
    logger.info("")
    logger.info("BUY available_volume:")
    buy_av = analysis['buy_available_volume']
    logger.info(f"  Min: {buy_av['min']:.6f}, Max: {buy_av['max']:.6f}")
    logger.info(f"  Mean: {buy_av['mean']:.6f}, Std: {buy_av['std']:.6f}")
    logger.info("")
    logger.info("BUY fill_ratio:")
    buy_fr = analysis['buy_fill_ratio']
    logger.info(f"  Mean: {buy_fr['mean']:.4f} ({buy_fr['mean']*100:.2f}%)")
    logger.info(f"  Std: {buy_fr['std']:.4f}")
    logger.info("")
    logger.info("Calibration 비교 (BUY):")
    cal_cmp = analysis['calibration_comparison']
    logger.info(f"  예측: {cal_cmp['expected_buy_fill_ratio']:.4f}")
    logger.info(f"  실측: {cal_cmp['actual_buy_fill_ratio_mean']:.4f}")
    logger.info(f"  차이: {abs(cal_cmp['actual_buy_fill_ratio_mean'] - cal_cmp['expected_buy_fill_ratio']):.4f}")
    logger.info("=" * 100)
    logger.info("")
    
    # 4. 리포트 생성
    output_report.parent.mkdir(parents=True, exist_ok=True)
    generate_report(analysis, events_file, calibration_file, output_report)
    
    logger.info(f"[D84-2] 분석 완료. 리포트: {output_report}")


if __name__ == "__main__":
    main()
