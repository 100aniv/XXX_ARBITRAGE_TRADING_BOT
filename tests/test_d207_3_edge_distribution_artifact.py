"""
D207-3: Edge Distribution Artifact Test

Goal: edge_distribution.json 저장 및 manifest 포함 확인.
SSOT: D_ROADMAP.md -> D207-3
"""

import json

from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector


def test_edge_distribution_artifact_saved(tmp_path):
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id="test_edge_distribution")
    metrics = PaperMetrics()
    run_meta = {
        "run_id": "test_edge_distribution",
        "git_sha": "dummy",
        "branch": "test",
        "config_path": "config/v2/config.yml",
        "symbols": [("BTC/KRW", "BTC/USDT")],
        "cli_args": {"duration": 1},
    }

    edge_distribution = [
        {
            "iteration": 1,
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "reason": "",
            "candidates": [
                {
                    "symbol": "BTC/KRW",
                    "exchange_a": "upbit",
                    "exchange_b": "binance",
                    "price_a": 100.0,
                    "price_b": 99.0,
                    "spread_bps": 101.0,
                    "break_even_bps": 55.0,
                    "edge_bps": 46.0,
                    "deterministic_drift_bps": 10.0,
                    "net_edge_bps": 36.0,
                    "direction": "buy_b_sell_a",
                    "profitable": True,
                    "exchange_a_bid": 99.5,
                    "exchange_a_ask": 100.5,
                    "exchange_b_bid": 98.5,
                    "exchange_b_ask": 99.5,
                    "fx_rate": 1300.0,
                    "fx_rate_source": "fixed",
                    "fx_rate_age_sec": 0.0,
                    "fx_rate_timestamp": "",
                    "fx_rate_degraded": False,
                }
            ],
        }
    ]

    collector.save(
        metrics=metrics,
        trade_history=[],
        edge_distribution=edge_distribution,
        phase="smoke",
        run_meta=run_meta,
    )

    edge_path = tmp_path / "edge_distribution.json"
    assert edge_path.exists()
    with open(edge_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved == edge_distribution

    summary_path = tmp_path / "edge_analysis_summary.json"
    assert summary_path.exists()
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
    assert "p50" in summary
    assert "min_net_edge_bps" in summary

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert "edge_distribution.json" in manifest.get("files", [])
    assert "edge_analysis_summary.json" in manifest.get("files", [])
    assert manifest.get("run_meta", {}).get("run_id") == "test_edge_distribution"
