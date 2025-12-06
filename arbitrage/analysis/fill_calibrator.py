# -*- coding: utf-8 -*-
"""
D84-1: Fill Model Calibrator

목적:
    Fill Event JSONL 데이터를 분석하여 Zone별 Fill Ratio 통계를 계산하고
    Calibration Table JSON을 생성.

기능:
    1. Fill Events JSONL 파일 로드
    2. Zone별 Fill Ratio 집계 (평균, 중앙값, 샘플 수)
    3. Calibration JSON 생성

Author: arbitrage-lite project
Date: 2025-12-06
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ZoneDefinition:
    """
    Zone 정의
    
    Attributes:
        zone_id: Zone 식별자
        entry_min: Entry Threshold 하한 (bps)
        entry_max: Entry Threshold 상한 (bps)
        tp_min: TP Threshold 하한 (bps)
        tp_max: TP Threshold 상한 (bps)
    """
    zone_id: str
    entry_min: float
    entry_max: float
    tp_min: float
    tp_max: float


class FillModelCalibrator:
    """
    Fill Model Calibrator
    
    Fill Event 데이터를 분석하여 Calibration Table 생성.
    
    기능:
        - JSONL 파일 로드
        - Zone별 Fill Ratio 통계 계산
        - Calibration JSON 저장
    """
    
    # 기본 Zone 정의 (D84-0 설계 문서 기준)
    DEFAULT_ZONES = [
        ZoneDefinition(
            zone_id="Z1",
            entry_min=5.0,
            entry_max=7.0,
            tp_min=7.0,
            tp_max=12.0,
        ),
        ZoneDefinition(
            zone_id="Z2",
            entry_min=7.0,
            entry_max=10.0,
            tp_min=10.0,
            tp_max=12.0,
        ),
        ZoneDefinition(
            zone_id="Z3",
            entry_min=10.0,
            entry_max=14.0,
            tp_min=12.0,
            tp_max=16.0,
        ),
        ZoneDefinition(
            zone_id="Z4",
            entry_min=14.0,
            entry_max=16.0,
            tp_min=16.0,
            tp_max=18.0,
        ),
    ]
    
    @staticmethod
    def load_fill_events(jsonl_paths: List[Path]) -> List[Dict]:
        """
        JSONL 파일에서 Fill Event 로드
        
        Args:
            jsonl_paths: JSONL 파일 경로 리스트
        
        Returns:
            Fill Event 리스트
        """
        events = []
        
        for path in jsonl_paths:
            if not path.exists():
                logger.warning(f"[D84-1_CALIBRATOR] File not found: {path}")
                continue
            
            logger.info(f"[D84-1_CALIBRATOR] Loading events from: {path.name}")
            
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        events.append(event)
                    except json.JSONDecodeError as e:
                        logger.warning(f"[D84-1_CALIBRATOR] Failed to parse line: {e}")
        
        logger.info(f"[D84-1_CALIBRATOR] Total events loaded: {len(events)}")
        return events
    
    @staticmethod
    def compute_zone_stats(
        events: List[Dict],
        zones: List[ZoneDefinition] = None,
    ) -> Dict:
        """
        Zone별 Fill Ratio 통계 계산
        
        Args:
            events: Fill Event 리스트
            zones: Zone 정의 (기본: DEFAULT_ZONES)
        
        Returns:
            Zone별 통계 (zone_id, buy/sell fill ratio, samples)
        """
        if zones is None:
            zones = FillModelCalibrator.DEFAULT_ZONES
        
        # Zone별 이벤트 분류
        zone_events = {zone.zone_id: {"BUY": [], "SELL": []} for zone in zones}
        unmatched_events = {"BUY": [], "SELL": []}
        
        for event in events:
            entry_bps = event.get("entry_bps", 0.0)
            tp_bps = event.get("tp_bps", 0.0)
            side = event.get("side", "BUY")
            fill_ratio = event.get("fill_ratio", 0.0)
            
            # Zone matching
            matched = False
            for zone in zones:
                if (zone.entry_min <= entry_bps <= zone.entry_max and
                    zone.tp_min <= tp_bps <= zone.tp_max):
                    zone_events[zone.zone_id][side].append(fill_ratio)
                    matched = True
                    break
            
            if not matched:
                unmatched_events[side].append(fill_ratio)
        
        # Zone별 통계 계산
        zone_stats = []
        for zone in zones:
            buy_ratios = zone_events[zone.zone_id]["BUY"]
            sell_ratios = zone_events[zone.zone_id]["SELL"]
            
            if len(buy_ratios) > 0:
                buy_fill_ratio_avg = statistics.mean(buy_ratios)
                buy_fill_ratio_median = statistics.median(buy_ratios)
            else:
                buy_fill_ratio_avg = 0.0
                buy_fill_ratio_median = 0.0
            
            if len(sell_ratios) > 0:
                sell_fill_ratio_avg = statistics.mean(sell_ratios)
                sell_fill_ratio_median = statistics.median(sell_ratios)
            else:
                sell_fill_ratio_avg = 1.0  # SELL 기본값
                sell_fill_ratio_median = 1.0
            
            zone_stats.append({
                "zone_id": zone.zone_id,
                "entry_min": zone.entry_min,
                "entry_max": zone.entry_max,
                "tp_min": zone.tp_min,
                "tp_max": zone.tp_max,
                "buy_fill_ratio": buy_fill_ratio_avg,
                "sell_fill_ratio": sell_fill_ratio_avg,
                "buy_fill_ratio_median": buy_fill_ratio_median,
                "sell_fill_ratio_median": sell_fill_ratio_median,
                "samples": len(buy_ratios) + len(sell_ratios),
                "buy_samples": len(buy_ratios),
                "sell_samples": len(sell_ratios),
            })
            
            logger.info(
                f"[D84-1_CALIBRATOR] {zone.zone_id}: "
                f"BUY={buy_fill_ratio_avg:.4f} (n={len(buy_ratios)}), "
                f"SELL={sell_fill_ratio_avg:.4f} (n={len(sell_ratios)})"
            )
        
        # Unmatched events 통계
        if len(unmatched_events["BUY"]) > 0:
            default_buy = statistics.mean(unmatched_events["BUY"])
        else:
            default_buy = 0.2615  # D82 기준 고정값
        
        if len(unmatched_events["SELL"]) > 0:
            default_sell = statistics.mean(unmatched_events["SELL"])
        else:
            default_sell = 1.0
        
        logger.info(
            f"[D84-1_CALIBRATOR] Unmatched events: "
            f"BUY={len(unmatched_events['BUY'])}, "
            f"SELL={len(unmatched_events['SELL'])}"
        )
        
        return {
            "zones": zone_stats,
            "default_buy_fill_ratio": default_buy,
            "default_sell_fill_ratio": default_sell,
            "total_events": len(events),
            "unmatched_events": len(unmatched_events["BUY"]) + len(unmatched_events["SELL"]),
        }
    
    @staticmethod
    def create_calibration_json(
        events: List[Dict],
        output_path: Path,
        version: str = "d84_1",
        source: str = "D84-1 PAPER execution",
        zones: List[ZoneDefinition] = None,
    ) -> Dict:
        """
        Calibration JSON 생성
        
        Args:
            events: Fill Event 리스트
            output_path: 출력 JSON 파일 경로
            version: Calibration 버전
            source: 데이터 출처
            zones: Zone 정의
        
        Returns:
            Calibration Table (dict)
        """
        logger.info(f"[D84-1_CALIBRATOR] Generating calibration JSON...")
        
        # Zone별 통계 계산
        stats = FillModelCalibrator.compute_zone_stats(events, zones)
        
        # Calibration Table 생성
        calibration = {
            "version": version,
            "created_at": datetime.utcnow().isoformat(),
            "source": source,
            "total_events": stats["total_events"],
            "unmatched_events": stats["unmatched_events"],
            "zones": stats["zones"],
            "default_buy_fill_ratio": stats["default_buy_fill_ratio"],
            "default_sell_fill_ratio": stats["default_sell_fill_ratio"],
        }
        
        # JSON 저장
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(calibration, f, indent=2)
        
        logger.info(f"[D84-1_CALIBRATOR] Saved calibration to: {output_path}")
        return calibration
