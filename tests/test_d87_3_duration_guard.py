#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D87-3_FIX: Duration Guard Unit Tests (no subprocess)

PaperOrchestrator의 wall-clock duration 종료 로직을 단위 테스트로 검증한다.
"""

import pytest

from arbitrage.v2.core.orchestrator import PaperOrchestrator
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.core.opportunity_source import OpportunitySource
from arbitrage.v2.harness.paper_runner import PaperRunnerConfig


class DummySource(OpportunitySource):
    def generate(self, iteration):
        return None


class DummyExecutor:
    def execute(self, *args, **kwargs):
        raise RuntimeError("should not execute")


class DummyLedgerWriter:
    def get_counts(self):
        return {"orders": 0, "fills": 0, "trades": 0}

    def record_order_and_fill(self, *args, **kwargs):
        return None

    def record_trade_complete(self, *args, **kwargs):
        return None


class FakeTime:
    def __init__(self, start: float = 0.0, step: float = 0.2):
        self.current = start
        self.step = step

    def time(self) -> float:
        value = self.current
        self.current += self.step
        return value

    def sleep(self, seconds: float) -> None:
        self.current += seconds


class NoWatcherOrchestrator(PaperOrchestrator):
    def start_watcher(self):
        return None

    def stop_watcher(self):
        return None


def test_duration_guard_time_reached(monkeypatch, tmp_path):
    fake_time = FakeTime(start=0.0, step=0.2)
    import arbitrage.v2.core.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.time, "time", fake_time.time)
    monkeypatch.setattr(orchestrator_module.time, "sleep", fake_time.sleep)

    config = PaperRunnerConfig(
        duration_minutes=1 / 60,
        phase="smoke",
        output_dir=str(tmp_path),
        db_mode="off",
    )
    config.symbols = [("BTC/KRW", "BTC/USDT")]
    config.cycle_interval_seconds = 0.0

    kpi = PaperMetrics()
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id=config.run_id)

    orch = NoWatcherOrchestrator(
        config=config,
        opportunity_source=DummySource(),
        executor=DummyExecutor(),
        ledger_writer=DummyLedgerWriter(),
        kpi=kpi,
        evidence_collector=collector,
        run_id=config.run_id,
    )

    exit_code = orch.run()

    assert exit_code == 0
    assert kpi.stop_reason == "TIME_REACHED"
    assert kpi.expected_duration_sec == pytest.approx(1.0, abs=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
