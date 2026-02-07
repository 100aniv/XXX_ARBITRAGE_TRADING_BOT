#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3: FillModel Analyzer 테스트

Calibration 기반 Zone 매핑, Notional 계산 검증
"""

import json
import pytest
from pathlib import Path
import sys

pytestmark = pytest.mark.optional_live

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.analyze_d87_3_fillmodel_ab_test import (
    load_calibration,
    map_zone,
    load_fill_events,
    analyze_session,
)


class TestCalibrationLoading:
    """Calibration JSON 로딩 테스트"""
    
    def test_load_valid_calibration(self):
        """정상 Calibration JSON 로딩"""
        cal_path = Path("logs/d86-1/calibration_20251207_123906.json")
        
        if not cal_path.exists():
            pytest.skip("Calibration 파일이 존재하지 않음")
        
        calibration = load_calibration(cal_path)
        
        assert calibration is not None
        assert "zones" in calibration
        assert len(calibration["zones"]) == 4
        
        # Zone 구조 검증
        for zone in calibration["zones"]:
            assert "zone_id" in zone
            assert "entry_min" in zone
            assert "entry_max" in zone
            assert "tp_min" in zone
            assert "tp_max" in zone


class TestZoneMapping:
    """Zone 매핑 로직 테스트"""
    
    @pytest.fixture
    def zones(self):
        """테스트용 Zones"""
        return [
            {
                "zone_id": "Z1",
                "entry_min": 5.0,
                "entry_max": 7.0,
                "tp_min": 7.0,
                "tp_max": 12.0,
            },
            {
                "zone_id": "Z2",
                "entry_min": 7.0,
                "entry_max": 12.0,
                "tp_min": 10.0,
                "tp_max": 20.0,
            },
            {
                "zone_id": "Z3",
                "entry_min": 12.0,
                "entry_max": 20.0,
                "tp_min": 15.0,
                "tp_max": 30.0,
            },
            {
                "zone_id": "Z4",
                "entry_min": 20.0,
                "entry_max": 30.0,
                "tp_min": 25.0,
                "tp_max": 40.0,
            },
        ]
    
    def test_map_zone_z1(self, zones):
        """Z1 매핑 테스트"""
        zone_id = map_zone(entry_bps=6.0, tp_bps=10.0, zones=zones)
        assert zone_id == "Z1"
    
    def test_map_zone_z2(self, zones):
        """Z2 매핑 테스트"""
        zone_id = map_zone(entry_bps=10.0, tp_bps=12.0, zones=zones)
        assert zone_id == "Z2"
    
    def test_map_zone_z3(self, zones):
        """Z3 매핑 테스트"""
        zone_id = map_zone(entry_bps=15.0, tp_bps=20.0, zones=zones)
        assert zone_id == "Z3"
    
    def test_map_zone_z4(self, zones):
        """Z4 매핑 테스트"""
        zone_id = map_zone(entry_bps=25.0, tp_bps=30.0, zones=zones)
        assert zone_id == "Z4"
    
    def test_map_zone_unknown(self, zones):
        """범위 밖 → UNKNOWN"""
        zone_id = map_zone(entry_bps=50.0, tp_bps=60.0, zones=zones)
        assert zone_id == "UNKNOWN"
    
    def test_map_zone_boundary(self, zones):
        """경계값 테스트 (Z1/Z2)"""
        # entry=7.0은 Z1 max이므로 Z2에 매핑되어야 함
        zone_id = map_zone(entry_bps=7.0, tp_bps=10.0, zones=zones)
        assert zone_id == "Z2"


class TestFillEventsAnalysis:
    """Fill Events 분석 테스트"""
    
    def test_analyze_session_with_calibration(self, tmp_path):
        """Calibration 포함 세션 분석"""
        # 더미 Fill Events JSONL 생성
        fill_events_path = tmp_path / "fill_events_test.jsonl"
        events = [
            {
                "side": "buy",
                "entry_bps": 10.0,
                "tp_bps": 12.0,
                "filled_quantity": 0.001,
            },
            {
                "side": "sell",
                "entry_bps": 10.0,
                "tp_bps": 12.0,
                "filled_quantity": 0.001,
            },
            {
                "side": "buy",
                "entry_bps": 15.0,
                "tp_bps": 20.0,
                "filled_quantity": 0.002,
            },
            {
                "side": "sell",
                "entry_bps": 15.0,
                "tp_bps": 20.0,
                "filled_quantity": 0.002,
            },
        ]
        
        with open(fill_events_path, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        
        # 더미 KPI JSON 생성
        kpi_path = tmp_path / "kpi_test.json"
        kpi = {
            "total_pnl_usd": 10.0,
            "entry_trades": 2,
        }
        
        with open(kpi_path, "w") as f:
            json.dump(kpi, f)
        
        # 더미 Calibration
        calibration = {
            "zones": [
                {
                    "zone_id": "Z2",
                    "entry_min": 7.0,
                    "entry_max": 12.0,
                    "tp_min": 10.0,
                    "tp_max": 20.0,
                },
                {
                    "zone_id": "Z3",
                    "entry_min": 12.0,
                    "entry_max": 20.0,
                    "tp_min": 15.0,
                    "tp_max": 30.0,
                },
            ]
        }
        
        # 분석 실행
        summary = analyze_session(tmp_path, "Test", calibration)
        
        assert summary is not None
        assert summary["entry_trades"] == 2
        assert summary["total_pnl"] == 10.0
        
        # Zone 분석 검증
        zone_analysis = summary["zone_analysis"]
        assert "Z2" in zone_analysis
        assert "Z3" in zone_analysis
        assert zone_analysis["Z2"]["trade_count"] == 1
        assert zone_analysis["Z3"]["trade_count"] == 1
        
        # Notional 계산 검증 (filled_quantity * $50,000)
        assert zone_analysis["Z2"]["notional_sum"] == pytest.approx(50.0, abs=1.0)
        assert zone_analysis["Z3"]["notional_sum"] == pytest.approx(100.0, abs=1.0)
    
    def test_analyze_session_without_calibration(self, tmp_path):
        """Calibration 없이 세션 분석 (UNKNOWN으로 처리)"""
        # 더미 Fill Events JSONL 생성
        fill_events_path = tmp_path / "fill_events_test.jsonl"
        events = [
            {
                "side": "buy",
                "entry_bps": 10.0,
                "tp_bps": 12.0,
                "filled_quantity": 0.001,
            },
        ]
        
        with open(fill_events_path, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        
        # Calibration 없이 분석
        summary = analyze_session(tmp_path, "Test", calibration=None)
        
        assert summary is not None
        assert summary["entry_trades"] == 1
        
        # 모두 UNKNOWN으로 분류되어야 함
        zone_analysis = summary["zone_analysis"]
        assert "UNKNOWN" in zone_analysis
        assert zone_analysis["UNKNOWN"]["trade_count"] == 1
