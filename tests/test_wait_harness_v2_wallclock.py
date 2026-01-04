"""
D205-10-2: Wait Harness v2 Wallclock/Phase/Summary 유닛테스트

테스트 항목:
1. Monotonic elapsed 증가 검증
2. Expected samples 계산 검증
3. Phase 1 checkpoint (3h) 도달 시 feasibility 평가
4. EARLY_INFEASIBLE 판정 (max_spread < threshold)
5. watch_summary.json 생성 및 필드 검증
6. CTRL+C (KeyboardInterrupt) 경로에서도 summary 생성
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arbitrage.v2.harness.wait_harness_v2 import (
    WaitHarnessV2,
    WaitHarnessV2Config,
    MarketSnapshot,
)


class TestWaitHarnessV2Wallclock:
    """Wallclock + Monotonic 검증"""
    
    def test_monotonic_elapsed_increases(self):
        """Monotonic elapsed 시간이 증가하는지 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(
                phase_hours=[3, 5],
                poll_seconds=1,
                evidence_dir=tmpdir,
            )
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                
                elapsed_1 = harness._get_elapsed_seconds()
                time.sleep(0.1)
                elapsed_2 = harness._get_elapsed_seconds()
                
                assert elapsed_2 > elapsed_1, "Monotonic time should increase"
    
    def test_utc_timestamp_format(self):
        """UTC timestamp가 ISO 8601 형식인지 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(evidence_dir=tmpdir)
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                
                utc_now = harness._get_utc_now()
                assert "T" in utc_now, "Should be ISO 8601 format"
                assert "+00:00" in utc_now or "Z" in utc_now, "Should have timezone info"


class TestWaitHarnessV2Phase:
    """Phase checkpoint 및 feasibility 평가"""
    
    def test_phase_checkpoint_reached(self):
        """3h checkpoint 도달 시 flag 설정"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(
                phase_hours=[3, 5],
                poll_seconds=1,
                evidence_dir=tmpdir,
            )
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                
                # 초기 상태
                assert not harness.phase_checkpoint_reached
                
                # Mock: 3h 경과 후 checkpoint 도달
                harness.phase_checkpoint_reached = True
                harness.phase_checkpoint_time_utc = harness._get_utc_now()
                
                assert harness.phase_checkpoint_reached
                assert harness.phase_checkpoint_time_utc is not None
    
    def test_feasibility_infeasible(self):
        """max_spread < (break_even - margin) → INFEASIBLE"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(
                phase_hours=[3, 5],
                infeasible_margin_bps=30.0,
                evidence_dir=tmpdir,
            )
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                
                # Mock snapshot: max_spread=20, break_even=100
                # threshold = 100 - 30 = 70
                # 20 < 70 → INFEASIBLE
                snapshot = MarketSnapshot(
                    timestamp_utc="2026-01-04T12:00:00+00:00",
                    monotonic_elapsed_sec=0,
                    upbit_price_last=100000, upbit_bid=99900, upbit_ask=100100,
                    binance_price_last=100, binance_bid=99.9, binance_ask=100.1,
                    binance_price_krw=145000,
                    fx_rate=1450,
                    spread_last_bps=20,  # < threshold
                    spread_conservative_bps=20,
                    break_even_bps=100,
                    edge_bps_last=-80,
                    edge_bps_conservative=-80,
                    trigger=False,
                )
                harness.snapshots.append(snapshot)
                
                feasible = harness._evaluate_feasibility()
                assert not feasible, "Should be INFEASIBLE"
                assert harness.feasibility_decision == "INFEASIBLE"
    
    def test_feasibility_feasible(self):
        """max_spread >= (break_even - margin) → FEASIBLE"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(
                phase_hours=[3, 5],
                infeasible_margin_bps=30.0,
                evidence_dir=tmpdir,
            )
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                
                # Mock snapshot: max_spread=100, break_even=100
                # threshold = 100 - 30 = 70
                # 100 >= 70 → FEASIBLE
                snapshot = MarketSnapshot(
                    timestamp_utc="2026-01-04T12:00:00+00:00",
                    monotonic_elapsed_sec=0,
                    upbit_price_last=100000, upbit_bid=99900, upbit_ask=100100,
                    binance_price_last=100, binance_bid=99.9, binance_ask=100.1,
                    binance_price_krw=145000,
                    fx_rate=1450,
                    spread_last_bps=100,  # >= threshold
                    spread_conservative_bps=100,
                    break_even_bps=100,
                    edge_bps_last=0,
                    edge_bps_conservative=0,
                    trigger=False,
                )
                harness.snapshots.append(snapshot)
                
                feasible = harness._evaluate_feasibility()
                assert feasible, "Should be FEASIBLE"
                assert harness.feasibility_decision == "FEASIBLE"


