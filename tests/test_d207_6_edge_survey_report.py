"""
D207-6: Edge Survey Report Artifact Test

Goal: edge_survey_report.json schema + manifest inclusion + zero-sample FAIL.
SSOT: D_ROADMAP.md -> D207-6
"""

import json

from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector


def test_edge_survey_report_saved(tmp_path):
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id="test_edge_survey")
    metrics = PaperMetrics()
    run_meta = {
        "run_id": "test_edge_survey",
        "git_sha": "dummy",
        "branch": "test",
        "config_path": "config/v2/config.yml",
        "symbols": [("BTC/KRW", "BTC/USDT"), ("ETH/KRW", "ETH/USDT")],
        "cli_args": {"duration": 1},
    }

    edge_distribution = [
        {
            "iteration": 1,
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "reason": "",
            "sampling_policy": {
                "mode": "round_robin",
                "max_symbols_per_tick": 1,
                "universe_size": 2,
                "symbols_sampled": 1,
            },
            "candidates": [
                {
                    "symbol": "BTC/KRW",
                    "spread_bps": 12.0,
                    "net_edge_bps": -5.5,
                },
                {
                    "symbol": "ETH/KRW",
                    "spread_bps": 8.0,
                    "net_edge_bps": -4.2,
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
    assert report["status"] == "PASS"
    assert report["total_candidates"] == 2
    assert report["sampling_policy"]["mode"] == "round_robin"
    assert report["run_meta"].get("run_id") == "test_edge_survey"

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert "edge_survey_report.json" in manifest.get("files", [])


def test_edge_survey_report_zero_samples_fail(tmp_path):
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id="test_edge_survey_zero")
    metrics = PaperMetrics()
    run_meta = {
        "run_id": "test_edge_survey_zero",
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
            "reason": "no_candidates",
            "sampling_policy": {
                "mode": "all",
                "max_symbols_per_tick": None,
                "universe_size": 1,
                "symbols_sampled": 1,
            },
            "candidates": [],
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
    assert report["status"] == "FAIL"
    assert report["total_candidates"] == 0
    assert report["run_meta"].get("run_id") == "test_edge_survey_zero"
