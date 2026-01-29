"""
D_ALPHA-0: Universe Truth 테스트

검증 항목:
- UniverseBuilder.get_snapshot()이 universe_requested_top_n, universe_loaded_count 반환
- runtime_factory가 universe_metadata를 config에 저장
- orchestrator가 run_meta에 universe_metadata 포함
- monitor가 edge_survey_report에 unique_symbols_evaluated 포함
"""

import pytest
from unittest.mock import MagicMock, patch
from arbitrage.v2.universe.builder import UniverseBuilder, UniverseBuilderConfig, UniverseMode
from arbitrage.v2.core.monitor import EvidenceCollector


def test_universe_snapshot_includes_metadata():
    """UniverseBuilder.get_snapshot()이 universe metadata 반환"""
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=50,
        static_symbols=None,
    )
    builder = UniverseBuilder(config)
    
    snapshot = builder.get_snapshot()
    
    # 필수 필드 존재 확인
    assert "universe_requested_top_n" in snapshot
    assert "universe_loaded_count" in snapshot
    
    # 값 검증
    assert snapshot["universe_requested_top_n"] == 50
    assert isinstance(snapshot["universe_loaded_count"], int)
    assert snapshot["universe_loaded_count"] >= 0




def test_edge_survey_report_includes_unique_symbols_evaluated():
    """edge_survey_report에 unique_symbols_evaluated 포함"""
    # Mock edge_distribution (monitor.py 구조에 맞춤)
    edge_distribution = [
        {
            "tick": 1,
            "candidates": [
                {"symbol": "BTC/KRW", "spread_bps": 50.0, "net_edge_bps": 20.0},
                {"symbol": "ETH/KRW", "spread_bps": 30.0, "net_edge_bps": 10.0},
            ]
        },
        {
            "tick": 2,
            "candidates": [
                {"symbol": "BTC/KRW", "spread_bps": 40.0, "net_edge_bps": 15.0},  # 중복
            ]
        },
    ]
    
    # Mock run_meta with universe_metadata
    run_meta = {
        "universe_metadata": {
            "universe_requested_top_n": 100,
            "universe_loaded_count": 50,
        },
        "metrics": {
            "reject_reasons": {},
        },
    }
    
    # EvidenceCollector._edge_survey_report 호출
    collector = EvidenceCollector(
        output_dir="logs/test",
        run_id="test_run",
    )
    
    report = collector._edge_survey_report(
        edge_distribution=edge_distribution,
        run_meta=run_meta,
    )
    
    # 필수 필드 검증
    assert "unique_symbols_evaluated" in report
    assert report["unique_symbols_evaluated"] == 2  # BTC/KRW, ETH/KRW
    
    # universe_metadata 검증
    assert "universe_metadata" in report
    assert report["universe_metadata"]["universe_requested_top_n"] == 100
    assert report["universe_metadata"]["universe_loaded_count"] == 50


def test_universe_metadata_end_to_end():
    """Universe metadata 전체 플로우 통합 테스트"""
    # 1. UniverseBuilder snapshot 생성
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=10,
    )
    builder = UniverseBuilder(config)
    snapshot = builder.get_snapshot()
    
    assert snapshot["universe_requested_top_n"] == 10
    assert "universe_loaded_count" in snapshot
    
    # 2. edge_survey_report에 unique_symbols_evaluated 포함 확인
    edge_distribution = [
        {
            "tick": 1,
            "candidates": [
                {"symbol": "BTC/KRW", "spread_bps": 50.0, "net_edge_bps": 20.0},
                {"symbol": "ETH/KRW", "spread_bps": 30.0, "net_edge_bps": 10.0},
            ]
        },
    ]
    
    run_meta = {
        "universe_metadata": snapshot,
        "metrics": {"reject_reasons": {}},
    }
    
    collector = EvidenceCollector(
        output_dir="logs/test",
        run_id="test_run",
    )
    
    report = collector._edge_survey_report(
        edge_distribution=edge_distribution,
        run_meta=run_meta,
    )
    
    assert report["unique_symbols_evaluated"] == 2
    assert report["universe_metadata"]["universe_requested_top_n"] == 10
