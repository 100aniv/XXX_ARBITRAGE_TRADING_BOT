"""
D207-1-3: Friction Costs Enforcement + Winrate Cap Test

목표: 현실 마찰 비용 강제 + 승률 상한 검증

AC:
- fees_total, slippage_cost, latency_cost 누적 기록
- RunWatcher FAIL 조건 F (Winrate >= 95%) 검증
- RunWatcher FAIL 조건 G (fees_total = 0) 검증

SSOT: D_ROADMAP.md → D207-1-3
"""

import pytest
from unittest.mock import Mock
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.run_watcher import WatcherConfig, RunWatcher


class TestFrictionEnforcementAndWinrateCap:
    """D207-1-3: Friction Costs Enforcement + Winrate Cap"""
    
    def test_friction_costs_recorded_in_kpi(self):
        """AT-1: Friction costs (fees_total) KPI 누적 검증"""
        # Given: PaperMetrics
        kpi = PaperMetrics()
        
        # When: Trade with fees
        kpi.fees_total += 100.0
        kpi.fees_total += 200.0
        
        # Then: fees_total should accumulate
        assert kpi.fees_total == 300.0, "fees_total should be 300.0"
        
        kpi_dict = kpi.to_dict()
        assert kpi_dict["fees_total"] == 300.0, "fees_total should be in KPI dict"
        
        print(f"✅ Friction costs recorded: fees_total={kpi.fees_total}")
    
    def test_winrate_cap_fail_condition(self):
        """AT-2: RunWatcher FAIL 조건 F (Winrate >= 95%) 검증"""
        # Given: WatcherConfig with winrate cap
        config = WatcherConfig(
            heartbeat_sec=1,
            early_stop_enabled=True,
            winrate_cap_threshold=0.95,
            min_trades_for_winrate_cap=10,
        )
        
        kpi = PaperMetrics()
        kpi.closed_trades = 10
        kpi.wins = 10
        kpi.losses = 0
        kpi.winrate_pct = 100.0
        kpi.fees_total = 100.0  # fees > 0
        
        stop_requested = []
        
        def stop_callback():
            stop_requested.append(True)
        
        watcher = RunWatcher(
            config=config,
            kpi_getter=lambda: kpi,
            stop_callback=stop_callback,
            run_id="test_winrate_cap",
        )
        
        # When: Check fail conditions
        watcher._check_fail_conditions()
        
        # Then: Should trigger FAIL (winrate >= 95%)
        assert watcher.stop_reason == "MODEL_ANOMALY", "stop_reason should be MODEL_ANOMALY"
        assert "Winrate too high" in watcher.diagnosis, "diagnosis should mention winrate"
        assert len(stop_requested) > 0, "stop_callback should be called"
        
        print(f"✅ Winrate cap triggered: winrate={kpi.winrate_pct}% >= 95%")
    
    def test_friction_zero_fail_condition(self):
        """AT-3: RunWatcher FAIL 조건 G (fees_total = 0) 검증"""
        # Given: WatcherConfig with friction check
        config = WatcherConfig(
            heartbeat_sec=1,
            early_stop_enabled=True,
            check_friction_nonzero=True,
        )
        
        kpi = PaperMetrics()
        kpi.closed_trades = 5
        kpi.wins = 3
        kpi.losses = 2
        kpi.winrate_pct = 60.0
        kpi.fees_total = 0.0  # ❌ fees = 0
        
        stop_requested = []
        
        def stop_callback():
            stop_requested.append(True)
        
        watcher = RunWatcher(
            config=config,
            kpi_getter=lambda: kpi,
            stop_callback=stop_callback,
            run_id="test_friction_zero",
        )
        
        # When: Check fail conditions
        watcher._check_fail_conditions()
        
        # Then: Should trigger FAIL (fees_total = 0)
        assert watcher.stop_reason == "MODEL_ANOMALY", "stop_reason should be MODEL_ANOMALY"
        assert "fees_total=0" in watcher.diagnosis, "diagnosis should mention fees_total=0"
        assert len(stop_requested) > 0, "stop_callback should be called"
        
        print(f"✅ Friction zero guard triggered: fees_total={kpi.fees_total}")
    
    def test_friction_nonzero_pass_condition(self):
        """AT-4: fees_total > 0 시 PASS (정상)"""
        # Given: WatcherConfig with friction check
        config = WatcherConfig(
            heartbeat_sec=1,
            early_stop_enabled=True,
            check_friction_nonzero=True,
            winrate_cap_threshold=0.95,
            min_trades_for_winrate_cap=10,
        )
        
        kpi = PaperMetrics()
        kpi.closed_trades = 5
        kpi.wins = 3
        kpi.losses = 2
        kpi.winrate_pct = 60.0
        kpi.fees_total = 100.0  # ✅ fees > 0
        
        stop_requested = []
        
        def stop_callback():
            stop_requested.append(True)
        
        watcher = RunWatcher(
            config=config,
            kpi_getter=lambda: kpi,
            stop_callback=stop_callback,
            run_id="test_friction_nonzero",
        )
        
        # When: Check fail conditions
        watcher._check_fail_conditions()
        
        # Then: Should NOT trigger FAIL
        assert watcher.stop_reason is None, "stop_reason should be None"
        assert len(stop_requested) == 0, "stop_callback should NOT be called"
        
        print(f"✅ Friction nonzero PASS: fees_total={kpi.fees_total}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
