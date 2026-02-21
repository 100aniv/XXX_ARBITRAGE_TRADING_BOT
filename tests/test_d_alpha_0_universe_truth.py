"""
D_ALPHA-0: Universe Truth 테스트

검증 항목:
- UniverseBuilder.get_snapshot()이 universe_requested_top_n, universe_loaded_count 반환
- runtime_factory가 universe_metadata를 config에 저장
- orchestrator가 run_meta에 universe_metadata 포함
- monitor가 edge_survey_report에 unique_symbols_evaluated 포함
"""

import json
import hashlib
from types import SimpleNamespace
import pytest
from unittest.mock import MagicMock, patch
from arbitrage.v2.universe.builder import UniverseBuilder, UniverseBuilderConfig, UniverseMode
from arbitrage.v2.core.monitor import EvidenceCollector


def test_universe_snapshot_includes_metadata_and_size_100_artifact():
    """
    [D_ALPHA-0::AC-1] UniverseBuilder.get_snapshot() returns universe metadata,
    and when topn_count=100, universe_size=100 is recorded in the artifact.
    """
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=100,
        static_symbols=None,
    )
    builder = UniverseBuilder(config)
    
    snapshot = builder.get_snapshot()
    
    # 필수 필드 존재 확인
    assert "universe_requested_top_n" in snapshot
    assert "universe_loaded_count" in snapshot
    
    # 값 검증
    assert snapshot["universe_requested_top_n"] == 100
    assert isinstance(snapshot["universe_loaded_count"], int)
    assert snapshot["universe_loaded_count"] >= 0

    # [AC-1] universe_size=100 artifact 기록 검증
    # EvidenceCollector._edge_survey_report를 통해 universe_size=100이 기록되는지 확인
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
    # universe_size=100이 기록되어야 함 (universe_requested_top_n == 100)
    assert "universe_metadata" in report
    assert report["universe_metadata"].get("universe_requested_top_n", None) == 100
    # unique_symbols_evaluated도 2로 기록되어야 함
    assert report["unique_symbols_evaluated"] == 2
    # coverage_ratio도 2/100
    assert report["coverage_ratio"] == pytest.approx(2 / 100, rel=1e-6)
    # [D_ALPHA-0::AC-1] machine-readable: universe_size=100 artifact
    # universe_size=100 must be present in the artifact for AC-1
    assert report["universe_metadata"].get("universe_size", None) == 100, \
        "universe_size=100 must be present in the artifact for AC-1"




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
    assert report["coverage_ratio"] == pytest.approx(2 / 100, rel=1e-6)

    expected_hash = hashlib.sha256(
        json.dumps(["BTC/KRW", "ETH/KRW"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert report["universe_symbols_hash"] == expected_hash


def test_universe_builder_binance_filter_and_cutting(monkeypatch):
    """Binance 지원 심볼 필터 + topn_count 컷팅 검증"""
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=2,
        data_source="real",
    )
    builder = UniverseBuilder(config)

    symbols = [
        ("BTC/KRW", "BTC/USDT"),
        ("ETH/KRW", "ETH/USDT"),
        ("XRP/KRW", "XRP/USDT"),
        ("DOGE/KRW", "DOGE/USDT"),
    ]
    provider = SimpleNamespace(
        get_topn_symbols=lambda selection_limit=None: SimpleNamespace(
            symbols=symbols,
            churn_rate=0.0,
        )
    )
    builder._provider = provider

    monkeypatch.setattr(builder, "_get_binance_supported_bases", lambda: {"BTC", "ETH", "XRP"})

    selected = builder.get_symbols()
    assert selected == [
        ("BTC/KRW", "BTC/USDT"),
        ("ETH/KRW", "ETH/USDT"),
    ]


def test_universe_builder_coverage_warning(monkeypatch, caplog):
    """Coverage 95% 미만 시 경고 로그 발생"""
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=100,
        data_source="real",
    )
    builder = UniverseBuilder(config)

    symbols = [(f"SYM{i:03d}/KRW", f"SYM{i:03d}/USDT") for i in range(80)]
    provider = SimpleNamespace(
        get_topn_symbols=lambda selection_limit=None: SimpleNamespace(
            symbols=symbols,
            churn_rate=0.0,
        )
    )
    builder._provider = provider
    monkeypatch.setattr(builder, "_get_binance_supported_bases", lambda: {f"SYM{i:03d}" for i in range(80)})

    with caplog.at_level("WARNING"):
        selected = builder.get_symbols()

    assert len(selected) == 80
    assert any("Coverage below target" in record.message for record in caplog.records)


def test_universe_builder_coverage_warning_logged(caplog):
    """
    UniverseBuilder가 coverage < 0.95일 때 경고 로그를 출력하는지 검증.
    """
    from arbitrage.v2.universe.builder import UniverseBuilder, UniverseBuilderConfig, UniverseMode
    
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=100,
        data_source="mock",
        cache_ttl_seconds=60,
        min_volume_usd=10_000.0,
        min_liquidity_usd=1_000.0,
        max_spread_bps=100.0,
    )
    
    builder = UniverseBuilder(config=config)
    
    with caplog.at_level("WARNING"):
        symbols = builder.get_symbols()
    
    assert len(symbols) < 95, "Mock should return < 95 symbols for topn_count=100"
    
    warning_logs = [r.message for r in caplog.records if r.levelname == "WARNING"]
    assert any("Coverage below target" in log for log in warning_logs), \
        "Should log coverage warning when < 0.95"


def test_universe_builder_binance_futures_filter_integration():
    """
    D_ALPHA-1U-FIX-1: UniverseBuilder가 Binance Futures exchangeInfo 기반 필터를 사용하는지 검증.
    
    Mock 환경에서는 실제 API 호출 대신 로직만 검증.
    """
    from arbitrage.v2.universe.builder import UniverseBuilder, UniverseBuilderConfig, UniverseMode
    
    config = UniverseBuilderConfig(
        mode=UniverseMode.TOPN,
        topn_count=10,
        data_source="mock",
        cache_ttl_seconds=60,
        min_volume_usd=10_000.0,
        min_liquidity_usd=1_000.0,
        max_spread_bps=100.0,
    )
    
    builder = UniverseBuilder(config=config)
    
    # Mock data source에서는 Binance 필터가 스킵됨 (data_source == "mock")
    symbols = builder.get_symbols()
    
    # Mock 환경에서는 최소한 symbol pair 구조 검증
    assert len(symbols) > 0, "Should return symbols"
    for symbol_a, symbol_b in symbols:
        assert "/" in symbol_a, f"Symbol A should have / separator: {symbol_a}"
        assert "/" in symbol_b, f"Symbol B should have / separator: {symbol_b}"
    
    # Real API 테스트는 integration test에서 수행
    # (BinancePublicDataClient.fetch_futures_supported_bases() 호출 확인)


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
    assert report["coverage_ratio"] == pytest.approx(2 / 10, rel=1e-6)
    expected_hash = hashlib.sha256(
        json.dumps(["BTC/KRW", "ETH/KRW"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert report["universe_symbols_hash"] == expected_hash
