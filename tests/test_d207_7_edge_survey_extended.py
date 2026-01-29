"""
D207-7: Edge Survey Report Extended Schema Test

Goal: Validate reject_total, reject_by_reason, tail_stats, per-symbol tail stats.
SSOT: D_ROADMAP.md -> D207-7
"""

import json

from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector


def test_edge_survey_report_extended_schema(tmp_path):
    """Validate extended schema: reject_total, reject_by_reason, tail_stats"""
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id="test_d207_7")
    metrics = PaperMetrics()
    
    # Simulate reject reasons
    metrics.bump_reject("profitable_false")
    metrics.bump_reject("profitable_false")
    metrics.bump_reject("fx_stale")
    metrics.bump_reject("candidate_none")
    
    run_meta = {
        "run_id": "test_d207_7",
        "git_sha": "dummy",
        "branch": "test",
        "config_path": "config/v2/config.yml",
        "symbols": [("BTC/KRW", "BTC/USDT"), ("ETH/KRW", "ETH/USDT")],
        "cli_args": {"duration": 1, "survey_mode": True},
        "metrics": metrics.to_dict(),
    }

    edge_distribution = [
        {
            "iteration": 1,
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "reason": "",
            "sampling_policy": {
                "mode": "round_robin",
                "max_symbols_per_tick": 2,
                "universe_size": 2,
                "symbols_sampled": 2,
            },
            "candidates": [
                {
                    "symbol": "BTC/KRW",
                    "spread_bps": 50.0,
                    "net_edge_bps": 15.5,
                },
                {
                    "symbol": "BTC/KRW",
                    "spread_bps": 45.0,
                    "net_edge_bps": 10.2,
                },
                {
                    "symbol": "ETH/KRW",
                    "spread_bps": 30.0,
                    "net_edge_bps": -5.0,
                },
                {
                    "symbol": "ETH/KRW",
                    "spread_bps": 35.0,
                    "net_edge_bps": 2.1,
                },
            ],
        },
        {
            "iteration": 2,
            "timestamp_utc": "2026-01-01T00:00:01Z",
            "reason": "",
            "sampling_policy": {
                "mode": "round_robin",
                "max_symbols_per_tick": 2,
                "universe_size": 2,
                "symbols_sampled": 2,
            },
            "candidates": [
                {
                    "symbol": "BTC/KRW",
                    "spread_bps": 60.0,
                    "net_edge_bps": 25.0,
                },
                {
                    "symbol": "ETH/KRW",
                    "spread_bps": 40.0,
                    "net_edge_bps": 8.5,
                },
            ],
        },
    ]

    collector.save(
        metrics=metrics,
        trade_history=[],
        edge_distribution=edge_distribution,
        phase="edge_survey",
        run_meta=run_meta,
    )

    report_path = tmp_path / "edge_survey_report.json"
    assert report_path.exists()
    
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    # Basic validation
    assert report["status"] == "PASS"
    assert report["total_candidates"] == 6
    
    # D207-7: Validate reject_total and reject_by_reason
    assert "reject_total" in report
    assert "reject_by_reason" in report
    assert report["reject_total"] == 4  # 2 profitable_false + 1 fx_stale + 1 candidate_none
    assert report["reject_by_reason"]["profitable_false"] == 2
    assert report["reject_by_reason"]["fx_stale"] == 1
    assert report["reject_by_reason"]["candidate_none"] == 1
    
    # D207-7: Validate global tail_stats
    assert "tail_stats" in report
    tail_stats = report["tail_stats"]
    assert tail_stats["max_spread_bps"] == 60.0
    assert tail_stats["max_net_edge_bps"] == 25.0
    assert tail_stats["min_net_edge_bps"] == -5.0
    assert tail_stats["p95_spread_bps"] is not None
    assert tail_stats["p99_spread_bps"] is not None
    assert tail_stats["p95_net_edge_bps"] is not None
    assert tail_stats["p99_net_edge_bps"] is not None
    assert "positive_net_edge_pct" in tail_stats
    
    # D207-7: Validate per-symbol tail stats
    assert "symbols" in report
    btc_stats = report["symbols"]["BTC/KRW"]
    assert btc_stats["opportunity_count"] == 3
    assert btc_stats["max_spread_bps"] == 60.0
    assert btc_stats["max_net_edge_bps"] == 25.0
    assert btc_stats["min_net_edge_bps"] == 10.2
    assert btc_stats["p95_net_edge_bps"] is not None
    assert btc_stats["p99_net_edge_bps"] is not None
    
    eth_stats = report["symbols"]["ETH/KRW"]
    assert eth_stats["opportunity_count"] == 3
    assert eth_stats["max_spread_bps"] == 40.0
    assert eth_stats["max_net_edge_bps"] == 8.5
    assert eth_stats["min_net_edge_bps"] == -5.0
    assert eth_stats["p95_net_edge_bps"] is not None
    assert eth_stats["p99_net_edge_bps"] is not None


def test_edge_survey_report_zero_rejects(tmp_path):
    """Validate report with zero reject reasons"""
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id="test_zero_rejects")
    metrics = PaperMetrics()
    
    run_meta = {
        "run_id": "test_zero_rejects",
        "git_sha": "dummy",
        "branch": "test",
        "config_path": "config/v2/config.yml",
        "symbols": [("BTC/KRW", "BTC/USDT")],
        "cli_args": {"duration": 1},
        "metrics": metrics.to_dict(),
    }

    edge_distribution = [
        {
            "iteration": 1,
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "reason": "",
            "sampling_policy": {
                "mode": "all",
                "max_symbols_per_tick": None,
                "universe_size": 1,
                "symbols_sampled": 1,
            },
            "candidates": [
                {
                    "symbol": "BTC/KRW",
                    "spread_bps": 50.0,
                    "net_edge_bps": 15.5,
                },
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

    report_path = tmp_path / "edge_survey_report.json"
    assert report_path.exists()
    
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    assert report["reject_total"] == 0
    assert all(count == 0 for count in report["reject_by_reason"].values())
    assert report["tail_stats"]["positive_net_edge_pct"] == 100.0
