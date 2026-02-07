"""
D207-3: Winrate 100% Kill-switch Test

Goal: verify FAIL when winrate=100% with trades>=20
SSOT: D_ROADMAP.md -> D207-3
"""

from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.run_watcher import RunWatcher, WatcherConfig


class TestWinrate100KillSwitch:
    """D207-3: WIN_RATE_100_SUSPICIOUS kill-switch"""

    def test_winrate_100_triggers_fail(self):
        config = WatcherConfig(
            heartbeat_sec=1,
            early_stop_enabled=False,
            winrate_100_trade_threshold=20,
            winrate_100_sustain_sec=0.0,
        )

        kpi = PaperMetrics()
        kpi.closed_trades = 20
        kpi.wins = 20
        kpi.losses = 0
        kpi.winrate_pct = 100.0
        kpi.fees_total = 10.0

        stop_requested = []

        def stop_callback():
            stop_requested.append(True)

        watcher = RunWatcher(
            config=config,
            kpi_getter=lambda: kpi,
            stop_callback=stop_callback,
            run_id="test_winrate_100",
        )

        watcher._check_fail_conditions()

        assert watcher.stop_reason == "WIN_RATE_100_SUSPICIOUS"
        assert "100% winrate" in watcher.diagnosis
        assert stop_requested
