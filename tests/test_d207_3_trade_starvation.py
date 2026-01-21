"""
D207-3: Trade Starvation Kill-switch Test

Goal: opportunities >= threshold AND intents == 0 after 20m triggers FAIL.
SSOT: D_ROADMAP.md -> D207-3
"""

import time

from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.run_watcher import RunWatcher, WatcherConfig


def test_trade_starvation_triggers_fail(tmp_path):
    config = WatcherConfig(
        heartbeat_sec=1,
        early_stop_enabled=False,
        trade_starvation_enabled=True,
        trade_starvation_after_sec=1200.0,
        trade_starvation_min_opportunities=100,
        trade_starvation_max_intents=0,
        evidence_dir=str(tmp_path),
    )

    now = time.time()
    kpi = PaperMetrics()
    kpi.wallclock_start = now - 1201.0
    kpi.opportunities_generated = 150
    kpi.intents_created = 0
    kpi.closed_trades = 0
    kpi.winrate_pct = 0.0

    stop_requested = []

    def stop_callback():
        stop_requested.append(True)

    watcher = RunWatcher(
        config=config,
        kpi_getter=lambda: kpi,
        stop_callback=stop_callback,
        run_id="test_trade_starvation",
    )

    watcher._check_fail_conditions()

    assert watcher.stop_reason == "TRADE_STARVATION"
    assert "Trade starvation" in watcher.diagnosis
    assert stop_requested
