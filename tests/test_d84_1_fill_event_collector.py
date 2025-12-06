# -*- coding: utf-8 -*-
"""
D84-1: FillEventCollector 유닛 테스트

테스트 목표:
    1. 이벤트 기록 정확도
    2. JSONL 파일 저장
    3. disabled 상태에서 side-effect 없음
    4. Thread-safe 동작

Author: arbitrage-lite project
Date: 2025-12-06
"""

import pytest
import json
import tempfile
from pathlib import Path

from arbitrage.metrics.fill_stats import FillEventCollector, FillEvent
from arbitrage.types import OrderSide


# Test 1: 기본 이벤트 기록
def test_fill_event_collector_basic_recording():
    """FillEventCollector: 기본 이벤트 기록"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_events.jsonl"
        collector = FillEventCollector(
            output_path=output_path,
            enabled=True,
            session_id="test_session",
        )
        
        collector.record_fill_event(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_bps=10.0,
            tp_bps=12.0,
            order_quantity=1000.0,
            filled_quantity=300.0,
            fill_ratio=0.3,
            slippage_bps=2.5,
        )
        
        assert output_path.exists()
        assert collector.events_count == 1


# Test 2: JSONL 형식 확인
def test_fill_event_collector_jsonl_format():
    """FillEventCollector: JSONL 형식 확인"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_events.jsonl"
        collector = FillEventCollector(
            output_path=output_path,
            enabled=True,
        )
        
        collector.record_fill_event(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_bps=10.0,
            tp_bps=12.0,
            order_quantity=1000.0,
            filled_quantity=300.0,
            fill_ratio=0.3,
            slippage_bps=2.5,
        )
        
        # JSONL 파일 읽기
        with open(output_path, "r") as f:
            line = f.readline()
            event = json.loads(line)
            
            assert event["symbol"] == "BTC/USDT"
            assert event["side"].upper() == "BUY"  # OrderSide.value는 소문자 반환
            assert event["entry_bps"] == 10.0
            assert event["tp_bps"] == 12.0
            assert event["fill_ratio"] == 0.3


# Test 3: Disabled 상태
def test_fill_event_collector_disabled():
    """FillEventCollector: disabled 상태에서 side-effect 없음"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_events.jsonl"
        collector = FillEventCollector(
            output_path=output_path,
            enabled=False,  # 비활성화
        )
        
        collector.record_fill_event(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_bps=10.0,
            tp_bps=12.0,
            order_quantity=1000.0,
            filled_quantity=300.0,
            fill_ratio=0.3,
            slippage_bps=2.5,
        )
        
        # 파일이 생성되지 않아야 함
        assert not output_path.exists()
        assert collector.events_count == 0


# Test 4: 여러 이벤트 기록
def test_fill_event_collector_multiple_events():
    """FillEventCollector: 여러 이벤트 기록"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_events.jsonl"
        collector = FillEventCollector(
            output_path=output_path,
            enabled=True,
        )
        
        for i in range(5):
            collector.record_fill_event(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                entry_bps=10.0 + i,
                tp_bps=12.0 + i,
                order_quantity=1000.0,
                filled_quantity=300.0,
                fill_ratio=0.3,
                slippage_bps=2.5,
            )
        
        assert collector.events_count == 5
        
        # JSONL 파일에 5줄이 있어야 함
        with open(output_path, "r") as f:
            lines = f.readlines()
            assert len(lines) == 5


# Test 5: 요약 정보
def test_fill_event_collector_summary():
    """FillEventCollector: 요약 정보 확인"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_events.jsonl"
        collector = FillEventCollector(
            output_path=output_path,
            enabled=True,
            session_id="test_summary",
        )
        
        collector.record_fill_event(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            entry_bps=10.0,
            tp_bps=12.0,
            order_quantity=1000.0,
            filled_quantity=300.0,
            fill_ratio=0.3,
            slippage_bps=2.5,
        )
        
        summary = collector.get_summary()
        
        assert summary["enabled"] is True
        assert summary["session_id"] == "test_summary"
        assert summary["events_count"] == 1
        assert str(output_path) in summary["output_path"]
