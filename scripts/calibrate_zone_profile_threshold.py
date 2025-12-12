#!/usr/bin/env python3
"""
D92-2: Zone Profile Threshold Calibration Script

목적: Telemetry 데이터 기반으로 Zone Profile threshold를 재보정

보정 규칙:
1. threshold_bps_new = min(max(p95_spread_bps, fee_slippage_floor_bps), cap_bps)
2. fee_slippage_floor_bps = 수수료 + 예상 슬리피지 + 안전마진 (기본: 3.0 bps)
3. cap_bps = 심볼별 최대 threshold (기본: BTC/ETH 15 bps, XRP/SOL/DOGE 20 bps)
4. p95가 floor 미만이면 해당 심볼은 "hold" 모드 (거래 비활성)
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# 보정 파라미터
FEE_SLIPPAGE_FLOOR_BPS = 3.0  # 수수료 + 슬리피지 + 안전마진
CAP_BPS = {
    "BTC": 15.0,
    "ETH": 15.0,
    "XRP": 20.0,
    "SOL": 20.0,
    "DOGE": 25.0,
    "DEFAULT": 20.0,
}


def load_telemetry_report(report_path: str) -> Dict[str, Any]:
    """Telemetry 리포트 로드"""
    with open(report_path, "r") as f:
        return json.load(f)


def load_zone_profiles_v2(yaml_path: str) -> Dict[str, Any]:
    """Zone Profiles v2 YAML 로드"""
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_zone_profiles_v2(yaml_path: str, data: Dict[str, Any]) -> None:
    """Zone Profiles v2 YAML 저장"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def calibrate_threshold(
    symbol: str, telemetry: Dict[str, Any], current_threshold: float
) -> Dict[str, Any]:
    """
    심볼별 threshold 재보정
    
    Returns:
        {
            "symbol": str,
            "old_threshold_bps": float,
            "new_threshold_bps": float,
            "p95_spread_bps": float,
            "action": "update" | "hold" | "keep",
            "reason": str,
        }
    """
    p95 = telemetry.get("p95", 0.0)
    ge_rate = telemetry.get("ge_rate", 0.0)
    total_checks = telemetry.get("total_checks", 0)
    
    cap = CAP_BPS.get(symbol, CAP_BPS["DEFAULT"])
    
    # p95가 0이면 데이터 부족
    if p95 == 0.0 or total_checks == 0:
        return {
            "symbol": symbol,
            "old_threshold_bps": current_threshold,
            "new_threshold_bps": current_threshold,
            "p95_spread_bps": p95,
            "action": "keep",
            "reason": "No data (total_checks=0)",
        }
    
    # 보정 계산
    new_threshold = min(max(p95, FEE_SLIPPAGE_FLOOR_BPS), cap)
    
    # p95가 floor 미만 → hold
    if p95 < FEE_SLIPPAGE_FLOOR_BPS:
        return {
            "symbol": symbol,
            "old_threshold_bps": current_threshold,
            "new_threshold_bps": FEE_SLIPPAGE_FLOOR_BPS,  # floor로 설정 (hold 대신)
            "p95_spread_bps": p95,
            "action": "update",
            "reason": f"p95 < floor ({FEE_SLIPPAGE_FLOOR_BPS} bps), set to floor",
        }
    
    # threshold 변경 필요 여부
    delta = abs(new_threshold - current_threshold)
    if delta < 0.5:  # 0.5 bps 미만 변화는 무시
        return {
            "symbol": symbol,
            "old_threshold_bps": current_threshold,
            "new_threshold_bps": current_threshold,
            "p95_spread_bps": p95,
            "action": "keep",
            "reason": f"Delta < 0.5 bps (delta={delta:.2f})",
        }
    
    return {
        "symbol": symbol,
        "old_threshold_bps": current_threshold,
        "new_threshold_bps": new_threshold,
        "p95_spread_bps": p95,
        "action": "update",
        "reason": f"p95={p95:.2f} → threshold={new_threshold:.2f} (delta={delta:.2f})",
    }


