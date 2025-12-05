#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-10: D82-9 KPI 기반 비용 구조 재측정

목적:
    D82-9 PAPER 실행 결과에서 관측된 실제 슬리피지/수수료/필률/RT빈도를
    정량화하여, 이론 Edge 모델 재보정에 사용할 비용 프로파일을 생성.

출력:
    logs/d82-10/d82_9_cost_profile.json
    - effective_fee_bps_total
    - effective_slippage_bps_total (buy + sell)
    - avg_buy_fill_ratio, avg_sell_fill_ratio
    - round_trips_per_minute
    - exit_reasons 분포
    - 후보별 지표 요약

Author: arbitrage-lite project
Date: 2025-12-05
"""

import json
import logging
import statistics
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional

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
# Data Classes
# =============================================================================

@dataclass
class D82CostProfile:
    """D82-9 실측 비용 프로파일"""
    # 슬리피지 (bps)
    slippage_avg: float
    slippage_median: float
    slippage_p75: float
    slippage_p90: float
    slippage_p95: float
    
    # 수수료 (bps)
    fee_total_bps: float
    
    # 필률 (%)
    buy_fill_ratio_avg: float
    buy_fill_ratio_median: float
    buy_fill_ratio_p25: float  # 하위 quartile (pessimistic용)
    
    sell_fill_ratio_avg: float
    sell_fill_ratio_median: float
    
    # Round Trips
    round_trips_per_minute_avg: float
    total_round_trips: int
    total_duration_minutes: float
    
    # Exit Reasons
    exit_reasons_distribution: Dict[str, int]
    exit_timeout_pct: float
    
    # 후보별 요약
    candidate_summaries: List[Dict[str, Any]]


# =============================================================================
# KPI Parsing
# =============================================================================

def load_d82_9_kpi_files(kpi_dir: Path) -> List[Dict[str, Any]]:
    """
    D82-9 KPI JSON 파일들을 로드.
    
    Args:
        kpi_dir: KPI 파일들이 있는 디렉토리
    
    Returns:
        KPI 레코드 리스트
    """
    kpi_files = list(kpi_dir.glob("d82-9-E*_kpi.json"))
    
    if not kpi_files:
        logger.warning(f"No D82-9 KPI files found in {kpi_dir}")
        return []
    
    records = []
    for kpi_file in kpi_files:
        try:
            with open(kpi_file, "r", encoding="utf-8") as f:
                kpi = json.load(f)
                records.append(kpi)
        except Exception as e:
            logger.error(f"Failed to load {kpi_file}: {e}")
    
    logger.info(f"Loaded {len(records)} KPI files from {kpi_dir}")
    return records


def compute_cost_profile(kpi_records: List[Dict[str, Any]]) -> D82CostProfile:
    """
    KPI 레코드들로부터 비용 프로파일 계산.
    
    Args:
        kpi_records: D82-9 KPI JSON 레코드 리스트
    
    Returns:
        D82CostProfile 객체
    """
    if not kpi_records:
        raise ValueError("No KPI records provided")
    
    # 슬리피지 추출 (buy + sell 평균)
    slippages = []
    for kpi in kpi_records:
        buy_slip = kpi.get("avg_buy_slippage_bps", 0)
        sell_slip = kpi.get("avg_sell_slippage_bps", 0)
        avg_slip = (buy_slip + sell_slip) / 2 if (buy_slip or sell_slip) else 0
        if avg_slip > 0:
            slippages.append(avg_slip)
    
    # 필률 추출
    buy_fill_ratios = []
    sell_fill_ratios = []
    for kpi in kpi_records:
        buy_fill = kpi.get("avg_buy_fill_ratio", 0)
        sell_fill = kpi.get("avg_sell_fill_ratio", 0)
        if buy_fill > 0:
            buy_fill_ratios.append(buy_fill * 100)  # Convert to %
        if sell_fill > 0:
            sell_fill_ratios.append(sell_fill * 100)
    
    # Round Trips
    total_rt = sum(kpi.get("round_trips_completed", 0) for kpi in kpi_records)
    total_duration_sec = sum(kpi.get("actual_duration_seconds", 0) for kpi in kpi_records)
    total_duration_min = total_duration_sec / 60 if total_duration_sec > 0 else 1
    rt_per_min = total_rt / total_duration_min if total_duration_min > 0 else 0
    
    # Exit Reasons
    exit_reasons = {}
    for kpi in kpi_records:
        reasons = kpi.get("exit_reasons", {})
        for reason, count in reasons.items():
            exit_reasons[reason] = exit_reasons.get(reason, 0) + count
    
    total_exits = sum(exit_reasons.values())
    exit_timeout_pct = (exit_reasons.get("time_limit", 0) / total_exits * 100) if total_exits > 0 else 0
    
    # 후보별 요약
    candidate_summaries = []
    for kpi in kpi_records:
        session_id = kpi.get("session_id", "unknown")
        # Extract Entry/TP from session_id (e.g., "d82-9-E10p0_TP13p0-...")
        entry_tp = "unknown"
        if "E" in session_id and "TP" in session_id:
            try:
                parts = session_id.split("-")
                if len(parts) >= 3:
                    entry_tp = parts[2].split("-")[0]  # "E10p0_TP13p0"
            except:
                pass
        
        summary = {
            "candidate": entry_tp,
            "session_id": session_id,
            "round_trips": kpi.get("round_trips_completed", 0),
            "win_rate_pct": kpi.get("win_rate_pct", 0),
            "total_pnl_usd": kpi.get("total_pnl_usd", 0),
            "buy_fill_ratio": kpi.get("avg_buy_fill_ratio", 0),
            "sell_fill_ratio": kpi.get("avg_sell_fill_ratio", 0),
            "buy_slippage_bps": kpi.get("avg_buy_slippage_bps", 0),
            "sell_slippage_bps": kpi.get("avg_sell_slippage_bps", 0),
        }
        candidate_summaries.append(summary)
    
    # 통계 계산
    def safe_percentile(data, p):
        if not data:
            return 0
        if len(data) == 1:
            return data[0]
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * p
        f = int(k)
        c = k - f
        if f + 1 < len(sorted_data):
            return sorted_data[f] * (1 - c) + sorted_data[f + 1] * c
        return sorted_data[f]
    
    profile = D82CostProfile(
        slippage_avg=statistics.mean(slippages) if slippages else 0,
        slippage_median=statistics.median(slippages) if slippages else 0,
        slippage_p75=safe_percentile(slippages, 0.75),
        slippage_p90=safe_percentile(slippages, 0.90),
        slippage_p95=safe_percentile(slippages, 0.95),
        fee_total_bps=9.0,  # Upbit 5 + Binance 4 (from D82-7)
        buy_fill_ratio_avg=statistics.mean(buy_fill_ratios) if buy_fill_ratios else 0,
        buy_fill_ratio_median=statistics.median(buy_fill_ratios) if buy_fill_ratios else 0,
        buy_fill_ratio_p25=safe_percentile(buy_fill_ratios, 0.25),
        sell_fill_ratio_avg=statistics.mean(sell_fill_ratios) if sell_fill_ratios else 0,
        sell_fill_ratio_median=statistics.median(sell_fill_ratios) if sell_fill_ratios else 0,
        round_trips_per_minute_avg=rt_per_min,
        total_round_trips=total_rt,
        total_duration_minutes=total_duration_min,
        exit_reasons_distribution=exit_reasons,
        exit_timeout_pct=exit_timeout_pct,
        candidate_summaries=candidate_summaries,
    )
    
    return profile


# =============================================================================
# Main
# =============================================================================

def main():
    """메인 함수."""
    logger.info("=" * 80)
    logger.info("[D82-10] D82-9 비용 프로파일 계산")
    logger.info("=" * 80)
    
    # KPI 파일 로드
    kpi_dir = Path("logs/d82-9/runs")
    if not kpi_dir.exists():
        logger.error(f"KPI directory not found: {kpi_dir}")
        return 1
    
    kpi_records = load_d82_9_kpi_files(kpi_dir)
    
    if not kpi_records:
        logger.error("No KPI records loaded. Exiting.")
        return 1
    
    # 비용 프로파일 계산
    logger.info("")
    logger.info("Computing cost profile...")
    profile = compute_cost_profile(kpi_records)
    
    # 결과 출력
    logger.info("")
    logger.info("=" * 80)
    logger.info("Cost Profile Summary")
    logger.info("=" * 80)
    logger.info(f"Slippage (bps):")
    logger.info(f"  Average: {profile.slippage_avg:.2f}")
    logger.info(f"  Median:  {profile.slippage_median:.2f}")
    logger.info(f"  P75:     {profile.slippage_p75:.2f}")
    logger.info(f"  P90:     {profile.slippage_p90:.2f}")
    logger.info(f"  P95:     {profile.slippage_p95:.2f}")
    logger.info(f"Fee (bps): {profile.fee_total_bps:.2f}")
    logger.info(f"")
    logger.info(f"Fill Ratios (%):")
    logger.info(f"  Buy Avg:    {profile.buy_fill_ratio_avg:.2f}%")
    logger.info(f"  Buy Median: {profile.buy_fill_ratio_median:.2f}%")
    logger.info(f"  Buy P25:    {profile.buy_fill_ratio_p25:.2f}%")
    logger.info(f"  Sell Avg:   {profile.sell_fill_ratio_avg:.2f}%")
    logger.info(f"")
    logger.info(f"Round Trips:")
    logger.info(f"  Total:  {profile.total_round_trips}")
    logger.info(f"  RT/min: {profile.round_trips_per_minute_avg:.2f}")
    logger.info(f"")
    logger.info(f"Exit Reasons:")
    for reason, count in profile.exit_reasons_distribution.items():
        logger.info(f"  {reason}: {count}")
    logger.info(f"  Timeout %: {profile.exit_timeout_pct:.1f}%")
    
    # JSON 저장
    output_dir = Path("logs/d82-10")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "d82_9_cost_profile.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, indent=2, ensure_ascii=False)
    
    logger.info("")
    logger.info(f"Cost profile saved to: {output_path}")
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