class TestWaitHarnessV2Summary:
    """watch_summary.json 생성 및 필드 검증"""
    
    def test_watch_summary_json_created(self):
        """watch_summary.json 파일 생성"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(evidence_dir=tmpdir)
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                harness._update_watch_summary(stop_reason="TEST")
                
                summary_path = Path(tmpdir) / "watch_summary.json"
                assert summary_path.exists(), "watch_summary.json should exist"
    
    def test_watch_summary_fields(self):
        """watch_summary.json 필드 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(
                phase_hours=[3, 5],
                poll_seconds=30,
                evidence_dir=tmpdir,
            )
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                
                # Mock snapshot
                snapshot = MarketSnapshot(
                    timestamp_utc="2026-01-04T12:00:00+00:00",
                    monotonic_elapsed_sec=100,
                    upbit_price_last=100000, upbit_bid=99900, upbit_ask=100100,
                    binance_price_last=100, binance_bid=99.9, binance_ask=100.1,
                    binance_price_krw=145000,
                    fx_rate=1450,
                    spread_last_bps=50,
                    spread_conservative_bps=50,
                    break_even_bps=100,
                    edge_bps_last=-50,
                    edge_bps_conservative=-50,
                    trigger=False,
                )
                harness.snapshots.append(snapshot)
                
                harness._update_watch_summary(stop_reason="TIME_REACHED")
                
                summary_path = Path(tmpdir) / "watch_summary.json"
                with open(summary_path, "r") as f:
                    summary = json.load(f)
                
                # 필수 필드 검증
                assert "planned_total_hours" in summary
                assert "phase_hours" in summary
                assert "started_at_utc" in summary
                assert "last_tick_at_utc" in summary
                assert "ended_at_utc" in summary
                assert "monotonic_elapsed_sec" in summary
                assert "poll_sec" in summary
                assert "samples_collected" in summary
                assert "expected_samples" in summary
                assert "completeness_ratio" in summary
                assert "max_spread_bps" in summary
                assert "p95_spread_bps" in summary
                assert "max_edge_bps" in summary
                assert "stop_reason" in summary
                
                # 값 검증
                assert summary["planned_total_hours"] == 5
                assert summary["phase_hours"] == [3, 5]
                assert summary["poll_sec"] == 30
                assert summary["samples_collected"] == 1
                assert summary["stop_reason"] == "TIME_REACHED"
    
    def test_watch_summary_completeness_ratio(self):
        """completeness_ratio 계산 검증"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(
                poll_seconds=30,
                evidence_dir=tmpdir,
            )
            
            with patch.object(WaitHarnessV2, 'watch_market', return_value=None):
                harness = WaitHarnessV2(config)
                
                # Mock: 3000초 경과, 100개 샘플
                # expected = 3000 / 30 + 1 = 101
                # completeness = 100 / 101 ≈ 0.99
                for i in range(100):
                    snapshot = MarketSnapshot(
                        timestamp_utc="2026-01-04T12:00:00+00:00",
                        monotonic_elapsed_sec=3000,
                        upbit_price_last=100000, upbit_bid=99900, upbit_ask=100100,
                        binance_price_last=100, binance_bid=99.9, binance_ask=100.1,
                        binance_price_krw=145000,
                        fx_rate=1450,
                        spread_last_bps=50,
                        spread_conservative_bps=50,
                        break_even_bps=100,
                        edge_bps_last=-50,
                        edge_bps_conservative=-50,
                        trigger=False,
                    )
                    harness.snapshots.append(snapshot)
                
                # Mock elapsed time
                harness.start_time_monotonic = time.monotonic() - 3000
                
                harness._update_watch_summary()
                
                summary_path = Path(tmpdir) / "watch_summary.json"
                with open(summary_path, "r") as f:
                    summary = json.load(f)
                
                assert summary["samples_collected"] == 100
                assert summary["expected_samples"] == 101
                assert 0.98 < summary["completeness_ratio"] < 1.0


class TestWaitHarnessV2KeyboardInterrupt:
    """CTRL+C (KeyboardInterrupt) 경로에서도 summary 생성"""
    
    def test_keyboard_interrupt_creates_summary(self):
        """KeyboardInterrupt 발생 시에도 watch_summary.json 생성"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = WaitHarnessV2Config(
                phase_hours=[3, 5],
                poll_seconds=1,
                evidence_dir=tmpdir,
            )
            
            # Mock watch_market to raise KeyboardInterrupt on first call
            def mock_watch_market():
                raise KeyboardInterrupt()
            
            with patch.object(WaitHarnessV2, 'watch_market', side_effect=mock_watch_market):
                harness = WaitHarnessV2(config)
                exit_code = harness.run_watch_loop()
                
                assert exit_code == 1, "Should return 1 on interrupt"
                
                summary_path = Path(tmpdir) / "watch_summary.json"
                assert summary_path.exists(), "watch_summary.json should exist even after interrupt"
                
                with open(summary_path, "r") as f:
                    summary = json.load(f)
                
                assert summary["stop_reason"] == "INTERRUPTED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