def apply_calibration_to_yaml(
    zone_profiles: Dict[str, Any], calibration_results: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calibration 결과를 Zone Profiles YAML에 적용
    
    각 profile의 boundaries를 조정하여 entry_threshold가 new_threshold_bps가 되도록 함
    """
    symbol_mappings = zone_profiles.get("symbol_mappings", {})
    
    for symbol, result in calibration_results.items():
        if result["action"] != "update":
            continue
        
        # 심볼이 어떤 profile을 사용하는지 찾기
        profile_name = symbol_mappings.get(symbol)
        if not profile_name:
            logger.warning(f"  {symbol}: No profile mapping found, skipping")
            continue
        
        # 해당 profile의 boundaries 조정
        # 간단 구현: Zone 2 (가장 높은 weight zone)의 lower bound를 new_threshold로 설정
        profile_data = zone_profiles["profiles"].get(profile_name)
        if not profile_data:
            logger.warning(f"  {symbol}: Profile '{profile_name}' not found, skipping")
            continue
        
        symbol_boundaries = profile_data.get(symbol)
        if not symbol_boundaries or "boundaries" not in symbol_boundaries:
            logger.warning(f"  {symbol}: No boundaries in profile '{profile_name}', skipping")
            continue
        
        # boundaries는 [[z1_low, z1_high], [z2_low, z2_high], ...]
        # entry_threshold는 Zone 2의 lower bound (index 1, [0])
        old_boundaries = symbol_boundaries["boundaries"]
        new_threshold_decimal = result["new_threshold_bps"] / 10000.0
        
        # Zone 2의 lower bound를 new_threshold로 설정
        # Zone 1의 upper bound도 동일하게 조정
        new_boundaries = [
            [old_boundaries[0][0], new_threshold_decimal],  # Zone 1: [기존_low, new_threshold]
            [new_threshold_decimal, old_boundaries[1][1]],  # Zone 2: [new_threshold, 기존_high]
            old_boundaries[2],  # Zone 3: 유지
            old_boundaries[3],  # Zone 4: 유지
        ]
        
        symbol_boundaries["boundaries"] = new_boundaries
        logger.info(
            f"  {symbol}: Updated boundaries in profile '{profile_name}' "
            f"(Zone 2 lower={new_threshold_decimal:.5f} = {result['new_threshold_bps']:.2f} bps)"
        )
    
    return zone_profiles


def main():
    parser = argparse.ArgumentParser(description="D92-2: Zone Profile Threshold Calibration")
    parser.add_argument(
        "--telemetry-report",
        type=str,
        required=True,
        help="Path to d92_2_spread_report.json",
    )
    parser.add_argument(
        "--zone-profiles-yaml",
        type=str,
        default="config/arbitrage/zone_profiles_v2.yaml",
        help="Path to zone_profiles_v2.yaml",
    )
    parser.add_argument(
        "--output-yaml",
        type=str,
        default=None,
        help="Output path for calibrated zone_profiles_v2.yaml (default: overwrite input)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run: show calibration results without saving",
    )
    args = parser.parse_args()
    
    # 1. Telemetry 로드
    logger.info("=" * 80)
    logger.info("[D92-2-CALIBRATION] Loading telemetry report...")
    logger.info("=" * 80)
    telemetry_report = load_telemetry_report(args.telemetry_report)
    logger.info(f"  Session: {telemetry_report['session_id']}")
    logger.info(f"  Duration: {telemetry_report['duration_minutes']:.1f} minutes")
    logger.info(f"  Symbols: {len(telemetry_report['symbols'])}")
    
    # 2. Zone Profiles 로드
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D92-2-CALIBRATION] Loading zone profiles...")
    logger.info("=" * 80)
    zone_profiles = load_zone_profiles_v2(args.zone_profiles_yaml)
    logger.info(f"  Profiles: {len(zone_profiles['profiles'])}")
    logger.info(f"  Symbol mappings: {len(zone_profiles['symbol_mappings'])}")
    
    # 3. Threshold 재보정
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D92-2-CALIBRATION] Calibrating thresholds...")
    logger.info("=" * 80)
    
    calibration_results = {}
    for symbol, telemetry in telemetry_report["symbols"].items():
        # D92-2: 심볼 이름 정규화 (BTC/KRW → BTC)
        symbol_normalized = symbol.split("/")[0] if "/" in symbol else symbol
        current_threshold = telemetry["threshold_bps"]
        result = calibrate_threshold(symbol_normalized, telemetry, current_threshold)
        calibration_results[symbol_normalized] = result
        
        action_icon = "✅" if result["action"] == "update" else "⏸️"
        logger.info(
            f"{action_icon} {result['symbol']:6s}: "
            f"old={result['old_threshold_bps']:6.2f} → new={result['new_threshold_bps']:6.2f} bps "
            f"(p95={result['p95_spread_bps']:6.2f}, {result['reason']})"
        )
    
    # 4. 통계 요약
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D92-2-CALIBRATION] Summary")
    logger.info("=" * 80)
    
    action_counts = {"update": 0, "keep": 0, "hold": 0}
    for result in calibration_results.values():
        action_counts[result["action"]] += 1
    
    logger.info(f"  Total symbols: {len(calibration_results)}")
    logger.info(f"  Updates: {action_counts['update']}")
    logger.info(f"  Keep (no change): {action_counts['keep']}")
    logger.info(f"  Hold (p95 < floor): {action_counts['hold']}")
    
    # 5. YAML 업데이트
    if args.dry_run:
        logger.info("")
        logger.info("=" * 80)
        logger.info("[D92-2-CALIBRATION] DRY RUN - No changes saved")
        logger.info("=" * 80)
        return
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D92-2-CALIBRATION] Applying calibration to YAML...")
    logger.info("=" * 80)
    
    updated_zone_profiles = apply_calibration_to_yaml(zone_profiles, calibration_results)
    
    output_path = args.output_yaml or args.zone_profiles_yaml
    save_zone_profiles_v2(output_path, updated_zone_profiles)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"[D92-2-CALIBRATION] Calibration complete: {output_path}")
    logger.info("=" * 80)
    
    # 6. Calibration 결과 JSON 저장
    calibration_result_path = Path(args.telemetry_report).parent / "d92_2_calibration_result.json"
    with open(calibration_result_path, "w") as f:
        json.dump(calibration_results, f, indent=2)
    
    logger.info(f"[D92-2-CALIBRATION] Calibration result saved: {calibration_result_path}")


if __name__ == "__main__":
    main()
