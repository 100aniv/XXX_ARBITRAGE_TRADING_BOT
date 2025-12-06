# -*- coding: utf-8 -*-
"""
D84-1: FillModelCalibrator 유닛 테스트

테스트 목표:
    1. JSONL 로드 정확도
    2. Zone별 통계 계산
    3. Calibration JSON 생성
    4. Edge case 처리

Author: arbitrage-lite project
Date: 2025-12-06
"""

import pytest
import json
import tempfile
from pathlib import Path

from arbitrage.analysis.fill_calibrator import FillModelCalibrator, ZoneDefinition


# Test 1: JSONL 로드
def test_fill_calibrator_load_events():
    """FillModelCalibrator: JSONL 로드"""
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "test_events.jsonl"
        
        # 샘플 이벤트 작성
        events = [
            {"entry_bps": 6.0, "tp_bps": 10.0, "side": "BUY", "fill_ratio": 0.3},
            {"entry_bps": 12.0, "tp_bps": 14.0, "side": "BUY", "fill_ratio": 0.25},
        ]
        
        with open(jsonl_path, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        
        loaded_events = FillModelCalibrator.load_fill_events([jsonl_path])
        
        assert len(loaded_events) == 2
        assert loaded_events[0]["entry_bps"] == 6.0


# Test 2: Zone별 통계 계산
def test_fill_calibrator_compute_zone_stats():
    """FillModelCalibrator: Zone별 통계 계산"""
    zones = [
        ZoneDefinition(
            zone_id="Z1",
            entry_min=5.0,
            entry_max=7.0,
            tp_min=7.0,
            tp_max=12.0,
        ),
        ZoneDefinition(
            zone_id="Z2",
            entry_min=10.0,
            entry_max=14.0,
            tp_min=12.0,
            tp_max=16.0,
        ),
    ]
    
    events = [
        {"entry_bps": 6.0, "tp_bps": 10.0, "side": "BUY", "fill_ratio": 0.3},
        {"entry_bps": 6.0, "tp_bps": 10.0, "side": "BUY", "fill_ratio": 0.4},
        {"entry_bps": 12.0, "tp_bps": 14.0, "side": "BUY", "fill_ratio": 0.25},
    ]
    
    stats = FillModelCalibrator.compute_zone_stats(events, zones)
    
    # Z1: 2 events, 평균 0.35
    # Z2: 1 event, 평균 0.25
    z1_stats = next(z for z in stats["zones"] if z["zone_id"] == "Z1")
    z2_stats = next(z for z in stats["zones"] if z["zone_id"] == "Z2")
    
    assert z1_stats["buy_fill_ratio"] == pytest.approx(0.35, abs=0.01)
    assert z2_stats["buy_fill_ratio"] == pytest.approx(0.25, abs=0.01)
    assert z1_stats["buy_samples"] == 2
    assert z2_stats["buy_samples"] == 1


# Test 3: Calibration JSON 생성
def test_fill_calibrator_create_calibration_json():
    """FillModelCalibrator: Calibration JSON 생성"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "calibration.json"
        
        events = [
            {"entry_bps": 6.0, "tp_bps": 10.0, "side": "BUY", "fill_ratio": 0.3},
            {"entry_bps": 6.0, "tp_bps": 10.0, "side": "SELL", "fill_ratio": 1.0},
        ]
        
        calibration = FillModelCalibrator.create_calibration_json(
            events=events,
            output_path=output_path,
            version="test_v1",
            source="test",
        )
        
        assert output_path.exists()
        assert calibration["version"] == "test_v1"
        assert calibration["total_events"] == 2
        assert "zones" in calibration


# Test 4: 빈 이벤트 처리
def test_fill_calibrator_empty_events():
    """FillModelCalibrator: 빈 이벤트 리스트 처리"""
    events = []
    
    stats = FillModelCalibrator.compute_zone_stats(events)
    
    # default 값 사용
    assert stats["default_buy_fill_ratio"] == 0.2615
    assert stats["default_sell_fill_ratio"] == 1.0
    assert stats["total_events"] == 0


# Test 5: Unmatched Events
def test_fill_calibrator_unmatched_events():
    """FillModelCalibrator: Unmatched Events 처리"""
    zones = [
        ZoneDefinition(
            zone_id="Z1",
            entry_min=5.0,
            entry_max=7.0,
            tp_min=7.0,
            tp_max=12.0,
        ),
    ]
    
    events = [
        {"entry_bps": 6.0, "tp_bps": 10.0, "side": "BUY", "fill_ratio": 0.3},  # 매칭
        {"entry_bps": 20.0, "tp_bps": 25.0, "side": "BUY", "fill_ratio": 0.4},  # 미매칭
    ]
    
    stats = FillModelCalibrator.compute_zone_stats(events, zones)
    
    assert stats["unmatched_events"] == 1
    assert stats["default_buy_fill_ratio"] == 0.4  # unmatched event의 평균
